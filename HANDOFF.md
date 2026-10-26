# SfCognitio: Handoff

Context for continuing work on this project in a new session (for example, Claude Code in WSL). Last updated 2026-10-25.

## What this is

**SfCognitio** (`sfcognitio-mcp`) is an open-source Salesforce documentation knowledge server. It's inspired by [jperram92/sfdocs-rag](https://github.com/jperram92/sfdocs-rag), but the goal is broader: **any agent** (Claude, Agentforce, Bedrock Agents, Cursor, ...) can connect and become a Salesforce expert.

- **Owner:** Juan / Santisi LLC (`Copyright 2026 Santisi LLC` in NOTICE)
- **Repo:** https://github.com/doppiomacchiatto/sfcognitio-mcp (public)
- **License:** Apache 2.0 (chosen for its explicit patent grant and enterprise-friendly terms)
- **Language:** Python 3.10+
- **Local path:** `~/dev/sfcognitio-mcp` in Ubuntu WSL (moved from `C:\Users\juan\dev\sfdc\sfcognitio-mcp`)

## Decisions made

| Decision | Choice | Why |
|---|---|---|
| Name | SfCognitio (`sfcognitio-mcp` slug) | Latin *cognitio* = knowledge; no trademark collision. Unclaimed on PyPI and npm as of 2026-10-25 |
| License | Apache 2.0 | Patent grant, contribution terms |
| Stack | Python | Strongest crawling, PDF, and embedding libraries |
| Content | **Bring your own index** | No Salesforce content in the repo. Users build their own with the crawler. Salesforce's terms may restrict redistributing their docs |
| Release | Prefer **Winter '27** (API 68.0, doc release 264.0); fall back to the latest published (Summer '26) per guide | Winter '27 is not officially out yet. Use 27 when a guide has it, 26 when it doesn't. `strict_release: false` does this |
| Fetch politeness | 2 concurrent, 2.5s per-host delay, stop after 5 consecutive 403/429 | Be a good citizen; resume later |
| Scope | **Salesforce Platform, Sales Cloud, Service Cloud** only | Focus. See "Scope" below |

## Scope

In scope: **Salesforce Platform, Sales Cloud, Service Cloud.**
Out of scope: **Marketing Cloud, Revenue Cloud, Tableau, Slack.** In the `llms.txt` index that means `llms-marketing-cloud`, `llms-marketing-cloud-mobilepush`, `llms-revenue-cloud`, `llms-analytics` (Tableau Next) and `llms-salesforce-slack-sdk`. I also treated `llms-pardot` (Account Engagement) and `llms-personalization` as Marketing; confirm that.

### Decisions by guide

`llms-product-docs.txt` (classic atlas, `.htm`, 15,661 pages, 32 guides):

| Guide | Pages | Decision |
|---|---|---|
| `apexcode` | 549 | Yes (already configured) |
| `api_meta` | 707 | Yes (already configured) |
| `apexref` | 2,331 | **Yes** |
| `object_reference` | 1,890 | **Yes** |
| `api_tooling` | 347 | **Yes** |
| `uiapi` | 269 | **Yes** |
| `bi_dev_guide_rest` (CRM Analytics) | 541 | **Yes** |
| `mobile_sdk` | 413 | Optional; **no for now** |
| `salesforce_recipes_api` | 299 | **No** |
| Industry clouds (Health, Insurance, Life Sciences, Financial Services, Retail, Education, Nonprofit, Net Zero, Media, Manufacturing, Automotive, Communications, ...) | thousands | No: not Platform, Sales or Service |

Not yet reviewed: the 7 smallest product-docs guides (only the top 25 were listed), and `bi_dev_guide_rest_sdd` (313 pages), which may also be CRM Analytics.

`llms-platform.txt` and related files (newer docs site, `.md`):

