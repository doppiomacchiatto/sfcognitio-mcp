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
| Release | Pinned to **Winter '27** (API 68.0, doc release 264.0) | Guides don't move to new releases in lockstep; pinning keeps them consistent |
| Fetch politeness | 2 concurrent, 2.5s per-host delay, stop after 5 consecutive 403/429 | Be a good citizen; resume later |

## Roadmap

| # | Milestone | Status |
|---|---|---|
| 1 | Crawler: discover, fetch, extract to versioned Markdown | **Built, 37 tests passing; live trial pending** |
| 2 | Index: heading-aware chunks (never split code), vector + keyword (BM25) hybrid search with RRF; swappable embeddings (local Ollama or Bedrock Titan) | Next |
| 3 | MCP server: `search_docs`, `get_page`, `get_governor_limits`; stdio + HTTP | Planned |
| 4 | Hosted on AWS (Lambda or container + API Gateway; S3 Vectors or OpenSearch Serverless), plus a REST/OpenAPI endpoint | Planned |
| 5 | Expert layer: structured lookups (limits, object/field reference, Apex/LWC signatures); pair with Juan's `salesforce-bedrock-mcp` server for live-org metadata | Later |

## Guides crawled (config.yaml)

| Guide id | Guide | Source |
|---|---|---|
| `apexcode` | Apex Developer Guide | classic atlas |
| `api_rest` | REST API Developer Guide | classic atlas |
| `api_meta` | Metadata API Developer Guide | classic atlas |
| `api` | SOAP API Developer Guide | classic atlas |
| `api_asynch` | Bulk API 2.0 and Bulk API Developer Guide | classic atlas |
| `lwc` | Lightning Web Components Developer Guide | newer docs site |
| `platform-events` | Platform Events Developer Guide | newer docs site |

**Open question:** add `object_reference` (Object Reference: every standard object and field)? It's large but valuable for field-level questions.

## How Salesforce docs work (verified live on 2026-10-25)

From `sfcognitio doctor` run in WSL. All endpoints returned HTTP 200.

**Classic atlas guides**
- Page URL: `https://developer.salesforce.com/docs/atlas.<locale>[.<doc_release>].<guide>.meta/<guide>/<page>.htm`
- Table of contents (JSON): `/docs/get_document/atlas.en-us[.<doc_release>].<guide>.meta`. The response has a `toc` tree with `a_attr.href` and a `version` object containing `doc_version` and `version_text`
- Page content (JSON with `content` HTML and `title`): `/docs/get_document_content/<guide>/<page>/en-us/<doc_release>`
- Sitemap fallback: `https://developer.salesforce.com/docs-atlas-sitemap.xml`
- Page counts at "latest": apexcode 548, api_rest 309, api_meta 707, api 207, api_asynch 127
- "Latest" versions differed: apexcode and api_meta were Winter '27; api_rest, api and api_asynch were Summer '26. That's why the release is pinned now. **Still unverified:** whether those three exist at Winter '27. If not, the crawler warns and uses their latest (`strict_release: false`)

**Newer docs site** (`/docs/platform/<guide>/guide/...`)
- Sitemap: `https://developer.salesforce.com/docs/ssg-sitemap.xml`
- **Serves raw Markdown**: replace `.html` with `.md` in any page URL. The crawler fetches `.md` first and falls back to HTML
- Not versioned; only serves the current release
- LWC's classic atlas TOC is a leftover 1-page Winter '23 stub. The crawler skips atlas for guides listed in `DOCS_GUIDES`

**Version math** (`versions.py`): `doc_release = 2 * api_version + 128`. API 60 = Spring '24, then +1 per release (Spring, Summer, Winter). So 68.0 = Winter '27 = 264.0.

**User agent:** developer.salesforce.com returns 403 to anonymous agents. Keep the descriptive UA in `config.yaml`.

## Code map

```
src/sfcognitio_mcp/
  cli.py        sfcognitio doctor|discover|fetch|extract|crawl|status  (--guide, --limit, --release)
  config.py     dataclasses loaded from config.yaml
  versions.py   release <-> API <-> doc release; parse_release_spec()
  manifest.py   SQLite manifest (data/manifest.sqlite3): status per URL, ETag, versions, paths
  http.py       PoliteClient: per-host delay, concurrency, retries, BlockedError
  discover.py   atlas TOC -> atlas sitemap fallback; SSG sitemap filtered by guide path segment
                ATLAS_GUIDES (never use SSG sitemap), DOCS_GUIDES (skip atlas), MIN_TOC_PAGES (stub check)
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
pytest                             # 37 tests
sfcognitio doctor                  # endpoint check, shows the pinned release per guide
sfcognitio crawl --limit 50        # trial
sfcognitio crawl --guide platform-events --limit 20
sfcognitio status
sfcognitio crawl                   # full run (resumable; re-run to continue)
```

## Gotchas learned

- **Underscores:** markdownify escapes `_` by default, which mangles `Invoice__c`. It's disabled (`escape_underscores=False`), and a test covers it.
- **Short guide ids:** `api` matches lots of `/api/` segments on the SSG sitemap. Atlas guides are kept off it via `ATLAS_GUIDES`.
- **Git identity** (Juan): `doppiomacchiatto <3484322+doppiomacchiatto@users.noreply.github.com>`.
- **Claude can't push to GitHub** unless GitHub is linked in claude.ai (Settings → Connectors). Until then, Juan commits and pushes.
- In WSL, the Windows drive is at `/mnt/c/Users/juan/...`.

## Immediate next steps

1. Unpack `sfcognitio-update.tgz` into the WSL repo, run `pytest`, then commit and push.
2. Run `sfcognitio doctor`. Check whether api_rest, api and api_asynch exist at Winter '27.
3. Run the trial `sfcognitio crawl --limit 50`. Inspect a few files in `data/text/` (code blocks, tables, front matter).
4. Run the full crawl of the 7 guides (roughly 2,000+ pages; at 2.5s/page with 2 workers, about 45-60 min).
5. Publish the placeholder packages (`packages/pypi-placeholder`: `python -m build && twine upload dist/*`; `packages/npm-placeholder`: `npm publish`).
6. Fill in the GitHub About description and topics (`salesforce`, `mcp`, `rag`, `ai-agents`, `model-context-protocol`).
7. Decide on `object_reference`, then start **milestone 2** (index).
