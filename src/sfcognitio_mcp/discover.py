"""Discover Salesforce documentation URLs.

Two source families:

* **atlas**: classic guides at
  ``/docs/atlas.<locale>[.<doc_release>].<guide>.meta/<guide>/<page>.htm``.
  Discovered from each guide's table-of-contents JSON, falling back to the
  atlas sitemap.
* **docs**: newer statically generated docs (e.g. ``/docs/platform/lwc/guide/...``),
  discovered from the SSG sitemap.
"""

from __future__ import annotations

import gzip
import logging
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urldefrag

import httpx

from .config import ARTICLES_GUIDE, Config
from .http import PoliteClient
from .manifest import PageRef
from .versions import parse_release_spec, release_name_to_api, version_info

log = logging.getLogger(__name__)

ATLAS_RE = re.compile(
    r"/docs/atlas\.(?P<locale>[a-z]{2}-[a-z]{2})\."
    r"(?:(?P<rel>\d+\.\d+)\.)?"
    r"(?P<guide>[a-z0-9_]+)\.meta/(?P<sub>[a-z0-9_]+)/(?P<page>[^?#/]+\.htm)",
    re.I,
)


# Guides known to live in the classic atlas. If their TOC can't be read they
# fall back to the atlas sitemap only, never the SSG sitemap, where short ids
# like "api" would match unrelated URL segments.
ATLAS_GUIDES = {
    "apexcode", "apexref", "api", "api_rest", "api_meta", "api_asynch", "api_tooling",
    "object_reference", "soql_sosl", "sfdx_dev", "sfdx_cli_reference", "pages", "lightning",
    "salesforce_vpm_guide", "api_streaming",
}


# Guides that moved to the newer docs site. Their classic atlas entry is a
# leftover stub (e.g. LWC returns a 1-page Winter '23 TOC), so skip atlas.
DOCS_GUIDES = {"lwc", "platform-events"}

# A non-atlas guide whose TOC has fewer pages than this is treated as a stub.
MIN_TOC_PAGES = 5


# -- sitemaps ---------------------------------------------------------------

def parse_sitemap(content: bytes) -> tuple[list[str], list[str]]:
    """Return (page_urls, child_sitemap_urls) from sitemap or sitemap-index XML."""
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    root = ET.fromstring(content)
    pages, children = [], []
    tag = root.tag.rsplit("}", 1)[-1]
    for loc in root.iter():
        if loc.tag.rsplit("}", 1)[-1] != "loc" or not loc.text:
            continue
        (children if tag == "sitemapindex" else pages).append(loc.text.strip())
    return pages, children


def _sitemap_cache_file(cache_dir: Path, url: str) -> Path:
    name = re.sub(r"[^A-Za-z0-9]+", "_", url.split("//", 1)[-1]).strip("_")
    return cache_dir / f"{name}.txt"


def sitemap_cache_args(cfg: Config) -> dict:
    return {"cache_dir": cfg.data_dir / "sitemaps", "max_age_hours": cfg.crawler.sitemap_cache_hours}


async def fetch_sitemap_urls(client: PoliteClient, url: str, max_depth: int = 3,
                             cache_dir: Path | None = None, max_age_hours: float = 0) -> list[str]:
    """Walk a sitemap tree. A child that keeps failing is skipped with a warning.

    The URL list is cached under ``cache_dir`` only when every sitemap loaded, and
    reused while younger than ``max_age_hours`` (0 = never reuse).
    """
    cache_file = _sitemap_cache_file(cache_dir, url) if cache_dir else None
    if cache_file and max_age_hours > 0 and cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            cached = cache_file.read_text(encoding="utf-8").split()
            log.info("Using cached sitemap URLs for %s (%d URLs, %.1fh old)", url, len(cached), age_hours)
            return cached

    out: list[str] = []
    failed: list[str] = []
    queue = [(url, 0)]
    seen: set[str] = set()
    while queue:
        sm, depth = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            resp = await client.get(sm)
        except httpx.TransportError as e:
            if depth == 0:
                raise
            log.warning("Sitemap %s unreachable, skipping: %s", sm, e.__class__.__name__)
            failed.append(sm)
            continue
        if resp.status_code != 200:
            log.warning("Sitemap %s returned %s", sm, resp.status_code)
            failed.append(sm)
            continue
        try:
            pages, children = parse_sitemap(resp.content)
        except ET.ParseError as e:
            log.warning("Sitemap %s is not valid XML: %s", sm, e)
            failed.append(sm)
            continue
        out.extend(pages)
        if depth < max_depth:
            queue.extend((c, depth + 1) for c in children)

    if failed:
        log.warning("%d sitemap(s) could not be read, so the URL list is incomplete and was not cached: %s",
                    len(failed), ", ".join(failed))
    elif cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("\n".join(out) + "\n", encoding="utf-8")
    return out


