"""Command-line interface: ``sfcognitio <command>``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from . import __version__
from .config import Config, load_config
from .discover import (DOCS_GUIDES, atlas_toc_url, discover, filter_docs_urls, parse_atlas_toc,
                       parse_sitemap)
from .extract import extract_all
from .fetch import atlas_content_urls, fetch_all
from .http import PoliteClient
from .manifest import Manifest
from .versions import parse_release_spec, version_info

log = logging.getLogger("sfcognitio")


def _guides(cfg: Config, args) -> list[str]:
    return args.guide or cfg.all_guides


def _apply_overrides(cfg: Config, args) -> None:
    if getattr(args, "release", None):
        cfg.atlas.release = args.release
    parse_release_spec(cfg.atlas.release)  # fail fast on a bad value


async def cmd_discover(cfg: Config, args) -> int:
    async with PoliteClient(cfg.crawler) as client:
        refs = await discover(client, cfg, _guides(cfg, args))
    with Manifest(cfg.manifest_path) as m:
        new = m.upsert_discovered(refs)
        pruned = m.prune_pending(refs)
        print(f"Discovered {len(refs)} pages ({new} new"
              + (f", {pruned} stale pending removed" if pruned else "") + f"). Manifest: {cfg.manifest_path}")
    return 0 if refs else 1


async def cmd_fetch(cfg: Config, args) -> int:
    with Manifest(cfg.manifest_path) as m:
        async with PoliteClient(cfg.crawler) as client:
            stats = await fetch_all(client, cfg, m, limit=args.limit, guides=_guides(cfg, args))
    print(f"Fetch: {stats}")
    return 2 if stats["blocked"] else 0


def cmd_extract(cfg: Config, args) -> int:
    with Manifest(cfg.manifest_path) as m:
        stats = extract_all(cfg, m, _guides(cfg, args))
    print(f"Extract: {stats}. Markdown in {cfg.text_dir}")
    return 0


async def cmd_crawl(cfg: Config, args) -> int:
    rc = await cmd_discover(cfg, args)
    if rc:
        return rc
    rc = await cmd_fetch(cfg, args)
    cmd_extract(cfg, args)
    cmd_status(cfg, args)
    return rc


def cmd_status(cfg: Config, args) -> int:
    if not cfg.manifest_path.exists():
        print("No manifest yet. Run `sfcognitio discover` first.")
        return 1
    with Manifest(cfg.manifest_path) as m:
        rows = m.summary()
        print(f"{'guide':<16}{'status':<14}{'pages':>7}")
        for r in rows:
            print(f"{r['guide']:<16}{r['status']:<14}{r['n']:>7}")
        print(f"{'total':<30}{m.count():>7}")
        errs = m.recent_errors(5)
        if errs:
            print("\nSample errors:")
            for e in errs:
                print(f"  [{e['http_status']}] {e['url']}  {e['error']}")
    return 0


async def cmd_doctor(cfg: Config, args) -> int:
    """Probe each endpoint the crawler relies on and report what works."""
    ok = True
    print(f"sfcognitio {__version__}")
    print(f"Config:   {args.config}")
    print(f"Data dir: {cfg.data_dir}")
    print(f"Guides:   {', '.join(_guides(cfg, args)) or '(all)'}")
    pinned = parse_release_spec(cfg.atlas.release)
    print(f"Release:  {version_info(doc_release=pinned)['release'] + ' (pinned)' if pinned else 'latest per guide'}\n")
    docs_xml = b""
    async with PoliteClient(cfg.crawler) as client:
        for name, url, enabled in (("atlas sitemap", cfg.atlas.sitemap, cfg.atlas.enabled),
                                   ("docs sitemap", cfg.docs.sitemap, cfg.docs.enabled)):
            if not enabled:
                continue
            resp = await client.get(url)
            print(f"[{'OK ' if resp.status_code == 200 else 'ERR'}] {name}: HTTP {resp.status_code}  {url}")
            ok &= resp.status_code == 200
            if name == "docs sitemap" and resp.status_code == 200:
                docs_xml = resp.content
            if resp.status_code == 403:
                print("      403 usually means the user agent was rejected. Check crawler.user_agent.")

        if cfg.atlas.enabled:
            for g in _guides(cfg, args):
                if g in DOCS_GUIDES:
                    n = 0
                    if docs_xml:
                        sub = Config(cfg.data_dir, cfg.crawler, [g], cfg.atlas, cfg.docs)
                        n = len(filter_docs_urls(parse_sitemap(docs_xml)[0], sub))
                    print(f"[{'OK ' if n else 'ERR'}] docs {g}: {n} pages in docs sitemap"
                          + ("" if n else " (may be in a child sitemap; discover will follow it)"))
                    continue
                toc = atlas_toc_url(cfg.atlas.base, cfg.atlas.locale, g, pinned)
                resp = await client.get(toc)
                pages, ver = [], {}
                if resp.status_code == 200:
                    try:
                        pages, ver = parse_atlas_toc(resp.json())
                    except ValueError:
                        pass
                if pinned and pages:
                    ver = version_info(doc_release=pinned)
                status = "OK " if pages else "-- "
                print(f"[{status}] atlas TOC {g}: HTTP {resp.status_code}, {len(pages)} pages, "
                      f"{ver.get('release') or 'version unknown'}")
                if pinned and not pages:
                    print("      not published for the pinned release; crawl will "
                          + ("skip it (strict_release)" if cfg.atlas.strict_release else "use its latest version"))
                if pages:
                    probe = atlas_content_urls(cfg.atlas.base, g, pages[0], cfg.atlas.locale, ver.get("doc_release"))
                    r2 = await client.get(probe[0])
                    is_json = "json" in r2.headers.get("content-type", "")
                    print(f"      content API sample: HTTP {r2.status_code}, {'JSON' if is_json else r2.headers.get('content-type')}")
                else:
                    print("      (not an atlas guide, or TOC unavailable; discovery will use sitemaps)")
    print("\nAll core endpoints reachable." if ok else "\nSome endpoints failed; see above.")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sfcognitio", description="SfCognitio Salesforce docs crawler")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("-c", "--config", default="config.yaml", help="path to config.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    for name, help_ in (
        ("doctor", "check that Salesforce endpoints are reachable"),
        ("discover", "find doc URLs and add them to the manifest"),
        ("fetch", "download pending pages"),
        ("extract", "convert downloaded pages to Markdown"),
        ("crawl", "discover + fetch + extract"),
        ("status", "show manifest progress"),
    ):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("-g", "--guide", action="append", help="limit to a guide (repeatable)")
        if name in ("fetch", "crawl"):
            sp.add_argument("-n", "--limit", type=int, default=0, help="max pages to fetch this run")
        if name in ("doctor", "discover", "crawl"):
            sp.add_argument("-r", "--release", help="override release: latest, \"Winter '27\", 68.0 or 264.0")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not Path(args.config).exists():
        print(f"Config not found: {args.config}", file=sys.stderr)
        return 1
    cfg = load_config(args.config)
    try:
        _apply_overrides(cfg, args)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    handlers = {
        "doctor": cmd_doctor, "discover": cmd_discover, "fetch": cmd_fetch,
        "extract": cmd_extract, "crawl": cmd_crawl, "status": cmd_status,
    }
    fn = handlers[args.command]
    result = fn(cfg, args)
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    return int(result or 0)


if __name__ == "__main__":
    sys.exit(main())
