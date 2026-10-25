# SfCognitio

**Salesforce documentation knowledge server (MCP) that lets any agent become a Salesforce expert.**

> Status: early development. Not affiliated with or endorsed by Salesforce, Inc.

## Goals

- **Any agent:** remote MCP server over HTTP, plus a REST/OpenAPI endpoint for agents that don't speak MCP.
- **Model-agnostic:** returns ranked passages with source links; each agent reasons with its own model.
- **Version-aware:** every chunk tagged with API version and release.
- **Structured facts:** governor limits, object/field reference, Apex and LWC signatures as lookup tools.
- **Bring your own index:** no Salesforce content ships in this repo. Users build their own index with the included crawler, subject to Salesforce's terms of use.

## License

Apache 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
