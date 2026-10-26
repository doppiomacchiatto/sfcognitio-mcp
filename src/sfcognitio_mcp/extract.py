"""Convert raw HTML/JSON into clean Markdown with YAML front matter."""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

from .config import Config
from .fetch import load_raw
from .manifest import Manifest

log = logging.getLogger(__name__)

STRIP_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form",
              "button", "svg", "iframe", "template"]
STRIP_SELECTORS = [
    "[role=navigation]", "[role=banner]", "[role=contentinfo]", ".breadcrumbs", ".breadcrumb",
    ".feedback", ".doc-feedback", ".toc", ".sidebar", ".cookie", "#onetrust-consent-sdk",
    ".skip-link", ".print-only", ".related-links-header",
]
MAIN_SELECTORS = ["article", "main", "[role=main]", "doc-content", "div.body", "div#content",
                  "div.content", "div.doc-content"]
LANG_HINTS = {
    "apex": "apex", "java": "java", "javascript": "javascript", "js": "javascript",
    "html": "html", "xml": "xml", "json": "json", "css": "css", "soql": "sql", "sql": "sql",
    "bash": "bash", "shell": "bash", "sh": "bash", "typescript": "typescript", "ts": "typescript",
    "yaml": "yaml", "python": "python", "visualforce": "html",
}


def _code_language(el: Tag) -> str:
    for node in (el, el.find("code")):
        if not isinstance(node, Tag):
            continue
        for attr in ("data-language", "lang"):
            v = node.get(attr)
            if v and v.lower() in LANG_HINTS:
                return LANG_HINTS[v.lower()]
        for cls in node.get("class") or []:
            c = cls.lower().removeprefix("language-").removeprefix("lang-").removeprefix("brush:")
            if c in LANG_HINTS:
                return LANG_HINTS[c]
    return ""


class _Converter(MarkdownConverter):
    def convert_pre(self, el, text, *args, **kwargs):
        code = el.get_text()
        if not code.strip():
            return ""
        lang = _code_language(el)
        fence = "````" if "```" in code else "```"
        return f"\n\n{fence}{lang}\n{code.strip(chr(10))}\n{fence}\n\n"


def _pick_main(soup: BeautifulSoup) -> Tag:
    for sel in MAIN_SELECTORS:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 200:
            return el
    return soup.body or soup


def html_to_markdown(html: str) -> tuple[str, str | None]:
    """Return (markdown, title)."""
    soup = BeautifulSoup(html, "html.parser")
    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
    elif soup.title:
        title = re.sub(r"\s*\|\s*.*$", "", soup.title.get_text(" ", strip=True)) or None

    for tag in STRIP_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    for sel in STRIP_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    main = _pick_main(soup)
    md = _Converter(heading_style="ATX", bullets="-", escape_underscores=False).convert_soup(main)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md + "\n", title


def slug_for(row: sqlite3.Row) -> str:
    base = row["page"] or row["url"].rstrip("/").rsplit("/", 1)[-1] or "index"
    base = re.sub(r"\.(html?|md)$", "", base)
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", base).strip("-") or "index"


def render_document(row: sqlite3.Row, markdown: str, title: str | None) -> str:
    meta = {
        "title": title or row["title"],
        "url": row["url"],
        "source": row["source"],
        "guide": row["guide"],
        "page": row["page"],
        "api_version": row["api_version"],
        "doc_release": row["doc_release"],
        "release": row["release"],
        "fetched_at": row["fetched_at"],
    }
    meta = {k: v for k, v in meta.items() if v is not None}
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{front}\n---\n\n{markdown}"


_FRONT_RE = re.compile(r"\A---\n.*?\n---\n", re.S)


def clean_source_markdown(text: str) -> tuple[str, str | None]:
    """Tidy Markdown served directly by the docs site. Returns (markdown, title)."""
    text = text.replace("\r\n", "\n")
    text = _FRONT_RE.sub("", text, count=1)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    m = re.search(r"^#\s+(.+?)\s*#*\s*$", text, re.M)
    return text, (m.group(1).strip() if m else None)


def extract_one(cfg: Config, row: sqlite3.Row) -> tuple[Path, str | None]:
    raw, payload = load_raw(row["raw_path"])
    if str(row["raw_path"]).endswith(".md"):
        md, title = clean_source_markdown(raw)
    else:
        md, title = html_to_markdown(raw)
    if payload and payload.get("title"):
        title = payload["title"]
    if title and not md.lstrip().startswith("# "):
        md = f"# {title}\n\n{md}"
    out = cfg.text_dir / (row["guide"] or "_misc") / f"{slug_for(row)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_document(row, md, title), encoding="utf-8")
    return out, title


def extract_all(cfg: Config, manifest: Manifest, guides: list[str] | None = None) -> dict:
    rows = manifest.due_for_extract(guides)
    stats = {"queued": len(rows), "extracted": 0, "empty": 0, "errors": 0}
    for row in rows:
        try:
            out, title = extract_one(cfg, row)
        except Exception as e:
            stats["errors"] += 1
            manifest.mark_error(row["url"], f"extract: {type(e).__name__}: {e}")
            continue
        body = out.read_text(encoding="utf-8").split("---", 2)[-1]
        if len(body.strip()) < 200:
            stats["empty"] += 1
            log.warning("Very little text extracted from %s (page may need JS rendering)", row["url"])
        manifest.mark_extracted(row["url"], str(out), title)
        stats["extracted"] += 1
    return stats
