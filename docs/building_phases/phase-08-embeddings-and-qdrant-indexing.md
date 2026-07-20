# Phase 8 — Embeddings and Qdrant indexing

## Objective

Convert Gold chunks into dense and sparse representations and index them in Qdrant with filterable metadata and reproducible model versions.

## What we will learn

- What embeddings represent.
- Multilingual embedding trade-offs.
- Dense versus sparse vectors.
- Vector dimensions and distance metrics.
- Batch inference.
- Idempotent upserts.
- Index and model versioning.

## Development steps

1. Add Qdrant to Docker Compose with persistent local storage.
2. Add the Qdrant client and the selected embedding packages.
3. Benchmark at least one practical multilingual dense model on local hardware using a small sample.
4. Record:
   - Model name.
   - Revision if available.
   - Vector dimension.
   - Normalization behaviour.
   - Maximum input length.
   - Inference time.
5. Add a sparse BM25-style representation.
6. Create a Qdrant collection with named vectors:
   - `dense`
   - `sparse`
7. Define the Qdrant payload:
   - Chunk ID.
   - Work ID.
   - Title.
   - Contributors.
   - Language.
   - Production year.
   - Subjects.
   - Page range.
   - Licence.
   - Text.
   - Source URL.
   - Dataset and embedding versions.
8. Batch embedding and upsert operations.
9. Add retry and failure reporting.
10. Make indexing idempotent.
11. Write an index manifest containing dataset, chunker, embedding, sparse-model, and collection versions.
12. Begin with 20–25 works, then expand to 50–100.

## UI work

Show:

- Current indexing run.
- Chunks embedded.
- Chunks indexed.
- Batch timing.
- Failure count.
- Active collection and model version.
- Qdrant health.

## Tests

- Embedding vector dimension is correct.
- Empty chunks are rejected.
- Payload schema is complete.
- Repeated indexing updates rather than duplicates.
- Metadata filters return expected points.

## Exit criteria

- A versioned Qdrant collection contains all selected chunks.
- Dense and sparse vectors are present.
- Indexing can be resumed or rerun safely.
- The UI reports index health and progress.

## Required ADR

`ADR-0008: Multilingual embeddings, sparse retrieval, and Qdrant index design`

Decision questions:

- Why Qdrant?
- Why named dense and sparse vectors?
- Why the selected multilingual model?
- Why store text and metadata in the payload?

---
