# Phase 9 — Hybrid retrieval and reranking

## Objective

Implement an explicit retrieval pipeline that combines semantic and lexical candidates, applies filters, reranks results, and returns traceable evidence.

## What we will learn

- Candidate generation versus final ranking.
- Dense search strengths and weaknesses.
- BM25 strengths and weaknesses.
- Reciprocal Rank Fusion.
- Cross-encoder reranking.
- Filter timing.
- Context diversity and duplicate control.

## Development steps

1. Define typed retrieval input and output models.
2. Implement query normalization without changing user intent.
3. Add metadata filters:
   - Language.
   - Date range.
   - Subject.
   - Work.
   - Licence.
4. Retrieve dense candidates.
5. Retrieve sparse candidates.
6. Fuse rankings using Reciprocal Rank Fusion.
7. Keep retrieval-stage scores and ranks for diagnostics.
8. Add a multilingual reranker to the fused top candidates.
9. Select a small final evidence set.
10. Merge or suppress near-duplicate adjacent chunks when appropriate.
11. Limit repeated evidence from one work unless the query needs it.
12. Add a search CLI with a `--debug` option.
13. Add `POST /v1/search` independently from answer generation.

## UI work

Create the retrieval workbench:

- Search query and filters.
- Dense candidates and scores.
- Sparse candidates and scores.
- Fused rank.
- Reranker score.
- Selected evidence.
- Chunk text and page image.
- Model and index versions.
- Stage latency.

## Tests

- Exact title query benefits from sparse retrieval.
- Paraphrased query benefits from dense retrieval.
- Filters are enforced.
- RRF ordering is deterministic for fixed inputs.
- Reranker receives only bounded candidates.
- Debug trace matches returned results.

## Exit criteria

- Search works without any LLM answer generation.
- Dense-only, sparse-only, hybrid, and reranked results can be compared.
- Every result has visible provenance.
- Retrieval latency is recorded per stage.

## Required ADR

`ADR-0009: Hybrid candidate generation, RRF, and multilingual reranking`

Decision questions:

- Why hybrid rather than dense-only retrieval?
- Why RRF?
- Why rerank only a candidate subset?
- How many candidates are retrieved and returned?

---
