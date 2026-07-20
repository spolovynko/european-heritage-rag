# Phase 11 — Grounded answer generation with Pydantic AI

## Objective

Add answer generation on top of the evaluated retrieval service while enforcing typed output, citations, uncertainty, and abstention.

## What we will learn

- Separating retrieval from generation.
- Prompt construction.
- Structured LLM output.
- Citation validation.
- Provider abstraction.
- Grounded abstention.
- Prompt-injection boundaries.

## Development steps

1. Add Pydantic AI and one configured model provider.
2. Keep retrieval outside the model-controlled agent loop.
3. Define typed models:
   - `RagAnswer`
   - `Citation`
   - `AbstentionReason`
4. Build a context formatter containing:
   - Evidence IDs.
   - Work title.
   - Page range.
   - Text.
   - Source URL.
5. Write instructions requiring:
   - Evidence-only answers.
   - Citations for substantive claims.
   - User-language responses.
   - Clear abstention when evidence is insufficient.
   - Retrieved content to be treated as untrusted reference material.
6. Add an output validator ensuring all cited chunk IDs were retrieved.
7. Add a post-generation citation-support check or evaluation rubric.
8. Add usage and latency recording.
9. Implement a non-streaming endpoint first.
10. Add streaming after output and error handling are stable.
11. Add `POST /v1/answer` or connect the answer service behind a chat endpoint.

## UI work

Connect the chat shell to stateless question answering:

- User message.
- Loading stages: rewriting, retrieving, reranking, generating.
- Assistant answer.
- Inline citations.
- Source cards.
- Abstention state.
- Retrieval-debug link.

## Tests

- Typed output validation.
- Invented chunk ID is rejected.
- Empty evidence causes abstention.
- Unsupported question causes abstention.
- Retrieved instruction-like text cannot alter system behaviour.
- Model provider is replaceable in tests.

## Exit criteria

- Answers use the evaluated retrieval service.
- Every citation points to retrieved evidence.
- Unsupported questions abstain.
- The chat UI can display a complete answer and sources.

## Required ADR

`ADR-0011: Deterministic RAG generation boundary and Pydantic AI`

Decision questions:

- Why Pydantic AI?
- Why keep retrieval outside the agent loop?
- What is the answer schema?
- How are citations and abstention validated?

---
