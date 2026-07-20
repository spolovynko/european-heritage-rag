# HeritageRAG Development and Learning Guide

## 1. Purpose of this guide

This document is the working playbook for building **HeritageRAG**, a production-oriented multilingual retrieval-augmented generation application based initially on digitised public-domain material from the Wellcome Collection.

The project has two equally important goals:

1. Learn the mechanics and engineering trade-offs of a real RAG system.
2. Produce a small, understandable GitHub portfolio project that can be explained and defended in a technical interview.

The project will be developed incrementally. We will start with a very small dataset and a small codebase. We will only add infrastructure, frameworks, abstractions, and scale when a concrete requirement justifies them.

The final product will include:

- A multilingual chat interface.
- Wellcome catalogue metadata and IIIF OCR ingestion.
- Bronze, Silver, and Gold data layers.
- Page-aware chunking.
- Dense and sparse hybrid retrieval.
- Reranking.
- Page-level citations.
- Evidence-based abstention.
- Conversation history.
- Retrieval and ingestion diagnostics in the UI.
- Evaluation, monitoring, tests, and production deployment documentation.

---

## 2. Project statement

> HeritageRAG helps users explore European medical, scientific, social, and cultural history through digitised public-domain documents from the Wellcome Collection. It answers questions using retrieved evidence, cites the relevant work and page, and abstains when the available evidence is insufficient.

Initial scope:

- Primary data source: Wellcome Collection.
- Material: digitised public-domain books with metadata, page images, and OCR where available.
- Initial language: English.
- Later languages: French and Dutch.
- Development dataset: 5 to 100 works.
- Portfolio dataset: approximately 250 to 500 works.
- Retrieval unit: page-aware text chunk.
- Required provenance: work ID, title, page range, source URL, and licence.

Out of scope for the first complete version:

- Autonomous web browsing.
- User-uploaded documents.
- Multiple museum sources.
- Image embeddings.
- A fully autonomous agent.
- Kubernetes.
- Microservices.
- Large-scale distributed processing.

These can become later extensions, but they must not delay the understandable baseline.

---

## 3. Working agreement: one chat per phase

Each development phase will have a separate chat and a fresh context window. A phase may require several messages, coding iterations, and debugging cycles, but the next phase starts only after the current phase meets its exit criteria.

### 3.1 Responsibilities in each phase

The assistant will:

- Explain the concept and its relevance before generating code.
- Explain important design choices and rejected alternatives.
- Generate code in small, reviewable increments.
- Identify the exact path for every file.
- Prefer complete file contents for small files and focused patches for existing files.
- Explain commands before asking the learner to run them.
- Provide tests alongside important behaviour.
- Help diagnose command output and errors pasted back into the chat.
- Avoid introducing unexplained abstractions.
- Draft one ADR for the phase.
- End the phase with verification steps and a handoff summary.

The learner will:

- Create the files and copy the generated code into the repository.
- Run the commands locally.
- Read the explanation before moving to the next step.
- Paste errors and relevant output back into the same phase chat.
- Ask questions when a decision or line of code is unclear.
- Verify the phase exit criteria.
- Commit the completed phase and its ADR.
- Start a fresh chat for the next phase with the handoff context.

### 3.2 Code delivery rules

To keep the project understandable:

- Generate no more than one to three related files at a time.
- Every code delivery must contain:
  1. What the code does.
  2. Why it belongs in that file.
  3. Important implementation decisions.
  4. The code itself.
  5. A command or test that proves it works.
- Prefer normal Python functions over framework-specific chains.
- Prefer composition over inheritance.
- Do not add an interface until there are at least two implementations or a clear test boundary.
- Do not add a framework solely because it is popular.
- Never place API keys or secrets in code or Git.

### 3.3 Phase chat starter template

Start every new phase chat with the following message, adapted to the current phase:

```text
We are building HeritageRAG, a production-oriented multilingual RAG project
using digitised public-domain Wellcome Collection books.

We work one phase per chat. I copy the code into my repository and run it.
Please explain concepts and decisions before generating small code increments.
Do not introduce unnecessary abstractions. We must create one ADR for this phase.

Current phase: Phase X — <phase name>

Current project status:
<paste docs/project-status.md>

Relevant previous ADRs:
<paste or link the most relevant ADRs>

Current repository tree:
<paste a shallow repository tree>

Please begin by reviewing the entry criteria and proposing the first small step.
```

### 3.4 Required phase handoff

At the end of every phase, update `docs/project-status.md`:

```markdown
# Project status

## Current state

- Last completed phase:
- Current branch:
- Dataset size:
- Active index version:
- Last successful command:

## Completed capabilities

- ...

## Verification results

- Tests:
- Linting:
- Manual checks:

## Important decisions

- ADR links:

## Known limitations

- ...

## Next phase

- Phase:
- Entry conditions:
- First intended task:
```