# -- atlas ------------------------------------------------------------------

def parse_atlas_url(url: str) -> dict | None:
    m = ATLAS_RE.search(url)
    if not m:
        return None
    return {
        "locale": m.group("locale").lower(),
        "doc_release": m.group("rel"),
        "guide": m.group("guide").lower(),
        "sub": m.group("sub"),
        "page": m.group("page"),
    }


def atlas_page_url(base: str, locale: str, guide: str, page: str, doc_release: str | None = None) -> str:
    """Canonical URL for an atlas page; versioned when ``doc_release`` is given."""
    rel = f"{doc_release}." if doc_release else ""
    return f"{base.rstrip('/')}/atlas.{locale}.{rel}{guide}.meta/{guide}/{page}"


def atlas_toc_url(base: str, locale: str, guide: str, doc_release: str | None = None) -> str:
    rel = f"{doc_release}." if doc_release else ""
    return f"{base.rstrip('/')}/get_document/atlas.{locale}.{rel}{guide}.meta"


def _toc_hrefs(node) -> list[str]:
    """Walk a TOC JSON tree of unknown exact shape and collect .htm hrefs."""
    found: list[str] = []
    if isinstance(node, dict):
        for key in ("a_attr", "attr", "link"):
            v = node.get(key)
            if isinstance(v, dict) and isinstance(v.get("href"), str):
                found.append(v["href"])
        if isinstance(node.get("href"), str):
            found.append(node["href"])
        for v in node.values():
            if isinstance(v, (dict, list)):
                found.extend(_toc_hrefs(v))
    elif isinstance(node, list):
        for item in node:
            found.extend(_toc_hrefs(item))
    return found


def parse_atlas_toc(data: dict) -> tuple[list[str], dict]:
    """Return (page_ids, version_dict) from a get_document TOC response."""
    pages: list[str] = []
    seen: set[str] = set()
    for href in _toc_hrefs(data.get("toc", data)):
        page = urldefrag(href)[0].rsplit("/", 1)[-1]
        if page.endswith(".htm") and page not in seen:
            seen.add(page)
            pages.append(page)

    ver = data.get("version") or {}
    doc_release = None
    api = None
    if isinstance(ver, dict):
        doc_release = ver.get("doc_version") or ver.get("release_version")
        text = ver.get("version_text") or ver.get("version_url") or ""
        m = re.search(r"API version\s*(\d+\.\d+)", text)
        if m:
            api = m.group(1)
        elif text:
            guess = release_name_to_api(text)
            api = f"{guess:.1f}" if guess else None
    elif isinstance(ver, str) and re.fullmatch(r"\d+\.\d+", ver):
        doc_release = ver
    return pages, version_info(doc_release=doc_release, api_version=api)


async def _read_toc(client: PoliteClient, url: str, guide: str) -> tuple[list[str], dict, int]:
    resp = await client.get(url)
    if resp.status_code != 200:
        return [], {}, resp.status_code
    try:
        pages, ver = parse_atlas_toc(resp.json())
    except ValueError:
        return [], {}, resp.status_code
    if len(pages) < MIN_TOC_PAGES and guide not in ATLAS_GUIDES:
        return [], {}, resp.status_code  # stub guide
    return pages, ver, 200