| Guide | Pages | Decision |
|---|---|---|
| `api-rest`, `api`, `api-asynch` | 310 / 208 / 128 | Yes. Moved to the new site; replace the atlas copies |
| `platform-events` | 240 | Yes (already configured) |
| `lwc` | 689 | Yes (already configured) |
| `field-reference` | 2,712 | **Yes** |
| `lightning-component-reference` (base components) | 443 | **Yes** |
| `lightning-components-security`, `utam`, `slds-linter`, `slds-validator` (from `llms-lwc.txt`) | 73 / 41 / 17 / 9 | **Yes** (LWC extras) |
| `connect-rest-api`, `graphql`, `pub-sub-api` | 49 / 76 / 49 | **Yes.** The connect-rest-api and graphql intro pages already in the `articles` bucket become redundant once the full guides are crawled |
| The other 23 guides in `llms-platform.txt` | see `guides.tsv` | **On hold until 2026-10-26: create a Platform subset** (below) |

Sales Cloud (`llms-sales-cloud.txt`, 125 pages):
- `channel-revenue-management` (83): **No.**
- `spiff` (6): **On hold until 2026-10-26**, Juan is analyzing it. (I had suggested excluding it as Revenue-like.)
- `maps-dev-guide` (17), `enablement` (13), `sales-engagement` (6): proposed to keep. **Not confirmed.**

Service Cloud (`llms-service-cloud.txt`, 28 guides, 2,585 pages): **On hold until 2026-10-26**, Juan is analyzing it. Questionable ones: `service-connector-api` (524), `agentforce-it-service` (394), `workdotcom-dev` (81).

## TODO

- [ ] **Create a Platform subset (on hold until 2026-10-26).** Decide which of the 26 guides in `llms-platform.txt` to keep. Exclude the legacy ones: candidates are `ajax`, `caf-dev`, `salesforce-developer-environment-dotnet-tipsheet`, `salesforce-pages-developers-guide` (494 pages, Visualforce) and `mobile-offline`. These are my suggestions, not decisions.
- [ ] Juan to analyze Service Cloud and `spiff` (both on hold until 2026-10-26).
- [ ] Review the 7 unlisted product-docs guides and `bi_dev_guide_rest_sdd`.
- [ ] Switch discovery to the `llms.txt` lists: add an allow-list of guides, and read page URLs from `llms-*.txt` instead of walking the sitemap. Move `api_rest`, `api` and `api_asynch` out of `ATLAS_GUIDES` and into the docs source.
- [ ] Check the stale-row problem when Winter '27 is published (see "Releases" below).
- [ ] Add the inventory scripts to the repo (they currently live in a temp directory), ideally as `sfcognitio inventory`.
- [ ] Add a `docs.exclude` list for Marketing, Revenue, Tableau and Slack once their URL path segments are known. The sitemap dump was never completed.
- [ ] Run the trial crawl: `sfcognitio crawl --guide articles`, then `--limit 50`. Inspect `data/text/` (code blocks, tables, front matter, any MDX leftovers in the `.md` source).
- [ ] Publish the placeholder packages (`packages/pypi-placeholder`: `python -m build && twine upload dist/*`; `packages/npm-placeholder`: `npm publish`).
- [ ] Fill in the GitHub About description and topics (`salesforce`, `mcp`, `rag`, `ai-agents`, `model-context-protocol`).
- [ ] Push the local commits; start **milestone 2** (index).

## Roadmap

| # | Milestone | Status |
|---|---|---|
| 1 | Crawler: discover, fetch, extract to versioned Markdown | **Built, 41 tests passing; live trial pending** |
| 2 | Index: heading-aware chunks (never split code), vector + keyword (BM25) hybrid search with RRF; swappable embeddings (local Ollama or Bedrock Titan) | Next |
| 3 | MCP server: `search_docs`, `get_page`, `get_governor_limits`; stdio + HTTP | Planned |
| 4 | Hosted on AWS (Lambda or container + API Gateway; S3 Vectors or OpenSearch Serverless), plus a REST/OpenAPI endpoint | Planned |
| 5 | Expert layer: structured lookups (limits, object/field reference, Apex/LWC signatures); pair with Juan's `salesforce-bedrock-mcp` server for live-org metadata | Later |

## Guides currently in config.yaml

