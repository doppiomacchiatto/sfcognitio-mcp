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

### How it works

- **Discover:** classic guides (Apex, REST API, ...) come from each guide's table of contents, falling back to the atlas sitemap. Newer docs (LWC, ...) come from the SSG sitemap. URLs go into a SQLite manifest (`data/manifest.sqlite3`).
- **Fetch:** polite by default (2 concurrent requests, 2.5s per-host delay, retries with backoff, stops on repeated 403/429). Re-runs resume and use conditional GETs.
- **Extract:** newer docs pages are fetched as the site's own Markdown source; other pages go HTML to Markdown with headings and code blocks preserved; Salesforce API names like `Invoice__c` are kept intact.

Choose guides in `config.yaml` or per run with `--guide apexcode --guide lwc`.

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
