# SfCognitio

**Salesforce documentation knowledge server (MCP) that lets any agent become a Salesforce expert.**

> Status: early development (milestone 1: crawler). Not affiliated with or endorsed by Salesforce, Inc.

## Goals

- **Any agent:** remote MCP server over HTTP, plus a REST/OpenAPI endpoint for agents that don't speak MCP.
- **Model-agnostic:** returns ranked passages with source links; each agent reasons with its own model.
- **Version-aware:** every chunk tagged with API version and release.
- **Structured facts:** governor limits, object/field reference, Apex and LWC signatures as lookup tools.
- **Bring your own index:** no Salesforce content ships in this repo. Users build their own index with the included crawler, subject to Salesforce's terms of use.

## Roadmap

| Milestone | What | Status |
|---|---|---|
| 1 | Crawler: discover, fetch, extract to versioned Markdown | In progress |
| 2 | Index: heading-aware chunks, vector + keyword search | Planned |
| 3 | MCP server: `search_docs`, `get_page`, `get_governor_limits` (stdio + HTTP) | Planned |
| 4 | Hosted on AWS for any agent (Agentforce, Bedrock Agents, Claude) | Planned |

## Quick start (crawler)

Requires Python 3.10+.

```bash
git clone https://github.com/doppiomacchiatto/sfcognitio-mcp.git
cd sfcognitio-mcp
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux/WSL: source .venv/bin/activate
pip install -e ".[dev]"

sfcognitio doctor                 # check Salesforce endpoints are reachable
sfcognitio crawl --limit 50       # trial run: discover, fetch 50 pages, extract
sfcognitio status                 # progress by guide
sfcognitio crawl                  # full run for the guides in config.yaml (resumable)
```

Markdown lands in `data/text/<guide>/`, each file with front matter:

```yaml
---
title: Trigger Syntax
url: https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_triggers_defining.htm
source: atlas
guide: apexcode
api_version: '68.0'
doc_release: '264.0'
release: Winter '27
---
```

## Commands

All commands read `config.yaml` (override with `-c path/to/config.yaml`). Add `-v` for debug logging.

| Command | What it does | Options |
|---|---|---|
| `sfcognitio doctor` | Checks that the Salesforce endpoints are reachable and shows the pinned release per guide. | `-g`, `-r` |
| `sfcognitio discover` | Finds doc URLs and adds them to the manifest. Removes stale never-fetched rows. | `-g`, `-r` |
| `sfcognitio fetch` | Downloads pending pages into `data/raw/`. | `-g`, `-n` |
| `sfcognitio extract` | Converts downloaded pages to Markdown in `data/text/`. | `-g` |
| `sfcognitio crawl` | `discover` + `fetch` + `extract`, then prints `status`. | `-g`, `-n`, `-r` |
| `sfcognitio status` | Shows manifest progress by guide and status, plus recent errors. | `-g` |

| Option | Meaning |
|---|---|
| `-g`, `--guide ID` | Limit to a guide. Repeatable: `--guide apexcode --guide lwc`. Defaults to every guide in `config.yaml`. |
| `-n`, `--limit N` | Fetch at most N pages this run (0 = no limit). |
| `-r`, `--release SPEC` | Override the pinned release: `latest`, `"Winter '27"`, `68.0` or `264.0`. |

Exit codes: `0` success, `1` error (bad config, nothing discovered, endpoint check failed), `2` fetch was blocked by repeated 403/429. Re-run the same command to resume.

Common runs:

```bash
sfcognitio discover --guide hosted-mcp-servers   # add one guide to the manifest
sfcognitio crawl --guide articles                # only the hand-picked extra_pages
sfcognitio fetch --limit 200                     # fetch the next 200 pending pages
sfcognitio extract                               # re-extract everything fetched
```

## Architecture

