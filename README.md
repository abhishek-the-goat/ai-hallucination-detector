# AI Hallucination Detector

Verifies AI-generated answers against trusted sources and flags hallucinated (made-up) facts.

## How it works
1. **Claim extraction** — an AI answer is broken into single, checkable facts.
2. **Evidence retrieval** — for each claim, the top matching passages are fetched from a trusted corpus (Wikipedia / fact dataset) using BM25 + embedding search.
3. **Verification** — each claim is scored as Supported, Contradicted, or Unverified using semantic similarity + entailment (NLI).
4. **Dashboard** — results shown with hallucinated lines highlighted, confidence scores, and the source evidence for/against each claim.

## Modules
| Folder | Owner | Responsibility |
|---|---|---|
| `verification/` | Abhishek | Verification engine (core) + pipeline integration |
| `retrieval/` | Ishan | Trusted corpus, inverted index, BM25 + embedding search |
| `claim_extractor/` | Pratham | Claim extraction + AI model input handling |
| `dashboard/` | Divyansh | Web dashboard UI |

## Workflow rules
- `main` is protected. Nobody pushes to `main` directly.
- Work on a feature branch, open a Pull Request.
- The CI check must pass before a PR can be merged — if your code breaks the build, it does not merge.