This file is the main bridge between separate chat context windows.

---

## 4. Architecture principles

### 4.1 Keep the important RAG logic visible

The following logic should be implemented explicitly in the repository so it can be learned and defended:

- Source discovery and pagination.
- IIIF manifest traversal.
- OCR reconstruction and cleaning.
- Data validation and lineage.
- Chunk boundary selection.
- Dense and sparse retrieval.
- Reciprocal Rank Fusion.
- Metadata filtering.
- Reranking.
- Context selection.
- Citation validation.
- Abstention.
- Retrieval evaluation.

Libraries may provide HTTP clients, model inference, storage, and database access, but the project must not hide the core behaviour behind an opaque RAG chain.

### 4.2 Framework policy

- **LangChain:** not used in the initial implementation. The Wellcome source adapter and retrieval pipeline are custom and explicit.
- **LangGraph:** not used in the deterministic baseline. It may be added later for an evaluated agentic-RAG experiment with retry loops or multiple sources.
- **Pydantic AI:** introduced only in the answer-generation phase for typed dependencies, model-provider integration, validated output, and streaming.
- **FastAPI:** used for HTTP endpoints and streaming.
- **React with TypeScript and Vite:** used for the chat and diagnostics UI.

### 4.3 Progressive scale

Use the smallest useful dataset at each stage:

| Stage | Dataset size | Purpose |
|---|---:|---|
| Automated fixture | 1–2 works | Fast repeatable tests |
| Ingestion smoke test | 5 works | Validate API and storage |
| Data-cleaning development | 20–25 works | Discover real anomalies |
| Retrieval development | 50–100 works | Build and inspect search |
| Portfolio evaluation | 250–500 works | Meaningful final demonstration |

Do not ingest the full catalogue during development.

### 4.4 Target architecture

```mermaid
flowchart LR
    W["Wellcome Catalogue API"] --> I["Ingestion client"]
    X["Wellcome IIIF"] --> I
    I --> B["Bronze: raw JSON"]
    B --> S["Silver: works and pages"]
    S --> G["Gold: chunks"]
    G --> E["Dense and sparse embeddings"]
    E --> Q["Qdrant"]
    U["React chat UI"] --> A["FastAPI"]
    A --> R["Hybrid retrieval and reranking"]
    R --> Q
    R --> L["Pydantic AI generation"]
    L --> A
    A --> P["PostgreSQL conversations"]
    A --> U
```

---

## 5. Technology stack

### Backend

- Python 3.12
- `uv` for Python and dependency management
- FastAPI and Uvicorn
- Pydantic and Pydantic Settings
- HTTPX and Tenacity
- Typer for pipeline commands
- Polars and PyArrow for tabular processing and Parquet
- Qdrant client
- A multilingual dense embedding model
- Sparse BM25-style retrieval
- A multilingual reranker
- Pydantic AI for generation
- SQLAlchemy, Alembic, and PostgreSQL for conversations
- Structlog and OpenTelemetry-compatible instrumentation

### Frontend

- React
- TypeScript
- Vite
- A small typed API client
- Server-Sent Events for chat and job progress
- Plain CSS or a very small component layer initially

### Development and operations

- Docker Compose
- pytest, pytest-asyncio, and respx
- Ruff and mypy
- Browser end-to-end tests later
- GitHub Actions
- Object storage in production; local filesystem during development

---

## 6. Planned repository structure

The structure will grow progressively. Do not create empty modules before their phase requires them.

```text
heritage-rag/
├── backend/
│   ├── src/heritage_rag/
│   │   ├── api/
│   │   ├── domain/
│   │   ├── generation/
│   │   ├── pipeline/
│   │   ├── retrieval/
│   │   ├── sources/wellcome/
│   │   ├── config.py
│   │   └── cli.py
│   ├── tests/
│   │   ├── fixtures/
│   │   ├── integration/
│   │   └── unit/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   └── pages/
│   └── package.json
├── data/
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── docs/
│   ├── adr/
│   ├── evaluation/
│   ├── architecture.md
│   └── project-status.md
├── infra/
│   └── compose.yaml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

`data/` must be excluded from Git except for deliberately small test fixtures.

---

## 7. Architectural Decision Records

One ADR is required for every phase. An ADR records a meaningful decision and its consequences; it is not a diary of tasks performed.

Store ADRs in `docs/adr/` with sequential names:

```text
docs/adr/0001-project-scope-and-evidence-contract.md
docs/adr/0002-development-environment.md
...
```

### ADR template

```markdown
# ADR-XXXX: Decision title

- Status: Accepted
- Date: YYYY-MM-DD
- Phase: Phase X — Name

## Context

What problem or decision did this phase introduce? What constraints matter?

## Decision

What did we choose?

## Alternatives considered

### Alternative A

What was considered, and why was it not selected?

