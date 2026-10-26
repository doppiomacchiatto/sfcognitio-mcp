"""SQLite manifest: every known doc URL and its crawl state.

Makes the crawl resumable: discovery inserts URLs, fetch updates status,
extract records output paths. Re-running picks up where it stopped.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    url            TEXT PRIMARY KEY,
    source         TEXT NOT NULL,          -- atlas | docs
    guide          TEXT,                   -- apexcode, lwc, ...
    page           TEXT,                   -- page id within guide (atlas)
    doc_release    TEXT,                   -- 264.0
    api_version    TEXT,                   -- 68.0
    release        TEXT,                   -- Winter '27
    status         TEXT NOT NULL DEFAULT 'pending',  -- pending|fetched|not_modified|error|extracted
    http_status    INTEGER,
    etag           TEXT,
    last_modified  TEXT,
    content_hash   TEXT,
    raw_path       TEXT,
    text_path      TEXT,
    title          TEXT,
    error          TEXT,
    attempts       INTEGER NOT NULL DEFAULT 0,
    discovered_at  TEXT NOT NULL,
    fetched_at     TEXT,
    extracted_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
CREATE INDEX IF NOT EXISTS idx_pages_guide ON pages(guide);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class PageRef:
    url: str
    source: str
    guide: str | None = None
    page: str | None = None
    doc_release: str | None = None
    api_version: str | None = None
    release: str | None = None


class Manifest:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- discovery ---------------------------------------------------------
    def upsert_discovered(self, refs: list[PageRef]) -> int:
        """Insert new URLs; refresh version metadata on known ones. Returns new count."""
        before = self.count()
        ts = now_iso()
        self.db.executemany(
            """
            INSERT INTO pages (url, source, guide, page, doc_release, api_version, release, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                guide = COALESCE(excluded.guide, pages.guide),
                page = COALESCE(excluded.page, pages.page),
                doc_release = COALESCE(excluded.doc_release, pages.doc_release),
                api_version = COALESCE(excluded.api_version, pages.api_version),
                release = COALESCE(excluded.release, pages.release)
            """,
            [(r.url, r.source, r.guide, r.page, r.doc_release, r.api_version, r.release, ts) for r in refs],
        )
        self.db.commit()
        return self.count() - before

    def prune_pending(self, refs: list[PageRef]) -> int:
        """Delete never-fetched rows of re-discovered guides whose URL is no longer listed."""
        keep: dict[str, set[str]] = {}
        for r in refs:
            if r.guide:
                keep.setdefault(r.guide, set()).add(r.url)
        stale: list[tuple[str]] = []
        for guide, urls in keep.items():
            rows = self.db.execute("SELECT url FROM pages WHERE guide = ? AND status = 'pending'", (guide,))
            stale.extend((row["url"],) for row in rows if row["url"] not in urls)
        self.db.executemany("DELETE FROM pages WHERE url = ?", stale)
        self.db.commit()
        return len(stale)

    # -- fetch -------------------------------------------------------------
    def due_for_fetch(self, recheck_after_days: int, limit: int = 0, guides: list[str] | None = None) -> list[sqlite3.Row]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=recheck_after_days)).isoformat(timespec="seconds")
        sql = """
            SELECT * FROM pages
            WHERE (status IN ('pending', 'error')
                   OR (fetched_at IS NOT NULL AND fetched_at < ?))
              AND attempts < 6
        """
        params: list = [cutoff]
        if guides:
            sql += f" AND guide IN ({','.join('?' * len(guides))})"
            params += guides
        sql += " ORDER BY guide, url"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return list(self.db.execute(sql, params))

    def mark_fetched(self, url: str, *, http_status: int, raw_path: str, content_hash: str,
                     etag: str | None, last_modified: str | None, title: str | None = None,
                     api_version: str | None = None, doc_release: str | None = None,
                     release: str | None = None) -> None:
        self.db.execute(
            """
            UPDATE pages SET status='fetched', http_status=?, raw_path=?, content_hash=?, etag=?,
                   last_modified=?, title=COALESCE(?, title), error=NULL, fetched_at=?,
                   attempts=attempts+1,
                   api_version=COALESCE(?, api_version), doc_release=COALESCE(?, doc_release),
                   release=COALESCE(?, release)
            WHERE url=?
            """,
            (http_status, raw_path, content_hash, etag, last_modified, title, now_iso(),
             api_version, doc_release, release, url),
        )
        self.db.commit()

    def mark_not_modified(self, url: str) -> None:
        self.db.execute(
            "UPDATE pages SET status=CASE WHEN text_path IS NOT NULL THEN 'extracted' ELSE 'fetched' END, "
            "http_status=304, fetched_at=?, error=NULL WHERE url=?",
            (now_iso(), url),
        )
        self.db.commit()

    def mark_error(self, url: str, error: str, http_status: int | None = None) -> None:
        self.db.execute(
            "UPDATE pages SET status='error', error=?, http_status=?, attempts=attempts+1 WHERE url=?",
            (error[:500], http_status, url),
        )
        self.db.commit()

    # -- extract -----------------------------------------------------------
    def due_for_extract(self, guides: list[str] | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM pages WHERE status='fetched' AND raw_path IS NOT NULL"
        params: list = []
        if guides:
            sql += f" AND guide IN ({','.join('?' * len(guides))})"
            params += guides
        return list(self.db.execute(sql, params))

    def mark_extracted(self, url: str, text_path: str, title: str | None) -> None:
        self.db.execute(
            "UPDATE pages SET status='extracted', text_path=?, title=COALESCE(?, title), extracted_at=? WHERE url=?",
            (text_path, title, now_iso(), url),
        )
        self.db.commit()

    # -- reporting ---------------------------------------------------------
    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]

    def get(self, url: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM pages WHERE url=?", (url,)).fetchone()

    def summary(self) -> list[sqlite3.Row]:
        return list(self.db.execute(
            "SELECT COALESCE(guide, '?') AS guide, status, COUNT(*) AS n FROM pages "
            "GROUP BY guide, status ORDER BY guide, status"
        ))

    def recent_errors(self, limit: int = 10) -> list[sqlite3.Row]:
        return list(self.db.execute(
            "SELECT url, http_status, error FROM pages WHERE status='error' ORDER BY url LIMIT ?", (limit,)
        ))
