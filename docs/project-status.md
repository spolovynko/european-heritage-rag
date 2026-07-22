# Project status

## Current state

- Last completed phase: Phase 3 — UI foundation and progress dashboard
- Active phase: Phase 4 — Wellcome discovery and ingestion client
- Current branch: `main`
- Dataset size: 0 works; no corpus has been selected or ingested
- Active index version: None
- Last successful checkpoint: the complete Phase 3 Python, frontend, and
  container verification suite passed on 2026-07-22
- Unrelated working-tree state: `frontend/.openai/hosting.json` has a pending
  deletion that must not be included implicitly in Phase 4 work

## Completed capabilities

- Defined a standalone product statement and three user personas.
- Bounded the initial corpus to English, public-domain, digitised Wellcome books
  with usable OCR and page provenance.
- Defined supported exact lookup, filtered search, passage, comparison,
  follow-up, and unanswerable question behaviour.
- Defined substantial claims, valid evidence, valid page-level citations,
  partial answers, and mandatory abstention cases.
- Separated retrieval-quality goals from answer-quality goals.
- Recorded measurable but not-yet-achieved targets for Recall@10, citation
  coverage/validity/support, abstention, and search latency.
- Documented ten example questions with evidence expectations, including two
  deliberately unanswerable cases.
- Documented the deterministic two-step RAG boundary and low-fidelity chat,
  source-panel, and pipeline-dashboard sketch.
- Accepted ADR-0001 and indexed it.
- Established the Python 3.12 and `uv` development environment.
- Added typed settings, structured logging, liveness and readiness endpoints,
  a version CLI, automated checks, and a one-service container baseline.
- Added a responsive frontend prototype with chat, ingestion, data, retrieval,
  and evaluation workspaces backed by explicit demo data.
- Connected the frontend status indicator to `/health/ready` through a stable
  same-origin API path.
- Accepted ADR-0002 and added the Phase 2 implementation guide.
- Served the Vite production build from FastAPI while preserving the existing
  health endpoints and backend startup when frontend assets are absent.
- Added a locked pnpm/Vite frontend workflow and a multi-stage Docker image
  that builds the frontend without carrying Node into the Python runtime.
- Added temporary-directory tests for frontend delivery, preserved API routes,
  and missing frontend assets.
- Accepted ADR-0003 and added the Phase 3 implementation guide.

## Verification results

- Tests: 16 backend tests pass.
- Linting and typing: Ruff check, Ruff formatting check, strict mypy, and
  `git diff --check` pass.
- Frontend: locked pnpm installation and the Vite production build pass;
  desktop and mobile interactions were checked during the prototype build.
- Container: the multi-stage image builds, Docker Compose reports the API
  healthy, and both `/` and `/health/ready` return HTTP 200.
- Manual checks: health API, CLI, Docker Compose, responsive navigation, data
  explorer states, and the chat placeholder have been exercised.
- Metrics: Not measured. Every numeric value is labelled as an initial target.

## Important decisions

- [ADR-0001: Project scope and evidence contract](adr/0001-project-scope-and-evidence-contract.md)
- [ADR-0002: Python, dependency management, and repository structure](adr/0002-python-dependency-management-and-repository-structure.md)
- [ADR-0003: Browser-native UI foundation and same-origin FastAPI delivery](adr/0003-browser-native-ui-and-fastapi-delivery.md)
- The initial answer contract requires page-bearing evidence even for
  bibliographic claims; metadata-only citations are a documented revisit point.
- English is an evaluated baseline. French and Dutch require their own reviewed
  evaluation slices before release.
- Retrieval and generation remain separate deterministic boundaries until an
  evaluated alternative justifies additional complexity.
- Browser-native HTML, CSS, and JavaScript remain the UI baseline until real
  feature complexity justifies React and TypeScript.
- Local development and the container runtime use the same relative API paths;
  FastAPI serves the production frontend and API from one origin.

## Known limitations

- No ingestion, search, retrieval, or answer-generation capability exists yet.
- No corpus, evaluation set, index, model, prompt, or empirical baseline exists.
- Ingestion, catalogue, OCR, retrieval, and evaluation values shown in the UI
  remain explicitly labelled demonstration data.
- Browser JavaScript is not statically typed, and there are no automated
  frontend unit or browser tests yet.
- FastAPI static delivery does not provide production CDN caching,
  compression, or independent frontend scaling.
- OCR and printed-page/canvas mapping behaviour is specified but untested.
- The strict page-evidence rule may abstain on facts available only in catalogue
  metadata.
- Numeric success targets are hypotheses to tune after reproducible evaluation,
  not claims of product performance.

## Next phase

- Phase: [Phase 4 — Wellcome discovery and ingestion client](building_phases/phase-04-wellcome-discovery-and-ingestion-client.md)
- Entry conditions:
  - Phase 3 implementation, ADR, implementation guide, and verification are
    complete.
  - The Python checks, Vite production build, and combined Docker application
    pass.
  - The current UI has a clearly isolated demonstration ingestion boundary to
    replace with real progress.
  - No corpus has been ingested and no Phase 4 source client exists yet.
- First intended task: align Phase 4 dependencies with the existing HTTPX2
  baseline, add resilient Wellcome configuration, and introduce narrow typed
  catalogue and IIIF source models backed by offline fixtures.

## Next-chat reading order

1. [README](../README.md)
2. [Scope and evidence contract](scope-and-evidence-contract.md)
3. [Architecture](architecture.md)
4. [Phase 3 implementation guide](building_guides/phase-03-ui-foundation-and-progress-dashboard.md)
5. [ADR-0003](adr/0003-browser-native-ui-and-fastapi-delivery.md)
6. [Phase 4 plan](building_phases/phase-04-wellcome-discovery-and-ingestion-client.md)
7. [Development and learning agreement](learning-guide-agreement.md)
