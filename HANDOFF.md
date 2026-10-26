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

## Terms and licensing (checked 2026-10-25; not legal advice)

Goal: help developers and stay within Salesforce's terms.

**What the site says:**
- `https://developer.salesforce.com/robots.txt` does not disallow our paths. Its rules cover query strings (`?q=`, `&page=`, ...), `/search*`, `/c/*` and a few settings files. It lists the atlas and SSG sitemaps and has a section "LLM and AI agent friendly content" pointing to `https://developer.salesforce.com/llms.txt` and `https://developer.salesforce.com/docs/llms.txt`. The `llms-*.txt` files describe their pages as "LLM-friendly markdown documentation pages". Salesforce's own docs pages have an "open in Claude" button (see below).
- The Salesforce Website Terms of Service (`https://www.salesforce.com/company/legal/sfdc-website-terms-of-service/`, last updated 2025-04-08), section G: "Using our Site does not give you ownership of any intellectual property rights to the content you access. You may not use content from our Sites unless you obtain permission from us or its owner, or unless you are otherwise permitted by law." Section H points to the Trademark and Copyright Usage Guidelines (`https://www.salesforce.com/company/legal/tmcusageguidelines/`).
- **Not verified:** whether developer.salesforce.com is covered by those Terms or has its own documentation terms. I did not find a developer-docs license.

**Reading of this (an interpretation):** the signals that the docs are meant for LLM use (`robots.txt`, `llms.txt`, the Claude button) are encouraging, but none is an explicit license. The Terms say content needs permission. So:
- A personal, local index built by each user from the public pages is the lowest-risk use, and it matches the project's "bring your own index" decision.
- **Redistributing Salesforce content is not safe without permission.** That includes committing crawled content to the repo, publishing a prebuilt index, and the hosted service in milestone 4.
- Training or fine-tuning a model on the content is a separate question (see `docs/rag-vs-training.md`); we are not doing it.

**Practices to keep:** honor `robots.txt`; keep the descriptive user agent; keep the 2.5s per-host delay; always keep the source URL and release in each page's front matter; link back to the original page in answers; never strip attribution; keep `data/` out of git.

## TODO

- [ ] **Terms review before anything is hosted or shared:** find the developer-docs terms (check the developer.salesforce.com footer and the Trademark and Copyright guidelines page), and decide whether to ask Salesforce for written permission before milestone 4 (hosted service) or before sharing any prebuilt index. Until then, treat the hosted service as blocked.
- [ ] **Evaluate an "open in Claude" style link (milestone 3 idea).** Salesforce's docs open `claude.ai/new` with this prompt: "I'm reading "Get Started with Pub/Sub API" at https://developer.salesforce.com/docs/platform/pub-sub-api/guide/intro.html. Read this page so I can ask questions about it. For broader context, see https://developer.salesforce.com/docs/llms.txt". It passes the HTML page URL (not the `.md`) and points at `llms.txt` as the index. A SfCognitio equivalent could be "I'm reading <title> at <url>. Use the SfCognitio MCP server (`get_page`, `search_docs`) for this page and related ones", returned next to a page by `get_page`. Evaluate what helps developers most and stays within the terms: link to the original Salesforce page, return only the chunks needed, include the release and source URL, no bulk redistribution.
- [ ] **Create a Platform subset (on hold until 2026-10-26).** Decide which of the 26 guides in `llms-platform.txt` to keep. Exclude the legacy ones: candidates are `ajax`, `caf-dev`, `salesforce-developer-environment-dotnet-tipsheet`, `salesforce-pages-developers-guide` (494 pages, Visualforce) and `mobile-offline`. These are my suggestions, not decisions.
- [ ] Juan to analyze Service Cloud and `spiff` (both on hold until 2026-10-26).
- [ ] **Test tomorrow (2026-10-26): the two sources not built yet.** Juan still wants all four: dev-atlas and dev-docs (built), plus pdf-guides and help. Nothing is verified about the last two, so probe them before designing.
  - **PDF guides.** Legacy docs may exist only as PDF, with no Markdown and no `llms.txt` entry, so there is no index to discover them from. Proposed design (not decided): an explicit `pdf_guides` list in config (guide id, PDF URL, release label); a PDF is crawled only when its guide has no docs-`.md` or atlas-HTML copy (precedence: docs `.md` > atlas HTML > PDF, decided per guide, so no page-level dedupe); a PDF-to-Markdown extractor (new dependency, e.g. PyMuPDF or pdfplumber; check code blocks and tables on one PDF first); front matter `source: pdf`, release label and `legacy: true`; page numbers for citations where available. Open: which legacy guides are PDF-only, and whether all are in scope.
  - **Help (`help.salesforce.com`).** Probably JavaScript-rendered (unverified). Likely where Sales Cloud and Service Cloud admin content lives, so it ties into the held Service Cloud decision. Proposed: keep it as its own `doc_type` (admin / how-to) and do not deconflict it against developer docs. Open: which products, and an example article URL.
  - Safety net for the index (milestone 2): catch leftover duplicates by chunk content hash, keeping the highest-precedence copy.
