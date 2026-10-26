import json

import pytest

from sfcognitio_mcp.discover import (
    docs_guide_for, filter_docs_urls, parse_atlas_toc, parse_atlas_url, parse_sitemap,
)
from sfcognitio_mcp.extract import html_to_markdown
from sfcognitio_mcp.versions import (
    api_to_release_name, doc_release_to_api, release_name_to_api, version_info,
)


@pytest.mark.parametrize("api,name", [
    (60, "Spring '24"), (61, "Summer '24"), (62, "Winter '25"), (63, "Spring '25"),
    (64, "Summer '25"), (65, "Winter '26"), (66, "Spring '26"), (67, "Summer '26"), (68, "Winter '27"),
])
def test_release_names_roundtrip(api, name):
    assert api_to_release_name(api) == name
    assert release_name_to_api(name) == float(api)


def test_doc_release_mapping():
    assert doc_release_to_api("248.0") == 60.0
    assert doc_release_to_api("264.0") == 68.0
    assert version_info(doc_release="264.0") == {
        "api_version": "68.0", "doc_release": "264.0", "release": "Winter '27"}
    assert version_info() == {"api_version": None, "doc_release": None, "release": None}


def test_parse_atlas_url_latest_and_versioned():
    latest = parse_atlas_url(
        "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_running.htm")
    assert latest == {"locale": "en-us", "doc_release": None, "guide": "apexcode",
                      "sub": "apexcode", "page": "apex_running.htm"}
    versioned = parse_atlas_url(
        "https://developer.salesforce.com/docs/atlas.en-us.264.0.apexcode.meta/pages/apex_dev_guide.htm")
    assert versioned["doc_release"] == "264.0"
    assert versioned["guide"] == "apexcode"
    assert parse_atlas_url("https://developer.salesforce.com/docs/platform/lwc/guide/intro.html") is None


def test_parse_sitemap_index_and_urlset():
    index = b"""<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://x/a.xml</loc></sitemap><sitemap><loc>https://x/b.xml</loc></sitemap></sitemapindex>"""
    pages, children = parse_sitemap(index)
    assert pages == [] and children == ["https://x/a.xml", "https://x/b.xml"]
    urlset = b"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc> https://x/p1 </loc></url><url><loc>https://x/p2</loc></url></urlset>"""
    assert parse_sitemap(urlset) == (["https://x/p1", "https://x/p2"], [])


def test_parse_sitemap_gzip():
    import gzip
    data = gzip.compress(b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                         b'<url><loc>https://x/p</loc></url></urlset>')
    assert parse_sitemap(data)[0] == ["https://x/p"]


def test_parse_atlas_toc_nested_and_version():
    toc = {
        "title": "Apex Developer Guide",
        "version": {"doc_version": "264.0", "version_text": "Winter '27 (API version 68.0)"},
        "toc": [
            {"text": "Getting Started", "a_attr": {"href": "apex_intro.htm"}, "children": [
                {"text": "What is Apex", "a_attr": {"href": "apex_intro_what_is_apex.htm#anchor"}},
                {"text": "Dup", "a_attr": {"href": "apex_intro.htm"}},
            ]},
            {"text": "Running", "a_attr": {"href": "apex_running.htm"}},
            {"text": "External", "a_attr": {"href": "https://example.com/not-a-page"}},
        ],
    }
    pages, ver = parse_atlas_toc(toc)
    assert pages == ["apex_intro.htm", "apex_intro_what_is_apex.htm", "apex_running.htm"]
    assert ver["release"] == "Winter '27" and ver["api_version"] == "68.0"


