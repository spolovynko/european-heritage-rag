# Phase 7 — Gold data layer and chunking experiments

## Objective

Create retrieval-ready chunks that preserve semantic coherence, language, work identity, and exact page citations.

## What we will learn

- The purpose and cost of chunking.
- Token-aware versus character-aware splitting.
- Page-aware and structure-aware chunking.
- Overlap trade-offs.
- Parent-child provenance.
- Deterministic chunk identifiers.

## Development steps

1. Select the tokenizer associated with the baseline embedding model.
2. Create a `ChunkingConfig` containing:
   - Target token count.
   - Maximum token count.
   - Overlap.
   - Minimum useful text length.
   - Header/footer policy.
   - Chunker version.
3. Implement a page-aware chunker:
   - Keep page order.
   - Preserve paragraph boundaries where possible.
   - Accumulate text until the target size.
   - Record all included page IDs.
   - Do not mix works or languages.
4. Implement three configurations:
   - Approximately 300 tokens with 30-token overlap.
   - Approximately 500 tokens with 50-token overlap.
   - Approximately 800 tokens with 80-token overlap.
5. Generate deterministic chunk IDs using work, page range, chunk version, and content hash.
6. Create `chunks.parquet`.
7. Store metadata needed for filters and citations.
8. Add a command to rebuild one work or one chunking version.
9. Add chunk statistics:
   - Count.
   - Token distribution.
   - Empty/short chunks.
   - Overlap ratio.
   - Pages per chunk.
10. Do not decide the best chunk size yet; Phase 10 will evaluate it.

## UI work

Create a chunk inspector showing:

- Chunk text.
- Token count.
- Page boundaries.
- Overlap highlighted against adjacent chunks.
- Source images.
- Metadata payload.
- Ability to switch between chunking configurations.

## Tests

- No chunk crosses work boundaries.
- No chunk crosses language boundaries.
- Page order is preserved.
- Chunk IDs are stable.
- Token limits are enforced.
- Citations contain every contributing page.

## Exit criteria

- Three reproducible Gold datasets exist.
- Chunks can be visually inspected.
- Every chunk has valid work and page provenance.
- Rebuilding with the same inputs produces identical IDs and text.

## Required ADR

`ADR-0007: Page-aware token chunking and versioned Gold datasets`

Decision questions:

- Why page-aware chunking?
- Why evaluate several sizes?
- Why deterministic IDs?
- Why preserve language per chunk?

---
