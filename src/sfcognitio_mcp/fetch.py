"""Fetch pages listed in the manifest and store raw responses.

Atlas pages render client-side, so for them we first try the content JSON
endpoint the docs site itself uses, then fall back to the HTML page.
Docs (SSG) pages are fetched as HTML.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import Config
from .http import BlockedError, PoliteClient
from .manifest import Manifest
from .versions import version_info

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    ok: bool
    not_modified: bool = False
    http_status: int | None = None
    body: bytes = b""
    ext: str = "html"
    etag: str | None = None
    last_modified: str | None = None
    title: str | None = None
    version: dict | None = None
    error: str | None = None


def atlas_content_urls(base: str, guide: str, page: str, locale: str, doc_release: str | None) -> list[str]:
    root = base.rstrip("/")
    urls = []
    if doc_release:
        urls.append(f"{root}/get_document_content/{guide}/{page}/{locale}/{doc_release}")
    urls.append(f"{root}/get_document_content/{guide}/{page}/{locale}")
    return urls


def docs_markdown_url(url: str) -> str | None:
    """The newer docs site serves raw Markdown at the same path with a .md extension."""
    base = url.split("#")[0].split("?")[0]
    if base.endswith(".md"):
        return base
    if base.endswith(".html"):
        return base[:-5] + ".md"
    if base.endswith("/"):
        return None
    last = base.rsplit("/", 1)[-1]
    return None if "." in last else base + ".md"


def _looks_like_markdown(resp: httpx.Response) -> bool:
    ctype = resp.headers.get("content-type", "").lower()
    if "html" in ctype or "json" in ctype:
        return False
    head = resp.text.lstrip()[:200].lower()
    return bool(head) and not head.startswith(("<!doctype", "<html", "<?xml", "{"))


def _cond_headers(row: sqlite3.Row) -> dict:
    h = {}
    if row["text_path"] or row["raw_path"]:
        if row["etag"]:
            h["If-None-Match"] = row["etag"]
        if row["last_modified"]:
            h["If-Modified-Since"] = row["last_modified"]
    return h


def _parse_atlas_json(resp: httpx.Response) -> tuple[str | None, dict | None, str | None]:
    """Return (title, version, content_html) or Nones if not a usable payload."""
    try:
        data = resp.json()
    except ValueError:
        return None, None, None
    if not isinstance(data, dict):
        return None, None, None
    content = data.get("content") or data.get("body")
    if not isinstance(content, str) or len(content) < 50:
        return None, None, None
    ver = None
    v = data.get("version")
    if isinstance(v, dict):
        ver = version_info(doc_release=v.get("doc_version"))
    return data.get("title"), ver, content


async def fetch_one(client: PoliteClient, cfg: Config, row: sqlite3.Row) -> FetchResult:
    url = row["url"]
    headers = _cond_headers(row)

    if row["source"] == "atlas" and row["guide"] and row["page"]:
        for api_url in atlas_content_urls(cfg.atlas.base, row["guide"], row["page"],
                                          cfg.atlas.locale, row["doc_release"]):
            resp = await client.get(api_url, headers=headers)
            if resp.status_code == 304:
                return FetchResult(url, ok=True, not_modified=True, http_status=304)
            if resp.status_code == 200:
                title, ver, content = _parse_atlas_json(resp)
                if content:
                    return FetchResult(
                        url, ok=True, http_status=200, body=resp.content, ext="json",
                        etag=resp.headers.get("ETag"), last_modified=resp.headers.get("Last-Modified"),
                        title=title, version=ver,
                    )
        log.debug("atlas content API unusable for %s; falling back to HTML", url)

    if row["source"] == "docs":
        md_url = docs_markdown_url(url)
        if md_url:
            resp = await client.get(md_url, headers=headers)
            if resp.status_code == 304:
                return FetchResult(url, ok=True, not_modified=True, http_status=304)
            if resp.status_code == 200 and _looks_like_markdown(resp):
                return FetchResult(
                    url, ok=True, http_status=200, body=resp.content, ext="md",
                    etag=resp.headers.get("ETag"), last_modified=resp.headers.get("Last-Modified"),
                )
            log.debug("markdown source unavailable for %s; falling back to HTML", url)

    resp = await client.get(url, headers=headers)
    if resp.status_code == 304:
        return FetchResult(url, ok=True, not_modified=True, http_status=304)
    if resp.status_code != 200:
        return FetchResult(url, ok=False, http_status=resp.status_code, error=f"HTTP {resp.status_code}")
    return FetchResult(
        url, ok=True, http_status=200, body=resp.content, ext="html",
        etag=resp.headers.get("ETag"), last_modified=resp.headers.get("Last-Modified"),
    )


def raw_path_for(cfg: Config, row: sqlite3.Row, ext: str) -> Path:
    key = hashlib.sha1(row["url"].encode()).hexdigest()[:16]
    return cfg.raw_dir / (row["guide"] or "_misc") / f"{key}.{ext}"


def save_result(cfg: Config, manifest: Manifest, row: sqlite3.Row, res: FetchResult) -> None:
    if res.not_modified:
        manifest.mark_not_modified(res.url)
        return
    if not res.ok:
        manifest.mark_error(res.url, res.error or "unknown error", res.http_status)
        return
    path = raw_path_for(cfg, row, res.ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(res.body)
    ver = res.version or {}
    manifest.mark_fetched(
        res.url, http_status=res.http_status or 200, raw_path=str(path),
        content_hash=hashlib.sha256(res.body).hexdigest(), etag=res.etag,
        last_modified=res.last_modified, title=res.title,
        api_version=ver.get("api_version"), doc_release=ver.get("doc_release"), release=ver.get("release"),
    )


async def fetch_all(client: PoliteClient, cfg: Config, manifest: Manifest,
                    limit: int = 0, guides: list[str] | None = None) -> dict:
    limit = limit or cfg.crawler.max_pages
    rows = manifest.due_for_fetch(cfg.crawler.recheck_after_days, limit=limit, guides=guides)
    stats = {"queued": len(rows), "fetched": 0, "not_modified": 0, "errors": 0, "blocked": False}
    if not rows:
        return stats
    log.info("Fetching %d pages (concurrency %d, %.1fs per-host delay)",
             len(rows), cfg.crawler.concurrency, cfg.crawler.per_host_delay_seconds)

    done = 0

    async def worker(row: sqlite3.Row) -> None:
        nonlocal done
        try:
            res = await fetch_one(client, cfg, row)
        except BlockedError:
            raise
        except Exception as e:  # network failure after retries, bad payload, etc.
            res = FetchResult(row["url"], ok=False, error=f"{type(e).__name__}: {e}")
        save_result(cfg, manifest, row, res)
        key = "not_modified" if res.not_modified else ("fetched" if res.ok else "errors")
        stats[key] += 1
        done += 1
        if done % 25 == 0 or done == len(rows):
            log.info("  %d/%d (fetched %d, unchanged %d, errors %d)", done, len(rows),
                     stats["fetched"], stats["not_modified"], stats["errors"])

    tasks = [asyncio.create_task(worker(r)) for r in rows]
    try:
        await asyncio.gather(*tasks)
    except BlockedError as e:
        stats["blocked"] = True
        log.error("%s", e)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return stats


def load_raw(path: str | Path) -> tuple[str, dict | None]:
    """Return (html_or_markdown, json_payload_or_None) for a stored raw file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix == ".json":
        data = json.loads(text)
        return data.get("content") or data.get("body") or "", data
    return text, None
