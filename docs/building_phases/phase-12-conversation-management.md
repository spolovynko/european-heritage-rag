# Phase 12 — Conversation management

## Objective

Add persistent multi-turn conversations without allowing chat history to become an unverified knowledge source.

## What we will learn

- Conversation data modelling.
- Follow-up query rewriting.
- Short-term context management.
- History summarization.
- Database migrations.
- Separating memory from evidence.

## Development steps

1. Add PostgreSQL to Docker Compose.
2. Add SQLAlchemy and Alembic.
3. Create tables for:
   - Conversations.
   - Messages.
   - Message citations.
   - Retrieval traces.
   - Feedback.
4. Add repository functions for conversation persistence.
5. Implement conversation endpoints.
6. Pass a bounded number of prior turns to a standalone-query rewriter.
7. Retrieve using the rewritten query, not the ambiguous follow-up alone.
8. Preserve the original user message for display and answer construction.
9. Ensure prior assistant messages are conversational context, not evidence.
10. Summarize older history when a configured limit is reached.
11. Persist model, prompt, index, and retrieval versions with each assistant message.
12. Persist the exact chunks used for each answer.

## UI work

Add:

- New conversation.
- Conversation list.
- Conversation title.
- Reload previous messages.
- Delete conversation.
- Display original and rewritten query in debug mode.

## Tests

- Follow-up pronoun resolution.
- Topic change resets retrieval intent appropriately.
- Conversation isolation.
- Old message reload.
- Deleted conversation behaviour.
- Assistant claims are not used as citations.

## Exit criteria

- Conversations survive application restart.
- Follow-up questions retrieve with a standalone query.
- Every historical answer remains linked to its original evidence and versions.
- Conversation state is isolated from the vector corpus.

## Required ADR

`ADR-0012: PostgreSQL conversation persistence and bounded chat memory`

Decision questions:

- Why PostgreSQL?
- Why rewrite follow-ups?
- How much history is retained in active context?
- Why is conversation memory not evidence?

---