async def discover_atlas_guide(client: PoliteClient, cfg: Config, guide: str,
                               sitemap_cache: dict | None = None) -> list[PageRef]:
    """Discover one atlas guide. ``sitemap_cache`` is a dict reused across guides."""
    base, locale = cfg.atlas.base, cfg.atlas.locale
    pinned = parse_release_spec(cfg.atlas.release)

    if pinned:
        pages, _, status = await _read_toc(client, atlas_toc_url(base, locale, guide, pinned), guide)
        if pages:
            ver = version_info(doc_release=pinned)
            log.info("atlas/%s: %d pages from TOC (pinned %s)", guide, len(pages), ver["release"])
            return [PageRef(url=atlas_page_url(base, locale, guide, p, pinned), source="atlas",
                            guide=guide, page=p, **ver) for p in pages]
        name = version_info(doc_release=pinned)["release"]
        if cfg.atlas.strict_release:
            log.warning("atlas/%s: not published for %s (HTTP %s); skipping (strict_release)", guide, name, status)
            return []
        log.warning("atlas/%s: not published for %s (HTTP %s); using its latest version", guide, name, status)

    pages, ver, status = await _read_toc(client, atlas_toc_url(base, locale, guide), guide)
    if pages:
        log.info("atlas/%s: %d pages from TOC (%s)", guide, len(pages), ver.get("release") or "version unknown")
        return [PageRef(url=atlas_page_url(base, locale, guide, p), source="atlas", guide=guide, page=p, **ver)
                for p in pages]
    log.info("atlas/%s: TOC unavailable (HTTP %s), falling back to sitemap", guide, status)

    cache = sitemap_cache if sitemap_cache is not None else {}
    if "urls" not in cache:
        cache["urls"] = await fetch_sitemap_urls(client, cfg.atlas.sitemap, **sitemap_cache_args(cfg))
    refs: dict[str, PageRef] = {}
    for u in cache["urls"]:
        info = parse_atlas_url(u)
        if not info or info["guide"] != guide or info["locale"] != locale:
            continue
        if pinned and info["doc_release"] and info["doc_release"] != pinned:
            continue
        canon = atlas_page_url(base, locale, guide, info["page"])
        ver = version_info(doc_release=info["doc_release"]) if info["doc_release"] else {}
        refs.setdefault(canon, PageRef(url=canon, source="atlas", guide=guide, page=info["page"], **ver))
    log.info("atlas/%s: %d pages from sitemap", guide, len(refs))
    return list(refs.values())


# -- docs (SSG) -------------------------------------------------------------

def docs_guide_for(url: str, guides: list[str]) -> str | None:
    """Return which configured guide a docs URL belongs to, by path segment."""
    segments = [s.lower() for s in url.split("?")[0].split("/")]
    for g in guides:
        if g.lower() in segments:
            return g
    return None


def filter_docs_urls(urls: list[str], cfg: Config) -> list[PageRef]:
    refs: dict[str, PageRef] = {}
    for u in urls:
        u = urldefrag(u)[0]
        if cfg.docs.include and not any(u.startswith(p) for p in cfg.docs.include):
            continue
        if any(x in u for x in cfg.docs.exclude):
            continue
        if parse_atlas_url(u):
            continue  # classic pages belong to the atlas source
        guide = docs_guide_for(u, cfg.guides) if cfg.guides else None
        if cfg.guides and not guide:
            continue
        refs.setdefault(u, PageRef(url=u, source="docs", guide=guide, page=u.rstrip("/").rsplit("/", 1)[-1]))
    return list(refs.values())


# -- extra pages ------------------------------------------------------------

def extra_page_refs(urls: list[str]) -> list[PageRef]:
    """Hand-picked URLs from ``extra_pages``, kept in the ``articles`` bucket."""
    refs: dict[str, PageRef] = {}
    for u in urls:
        u = urldefrag(u)[0]
        parts = [p for p in u.split("/docs/", 1)[-1].split("/") if p and p not in ("platform", "guide")]
        page = re.sub(r"\.(html?|md)$", "", "-".join(parts))
        refs.setdefault(u, PageRef(url=u, source="docs", guide=ARTICLES_GUIDE, page=page))
    return list(refs.values())


# -- entry point ------------------------------------------------------------

async def discover(client: PoliteClient, cfg: Config, guides: list[str] | None = None) -> list[PageRef]:
    guides = guides or cfg.all_guides
    refs: list[PageRef] = []

    if ARTICLES_GUIDE in guides:
        refs.extend(extra_page_refs(cfg.extra_pages))
        guides = [g for g in guides if g != ARTICLES_GUIDE]

    docs_guides = list(guides)
    if cfg.atlas.enabled:
        sitemap_cache: dict = {}
        for g in guides:
            if g in DOCS_GUIDES:
                continue
            found = await discover_atlas_guide(client, cfg, g, sitemap_cache)
            if found or g in ATLAS_GUIDES:
                refs.extend(found)
                docs_guides.remove(g)

    if cfg.docs.enabled and docs_guides:
        urls = await fetch_sitemap_urls(client, cfg.docs.sitemap, **sitemap_cache_args(cfg))
        sub = Config(cfg.data_dir, cfg.crawler, docs_guides, cfg.atlas, cfg.docs)
        found = filter_docs_urls(urls, sub)
        log.info("docs: %d pages for %s", len(found), ", ".join(docs_guides))
        refs.extend(found)

    missing = [g for g in guides if not any(r.guide == g for r in refs)]
    if missing:
        log.warning("No pages found for: %s", ", ".join(missing))
    return refs