### Alternative B

What was considered, and why was it not selected?

## Consequences

### Positive

- ...

### Negative or accepted trade-offs

- ...

## Validation

How will we know this decision works?

## Revisit when

What future evidence or requirement would justify changing the decision?
```

Maintain `docs/adr/README.md` as an ADR index.

---

# Development phases

## Phase 1 — Scope, evidence contract, and success criteria

### Objective

Turn the project idea into a precise product and evidence contract. Define what the assistant can answer, what constitutes a valid citation, when it must abstain, and how success will be measured.

### What we will learn

- Why RAG projects need a bounded domain.
- The difference between retrieval quality and answer quality.
- Why citations and abstention must be designed before prompts.
- How measurable requirements guide later architecture.

### Development steps

1. Write the initial project statement and user personas.
2. Define supported question types:
   - Exact title, author, and date lookup.
   - Subject and period filtering.
   - Passage-level historical questions.
   - Follow-up questions.
   - Unanswerable questions.
3. Define the evidence contract:
   - Every substantial claim requires retrieved support.
   - Citations identify the work and page range.
   - The cited chunk must be among the retrieved context.
   - Answers must not use previous assistant statements as evidence.
4. Define initial language scope:
   - English baseline.
   - French and Dutch added after English retrieval is evaluated.
5. Define initial success targets. Treat them as goals to tune, not fabricated achievements:
   - Retrieval Recall@10 target.
   - Citation coverage target.
   - Abstention test set.
   - Search latency budget.
6. Create:
   - `README.md`
   - `docs/project-status.md`
   - `docs/architecture.md`
   - `docs/adr/README.md`

### UI work

Create only a low-fidelity sketch showing the intended chat, source panel, and pipeline dashboard. No frontend implementation is required yet.

### Verification

- Ten example user questions are documented.
- At least two examples are deliberately unanswerable.
- Every example specifies the expected evidence type.
- The project scope excludes unsupported capabilities clearly.

### Exit criteria

- The product statement is understandable without verbal explanation.
- Citation and abstention rules are explicit.
- Initial evaluation targets are documented.
- The next chat can understand the project using the repository documents alone.

### Required ADR

`ADR-0001: Project scope and evidence contract`

Decision questions:

- Why Wellcome public-domain digitised books?
- Why begin with English?
- Why require page-level citations?
- Why use deterministic two-step RAG as the baseline?

---

## Phase 2 — Environment and repository setup

### Objective

Create a reproducible development environment and the smallest runnable backend. Avoid installing the full future stack before it is required.

### What we will learn

- Python dependency locking with `uv`.
- Environment-based configuration.
- Package layout and imports.
- Docker Compose basics.
- The difference between liveness and readiness.
- Basic automated quality checks.

### Development steps

1. Create the GitHub repository `heritage-rag`.
2. Initialize Git and create the backend Python project using Python 3.12 and `uv`.
3. Add the initial dependencies only:
   - FastAPI
   - Uvicorn
   - Pydantic Settings
   - Typer
   - Structlog
4. Add development dependencies:
   - pytest
   - Ruff
   - mypy
5. Create a minimal settings model that reads environment variables.
6. Create `.env.example` without real credentials.
7. Implement:
   - `GET /health/live`
   - `GET /health/ready`
8. Add a small CLI entry point such as `heritage-rag version`.
9. Configure Ruff, mypy, and pytest in `pyproject.toml`.
10. Add a minimal Docker Compose file. Initially it may contain only backend development support; Qdrant is added when indexing begins and PostgreSQL when conversations begin.
11. Document setup and run commands in the README.

### Typical local commands

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run mypy backend/src
uv run uvicorn heritage_rag.api.main:app --reload
```

Exact paths will be adjusted to the repository layout created in this phase.

### UI work

None beyond confirming that the backend is reachable from a browser.

### Verification

- A clean clone can run `uv sync` successfully.
- The lockfile is committed.
- The health endpoint returns a typed JSON response.
- Tests and static checks pass.
- No secrets are tracked by Git.

### Exit criteria

- Backend starts with one documented command.
- All development checks pass.
- Repository structure is small and explained.

### Required ADR

`ADR-0002: Python, dependency management, and initial repository structure`

Decision questions:

- Why Python 3.12?
- Why `uv`?
- Why a monorepo with backend and frontend?
- Why progressively add dependencies?

---

## Phase 3 — UI foundation and progress dashboard

### Objective

Build the visual shell before ingestion so every later pipeline phase can expose visible progress and inspectable intermediate data.

### What we will learn

- React component structure.
- TypeScript API contracts.
- Separating UI state from backend state.
- Designing diagnostic interfaces for data pipelines.
- Mock-first UI development.

### Development steps

1. Create the React and TypeScript frontend with Vite.
2. Establish a deliberately small structure:
   - `pages/`
   - `components/`
   - `api/`
   - `types/`
