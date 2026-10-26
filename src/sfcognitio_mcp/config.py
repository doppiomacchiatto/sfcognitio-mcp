"""Load and validate config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class CrawlerConfig:
    user_agent: str = "sfcognitio-mcp/0.1 (+https://github.com/doppiomacchiatto/sfcognitio-mcp) python-httpx"
    concurrency: int = 2
    per_host_delay_seconds: float = 2.5
    timeout_seconds: float = 60
    max_retries: int = 4
    max_backoff_seconds: float = 300
    recheck_after_days: int = 14
    max_pages: int = 0
    # Reuse a fully-read sitemap URL list for this long before walking it again (0 = always re-fetch).
    sitemap_cache_hours: float = 24


@dataclass
class AtlasSource:
    enabled: bool = True
    sitemap: str = "https://developer.salesforce.com/docs-atlas-sitemap.xml"
    base: str = "https://developer.salesforce.com/docs"
    locale: str = "en-us"
    # "latest", a release name ("Winter '27"), API version ("68.0") or doc release ("264.0").
    release: str = "latest"
    # If a guide isn't published for the pinned release: False = use its latest, True = skip it.
    strict_release: bool = False


@dataclass
class DocsSource:
    enabled: bool = True
    sitemap: str = "https://developer.salesforce.com/docs/ssg-sitemap.xml"
    include: list[str] = field(default_factory=lambda: ["https://developer.salesforce.com/docs/"])
    exclude: list[str] = field(default_factory=list)


ARTICLES_GUIDE = "articles"


@dataclass
class Config:
    data_dir: Path
    crawler: CrawlerConfig
    guides: list[str]
    atlas: AtlasSource
    docs: DocsSource
    extra_pages: list[str] = field(default_factory=list)

    @property
    def all_guides(self) -> list[str]:
        """Configured guides plus the ``articles`` bucket when extra pages are listed."""
        return self.guides + ([ARTICLES_GUIDE] if self.extra_pages else [])

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.sqlite3"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def text_dir(self) -> Path:
        return self.data_dir / "text"


def _pick(cls, data: dict | None):
    data = data or {}
    known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
    return cls(**known)


def load_config(path: str | Path) -> Config:
    path = Path(path).resolve()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data_dir = Path(raw.get("data_dir", "./data"))
    if not data_dir.is_absolute():
        data_dir = (path.parent / data_dir).resolve()
    sources = raw.get("sources") or {}
    return Config(
        data_dir=data_dir,
        crawler=_pick(CrawlerConfig, raw.get("crawler")),
        guides=[g.strip() for g in (raw.get("guides") or []) if g and g.strip()],
        atlas=_pick(AtlasSource, sources.get("atlas")),
        docs=_pick(DocsSource, sources.get("docs")),
        extra_pages=[u.strip() for u in (raw.get("extra_pages") or []) if u and u.strip()],
    )
