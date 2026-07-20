# HeritageRAG building phases

This directory is the implementation roadmap for HeritageRAG. Each numbered
file contains one independently reviewable development and learning phase.
Read the current phase together with the [project status](../project-status.md)
and the ADRs it references; do not treat later-phase plans as implemented
capabilities.

## How to use this roadmap

1. Read the [project status](../project-status.md) to find the active phase.
2. Open only that phase file and its referenced ADRs.
3. Complete its development steps and verification.
4. Update docs/project-status.md and accept the phase ADR before continuing.

## Phase index

| Phase | Document |
|---:|---|
| 1 | [Scope, evidence contract, and success criteria](phase-01-scope-evidence-contract-and-success-criteria.md) |
| 2 | [Environment and repository setup](phase-02-environment-and-repository-setup.md) |
| 3 | [UI foundation and progress dashboard](phase-03-ui-foundation-and-progress-dashboard.md) |
| 4 | [Wellcome discovery and ingestion client](phase-04-wellcome-discovery-and-ingestion-client.md) |
| 5 | [Bronze data layer](phase-05-bronze-data-layer.md) |
| 6 | [Silver normalization and OCR cleaning](phase-06-silver-normalization-and-ocr-cleaning.md) |
| 7 | [Gold data layer and chunking experiments](phase-07-gold-data-layer-and-chunking-experiments.md) |
| 8 | [Embeddings and Qdrant indexing](phase-08-embeddings-and-qdrant-indexing.md) |
| 9 | [Hybrid retrieval and reranking](phase-09-hybrid-retrieval-and-reranking.md) |
| 10 | [Retrieval evaluation](phase-10-retrieval-evaluation.md) |
| 11 | [Grounded answer generation with Pydantic AI](phase-11-grounded-answer-generation-with-pydantic-ai.md) |
| 12 | [Conversation management](phase-12-conversation-management.md) |
| 13 | [Complete streaming chat experience](phase-13-complete-streaming-chat-experience.md) |
| 14 | [Testing, security, and abuse resistance](phase-14-testing-security-and-abuse-resistance.md) |
| 15 | [Observability, CI/CD, and production deployment](phase-15-observability-ci-cd-and-production-deployment.md) |
| 16 | [Portfolio packaging and technical defence](phase-16-portfolio-packaging-and-technical-defence.md) |

## Shared guidance

- [Cross-phase project workflow](project-workflow.md) — daily commands, Git
  workflow, environment policy, overall definition of done, and learning
  principle.
- [Optional agentic RAG with LangGraph](optional-agentic-rag-with-langgraph.md) —
  a post-baseline experiment, not part of the required 16 phases.
- [Learning guide agreement](../learning-guide-agreement.md) — collaboration,
  architecture, technology, repository, and ADR working agreements.