These seven were the original set. The scope work above will change this list.

| Guide id | Guide | Where it actually lives (verified 2026-10-25) |
|---|---|---|
| `apexcode` | Apex Developer Guide | classic atlas |
| `api_meta` | Metadata API Developer Guide | classic atlas |
| `api_rest` | REST API Developer Guide | atlas copy is Summer '26; **also on the new site** as `platform/api-rest` |
| `api` | SOAP API Developer Guide | atlas copy is Summer '26; also on the new site as `platform/api` |
| `api_asynch` | Bulk API 2.0 and Bulk API Developer Guide | atlas copy is Summer '26; also on the new site as `platform/api-asynch` |
| `lwc` | Lightning Web Components Developer Guide | new site |
| `platform-events` | Platform Events Developer Guide | new site |

`extra_pages` in `config.yaml` adds hand-picked URLs under guide `articles` (`data/text/articles/`). Currently: Connect REST API intro, GraphQL about, Streaming API intro.

## How Salesforce docs work (verified live on 2026-10-25)

**`llms.txt` index (best discovery source).** `https://developer.salesforce.com/docs/llms.txt` lists about 45 product files, `https://developer.salesforce.com/docs/llms-<product>.txt`. Each lists page URLs, so no sitemap walk is needed. All fetched with HTTP 200.
- Newer-site files list `.md` URLs: `llms-platform` (2,872 pages), `llms-platform-field-ref` (2,712), `llms-service-cloud` (2,585), `llms-lwc` (829), `llms-lightning-base-components` (443), `llms-sales-cloud` (125), `llms-graphql-api` (76), `llms-connect-rest` (49), `llms-event-bus` (49).
- `llms-product-docs.txt` (3.7 MB) lists classic atlas `.htm` URLs with no version in the URL, which means "latest".
- The index tells agents to default to the latest API version.
- Saved copies are in `data/llms/` and the combined inventory (25,401 unique URLs, 101 guides) is in `data/inventory/urls.tsv` and `guides.tsv`. Both are gitignored.
- Not fetched: `llms-security`, `llms-metadata-coverage`, `llms-mobile-sdk`, `llms-salesforcedx` (possibly in scope), and the out-of-scope files.

**Classic atlas guides**
- Page URL: `https://developer.salesforce.com/docs/atlas.<locale>[.<doc_release>].<guide>.meta/<guide>/<page>.htm`
- Table of contents (JSON): `/docs/get_document/atlas.en-us[.<doc_release>].<guide>.meta`. The response has a `toc` tree with `a_attr.href` and a `version` object containing `doc_version` and `version_text`
- Page content (JSON with `content` HTML and `title`): `/docs/get_document_content/<guide>/<page>/en-us/<doc_release>`
- Sitemap fallback: `https://developer.salesforce.com/docs-atlas-sitemap.xml`
- Winter '27 (`264.0`) is published for `apexcode` (548 pages) and `api_meta` (707). It is **not** published for `api_rest`, `api` and `api_asynch`; their atlas TOC returns 0 pages, and the crawler falls back to Summer '26 (309 / 207 / 127 pages). Those three guides have moved to the new site.

**Newer docs site** (`/docs/<section>/<guide>/guide/...`, sections seen: `platform`, `sales`, `service`)
- Sitemap: `https://developer.salesforce.com/docs/ssg-sitemap.xml`. It is a tree of child sitemaps and takes about 4 minutes to walk. The crawler now caches the URL list in `data/sitemaps/` for 24 hours.
- **Serves raw Markdown**: replace `.html` with `.md` in any page URL (verified on `platform/api-rest/guide/intro-what-is-rest-api.md`: HTTP 200, clean Markdown, relative links to other `.md` pages). The crawler fetches `.md` first and falls back to HTML
- Not versioned; only serves the current release
- LWC's classic atlas TOC is a leftover 1-page Winter '23 stub. The crawler skips atlas for guides listed in `DOCS_GUIDES`

**Version math** (`versions.py`): `doc_release = 2 * api_version + 128`. API 60 = Spring '24, then +1 per release (Spring, Summer, Winter). So 68.0 = Winter '27 = 264.0.