def test_docs_filtering(tmp_path):
    from sfcognitio_mcp.config import AtlasSource, Config, CrawlerConfig, DocsSource
    cfg = Config(tmp_path, CrawlerConfig(), ["lwc"], AtlasSource(),
                 DocsSource(exclude=["/ja-jp/"]))
    urls = [
        "https://developer.salesforce.com/docs/platform/lwc/guide/intro.html",
        "https://developer.salesforce.com/docs/platform/lwc/guide/intro.html#top",
        "https://developer.salesforce.com/docs/ja-jp/platform/lwc/guide/intro.html",
        "https://developer.salesforce.com/docs/platform/einstein/guide/x.html",
        "https://developer.salesforce.com/docs/atlas.en-us.lwc.meta/lwc/x.htm",
        "https://example.com/docs/platform/lwc/guide/y.html",
    ]
    refs = filter_docs_urls(urls, cfg)
    assert [r.url for r in refs] == ["https://developer.salesforce.com/docs/platform/lwc/guide/intro.html"]
    assert refs[0].guide == "lwc" and refs[0].source == "docs"
    assert docs_guide_for("https://d/docs/platform/lwc/guide/a.html", ["apexcode", "lwc"]) == "lwc"


def test_html_to_markdown_keeps_code_and_strips_chrome():
    html = """<html><head><title>Trigger Syntax | Apex Developer Guide</title></head><body>
      <header>Site header</header><nav>Menu</nav>
      <main><h1>Trigger Syntax</h1>
        <p>To define a trigger, use the following syntax. This paragraph is long enough to count as
        real content for the main picker, which needs a couple hundred characters of text to pick the
        main element instead of falling back to the whole body of the page.</p>
        <h2>Example</h2>
        <pre class="language-apex">trigger HelloWorld on Account (before insert) {
    for (Account a : Trigger.new) {
        a.Description = 'Hello';
    }
}</pre>
        <ul><li>Before triggers</li><li>After triggers</li></ul>
      </main><footer>Copyright</footer><script>track()</script></body></html>"""
    md, title = html_to_markdown(html)
    assert title == "Trigger Syntax"
    assert "# Trigger Syntax" in md and "## Example" in md
    assert "```apex\ntrigger HelloWorld on Account (before insert) {" in md
    assert "    for (Account a : Trigger.new) {" in md  # indentation preserved
    assert "- Before triggers" in md
    for junk in ("Site header", "Menu", "Copyright", "track()"):
        assert junk not in md


def test_salesforce_api_names_not_escaped():
    md, _ = html_to_markdown("<p>Query Invoice__c and npe01__OppPayment__c from apex_intro.htm.</p>")
    assert "Invoice__c" in md and "npe01__OppPayment__c" in md and "\\_" not in md


@pytest.mark.parametrize("spec,expected", [
    ("latest", None), ("", None), (None, None),
    ("Winter '27", "264.0"), ("winter 27", "264.0"), ("Summer '26", "262.0"),
    ("68.0", "264.0"), (68, "264.0"), ("264.0", "264.0"),
])
def test_parse_release_spec(spec, expected):
    from sfcognitio_mcp.versions import parse_release_spec
    assert parse_release_spec(spec) == expected


def test_parse_release_spec_rejects_garbage():
    from sfcognitio_mcp.versions import parse_release_spec
    with pytest.raises(ValueError):
        parse_release_spec("next week")


def test_docs_markdown_url():
    from sfcognitio_mcp.fetch import docs_markdown_url
    b = "https://developer.salesforce.com/docs/platform/platform-events/guide"
    assert docs_markdown_url(f"{b}/platform-events-intro.html") == f"{b}/platform-events-intro.md"
    assert docs_markdown_url(f"{b}/platform-events-intro.html#x") == f"{b}/platform-events-intro.md"
    assert docs_markdown_url(f"{b}/platform-events-intro.md") == f"{b}/platform-events-intro.md"
    assert docs_markdown_url(f"{b}/platform-events-intro") == f"{b}/platform-events-intro.md"
    assert docs_markdown_url(f"{b}/") is None


def test_clean_source_markdown():
    from sfcognitio_mcp.extract import clean_source_markdown
    md, title = clean_source_markdown("---\nlayout: x\n---\n\r\n# Platform Events Developer Guide\r\n\n\n\nUse `Order_Event__e`.\n")
    assert title == "Platform Events Developer Guide"
    assert md == "# Platform Events Developer Guide\n\nUse `Order_Event__e`.\n"
