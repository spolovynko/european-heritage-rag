# Phase 13 — Complete streaming chat experience

## Objective

Turn the functional RAG backend into a polished, transparent chat experience with structured streaming and evidence inspection.

## What we will learn

- Server-Sent Events.
- Streaming lifecycle and cancellation.
- Structured UI events.
- Optimistic and error states.
- Evidence-focused UX.
- Accessibility and responsive design.

## Development steps

1. Define the streaming event contract:
   - `status`
   - `citation`
   - `token`
   - `done`
   - `error`
2. Implement `POST /v1/chat/stream`.
3. Stream pipeline stage updates before answer tokens.
4. Support cancellation and cleanup.
5. Make retry behaviour explicit and safe.
6. Add filters to the chat request:
   - Language.
   - Date range.
   - Subject.
   - Work.
7. Add source cards with:
   - Title.
   - Contributor.
   - Page range.
   - Supporting passage.
   - Page image.
   - Original source link.
   - Licence.
8. Add feedback controls.
9. Add copy-answer and new-chat actions.
10. Complete the retrieval-debug panel.
11. Add empty, timeout, rate-limit, and provider-error experiences.
12. Test keyboard navigation, readable contrast, and mobile layout.

## Tests

- Stream event ordering.
- Partial-answer cancellation.
- Citation-source expansion.
- Conversation reload.
- Filter submission.
- Error rendering.
- End-to-end happy path in a browser.

## Exit criteria

- The UI supports a complete multi-turn conversation.
- Answers stream without losing structured citations.
- Source evidence is one click away.
- Retrieval diagnostics are available but do not overwhelm normal users.

## Required ADR

`ADR-0013: Structured SSE protocol and evidence-centred chat UX`

Decision questions:

- Why Server-Sent Events rather than WebSockets?
- What events are part of the public contract?
- How are citations represented during streaming?
- Which diagnostics are user-facing versus developer-only?

---