**User agent:** developer.salesforce.com returns 403 to anonymous agents. Keep the descriptive UA in `config.yaml`.

### Releases

The pin is `release: "Winter '27"` with `strict_release: false`. Each page's front matter records its own `api_version`, `doc_release` and `release`. Open risk: Winter '27 atlas URLs contain `264.0` but the fallback URLs don't, so when Winter '27 is published for a guide, discovery may add new manifest rows next to the old Summer '26 ones, both mapping to the same `data/text/<guide>/<page>.md`. Untested. Plan to re-discover (or re-crawl those guides) after the release goes live.

## Code map

```
src/sfcognitio_mcp/
  cli.py        sfcognitio doctor|discover|fetch|extract|crawl|status  (--guide, --limit, --release)
  config.py     dataclasses loaded from config.yaml; extra_pages, all_guides, sitemap_cache_hours
  versions.py   release <-> API <-> doc release; parse_release_spec()
  manifest.py   SQLite manifest (data/manifest.sqlite3): status per URL, ETag, versions, paths
  http.py       PoliteClient: per-host delay, concurrency, retries, BlockedError
  discover.py   atlas TOC -> atlas sitemap fallback; SSG sitemap filtered by guide path segment
                ATLAS_GUIDES (never use SSG sitemap), DOCS_GUIDES (skip atlas), MIN_TOC_PAGES (stub check)
                extra_page_refs() for the "articles" bucket; fetch_sitemap_urls() with on-disk cache
                and skip-on-failure for child sitemaps (a failed root sitemap still raises)
  fetch.py      atlas content JSON API -> HTML fallback; docs .md source -> HTML fallback; conditional GETs
  extract.py    HTML -> Markdown (code fences with language), or tidy the .md source; YAML front matter
tests/          test_units.py, test_pipeline.py (mocked with httpx.MockTransport; no network needed)
packages/       one-off placeholder packages (v0.0.1) for claiming PyPI/npm names
```

Output: `data/text/<guide>/<page>.md`, with front matter containing `title, url, source, guide, page, api_version, doc_release, release, fetched_at`. `data/` is gitignored.

## Commands (WSL)

```bash
cd ~/dev/sfcognitio-mcp
source .venv/bin/activate          # first time: python3 -m venv .venv && pip install -e ".[dev]"
pytest                             # 41 tests
sfcognitio doctor                  # endpoint check, shows the pinned release per guide
sfcognitio discover --guide articles   # no network: loads extra_pages into the manifest
sfcognitio crawl --guide articles  # fetch just the extra pages
sfcognitio crawl --limit 50        # trial
sfcognitio status
sfcognitio crawl                   # full run (resumable; re-run to continue)
```

`doctor` reports `lwc` and `platform-events` as ERR ("0 pages in docs sitemap"); that is a limitation of the check, since `discover` follows the child sitemaps and found 692 and 242 pages.

## Gotchas learned

- **Underscores:** markdownify escapes `_` by default, which mangles `Invoice__c`. It's disabled (`escape_underscores=False`), and a test covers it.
- **Short guide ids:** `api` matches lots of `/api/` segments on the SSG sitemap. Atlas guides are kept off it via `ATLAS_GUIDES`. This will need rethinking now that `api` is also a new-site guide.
- **Throttling:** after about an hour of repeated full sitemap walks (3 passes) plus a few other requests, developer.salesforce.com refused TLS connections for a while (`unexpected eof`). It recovered. Avoid re-walking the sitemap; prefer the `llms.txt` lists and the sitemap cache.
- **Git identity** (Juan): `doppiomacchiatto <3484322+doppiomacchiatto@users.noreply.github.com>`.
- **Claude can't push to GitHub** unless GitHub is linked in claude.ai (Settings → Connectors). Until then, Juan commits and pushes.
- In WSL, the Windows drive is at `/mnt/c/Users/juan/...`.
- Don't name a helper script `inspect.py` (or any stdlib module name) next to other scripts: it shadows the standard library.
