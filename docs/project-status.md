# Project status

## Current state

- Last completed phase: Phase 5 — Bronze data layer
- Next phase: Phase 6 — Silver normalization and OCR cleaning
- Current branch: `main`
- Persisted local Bronze corpus: 5 works and 310 immutable resources from the
  verified `cholera` acceptance run
- Live run ID: `0e96cc69c1cf4124bf61e1bf2242a4ca`
- Active index version: None
- Last successful closure gate: complete Phase 5 Python, frontend, live-source,
  browser, and container verification on 2026-07-23

## Completed capabilities

### Product, environment, and browser foundation

- The product scope, evidence contract, supported questions, abstention rules,
  and future quality targets are documented.
- Python 3.12, `uv`, typed settings, structured logging, FastAPI health routes,
  Typer CLI, Ruff, mypy, pytest, Vite, pnpm, Docker, and Compose are reproducible.
- A responsive browser-native diagnostic application is built with same-origin
  API calls and served by FastAPI.

### Wellcome discovery and traversal

- A narrow tolerant Wellcome catalogue and IIIF client discovers English,
  online, Public Domain Mark books in stable source order.
- HTTP calls use bounded timeouts, retry classification, capped exponential
  backoff, and retry accounting.
- Typed traversal preserves ordered OCR lines, treats missing OCR as visible
  nonfailure state, and isolates terminal failures per work.
- Work-level checkpoints, matching resume, atomic status, CLI ingestion, status
  API, and dashboard polling are operational.

### Bronze data layer

- `BRONZE_DATA_DIRECTORY` configures the generated corpus root and defaults to
  `data/bronze`.
- Strict immutable Pydantic contracts define run identity, deterministic
  resource identity/path, acquisition parameters, resource receipts, failure
  history, and whole-manifest consistency.
- The filesystem store writes raw resources through synchronized temporary
  siblings, exposes only complete files, calculates SHA-256, recognizes
  identical content, and rejects changed content at an existing identity.
- Mutable run manifests are atomically replaced as complete validated ledgers.
- Selected catalogue work JSON retains unknown source fields; IIIF manifests
  and OCR annotation lists retain exact HTTP response bytes.
- The ingestion runner records source payloads and receipts as they arrive,
  reconciles Bronze with Phase 4 resume state, retains retry history, and writes
  honest terminal status.
- Offline validation checks existence, byte length, hash, JSON, expected source
  model, inventory coverage, and temporary-file cleanup.
- `bronze inspect` and `bronze validate` support all runs or one run ID.
- Read-only `/bronze` API routes list runs, return one manifest, and resolve one
  manifest-declared raw resource without accepting filesystem paths.
- The Data workspace is a real Bronze explorer with run summary, unresolved
  failures, search/type filtering, provenance, source links, and raw JSON
  preview.
- Local `data/` is ignored. The image prepares `/app/data/bronze` for UID 10001,
  and Compose persists it through the `bronze-data` named volume.
- ADR-0005 and the Phase 5 implementation guide record the design and every
  implementation step.

## Verification results

### Automated

- Tests: 95 passed in the final full run.
- Lint/format: Ruff check and Ruff format check passed.
- Types: mypy reported no issues in 19 source files.
- Frontend: Vite production build passed.
- Compose: `docker compose config --quiet` passed.
- Container: `european-heritage-rag:phase5` built successfully.

### Live Bronze acceptance

- Command: `uv run european-heritage-rag ingest wellcome --limit 5 --query cholera`
- Result: 5/5 works completed, 300 canvases traversed, 6 canvases without OCR,
  zero retries, and zero terminal failures.
- Inventory: 5 catalogue works, 5 IIIF manifests, 300 annotation lists, 310
  immutable resources total, plus one run manifest.
- Size: 5,188,796 bytes including the run manifest.
- Offline replay: `bronze validate` accepted all 310 declared resources.
- Idempotency: resume retained 310 resources and the complete sorted resource
  ID/path/SHA-256 inventory was unchanged.

### Browser and container

- Desktop rendered the live run and decoded resource JSON; filtering for
  catalogue work returned exactly five resources.
- At 390 × 844 the explorer had no horizontal overflow and used responsive run,
  summary, list, and detail layouts.
- Browser console inspection found no warnings or errors.
- Compose became healthy, ran as UID 10001, returned HTTP 200, and confirmed
  `/app/data/bronze` was writable through its named volume.

## Important decisions

- [ADR-0001: Project scope and evidence contract](adr/0001-project-scope-and-evidence-contract.md)
- [ADR-0002: Python, dependency management, and repository structure](adr/0002-python-dependency-management-and-repository-structure.md)
- [ADR-0003: Browser-native UI foundation and same-origin FastAPI delivery](adr/0003-browser-native-ui-and-fastapi-delivery.md)
- [ADR-0004: Wellcome API and IIIF ingestion strategy](adr/0004-wellcome-api-and-iiif-ingestion-strategy.md)
- [ADR-0005: Append-only Bronze storage and idempotent ingestion](adr/0005-append-only-bronze-storage-and-idempotent-ingestion.md)
- Preserve evidence before interpretation: cleaning and canonicalization begin
  only in Silver.
- Treat raw resource files as immutable and the run manifest as a progressing
  atomically replaced ledger.
- Define idempotent resume as an unchanged resource ID/path/hash inventory for
  the same run and acquisition parameters.
- Use one concrete local filesystem store until deployment provides evidence
  for object storage.

## Known limitations

- Bronze assumes one writer per run and one shared filesystem.
- The full manifest is rewritten after every receipt or lifecycle event.
- Raw JSON is uncompressed.
- Catalogue work data is lossless JSON but not a byte copy of the full
  catalogue page.
- The API returns complete run manifests and has no pagination yet.
- Resume is work-granular; an interruption inside a work can repeat network
  traversal for that work while immutable writes remain protected.
- Traversal uses the first IIIF sequence and does not normalize printed page
  numbers.
- English remains the only discovery language.
- Browser acceptance is manual; no automated frontend unit or end-to-end suite
  exists.
- No canonical works/pages, cleaned OCR, Parquet, chunks, embeddings, retrieval,
  generation, citations, evaluation, or working chat answers exist yet.

## Next phase

- Phase: [Phase 6 — Silver normalization and OCR cleaning](building_phases/phase-06-silver-normalization-and-ocr-cleaning.md)
- Entry conditions satisfied:
  - five complete works exist in validated Bronze;
  - every resource has source URL, acquisition time, path, size, and hash;
  - source shapes can be parsed offline without Wellcome;
  - idempotent resume has been proven against a live run;
  - operator, browser, and container paths can inspect the same manifest.
- First intended task: define canonical `Work` and `Page` models and exact
  Bronze-to-Silver lineage before implementing conservative OCR-cleaning
  functions.

## Next-chat reading order

1. [README](../README.md)
2. [Scope and evidence contract](scope-and-evidence-contract.md)
3. [Architecture](architecture.md)
4. [Phase 5 implementation guide](building_guides/phase-05-bronze-data-layer.md)
5. [ADR-0005](adr/0005-append-only-bronze-storage-and-idempotent-ingestion.md)
6. [Phase 6 plan](building_phases/phase-06-silver-normalization-and-ocr-cleaning.md)
7. [Development and learning agreement](learning-guide-agreement.md)
