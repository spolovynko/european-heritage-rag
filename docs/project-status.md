# Project status

## Current state

- Last completed phase: Phase 4 - Wellcome discovery and ingestion client
- Active phase: Phase 5 - Bronze data layer
- Current branch: `main`
- Persisted corpus size: 0 works; Phase 4 traverses source data but does not
  retain Bronze payloads
- Last bounded source smoke test: 5/5 works completed, 246 canvases traversed,
  14 canvases without OCR, 0 retry waits, and 0 terminal failures
- Active index version: None
- Last successful closure gate: the complete Phase 4 Python, frontend, browser,
  live-source, and container verification passed on 2026-07-22

## Completed capabilities

### Product and evidence boundary

- Defined the product statement, user personas, initial English public-domain
  Wellcome book scope, supported question types, and unanswerable cases.
- Defined substantial claims, page-level evidence, valid citations, partial
  answers, and abstention behavior.
- Separated retrieval-quality goals from answer-quality goals and recorded
  measurable targets as future goals rather than achieved metrics.
- Recorded the deterministic two-step RAG baseline in ADR-0001.

### Environment and delivery foundation

- Established Python 3.12, `uv`, a root `src` layout, typed Pydantic settings,
  structured logging, FastAPI liveness/readiness, a Typer CLI, and automated
  Ruff/mypy/pytest checks.
- Added a reproducible multi-stage image and one-service Docker Compose runtime
  under an unprivileged user.
- Recorded the environment and repository choices in ADR-0002.

### Browser application foundation

- Added a responsive browser-native HTML/CSS/JavaScript application built with
  Vite and a locked pnpm dependency graph.
- Served the Vite production build from FastAPI while preserving API routes and
  backend startup without frontend assets.
- Connected system status to `/health/ready` through a same-origin relative
  path.
- Added chat, ingestion, data, retrieval, and evaluation workspaces with clear
  demonstration boundaries.
- Recorded this delivery decision in ADR-0003.

### Wellcome discovery and traversal

- Added validated settings for the catalogue URL, User-Agent, four timeouts,
  retry attempts/waits, and ingestion state directory. Environment variables
  can override every default.
- Added narrow tolerant Pydantic models for catalogue pages, works, digital
  locations, IIIF Presentation 2 manifests, canvases, OCR annotation lists,
  traversed pages, and traversed works.
- Added an offline fixture set for catalogue, manifest, and OCR shapes,
  including observed optional physical-location and picture-annotation
  variants.
- Added a reusable `httpx2` client with redirects, connection pooling, bounded
  timeouts, retry classification, capped exponential backoff, numeric
  `Retry-After`, and retry counting.
- Added server filters and local validation for English, online,
  public-domain-marked books with an IIIF Presentation location.
- Added source-order pagination, manifest selection, first-sequence canvas
  traversal, ordered annotation retrieval, and exact OCR line preservation.
- Treats missing OCR as a visible nonfailure and failed referenced resources as
  terminal work errors.
- Added sequential run orchestration with per-work failure isolation, atomic
  JSON status, work-granular checkpoints, option fingerprints, dry-run, and
  resume.
- Added `european-heritage-rag ingest wellcome` with `--limit`, `--query`,
  `--language`, `--resume`, and `--dry-run`.
- Added `GET /ingestion/status` and connected the ingestion dashboard to it
  with safe three-second polling.
- Added a persistent Compose volume for status and checkpoints.
- Recorded the source strategy in ADR-0004 and added the detailed Phase 4
  building guide.

## Verification results

- Dependencies: `uv sync --locked` passed with 43 packages checked.
- Tests: 53 backend tests passed in the final full run.
- Linting and typing: Ruff check, Ruff formatting check, strict mypy over 13
  source files, and `git diff --check` passed.
- Frontend: the Vite production build passed.
- Browser: real ingestion state rendered correctly at 1280 px and 390 px;
  the mobile view had no horizontal scroll and the browser reported no console
  warnings or errors.
