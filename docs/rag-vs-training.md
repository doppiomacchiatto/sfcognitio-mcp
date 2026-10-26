# Retrieval, not training

Once SfCognitio has crawled the Salesforce docs and articles, we do **not** download and train a chat model. The plan is retrieval (RAG). We run an embedding model, but we don't train anything.

## How it works

1. **Crawl (milestone 1):** the docs become Markdown files with YAML front matter (title, URL, guide, release).
2. **Index (milestone 2):** each page is split into chunks along its headings, and code is never split. For each chunk we store the text, an embedding vector and a keyword (BM25) entry. Search combines the two with reciprocal rank fusion. The embedding model is pre-trained and either runs locally (Ollama) or is called (Bedrock Titan). We use it as is.
3. **MCP server (milestone 3):** the agent's own LLM (Claude, Agentforce, Cursor, ...) calls tools such as `search_docs` and `get_page`. It gets the relevant chunks back with their source URLs and release, and answers from those.

We never host or train a chat model. Every agent brings its own.

## Why retrieval fits better than training

- **Release changes:** Salesforce ships three releases a year, and the crawler pins one release or falls back per guide. With an index, a re-crawl updates the knowledge. A trained model is out of date as soon as a release lands and needs retraining.
- **Citations:** retrieval returns the exact page and release, so answers can be checked. A fine-tuned model can't show where a fact came from, and it tends to state wrong API details with confidence.
- **Precision:** governor limits, field names and method signatures need exact text. Retrieval supplies it, and fine-tuning blurs it.
- **Cost:** training or fine-tuning needs GPUs and ongoing effort. Retrieval costs far less.
- **Content terms:** `HANDOFF.md` already notes that Salesforce's terms may restrict redistributing their docs. Training a model on them is a separate question that has not been looked into. Check the terms before anyone considers it.

## Where training could help later

- **Embedding model or reranker:** fine-tuning one on Salesforce question-and-answer pairs could improve search quality. This is optional and comes after the basic index works.
- **Small tuned model:** a model that only picks tools or rewrites queries might help, but it isn't needed to start.

## Decision

Build the index first and measure how good the search is. If it falls short, try a reranker or tuned embeddings before anything else.