```
config.yaml ──► discover ──► manifest.sqlite3 ──► fetch ──► data/raw/ ──► extract ──► data/text/<guide>/<page>.md
 (allow-list,      │          (one row per URL:      │                                  (Markdown + front matter)
  sources)         │           status, ETag, hashes) └─ conditional GETs, polite client
                   ├─ llms-<product>.txt lists  (newer docs site: page URLs, .md)
                   ├─ atlas table of contents   (classic guides)
                   └─ sitemaps                  (fallback only)
```

**Stages**

- **Discover.** `guides` in `config.yaml` is the allow-list. The `llms-<product>.txt` files listed under `sources.llms.files` say which source each guide lives in:
  - *Newer docs site* (LWC, REST API, Hosted MCP Servers, ...): page URLs come straight from the llms list, as `.md` URLs. No sitemap walk.
  - *Classic atlas* (Apex, Metadata API, Object Reference, ...): pages come from each guide's table of contents, pinned to a release, falling back to the guide's latest, then to the llms list.
  - Guides not found in any llms file fall back to the atlas sitemap, then the SSG sitemap.
  - `extra_pages` adds hand-picked URLs under the `articles` guide, unless a full guide already covers them.
- **Manifest.** `data/manifest.sqlite3` holds one row per URL with its guide, versions, ETag, content hash and status (`pending`, `fetched`, `not_modified`, `error`, `extracted`). This is what makes runs resumable.
- **Fetch.** Polite by default: 2 concurrent requests, 2.5s per-host delay, retries with backoff, and a stop after repeated 403/429. It sends a descriptive user agent (the site rejects anonymous ones). Re-runs use conditional GETs.
- **Extract.** Newer-site pages are fetched as the site's own Markdown source and tidied. Other pages go from HTML to Markdown with headings and code fences preserved. Salesforce API names like `Invoice__c` are kept intact. Each file gets YAML front matter (see above).

**Modules** (`src/sfcognitio_mcp/`)

| Module | Role |
|---|---|
| `cli.py` | The `sfcognitio` commands. |
| `config.py` | Loads `config.yaml` into dataclasses. |
| `discover.py` | Atlas TOC, llms lists and sitemap discovery. |
| `manifest.py` | SQLite manifest and crawl state. |
| `fetch.py` | Downloads pages; atlas JSON API or docs `.md`, with HTML fallback. |
| `extract.py` | HTML or `.md` to Markdown with front matter. |
| `http.py` | `PoliteClient`: rate limiting, concurrency, retries. |
| `versions.py` | Release name, API version and doc release conversion. |

**Data layout** (`data/` is gitignored; nothing from Salesforce is committed)

| Path | Contents |
|---|---|
| `data/llms/` | Cached `llms-*.txt` lists (reused for `sitemap_cache_hours`). |
| `data/sitemaps/` | Cached sitemap URL lists. |
| `data/manifest.sqlite3` | The manifest. |
| `data/raw/` | Downloaded pages. |
| `data/text/<guide>/` | Extracted Markdown. |

### Configuration

`config.yaml` has four parts:

- `crawler`: user agent, concurrency, delay, retries, cache hours.
- `guides`: the allow-list of guide ids (the guide segment in the docs URL).
- `extra_pages`: extra URLs to crawl into the `articles` bucket.
- `sources`: `llms` (which product lists to read), `atlas` (release pin, sitemap) and `docs` (SSG sitemap, include and exclude filters).

To add a guide, add its id to `guides`. If it comes from a product list not yet in `sources.llms.files`, add that list name too (the file is `https://developer.salesforce.com/docs/llms-<name>.txt`), then run `sfcognitio discover --guide <id>`.

### Pinning a release

Guides don't all move to a new release at the same time, so `latest` can mix versions. Pin one release in `config.yaml`:

```yaml
sources:
  atlas:
    release: "Winter '27"   # or API version "68.0", or doc release "264.0"
    strict_release: false   # guide not published for that release: false = use its latest, true = skip
```

Or per run: `sfcognitio crawl --release "Winter '27"`. Pinning applies to classic guides; the newer docs site (LWC) only serves its current version.

## Development

```bash
pytest
```

## License

Apache 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
