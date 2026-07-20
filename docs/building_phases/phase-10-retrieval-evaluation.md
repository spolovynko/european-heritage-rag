# Phase 10 — Retrieval evaluation

## Objective

Create a repeatable evaluation system that measures whether chunking, retrieval, filtering, and reranking changes actually improve results.

## What we will learn

- Ground-truth relevance judgements.
- Recall@K, MRR, and nDCG.
- Query-set design.
- Hard negatives.
- Regression testing.
- Why answer evaluation cannot replace retrieval evaluation.

## Development steps

1. Design an evaluation-case schema:
   - Case ID.
   - Question.
   - Language.
   - Query type.
   - Required filters.
   - Relevant work IDs.
   - Relevant chunk or page IDs.
   - Expected answerability.
2. Begin with 25 manually reviewed cases.
3. Expand toward approximately 100 cases:
   - Factual.
   - Conceptual.
   - Exact-name/date/title.
   - Metadata filters.
   - Unanswerable.
4. Implement Recall@K.
5. Implement MRR@K.
6. Implement nDCG@K.
7. Record latency and zero-result rate.
8. Create an experiment runner covering:
   - 300-, 500-, and 800-token chunks.
   - Dense only.
   - Sparse only.
   - Hybrid.
   - Hybrid plus reranking.
9. Save configuration and results in version-controlled files.
10. Add retrieval regression thresholds to tests only after establishing a trustworthy baseline.
11. Manually inspect failed cases and classify causes:
   - Ingestion.
   - OCR.
   - Chunking.
   - Embedding.
   - Lexical retrieval.
   - Filtering.
   - Reranking.

## UI work

Create an evaluation dashboard with:

- Experiment selector.
- Aggregate metrics.
- Per-language metrics.
- Per-query-type metrics.
- Failed cases.
- Side-by-side ranking comparison.
- Latency distribution.

## Exit criteria

- An evaluation run is reproducible from a committed configuration.
- Chunking and retrieval choices are backed by measurements.
- At least one failure analysis produces an explainable improvement.
- The selected baseline is recorded for future regression checks.

## Required ADR

`ADR-0010: Retrieval evaluation dataset, metrics, and release gates`

Decision questions:

- Why these query categories?
- Why these metrics?
- How is ground truth created?
- What metric thresholds block a regression?

---
