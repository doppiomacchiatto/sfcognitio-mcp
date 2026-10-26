"""End-to-end pipeline against a mocked developer.salesforce.com."""

import json

import httpx
import pytest

from sfcognitio_mcp.config import AtlasSource, Config, CrawlerConfig, DocsSource
from sfcognitio_mcp.discover import discover
from sfcognitio_mcp.extract import extract_all
from sfcognitio_mcp.fetch import fetch_all
from sfcognitio_mcp.http import BlockedError, PoliteClient
from sfcognitio_mcp.manifest import Manifest

BASE = "https://developer.salesforce.com/docs"
LONG = "Apex is a strongly typed, object-oriented programming language. " * 6

TOC = {
    "version": {"doc_version": "264.0", "version_text": "Winter '27 (API version 68.0)"},
    "toc": [{"a_attr": {"href": "apex_intro.htm"}, "children": [{"a_attr": {"href": "apex_running.htm"}}]}],
}
DOCS_SITEMAP = f"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>{BASE}/platform/lwc/guide/get-started.html</loc></url>
<url><loc>{BASE}/platform/einstein/guide/other.html</loc></url>
</urlset>""".encode()
LWC_HTML = f"""<html><body><nav>nav</nav><main><h1>Get Started with LWC</h1><p>{LONG}</p>
<pre class="language-javascript">import {{ LightningElement }} from 'lwc';</pre></main></body></html>"""


def make_cfg(tmp_path, guides=("apexcode", "lwc")):
    return Config(
        data_dir=tmp_path / "data",
        crawler=CrawlerConfig(per_host_delay_seconds=0, max_retries=1, max_backoff_seconds=0),
        guides=list(guides), atlas=AtlasSource(), docs=DocsSource(),
    )


def handler_factory(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append((url, dict(request.headers)))
        if url == f"{BASE}/get_document/atlas.en-us.apexcode.meta":
            return httpx.Response(200, json=TOC)
        if url == f"{BASE}/get_document/atlas.en-us.lwc.meta":
            return httpx.Response(404)
        if url.startswith(f"{BASE}/get_document_content/apexcode/"):
            if request.headers.get("If-None-Match") == '"v1"':
                return httpx.Response(304)
            page = url.split("/")[-3]
            return httpx.Response(200, headers={"ETag": '"v1"'}, json={
                "title": f"Title {page}",
                "content": f"<h1>Title {page}</h1><p>{LONG}</p><pre>System.debug('hi');</pre>",
            })
        if url.endswith("docs-atlas-sitemap.xml"):
            return httpx.Response(200, content=b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>')
        if url.endswith("ssg-sitemap.xml"):
            return httpx.Response(200, content=DOCS_SITEMAP)
        if url == f"{BASE}/platform/lwc/guide/get-started.html":
            return httpx.Response(200, text=LWC_HTML, headers={"Content-Type": "text/html"})
        return httpx.Response(404)
    return handler


async def test_full_pipeline_and_resume(tmp_path):
    cfg = make_cfg(tmp_path)
    calls = []
    transport = httpx.MockTransport(handler_factory(calls))

    async with PoliteClient(cfg.crawler, transport=transport) as client:
        refs = await discover(client, cfg)
    by_guide = {}
    for r in refs:
        by_guide.setdefault(r.guide, []).append(r)
    assert len(by_guide["apexcode"]) == 2
    assert by_guide["apexcode"][0].release == "Winter '27"
    assert [r.url for r in by_guide["lwc"]] == [f"{BASE}/platform/lwc/guide/get-started.html"]

    with Manifest(cfg.manifest_path) as m:
        assert m.upsert_discovered(refs) == 3
        assert m.upsert_discovered(refs) == 0  # idempotent

        async with PoliteClient(cfg.crawler, transport=transport) as client:
            stats = await fetch_all(client, cfg, m)
        assert stats["fetched"] == 3 and stats["errors"] == 0

        # Atlas used the versioned content API first.
        assert any("/get_document_content/apexcode/apex_intro.htm/en-us/264.0" in u for u, _ in calls)

        ex = extract_all(cfg, m)
        assert ex["extracted"] == 3 and ex["errors"] == 0

        apex_md = (cfg.text_dir / "apexcode" / "apex_intro.md").read_text()
        assert "release: Winter '27" in apex_md
        assert "api_version: '68.0'" in apex_md
        assert "# Title apex_intro.htm" in apex_md
        assert "```\nSystem.debug('hi');\n```" in apex_md

        lwc_md = (cfg.text_dir / "lwc" / "get-started.md").read_text()
        assert "source: docs" in lwc_md and "```javascript" in lwc_md and "nav" not in lwc_md.split("---")[-1]

        # Nothing left to fetch on a second run.
        async with PoliteClient(cfg.crawler, transport=transport) as client:
            again = await fetch_all(client, cfg, m)
        assert again["queued"] == 0

        # Forced recheck sends conditional headers and handles 304.
        m.db.execute("UPDATE pages SET fetched_at='2000-01-01T00:00:00+00:00' WHERE guide='apexcode'")
        m.db.commit()
        calls.clear()
        async with PoliteClient(cfg.crawler, transport=transport) as client:
            re = await fetch_all(client, cfg, m)
        assert re["not_modified"] == 2
        assert all(h.get("if-none-match") == '"v1"' for u, h in calls if "get_document_content" in u)
        assert {r["status"] for r in m.summary()} == {"extracted"}


async def test_atlas_falls_back_to_html(tmp_path):
    cfg = make_cfg(tmp_path, guides=("apexcode",))

    def handler(request):
        url = str(request.url)
        if "get_document/" in url:
            return httpx.Response(200, json=TOC)
        if "get_document_content" in url:
            return httpx.Response(200, text="<html>not json</html>")
        if url.endswith(".htm"):
            return httpx.Response(200, text=f"<main><h1>HTML page</h1><p>{LONG}</p></main>")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with PoliteClient(cfg.crawler, transport=transport) as client:
        refs = await discover(client, cfg)
        with Manifest(cfg.manifest_path) as m:
            m.upsert_discovered(refs)
            stats = await fetch_all(client, cfg, m)
            assert stats["fetched"] == 2
            assert all(r["raw_path"].endswith(".html") for r in m.db.execute("SELECT raw_path FROM pages"))


async def test_errors_recorded_and_blocking_stops(tmp_path):
    cfg = make_cfg(tmp_path, guides=("apexcode",))

    def handler(request):
        url = str(request.url)
        if "get_document/" in url:
            return httpx.Response(200, json=TOC)
        return httpx.Response(403)

    transport = httpx.MockTransport(handler)
    async with PoliteClient(cfg.crawler, transport=transport) as client:
        refs = await discover(client, cfg)
        with Manifest(cfg.manifest_path) as m:
            m.upsert_discovered(refs)
            stats = await fetch_all(client, cfg, m)
            assert stats["blocked"] is True
            # Pages stay pending or errored so the next run resumes them.
            assert {r["status"] for r in m.summary()} <= {"pending", "error"}


async def test_known_atlas_guide_never_uses_docs_sitemap(tmp_path):
    cfg = make_cfg(tmp_path, guides=("api",))
    seen = []

    def handler(request):
        url = str(request.url)
        seen.append(url)
        if url.endswith("ssg-sitemap.xml"):
            return httpx.Response(200, content=(
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f'<url><loc>{BASE}/platform/x/api/unrelated.html</loc></url></urlset>').encode())
        if url.endswith("docs-atlas-sitemap.xml"):
            return httpx.Response(200, content=(
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f'<url><loc>{BASE}/atlas.en-us.248.0.api.meta/api/sforce_api_calls_list.htm</loc></url>'
                '</urlset>').encode())
        return httpx.Response(404)

    async with PoliteClient(cfg.crawler, transport=httpx.MockTransport(handler)) as client:
        refs = await discover(client, cfg)
    assert [r.url for r in refs] == [f"{BASE}/atlas.en-us.api.meta/api/sforce_api_calls_list.htm"]
    assert refs[0].release == "Spring '24"
    assert not any(u.endswith("ssg-sitemap.xml") for u in seen)


async def test_stub_atlas_toc_falls_through_to_docs(tmp_path):
    """LWC's classic TOC is a 1-page stub; real pages come from the SSG sitemap."""
    cfg = make_cfg(tmp_path, guides=("lwc", "somenewguide"))
    stub = {"version": {"doc_version": "240.0"}, "toc": [{"a_attr": {"href": "lwc_moved.htm"}}]}

    def handler(request):
        url = str(request.url)
        if "/get_document/" in url:
            return httpx.Response(200, json=stub)
        if url.endswith("docs-atlas-sitemap.xml"):
            return httpx.Response(200, content=b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>')
        if url.endswith("ssg-sitemap.xml"):
            return httpx.Response(200, content=(
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f'<url><loc>{BASE}/platform/lwc/guide/get-started.html</loc></url>'
                f'<url><loc>{BASE}/platform/somenewguide/guide/a.html</loc></url>'
                '</urlset>').encode())
        return httpx.Response(404)

    async with PoliteClient(cfg.crawler, transport=httpx.MockTransport(handler)) as client:
        refs = await discover(client, cfg)
    assert sorted((r.guide, r.source) for r in refs) == [("lwc", "docs"), ("somenewguide", "docs")]


def pinned_cfg(tmp_path, guides, strict=False):
    cfg = make_cfg(tmp_path, guides=guides)
    cfg.atlas.release = "Winter '27"
    cfg.atlas.strict_release = strict
    return cfg


def pinned_handler(seen):
    def handler(request):
        url = str(request.url)
        seen.append(url)
        if url == f"{BASE}/get_document/atlas.en-us.264.0.apexcode.meta":
            return httpx.Response(200, json=TOC)
        if url == f"{BASE}/get_document/atlas.en-us.264.0.api_rest.meta":
            return httpx.Response(404)
        if url == f"{BASE}/get_document/atlas.en-us.api_rest.meta":
            return httpx.Response(200, json={
                "version": {"doc_version": "262.0"},
                "toc": [{"a_attr": {"href": f"p{i}.htm"}} for i in range(6)]})
        if "/get_document_content/apexcode/" in url:
            return httpx.Response(200, json={"title": "T", "content": f"<h1>T</h1><p>{LONG}</p>"})
        return httpx.Response(404)
    return handler


async def test_pinned_release_uses_versioned_urls(tmp_path):
    cfg = pinned_cfg(tmp_path, ("apexcode", "api_rest"))
    seen = []
    transport = httpx.MockTransport(pinned_handler(seen))
    async with PoliteClient(cfg.crawler, transport=transport) as client:
        refs = await discover(client, cfg)
        apex = [r for r in refs if r.guide == "apexcode"]
        rest = [r for r in refs if r.guide == "api_rest"]
        assert apex[0].url == f"{BASE}/atlas.en-us.264.0.apexcode.meta/apexcode/apex_intro.htm"
        assert {r.release for r in apex} == {"Winter '27"}
        # api_rest isn't published for Winter '27 here, so it falls back to its latest.
        assert len(rest) == 6 and {r.release for r in rest} == {"Summer '26"}
        assert "264.0" not in rest[0].url

        with Manifest(cfg.manifest_path) as m:
            m.upsert_discovered(apex)
            await fetch_all(client, cfg, m)
    assert any(u.endswith("/get_document_content/apexcode/apex_intro.htm/en-us/264.0") for u in seen)


async def test_strict_release_skips_unpublished_guide(tmp_path):
    cfg = pinned_cfg(tmp_path, ("api_rest",), strict=True)
    async with PoliteClient(cfg.crawler, transport=httpx.MockTransport(pinned_handler([]))) as client:
        refs = await discover(client, cfg)
    assert refs == []


async def test_docs_pages_prefer_markdown_source(tmp_path):
    cfg = make_cfg(tmp_path, guides=("platform-events",))
    pe = f"{BASE}/platform/platform-events/guide"
    seen = []

    def handler(request):
        url = str(request.url)
        seen.append(url)
        if url.endswith("ssg-sitemap.xml"):
            return httpx.Response(200, content=(
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f'<url><loc>{pe}/platform-events-intro.html</loc></url>'
                f'<url><loc>{pe}/platform-events-publish.html</loc></url></urlset>').encode())
        if url == f"{pe}/platform-events-intro.md":
            return httpx.Response(200, headers={"Content-Type": "text/markdown"},
                                  text=f"# Platform Events Developer Guide\n\n{LONG}\n\n```apex\nEventBus.publish(e);\n```\n")
        if url == f"{pe}/platform-events-publish.md":
            return httpx.Response(200, headers={"Content-Type": "text/html"}, text="<!doctype html><p>app shell</p>")
        if url == f"{pe}/platform-events-publish.html":
            return httpx.Response(200, text=f"<main><h1>Publish Events</h1><p>{LONG}</p></main>")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with PoliteClient(cfg.crawler, transport=transport) as client:
        refs = await discover(client, cfg)
        assert not any("/get_document/" in u for u in seen)  # docs-only guide skips atlas
        with Manifest(cfg.manifest_path) as m:
            m.upsert_discovered(refs)
            stats = await fetch_all(client, cfg, m)
            assert stats["fetched"] == 2
            ex = extract_all(cfg, m)
            assert ex["extracted"] == 2

    intro = (cfg.text_dir / "platform-events" / "platform-events-intro.md").read_text()
    assert "title: Platform Events Developer Guide" in intro
    assert "```apex\nEventBus.publish(e);\n```" in intro
    publish = (cfg.text_dir / "platform-events" / "platform-events-publish.md").read_text()
    assert "# Publish Events" in publish and "app shell" not in publish


NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
SM = "https://developer.salesforce.com/docs"
INDEX = (f'<sitemapindex xmlns="{NS}"><sitemap><loc>{SM}/a.xml</loc></sitemap>'
         f'<sitemap><loc>{SM}/b.xml</loc></sitemap></sitemapindex>').encode()


def _urlset(*urls):
    return (f'<urlset xmlns="{NS}">' + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>").encode()


async def test_sitemap_skips_failing_child_and_does_not_cache(tmp_path):
    from sfcognitio_mcp.discover import fetch_sitemap_urls
    cfg = make_cfg(tmp_path)

    def handler(request):
        url = str(request.url)
        if url.endswith("index.xml"):
            return httpx.Response(200, content=INDEX)
        if url.endswith("a.xml"):
            return httpx.Response(200, content=_urlset("https://x/1"))
        raise httpx.ConnectError("boom")

    cache_dir = tmp_path / "sm"
    async with PoliteClient(cfg.crawler, transport=httpx.MockTransport(handler)) as client:
        urls = await fetch_sitemap_urls(client, f"{SM}/index.xml", cache_dir=cache_dir, max_age_hours=24)
    assert urls == ["https://x/1"]
    assert not cache_dir.exists() or not list(cache_dir.iterdir())


async def test_sitemap_root_failure_still_raises(tmp_path):
    from sfcognitio_mcp.discover import fetch_sitemap_urls
    cfg = make_cfg(tmp_path)

    def handler(request):
        raise httpx.ConnectError("boom")

    async with PoliteClient(cfg.crawler, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ConnectError):
            await fetch_sitemap_urls(client, f"{SM}/index.xml")


async def test_sitemap_cache_is_reused_then_expires(tmp_path):
    import os
    import time
    from sfcognitio_mcp.discover import fetch_sitemap_urls
    cfg = make_cfg(tmp_path)
    hits = []

    def handler(request):
        hits.append(str(request.url))
        return httpx.Response(200, content=_urlset("https://x/1", "https://x/2"))

    url = f"{SM}/ssg-sitemap.xml"
    kw = dict(cache_dir=tmp_path / "sm", max_age_hours=24)
    async with PoliteClient(cfg.crawler, transport=httpx.MockTransport(handler)) as client:
        first = await fetch_sitemap_urls(client, url, **kw)
        second = await fetch_sitemap_urls(client, url, **kw)
        assert first == second == ["https://x/1", "https://x/2"] and len(hits) == 1

        old = time.time() - 48 * 3600
        for f in (tmp_path / "sm").iterdir():
            os.utime(f, (old, old))
        await fetch_sitemap_urls(client, url, **kw)
        assert len(hits) == 2
        await fetch_sitemap_urls(client, url, cache_dir=tmp_path / "sm", max_age_hours=0)
        assert len(hits) == 3