3. Create three initial screens:
   - Chat shell.
   - Pipeline dashboard.
   - Data explorer.
4. Create a navigation layout and basic responsive styling.
5. Use static typed mock data for:
   - Ingestion run status.
   - Work counts.
   - Page counts.
   - Errors.
   - Sample metadata record.
   - Sample OCR page.
6. Add a typed API client with one backend status request.
7. Replace one mock widget with real backend health information.
8. Add loading, empty, and error states from the beginning.
9. Add a frontend type-check and production-build command.
10. Document how to run backend and frontend together.

### Initial UI layout

```text
┌──────────────────────────────────────────────────────────────┐
│ HeritageRAG                                    System status │
├──────────────┬───────────────────────────────────────────────┤
│ Chat         │ Pipeline dashboard                            │
│ Ingestion    │                                               │
│ Data         │ Works  Pages  Failures  Last run              │
│ Retrieval    │                                               │
│ Evaluation   │ Progress and recent events                    │
└──────────────┴───────────────────────────────────────────────┘
```

### Verification

- Frontend runs with one command.
- Frontend production build succeeds.
- Backend health appears in the UI.
- Mock data is isolated and can later be replaced easily.
- No state-management framework is added without need.

### Exit criteria

- The application has a navigable visual shell.
- Later phases have clear locations for progress and inspection.
- The chat UI visibly exists even though it is not yet connected to RAG.

### Required ADR

`ADR-0003: React UI architecture and early diagnostic dashboard`

Decision questions:

- Why build the UI before ingestion?
- Why React, TypeScript, and Vite?
- Why start with typed mock data?
- Why avoid a large component or state framework initially?

---

## Phase 4 — Wellcome discovery and ingestion client

### Objective

Build a small, resilient client that discovers digitised public-domain Wellcome works and retrieves catalogue records, IIIF manifests, and OCR annotations.

### What we will learn

- REST pagination.
- HTTP timeouts and retries.
- IIIF Presentation manifests.
- Per-page OCR annotations.
- Rate-conscious ingestion.
- Checkpointing and resumable work.

### Development steps

1. Add HTTPX, Tenacity, and respx.
2. Create typed source models for only the fields currently needed.
3. Implement a Wellcome client with:
   - Configurable base URL.
   - Timeouts.
   - Retry policy.
   - User-Agent.
   - Pagination.
4. Implement work discovery using:
   - `workType=a`
   - `availabilities=online`
   - `items.locations.license=pdm`
5. Extract each work's IIIF Presentation URL.
6. Retrieve the IIIF manifest.
7. Traverse canvases in sequence order.
8. Extract OCR annotation-list URLs from page canvases.
9. Retrieve OCR annotations and reconstruct page lines.
10. Add an ingestion CLI:
    - `--limit`
    - `--query`
    - `--language`
    - `--resume`
    - `--dry-run`
11. Begin with one known work fixture.
12. Run a five-work live smoke test.

### UI work

Replace ingestion mock data with a small in-memory or file-backed job status endpoint. Initially use polling every few seconds. Show:

- Current work.
- Works discovered.
- Works completed.
- Pages downloaded.
- Retry and failure counts.
- Recent ingestion events.

Streaming progress can replace polling later when the behaviour is stable.

### Tests

- Pagination across two mocked pages.
- Retry after a transient error.
- No retry for a permanent invalid request.
- Manifest with OCR annotations.
- Manifest without OCR annotations.
- Work with no public-domain digital location.

### Exit criteria

- Five works can be discovered and traversed.
- The client handles missing OCR without crashing.
- An interrupted run can identify where it stopped.
- Tests do not call the live API.
- The UI shows real ingestion progress.

### Required ADR

`ADR-0004: Wellcome API and IIIF ingestion strategy`

Decision questions:

- Why use the API rather than scraping?
- Why start with API harvesting rather than the daily snapshot?
- Why filter to public-domain online books?
- Why bound concurrency?

---

## Phase 5 — Bronze data layer

### Objective

Persist raw source responses unchanged and make ingestion reproducible, auditable, resumable, and inspectable.

### What we will learn

- Append-only raw data design.
- Data lineage.
- Content hashing.
- Idempotency.
- Run manifests.
- The difference between ingestion and transformation.

### Development steps

1. Define the Bronze directory convention:

```text
data/bronze/wellcome/
└── ingestion_date=YYYY-MM-DD/
    └── run_id=<run-id>/
        ├── run-manifest.json
        └── works/
            └── <work-id>/
                ├── work.json
                ├── manifest.json
                └── annotations/
                    └── <page-id>.json
```

2. Define a run manifest containing:
   - Run ID.
   - Start and end timestamps.
   - Query parameters.
   - Source URLs.
   - Requested and completed counts.
   - Failure records.
   - Pipeline version.
