# Phase 14 — Testing, security, and abuse resistance

## Objective

Create confidence that the system behaves correctly under malformed input, retrieval regressions, prompt injection, service failures, and rights constraints.

## What we will learn

- Test pyramid design.
- Contract and integration testing.
- RAG-specific security threats.
- Prompt injection through retrieved documents.
- Licence enforcement.
- Rate limiting and request validation.
- Dependency and secret hygiene.

## Development steps

1. Review the test pyramid:
   - Pure unit tests.
   - Source-client contract tests.
   - Pipeline integration tests.
   - Qdrant retrieval tests.
   - API tests.
   - Browser tests.
   - Retrieval regression tests.
2. Create a small deterministic end-to-end fixture corpus.
3. Add malicious or adversarial retrieved passages.
4. Verify retrieved instructions are quoted as evidence and never executed.
5. Enforce licence filters both during ingestion and retrieval.
6. Reject arbitrary user-provided URLs.
7. Sanitize rendered Markdown and prohibit unsafe HTML.
8. Add request-size limits and validation.
9. Add rate limiting to public endpoints.
10. Define authentication scope if the public deployment stores user conversations.
11. Ensure conversation-level authorization.
12. Redact secrets and avoid logging sensitive conversation text unnecessarily.
13. Run dependency vulnerability checks in CI.
14. Create a simple threat model.

## UI work

- Safe Markdown rendering.
- Clear rate-limit and validation errors.
- Conversation deletion.
- Privacy notice for stored messages.
- No automatic loading of untrusted external content.

## Exit criteria

- The deterministic end-to-end fixture passes.
- Adversarial retrieval tests pass.
- Licence restrictions are enforced.
- User conversations are isolated or the application is explicitly single-user.
- The threat model and residual risks are documented.

## Required ADR

`ADR-0014: RAG security boundary, rights enforcement, and test strategy`

Decision questions:

- What content is untrusted?
- What can retrieved text influence?
- How are licences enforced?
- Which tests are required before deployment?

---
