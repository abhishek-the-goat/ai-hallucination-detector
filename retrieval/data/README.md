# Multi-Source Evidence Corpus & Retrieval

This directory contains the static reference corpus and documentation for the multi-source evidence retrieval system.

## Supported Sources

The verification pipeline consults three independent, complementary knowledge sources:

1. **Wikipedia** (`wikipedia`)
   - **Static Corpus**: 390 curated passages in `corpus.json` representing factual encyclopedic knowledge, indexed by BM25Okapi and FAISS vector embeddings (`all-MiniLM-L6-v2`).
   - **Live Retrieval**: Real-time article lookup using the MediaWiki action API (`action=query&list=search`) and extract generation (`prop=extracts&explaintext=1`), cached under `retrieval/data/wiki_cache/`.

2. **Wikidata** (`wikidata`)
   - **Structured Knowledge**: Structured factual claims including capitals, dates of birth/death, populations, country boundaries, and occupations.
   - **API**: Uses the Wikidata API `wbsearchentities` to identify entity QIDs and `Special:EntityData/{qid}.json` to parse snak statements into factual evidence sentences (e.g., `"Paris - capital of France (Wikidata)"`).

3. **arXiv** (`arxiv`)
   - **Scientific Research**: Scholarly preprints and research claims across computer science, physics, mathematics, and biology.
   - **API**: Queries the open arXiv API (`export.arxiv.org/api/query`, Atom XML feed) and constructs evidence using paper titles and the lead sentence of abstracts.

## Key-Free and Open Access

All sources used in this project are strictly free and open:
- **No API keys** required.
- **No paid accounts** or authentication tokens needed.
- Operates over standard HTTP with a descriptive User-Agent header.

## Per-Source Fault Tolerance & Failure Behaviour

Network stability varies across external APIs. To guarantee reliable verification:
- Every external fetcher operates with a strict **5-second timeout** and a shared `requests.Session`.
- On **ANY error** (connection timeout, HTTP error code, rate limit, XML/JSON parsing failure, or zero matches), the source handler catches the exception, prints a warning message, and safely returns an empty list `[]`.
- A dead, slow, or throttled source will **never crash the pipeline**. The retrieval engine merges all responding sources and continues verification uninterrupted.

## Corpus Attribution

The text in `corpus.json` contains passages extracted from Wikipedia articles using the MediaWiki API.

Each record in `corpus.json` includes its source title and source URL.

Reused Wikipedia text is available under the Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0), subject to the terms applicable to the individual source material.

- License: https://creativecommons.org/licenses/by-sa/4.0/
- Wikipedia terms: https://foundation.wikimedia.org/wiki/Terms_of_Use
