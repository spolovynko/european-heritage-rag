# Cross-phase project workflow

## Daily development workflow

Once the repository contains both applications, a typical development session will be:

1. Read `docs/project-status.md`.
2. Check out the branch for the current phase.
3. Synchronize dependencies.
4. Start required Docker services.
5. Start the backend.
6. Start the frontend.
7. Make one small change.
8. Run the narrowest relevant test.
9. Run the full phase checks before committing.
10. Update the ADR and project status.

Illustrative commands:

```powershell
docker compose up -d

uv sync --locked
uv run pytest
uv run uvicorn european_heritage_rag.api.main:app --reload

Set-Location frontend
npm install
npm run dev
```

Exact commands in the README are authoritative once the corresponding phase is implemented.

---

## Git workflow

Use one branch per phase or meaningful phase slice:

```text
phase/01-scope
phase/02-environment
phase/03-ui-foundation
phase/04-wellcome-ingestion
```

Prefer small commits describing one verified change:

```text
docs: define evidence and citation contract
feat(api): add typed health endpoints
feat(ui): add pipeline dashboard shell
feat(ingestion): paginate Wellcome works
test(ingestion): cover manifests without OCR
```

Before completing a phase:

- Working tree is understood.
- Tests pass.
- Static checks pass.
- README commands are current.
- ADR is accepted.
- `docs/project-status.md` is updated.

---

## Environment and secret policy

Commit `.env.example`, never `.env`.

Expected variables will grow by phase. A likely final set is:

```dotenv
APP_ENV=local
LOG_LEVEL=INFO

WELLCOME_CATALOGUE_BASE_URL=https://api.wellcomecollection.org/catalogue/v2
DATA_ROOT=data

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=heritage-rag-chunks

DATABASE_URL=postgresql+psycopg://heritage:heritage@localhost:5432/heritage

LLM_MODEL=provider:model-name
LLM_API_KEY=
```

Only add a variable when code uses it. Tests should use safe overrides and must not require production credentials.

---

## Definition of done for the complete project

The first production-oriented portfolio version is complete when:

- The source and selection policy are documented.
- Ingestion is resumable and idempotent.
- Bronze, Silver, and Gold layers are reproducible.
- OCR cleaning is inspectable.
- Chunking strategies were compared rather than assumed.
- Dense, sparse, hybrid, and reranked retrieval are measurable.
- The evaluation dataset is version controlled.
- Answers contain valid page-level citations.
- Unsupported questions abstain.
- Conversations persist without becoming evidence.
- The chat UI streams responses and exposes sources.
- Prompt-injection and licence tests exist.
- Active dataset, chunker, index, model, and prompt versions are traceable.
- CI passes from a clean clone.
- The public demo is rate-limited and observable.
- Every phase has an ADR.
- The README, evaluation report, and demonstration make the work defensible to a technical reviewer.

---

## Final learning principle

At every phase, the primary question is not merely “does it run?” It is:

> Can I explain what this component does, why it exists, what alternative we rejected, how we tested it, and what evidence would make us change the decision?

If the answer is no, the phase is not complete yet.
