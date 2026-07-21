# Project status

## Current state

- Last completed phase: Phase 2 — Environment and repository setup
- Active phase: Phase 3 — UI foundation and progress dashboard
- Current branch: `main`
- Dataset size: 0 works; no corpus has been selected or ingested
- Active index version: None
- Last successful command: `pnpm build` for the Phase 3 frontend prototype

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

## Verification results

- Tests: 14 backend tests pass.
- Linting: Ruff and strict mypy pass for the Phase 2 backend; `git diff --check`
  passes for the current changes.
- Frontend: the Vite production build passes; desktop and mobile interactions
  were checked during the prototype build.
- Manual checks: health API, CLI, Docker Compose, responsive navigation, data
  explorer states, and the chat placeholder have been exercised.
- Metrics: Not measured. Every numeric value is labelled as an initial target.

## Important decisions

- [ADR-0001: Project scope and evidence contract](adr/0001-project-scope-and-evidence-contract.md)
- [ADR-0002: Python, dependency management, and repository structure](adr/0002-python-dependency-management-and-repository-structure.md)
- The initial answer contract requires page-bearing evidence even for
  bibliographic claims; metadata-only citations are a documented revisit point.
- English is an evaluated baseline. French and Dutch require their own reviewed
  evaluation slices before release.
- Retrieval and generation remain separate deterministic boundaries until an
  evaluated alternative justifies additional complexity.

## Known limitations

- The frontend is not yet served by FastAPI; Vite remains the development and
  build boundary until the next integration step.
- The hosted UI is a frontend-only prototype and cannot reach the local API.
- No ingestion, search, retrieval, or answer-generation capability exists yet.
- No corpus, evaluation set, index, model, prompt, or empirical baseline exists.
- OCR and printed-page/canvas mapping behaviour is specified but untested.
- The strict page-evidence rule may abstain on facts available only in catalogue
  metadata.
- Numeric success targets are hypotheses to tune after reproducible evaluation,
  not claims of product performance.

## Next phase

- Phase: [Phase 3 — UI foundation and progress dashboard](building_phases/phase-03-ui-foundation-and-progress-dashboard.md)
- Entry conditions:
  - Phase 2 implementation and ADR are accepted.
  - The backend health endpoints and frontend production build pass.
  - The frontend uses `/health/ready` as its same-origin API contract.
- First intended task: Mount the built frontend in FastAPI while preserving the
  existing health routes and testability when frontend assets are absent.

## Next-chat reading order

1. [README](../README.md)
2. [Scope and evidence contract](scope-and-evidence-contract.md)
3. [Architecture](architecture.md)
4. [ADR-0002](adr/0002-python-dependency-management-and-repository-structure.md)
5. [Phase roadmap](building_phases/README.md)
6. [Development and learning agreement](learning-guide-agreement.md)
