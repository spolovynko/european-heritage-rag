# Phase 16 — Portfolio packaging and technical defence

## Objective

Turn the working system into a clear engineering narrative that demonstrates knowledge, measurements, trade-offs, and limitations.

## What we will learn

- Technical storytelling.
- Reproducibility for reviewers.
- Communicating architectural trade-offs.
- Presenting evaluation honestly.
- Separating demonstrated capability from future ideas.

## Development steps

1. Rewrite the README for a first-time reviewer:
   - Problem.
   - Product screenshot.
   - Architecture.
   - Quick start.
   - Example questions.
   - Evaluation results.
   - Limitations.
2. Add a ten-record or similarly small reproducible demonstration dataset.
3. Ensure the demo can run without downloading hundreds of books.
4. Create a data-source and dataset card:
   - Wellcome source.
   - Selection filters.
   - Languages.
   - Licences.
   - Known OCR issues.
5. Create an architecture diagram and request-flow diagram.
6. Publish the ADR index.
7. Write an evaluation report including failed cases.
8. Document cost and latency for the demonstrated configuration.
9. Document security decisions and limitations.
10. Add screenshots of:
    - Ingestion dashboard.
    - Raw/clean OCR comparison.
    - Chunk inspector.
    - Retrieval workbench.
    - Evaluation dashboard.
    - Chat with citations.
11. Record a short demonstration video.
12. Prepare interview answers for:
    - Why this data source?
    - Why these data layers?
    - Why this chunking strategy?
    - Why hybrid retrieval?
    - Why reranking?
    - How are citations validated?
    - How does abstention work?
    - What would break at ten times the scale?
    - Why Pydantic AI but not LangChain or LangGraph?
13. Tag a portfolio release.

## Exit criteria

- A reviewer can run a small demo using documented commands.
- Architecture and important decisions are visible.
- Evaluation results are reproducible.
- Limitations and trade-offs are stated honestly.
- The repository tells a coherent story without requiring the developer to explain basic navigation.

## Required ADR

`ADR-0016: Reproducible portfolio distribution and demonstration scope`

Decision questions:

- What sample data is included?
- What does the default demo run?
- Which evaluation results are published?
- What is deliberately excluded from the portfolio release?

---