- [ ] Trial fetch of the built sources: `sfcognitio crawl --guide articles` (1 page), then `crawl --limit 50`. A full crawl is about 11,700 pages, roughly 4 to 5 hours at 2.5s per page with 2 workers, so run it in WSL in the background and let it resume.
- [ ] Review the 7 unlisted product-docs guides and `bi_dev_guide_rest_sdd`.
- [x] Switch discovery to the `llms.txt` lists, with `guides` in `config.yaml` as the allow-list (done 2026-10-25, see "Discovery" below). The manifest now holds 11,681 pending pages for the 21 decided guides plus `articles`; nothing is fetched yet.
- [ ] When the held guides are decided, add them to `guides` and add `service-cloud` / `sales-cloud` to `sources.llms.files`.
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
| 1 | Crawler: discover, fetch, extract to versioned Markdown | **Built, 47 tests passing; discovery done (11,681 pages pending); live fetch trial pending** |
| 2 | Index: heading-aware chunks (never split code), vector + keyword (BM25) hybrid search with RRF; swappable embeddings (local Ollama or Bedrock Titan) | Next |
| 3 | MCP server: `search_docs`, `get_page`, `get_governor_limits`; stdio + HTTP | Planned |
| 4 | Hosted on AWS (Lambda or container + API Gateway; S3 Vectors or OpenSearch Serverless), plus a REST/OpenAPI endpoint | Planned |
| 5 | Expert layer: structured lookups (limits, object/field reference, Apex/LWC signatures); pair with Juan's `salesforce-bedrock-mcp` server for live-org metadata | Later |

## Discovery

`guides` in `config.yaml` is the allow-list: the 21 decided guides.
- **Classic atlas (7):** `apexcode`, `apexref`, `api_meta`, `object_reference`, `api_tooling`, `uiapi`, `bi_dev_guide_rest`.
- **Newer docs site (14):** `api-rest`, `api`, `api-asynch`, `platform-events`, `field-reference`, `connect-rest-api`, `graphql`, `pub-sub-api`, `lwc`, `lightning-components-security`, `utam`, `slds-linter`, `slds-validator`, `lightning-component-reference`.
- The old ids `api_rest` and `api_asynch` (atlas, Summer '26) were replaced by `api-rest` and `api-asynch`; their stale manifest rows were deleted.

How `discover` works now (`sources.llms.files` in `config.yaml` lists the eight `llms-*.txt` files used):
1. Each file is fetched once and cached in `data/llms/` for `sitemap_cache_hours` (24).
2. The llms index says which source each allow-listed guide lives in.
3. **Newer-site guides:** page URLs (`.md`) come straight from the llms list. No sitemap walk.
4. **Atlas guides:** still discovered from the table of contents, pinned to Winter '27, falling back to the guide's latest. The llms list is the fallback if the TOC is unavailable.
5. Guides not found in any llms file fall back to the old atlas/sitemap logic.
6. After discovery, never-fetched (`pending`) rows of re-discovered guides whose URL is no longer listed are deleted. Fetched rows are never deleted.
7. `extra_pages` adds hand-picked URLs under guide `articles` (`data/text/articles/`), unless a full guide already covers the URL. Currently only the Streaming API intro remains in `articles`; the Connect REST and GraphQL intros belong to their full guides.

Page counts (manifest, 2026-10-25): atlas TOCs give `apexref` 2,329, `object_reference` 1,895 and `apexcode` 548, slightly different from the llms lists (2,331 / 1,890 / 549). The TOC wins.

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
  config.py     dataclasses loaded from config.yaml; extra_pages, all_guides, sitemap_cache_hours, LlmsSource
  versions.py   release <-> API <-> doc release; parse_release_spec()
  manifest.py   SQLite manifest (data/manifest.sqlite3): status per URL, ETag, versions, paths;
                prune_pending() drops stale never-fetched rows
  http.py       PoliteClient: per-host delay, concurrency, retries, BlockedError
  discover.py   atlas TOC -> atlas sitemap fallback; SSG sitemap filtered by guide path segment
                ATLAS_GUIDES (never use SSG sitemap), DOCS_GUIDES (skip atlas), MIN_TOC_PAGES (stub check)
                llms lists: fetch_llms_text(), index_llms_urls(), load_llms_index() (guide -> source + URLs)
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
pytest                             # 47 tests
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
- **Short guide ids:** `api` matches lots of `/api/` segments on the SSG sitemap. With the llms index the guide id is read from the URL's own guide segment, so `api` (SOAP API, now on the new site) resolves correctly. The sitemap path is only a fallback for guides not found in any llms file. `api` is still in the code's `ATLAS_GUIDES` set, which only matters on that fallback path; clean it up if the fallback is ever needed for `api`.
- **llms URL shapes:** new-site pages are `/docs/<section>/<guide>/<guide|references>/.../<page>.md`, sometimes more than one level deep (e.g. `field-reference`, `utam`). Page names (last segment) had no duplicates within a guide in the 2026-10-25 data.
- **Manifest keys on URL:** if an `extra_pages` URL is also listed in a full guide, the row follows the guide. Discovery drops the extra page in that case.
- **Throttling:** after about an hour of repeated full sitemap walks (3 passes) plus a few other requests, developer.salesforce.com refused TLS connections for a while (`unexpected eof`). It recovered. Avoid re-walking the sitemap; prefer the `llms.txt` lists and the sitemap cache.
- **Git identity** (Juan): `doppiomacchiatto <3484322+doppiomacchiatto@users.noreply.github.com>`.
- **Claude can't push to GitHub** unless GitHub is linked in claude.ai (Settings → Connectors). Until then, Juan commits and pushes.
- In WSL, the Windows drive is at `/mnt/c/Users/juan/...`.
- Don't name a helper script `inspect.py` (or any stdlib module name) next to other scripts: it shadows the standard library.