3. Store raw response bytes or losslessly decoded JSON.
4. Calculate a stable content hash.
5. Use atomic file writes so partial files are not mistaken for completed files.
6. Skip unchanged completed resources on rerun.
7. Record failed URLs separately for retry.
8. Add a `bronze inspect` CLI command.
9. Add a `bronze validate` CLI command.
10. Keep storage functions simple and filesystem-specific; defer an object-storage abstraction until deployment.

### UI work

Add Bronze inspection:

- Run list.
- Run status and duration.
- Work and page counts.
- Failure list.
- Raw work JSON preview.
- Raw OCR annotation preview.
- Source link.

### Tests

- Atomic write behaviour.
- Stable hash for identical content.
- Changed hash for changed content.
- Repeated ingestion does not duplicate a completed work.
- Failed resource remains retryable.

### Exit criteria

- A five-work ingestion is fully represented in Bronze.
- Every stored file has provenance.
- Re-running creates no unintended duplicates.
- Raw data can be reprocessed without calling Wellcome again.

### Required ADR

`ADR-0005: Append-only Bronze storage and idempotent ingestion`

Decision questions:

- Why keep Bronze unchanged?
- Why use the local filesystem first?
- Why content hashes?
- What qualifies as an idempotent rerun?

---

## Phase 6 — Silver normalization and OCR cleaning

### Objective

Transform heterogeneous raw records into validated canonical works and pages while preserving the original OCR and complete provenance.

### What we will learn

- Canonical data modelling.
- Schema validation.
- OCR-cleaning trade-offs.
- Data-quality reporting.
- Columnar storage with Parquet.
- Why normalization must not destroy source information.

### Development steps

1. Add Polars and PyArrow.
2. Define canonical `Work` and `Page` models.
3. Create `works.parquet` with fields such as:
   - `work_id`
   - `title`
   - `contributors`
   - `production_date`
   - `subjects`
   - `genres`
   - `language`
   - `license`
   - `source_url`
   - `iiif_manifest_url`
   - `source_content_hash`
4. Create `pages.parquet` with fields such as:
   - `work_id`
   - `page_id`
   - `page_number`
   - `sequence_number`
   - `raw_text`
   - `clean_text`
   - `ocr_quality`
   - `image_url`
   - `annotation_url`
5. Implement small pure cleaning functions:
   - Unicode normalization.
   - HTML removal.
   - Whitespace normalization.
   - OCR-line joining.
   - Conservative dehyphenation.
   - Empty-page detection.
6. Detect repeated headers and footers across pages of the same work.
7. Preserve `raw_text`; never replace it with cleaned text.
8. Add quality flags rather than silently discarding suspicious pages.
9. Produce a machine-readable and human-readable quality report.
10. Run first on five works, then on 20–25 works to discover anomalies.

### UI work

Create a side-by-side page inspector:

- Page image.
- Raw OCR.
- Cleaned text.
- Detected header/footer.
- Quality flags.
- Work metadata.

Add aggregate charts or simple counters for empty pages, average words per page, languages, and processing failures.

### Tests

- Unicode normalization.
- Hyphenated line joining.
- Paragraph preservation.
- Repeated header detection.
- Empty page.
- Invalid or missing metadata.
- Exact Bronze-to-Silver lineage.

### Exit criteria

- Silver datasets are valid Parquet files.
- Every Silver row links to its Bronze source.
- Raw and cleaned OCR can be compared.
- Cleaning quality is visible rather than assumed.
- Transformation is deterministic.

### Required ADR

`ADR-0006: Canonical work/page schemas and conservative OCR cleaning`

Decision questions:

- Why separate works and pages?
- Why store raw and cleaned text?
- Why Parquet?
- Which OCR corrections are safe to automate?

---

## Phase 7 — Gold data layer and chunking experiments

### Objective

Create retrieval-ready chunks that preserve semantic coherence, language, work identity, and exact page citations.

### What we will learn

- The purpose and cost of chunking.
- Token-aware versus character-aware splitting.
- Page-aware and structure-aware chunking.
- Overlap trade-offs.
- Parent-child provenance.
- Deterministic chunk identifiers.

### Development steps

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

### UI work

Create a chunk inspector showing:

- Chunk text.
- Token count.
- Page boundaries.
- Overlap highlighted against adjacent chunks.
- Source images.
- Metadata payload.
- Ability to switch between chunking configurations.

### Tests

- No chunk crosses work boundaries.
- No chunk crosses language boundaries.
- Page order is preserved.
- Chunk IDs are stable.
- Token limits are enforced.
- Citations contain every contributing page.

### Exit criteria

- Three reproducible Gold datasets exist.
- Chunks can be visually inspected.
- Every chunk has valid work and page provenance.
- Rebuilding with the same inputs produces identical IDs and text.

### Required ADR