- Live source: a five-work `cholera` run completed all 5 works and traversed 246
  canvases; 14 canvases had no OCR, with 0 retries and 0 terminal failures.
- Resume: a matching checkpoint resumed successfully, skipping completed work
  IDs and retrying prior failures.
- Container: the Phase 4 image built, Compose became healthy, `/` and
  `/health/ready` returned HTTP 200, `/ingestion/status` returned an idle
  typed response before the first volume run, and a containerized dry run wrote
  status through the named volume as the unprivileged user.
- Metrics: retrieval, citation, answer-quality, abstention, and latency targets
  remain unmeasured.

## Important decisions

- [ADR-0001: Project scope and evidence contract](adr/0001-project-scope-and-evidence-contract.md)
- [ADR-0002: Python, dependency management, and repository structure](adr/0002-python-dependency-management-and-repository-structure.md)
- [ADR-0003: Browser-native UI foundation and same-origin FastAPI delivery](adr/0003-browser-native-ui-and-fastapi-delivery.md)
- [ADR-0004: Wellcome API and IIIF ingestion strategy](adr/0004-wellcome-api-and-iiif-ingestion-strategy.md)
- Use supported Wellcome catalogue and IIIF APIs rather than scraping public
  pages.
- Start with small API harvesting rather than the daily catalogue snapshot.
- Restrict the first source slice to English online books with a Public Domain
  Mark and an IIIF Presentation location.
- Traverse sequentially until measurement justifies bounded concurrency.
- Preserve OCR lines exactly during ingestion; cleaning belongs to Silver.
- Keep Phase 4 status/checkpoints separate from Phase 5 Bronze source payloads.
- Keep the CLI as the ingestion write boundary; API and browser read the same
  persisted status.
- Continue using relative same-origin browser API paths.

## Known limitations

- No raw catalogue, manifest, annotation, or OCR payload is persisted yet.
- The corpus remains empty and cannot be replayed without the network until
  Phase 5 is complete.
- Resume is work-granular; interruption inside a book repeats that book.
- File-backed status assumes one local writer and one shared filesystem.
- Traversal uses the first IIIF sequence and does not normalize printed page
  numbers.
- `pages_downloaded` means canvases traversed, not durable files stored.
- Numeric `Retry-After` is handled; HTTP-date values fall back to exponential
  delay.
- English is the only supported discovery language.
- The browser uses polling and has manual browser acceptance but no automated
  frontend unit or end-to-end suite.
- Search, retrieval, generation, citations, evaluation, and chat answers do
  not exist yet.
- The strict page-evidence rule may abstain on facts only present in catalogue
  metadata.

## Next phase

- Phase: [Phase 5 - Bronze data layer](building_phases/phase-05-bronze-data-layer.md)
- Entry conditions satisfied:
  - eligible works can be discovered through a narrow typed client;
  - manifests and OCR annotations can be traversed in source order;
  - missing OCR is represented without crashing the run;
  - retries, per-work failures, checkpoints, and matching resume are tested;
  - the CLI, status API, dashboard, and container state volume are operational;
  - five current live works were traversed successfully;
  - Phase 4 ADR, building guide, and closure verification are complete.
- First intended task: define immutable Bronze identities and paths for raw
  catalogue records, manifests, annotation lists, and acquisition metadata,
  then make the current traversal write those payloads without cleaning them.

## Next-chat reading order

1. [README](../README.md)
2. [Scope and evidence contract](scope-and-evidence-contract.md)
3. [Architecture](architecture.md)
4. [Phase 4 implementation guide](building_guides/phase-04-wellcome-discovery-and-ingestion-client.md)
5. [ADR-0004](adr/0004-wellcome-api-and-iiif-ingestion-strategy.md)
6. [Phase 5 plan](building_phases/phase-05-bronze-data-layer.md)
7. [Development and learning agreement](learning-guide-agreement.md)