`ADR-0007: Page-aware token chunking and versioned Gold datasets`

Decision questions:

- Why page-aware chunking?
- Why evaluate several sizes?
- Why deterministic IDs?
- Why preserve language per chunk?

---

## Phase 8 — Embeddings and Qdrant indexing

### Objective

Convert Gold chunks into dense and sparse representations and index them in Qdrant with filterable metadata and reproducible model versions.

### What we will learn

- What embeddings represent.
- Multilingual embedding trade-offs.
- Dense versus sparse vectors.
- Vector dimensions and distance metrics.
- Batch inference.
- Idempotent upserts.
- Index and model versioning.

### Development steps

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

### UI work

Show:

- Current indexing run.
- Chunks embedded.
- Chunks indexed.
- Batch timing.
- Failure count.
- Active collection and model version.
- Qdrant health.

### Tests

- Embedding vector dimension is correct.
- Empty chunks are rejected.
- Payload schema is complete.
- Repeated indexing updates rather than duplicates.
- Metadata filters return expected points.

### Exit criteria

- A versioned Qdrant collection contains all selected chunks.
- Dense and sparse vectors are present.
- Indexing can be resumed or rerun safely.
- The UI reports index health and progress.

### Required ADR

`ADR-0008: Multilingual embeddings, sparse retrieval, and Qdrant index design`

Decision questions:

- Why Qdrant?
- Why named dense and sparse vectors?
- Why the selected multilingual model?
- Why store text and metadata in the payload?

---

## Phase 9 — Hybrid retrieval and reranking

### Objective

Implement an explicit retrieval pipeline that combines semantic and lexical candidates, applies filters, reranks results, and returns traceable evidence.

### What we will learn

- Candidate generation versus final ranking.
- Dense search strengths and weaknesses.
- BM25 strengths and weaknesses.
- Reciprocal Rank Fusion.
- Cross-encoder reranking.
- Filter timing.
- Context diversity and duplicate control.

### Development steps

1. Define typed retrieval input and output models.
2. Implement query normalization without changing user intent.
3. Add metadata filters:
   - Language.
   - Date range.
   - Subject.
   - Work.
   - Licence.
4. Retrieve dense candidates.
5. Retrieve sparse candidates.
6. Fuse rankings using Reciprocal Rank Fusion.
7. Keep retrieval-stage scores and ranks for diagnostics.
8. Add a multilingual reranker to the fused top candidates.
9. Select a small final evidence set.
10. Merge or suppress near-duplicate adjacent chunks when appropriate.
11. Limit repeated evidence from one work unless the query needs it.
12. Add a search CLI with a `--debug` option.
13. Add `POST /v1/search` independently from answer generation.

### UI work

Create the retrieval workbench:

- Search query and filters.
- Dense candidates and scores.
- Sparse candidates and scores.
- Fused rank.
- Reranker score.
- Selected evidence.
- Chunk text and page image.
- Model and index versions.
- Stage latency.

### Tests

- Exact title query benefits from sparse retrieval.
- Paraphrased query benefits from dense retrieval.
- Filters are enforced.
- RRF ordering is deterministic for fixed inputs.
- Reranker receives only bounded candidates.
- Debug trace matches returned results.

### Exit criteria

- Search works without any LLM answer generation.
- Dense-only, sparse-only, hybrid, and reranked results can be compared.
- Every result has visible provenance.
- Retrieval latency is recorded per stage.

### Required ADR

`ADR-0009: Hybrid candidate generation, RRF, and multilingual reranking`

Decision questions:

- Why hybrid rather than dense-only retrieval?
- Why RRF?
- Why rerank only a candidate subset?
- How many candidates are retrieved and returned?

---

## Phase 10 — Retrieval evaluation

### Objective

Create a repeatable evaluation system that measures whether chunking, retrieval, filtering, and reranking changes actually improve results.

### What we will learn

- Ground-truth relevance judgements.
- Recall@K, MRR, and nDCG.
- Query-set design.
- Hard negatives.
- Regression testing.
- Why answer evaluation cannot replace retrieval evaluation.

### Development steps

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

### UI work

Create an evaluation dashboard with:

- Experiment selector.
- Aggregate metrics.
- Per-language metrics.
- Per-query-type metrics.
- Failed cases.
- Side-by-side ranking comparison.
- Latency distribution.

### Exit criteria

- An evaluation run is reproducible from a committed configuration.
- Chunking and retrieval choices are backed by measurements.
- At least one failure analysis produces an explainable improvement.
- The selected baseline is recorded for future regression checks.

### Required ADR

`ADR-0010: Retrieval evaluation dataset, metrics, and release gates`

Decision questions:

- Why these query categories?
- Why these metrics?
- How is ground truth created?
- What metric thresholds block a regression?

---

## Phase 11 — Grounded answer generation with Pydantic AI

### Objective

Add answer generation on top of the evaluated retrieval service while enforcing typed output, citations, uncertainty, and abstention.

### What we will learn

- Separating retrieval from generation.
- Prompt construction.
- Structured LLM output.
- Citation validation.
- Provider abstraction.
- Grounded abstention.
- Prompt-injection boundaries.

### Development steps

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

### UI work

Connect the chat shell to stateless question answering:

- User message.
- Loading stages: rewriting, retrieving, reranking, generating.
- Assistant answer.
- Inline citations.
- Source cards.
- Abstention state.
- Retrieval-debug link.

### Tests

- Typed output validation.
- Invented chunk ID is rejected.
- Empty evidence causes abstention.
- Unsupported question causes abstention.
- Retrieved instruction-like text cannot alter system behaviour.
- Model provider is replaceable in tests.

### Exit criteria

- Answers use the evaluated retrieval service.
- Every citation points to retrieved evidence.
- Unsupported questions abstain.
- The chat UI can display a complete answer and sources.

### Required ADR

`ADR-0011: Deterministic RAG generation boundary and Pydantic AI`

Decision questions:

- Why Pydantic AI?
- Why keep retrieval outside the agent loop?
- What is the answer schema?
- How are citations and abstention validated?

---

## Phase 12 — Conversation management

### Objective

Add persistent multi-turn conversations without allowing chat history to become an unverified knowledge source.

### What we will learn

- Conversation data modelling.
- Follow-up query rewriting.
- Short-term context management.
- History summarization.
- Database migrations.
- Separating memory from evidence.

### Development steps

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

### UI work

Add:

- New conversation.
- Conversation list.
- Conversation title.
- Reload previous messages.
- Delete conversation.
- Display original and rewritten query in debug mode.

### Tests

- Follow-up pronoun resolution.
- Topic change resets retrieval intent appropriately.
- Conversation isolation.
- Old message reload.
- Deleted conversation behaviour.
- Assistant claims are not used as citations.

### Exit criteria

- Conversations survive application restart.
- Follow-up questions retrieve with a standalone query.
- Every historical answer remains linked to its original evidence and versions.
- Conversation state is isolated from the vector corpus.

### Required ADR

`ADR-0012: PostgreSQL conversation persistence and bounded chat memory`

Decision questions:

- Why PostgreSQL?
- Why rewrite follow-ups?
- How much history is retained in active context?
- Why is conversation memory not evidence?

---

## Phase 13 — Complete streaming chat experience

### Objective

Turn the functional RAG backend into a polished, transparent chat experience with structured streaming and evidence inspection.

### What we will learn

- Server-Sent Events.
- Streaming lifecycle and cancellation.
- Structured UI events.
- Optimistic and error states.
- Evidence-focused UX.
- Accessibility and responsive design.

### Development steps

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

### Tests

- Stream event ordering.
- Partial-answer cancellation.
- Citation-source expansion.
- Conversation reload.
- Filter submission.
- Error rendering.
- End-to-end happy path in a browser.

### Exit criteria

- The UI supports a complete multi-turn conversation.
- Answers stream without losing structured citations.
- Source evidence is one click away.
- Retrieval diagnostics are available but do not overwhelm normal users.

### Required ADR

`ADR-0013: Structured SSE protocol and evidence-centred chat UX`

Decision questions:

- Why Server-Sent Events rather than WebSockets?
- What events are part of the public contract?
- How are citations represented during streaming?
- Which diagnostics are user-facing versus developer-only?

---

## Phase 14 — Testing, security, and abuse resistance

### Objective

Create confidence that the system behaves correctly under malformed input, retrieval regressions, prompt injection, service failures, and rights constraints.

### What we will learn

- Test pyramid design.
- Contract and integration testing.
- RAG-specific security threats.
- Prompt injection through retrieved documents.
- Licence enforcement.
- Rate limiting and request validation.
- Dependency and secret hygiene.

### Development steps

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

### UI work

- Safe Markdown rendering.
- Clear rate-limit and validation errors.
- Conversation deletion.
- Privacy notice for stored messages.
- No automatic loading of untrusted external content.

### Exit criteria

- The deterministic end-to-end fixture passes.
- Adversarial retrieval tests pass.
- Licence restrictions are enforced.
- User conversations are isolated or the application is explicitly single-user.
- The threat model and residual risks are documented.

### Required ADR

`ADR-0014: RAG security boundary, rights enforcement, and test strategy`

Decision questions:

- What content is untrusted?
- What can retrieved text influence?
- How are licences enforced?
- Which tests are required before deployment?

---

## Phase 15 — Observability, CI/CD, and production deployment

### Objective

Make the system deployable, diagnosable, recoverable, and version-aware without changing the understandable local development experience.

### What we will learn

- Container builds.
- CI/CD gates.
- Logs, metrics, and traces.
- Production configuration.
- Data and index version rollouts.
- Scheduled ingestion.
- Backups and recovery.
- Cost and latency monitoring.

### Development steps

1. Add production Dockerfiles for backend and frontend.
2. Run containers as non-root users.
3. Add liveness and readiness health checks.
4. Configure production settings through environment variables or a secret manager.
5. Add structured logs with request, conversation, retrieval, and ingestion trace IDs.
6. Instrument:
   - HTTP calls.
   - Retrieval stages.
   - Reranking.
   - LLM calls.
   - Database queries.
7. Track operational metrics:
   - Ingestion success rate.
   - Empty OCR rate.
   - Indexed chunks.
   - Search latency.
   - Reranker latency.
   - Answer latency.
   - Zero-result rate.
   - Abstention rate.
   - Citation coverage.
   - LLM tokens and cost.
8. Create GitHub Actions for:
   - Dependency lock validation.
   - Linting.
   - Type checking.
   - Unit and integration tests.
   - Retrieval regression fixture.
   - Frontend type check and build.
   - Container builds.
9. Move large Bronze, Silver, and Gold artefacts to object storage in production.
10. Use persistent or managed Qdrant and PostgreSQL.
11. Introduce index aliases or equivalent version switching.
12. Validate a new index before switching traffic.
13. Schedule incremental ingestion.
14. Define backup and restore procedures.
15. Perform a basic load test.
16. Write a deployment runbook.

### UI work

Add an operations view restricted to appropriate users:

- Service status.
- Active versions.
- Recent ingestion/indexing runs.
- Error rates.
- Latency.
- Retrieval and answer usage.

### Exit criteria

- A clean deployment can be produced from committed code and configuration.
- CI blocks known regressions.
- Active data and model versions are visible.
- Backup and rollback procedures are documented and tested at least once.
- A public demo has rate limits and safe secret handling.

### Required ADR

`ADR-0015: Deployment topology, observability, and versioned index rollout`

Decision questions:

- Which services run separately in production?
- Where are raw data, Qdrant, and PostgreSQL hosted?
- How is a new index released and rolled back?
- Which signals are required to diagnose a bad answer?

---

## Phase 16 — Portfolio packaging and technical defence

### Objective

Turn the working system into a clear engineering narrative that demonstrates knowledge, measurements, trade-offs, and limitations.

### What we will learn

- Technical storytelling.
- Reproducibility for reviewers.
- Communicating architectural trade-offs.
- Presenting evaluation honestly.
- Separating demonstrated capability from future ideas.

### Development steps

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

### Exit criteria

- A reviewer can run a small demo using documented commands.
- Architecture and important decisions are visible.
- Evaluation results are reproducible.
- Limitations and trade-offs are stated honestly.
- The repository tells a coherent story without requiring the developer to explain basic navigation.

### Required ADR

`ADR-0016: Reproducible portfolio distribution and demonstration scope`

Decision questions:

- What sample data is included?
- What does the default demo run?
- Which evaluation results are published?
- What is deliberately excluded from the portfolio release?

---

## Optional extension — Agentic RAG with LangGraph

This extension begins only after the deterministic baseline is complete and evaluated.

Potential graph:

```text
classify question
→ rewrite query
→ retrieve
→ judge evidence sufficiency
→ answer, abstain, or reformulate and retry
→ validate citations
```

The extension must be compared against the baseline using the same evaluation dataset. It is retained only if it produces a meaningful improvement that justifies additional latency, model calls, state, and operational complexity.

A separate ADR should be created if this extension is implemented.

---

## 8. Daily development workflow

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
docker compose -f infra/compose.yaml up -d

Set-Location backend
uv sync --locked
uv run pytest
uv run uvicorn heritage_rag.api.main:app --reload

Set-Location ..\frontend
npm install
npm run dev
```

Exact commands in the README are authoritative once the corresponding phase is implemented.

---

## 9. Git workflow

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

## 10. Environment and secret policy

Commit `.env.example`, never `.env`.

Expected variables will grow by phase. A likely final set is:

```dotenv
APP_ENV=local
LOG_LEVEL=INFO

WELLCOME_CATALOGUE_BASE_URL=https://api.wellcomecollection.org/catalogue/v2
DATA_ROOT=../data

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=heritage-rag-chunks

DATABASE_URL=postgresql+psycopg://heritage:heritage@localhost:5432/heritage

LLM_MODEL=provider:model-name
LLM_API_KEY=
```

Only add a variable when code uses it. Tests should use safe overrides and must not require production credentials.

---

## 11. Definition of done for the complete project

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

## 12. Final learning principle

At every phase, the primary question is not merely “does it run?” It is:

> Can I explain what this component does, why it exists, what alternative we rejected, how we tested it, and what evidence would make us change the decision?

If the answer is no, the phase is not complete yet.
