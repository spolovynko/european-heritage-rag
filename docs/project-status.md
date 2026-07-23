# Project status

## Current state

- Last completed phase: Phase 6 — Silver normalization and OCR cleaning
- Next phase: Phase 7 — Gold data layer and chunking experiments
- Current branch: `main`
- Largest persisted local Bronze corpus: 20 works, 1,670 canvases, and 1,710
  immutable resources
- Largest Bronze run ID: `9f2423adf01746d7baca5c0a504b5b2f`
- Active Silver development dataset:
  `73eb5f4fd79ded1e68dd8a341e0f5270924619777eea3f4523b19b6b3718c5d5`
- Active Silver size: 20 works and 1,670 pages
- Active index version: None
- Last successful closure gate: complete Phase 6 Python, frontend, live-source,
  browser, and container verification on 2026-07-23

## Completed capabilities

### Product, environment, and browser foundation

- Product scope, evidence contract, supported questions, abstention rules, and
  future evaluation goals are documented.
- Python 3.12, `uv`, Pydantic settings, structured logging, FastAPI, Typer,
  Ruff, mypy, pytest, Vite, pnpm, Docker, and Compose are reproducible.
- A responsive browser-native diagnostic application is built with same-origin
  API calls and served by FastAPI.

### Wellcome discovery and Bronze evidence

- Bounded English public-domain Wellcome discovery and sequential IIIF
  traversal use timeouts, classified retries, atomic progress, and work-level
  resume.
- New catalogue acquisition includes contributors, production, subjects, and
  genres while legacy Bronze manifests remain valid.
- Source models also capture IIIF page images and services.
- Bronze preserves selected catalogue work JSON, exact IIIF manifests, exact
  OCR annotation-list responses, source URLs, timestamps, paths, sizes, and
  SHA-256 receipts.
- Immutable atomic resource writes, append-only failure history, complete run
  manifests, offline validation, CLI/API inspection, and the Bronze explorer
  remain operational.

### Silver canonical data

- `SILVER_DATA_DIRECTORY` configures the generated Silver root.
- Strict immutable Pydantic contracts define canonical works, pages,
  contributors, lineage, file receipts, quality reports, dataset manifests,
  and validation issues.
- Work metadata is stored once; page OCR, labels, images, quality, and
  annotation evidence are stored per canvas.
- Every work records catalogue/manifest lineage. Every page records manifest
  and contributing annotation lineage.
- Empty OCR canvases remain canonical pages with explicit `missing` quality.
- Page and dataset IDs are deterministic hashes of stable source identities,
  content inventories, and versioned transform rules.

### OCR normalization and quality

- Raw OCR is reconstructed in source line order and never overwritten.
- Clean OCR applies Unicode NFC, parser-based HTML removal, horizontal
  whitespace normalization, paragraph-preserving line joins, and conservative
  lowercase-continuation dehyphenation.
- Work-level repeated header/footer detection uses normalized first/last
  non-empty lines, a minimum of three pages, and a 15% threshold.
- Page/work flags expose missing metadata, source anomalies, review heuristics,
  and every applied cleaning behavior.
- `missing`, `needs_review`, and `usable` are broad operator queues, not OCR
  accuracy claims.
- JSON and Markdown reports aggregate page bands, flags, mean clean words,
  language counts, per-work summaries, and processing failures.

### Parquet publication and validation

- Polars writes explicit nested schemas to Zstandard-compressed
  `works.parquet` and `pages.parquet`.
- Each data/report file is synchronized and atomically replaced, then recorded
  by byte length and SHA-256.
- `silver-manifest.json` is published last as the completeness marker.
- Existing valid deterministic datasets are reused rather than rewritten.
- Offline validation checks file integrity, temporary files, Polars/PyArrow
  schemas, Pydantic row round-trips, unique IDs, page-to-work references, and
  count reconciliation.

### Operator, API, browser, and container paths

- `silver build`, `silver inspect`, and `silver validate` operate on exact run
  or dataset IDs.
- Read-only `/silver` routes list datasets and works, return filtered/paginated
  page summaries, return one full page, and return quality evidence.
- The Data workspace switches between Bronze and Silver.
- The Silver inspector shows dataset counters, languages, average words,
  failures, work metadata, image, raw/clean OCR, quality flags, detected
  boundaries, source links, and exact lineage.
- The image runs as UID 10001 and prepares `/app/data/silver`. Compose persists
  it in a separate `silver-data` named volume.
- ADR-0006 and the Phase 6 guide record the design, implementation steps,
  measured results, and trade-offs.

## Verification results

### Automated

- Tests: 115 passed.
- Format/lint: Ruff format check and Ruff check passed.
- Types: strict mypy reported no issues in 26 source files.
- Frontend: Vite production build passed.
- Compose: `docker compose config --quiet` passed.
- Container: `european-heritage-rag:phase6` built successfully, became healthy,
  and returned HTTP 200 from `/health/ready` and `/silver/datasets`.

### Existing five-work replay

- Bronze run: `0e96cc69c1cf4124bf61e1bf2242a4ca`
- Bronze validation: all 310 declared resources valid.
- Silver: 5 works and 300 pages.
- Quality: 6 missing, 80 needing review, 214 usable.
- Dataset:
  `21bc031c562fe4b2c14552a8452ba5b7e1af3687c469e050a20c58e31d60ab09`
- Repeat build status: reused.
- Purpose: proved legacy Bronze input remains replayable.

### Fresh enriched five-work acceptance

- Command:
  `uv run european-heritage-rag ingest wellcome --limit 5 --query cholera`
- Bronze run: `dd0eae25f9994c7597d28814a4848982`
- Result: 5/5 works, 246 canvases, 14 without OCR, zero work failures.
- Bronze validation: all 256 resources valid.
- Silver: 5 works and 246 pages.
- Quality: 14 missing, 10 needing review, 222 usable.
- Metadata: contributors and production on 5/5; subjects and genres on 4/5.
- Dataset:
  `4d042f4b68d9845bca80085929aed8fe6a55bd12ca242f8a8e0e716b491fbc6c`

### Twenty-work anomaly acceptance

- Command:
  `uv run european-heritage-rag ingest wellcome --limit 20 --query cholera`
- Bronze run: `9f2423adf01746d7baca5c0a504b5b2f`
- Result: 20/20 works, 1,670 canvases, 87 without OCR, zero work failures.
- Bronze validation: all 1,710 resources valid.
- Silver: 20 works and 1,670 pages.
- Quality: 87 missing, 129 needing review, 1,454 usable.
- Average clean words: 232.94 per page.
- Metadata: contributors, production, languages, and licence on 20/20;
  subjects on 18/20; genres on 17/20.
- Images and lineage: present on every page.
- Notable flags: 1,154 dehyphenated, 252 non-text annotations, 248 missing
  source page labels, 160 duplicate labels, 120 very short, 93 high symbol
  ratio, and 2 HTML removals.
- Confirmed repeated boundaries: none at the conservative version-one
  threshold.
- Dataset:
  `73eb5f4fd79ded1e68dd8a341e0f5270924619777eea3f4523b19b6b3718c5d5`
- Repeat build status: reused.

### Browser acceptance

- Loaded and reconciled the 20-work dataset and quality report.
- Displayed metadata, image, source link, raw/clean OCR, flags, and lineage.
- Dehyphenation filter returned 1,154 pages.
- Selected page showed 354 raw versus 352 clean characters and preserved the
  original line-ending split only in raw OCR.
- Bounded result label showed `Showing 500 of 1154 pages`.
- Browser console inspection found no errors.
- The browser pass found and fixed a shared data-attribute bug that had replaced
  the active list label with the page hash.

## Important decisions

- [ADR-0001: Project scope and evidence contract](adr/0001-project-scope-and-evidence-contract.md)
- [ADR-0002: Python, dependency management, and repository structure](adr/0002-python-dependency-management-and-repository-structure.md)
- [ADR-0003: Browser-native UI foundation and same-origin FastAPI delivery](adr/0003-browser-native-ui-and-fastapi-delivery.md)
- [ADR-0004: Wellcome API and IIIF ingestion strategy](adr/0004-wellcome-api-and-iiif-ingestion-strategy.md)
- [ADR-0005: Append-only Bronze storage and idempotent ingestion](adr/0005-append-only-bronze-storage-and-idempotent-ingestion.md)
- [ADR-0006: Canonical work/page schemas and conservative OCR cleaning](adr/0006-canonical-work-page-schemas-and-conservative-ocr-cleaning.md)
- Keep work metadata and page evidence separate and linked by `work_id`.
- Store raw and clean OCR together; cleaning never replaces evidence.
- Prefer conservative false negatives over destructive OCR “corrections.”
- Represent quality through explainable flags and broad review bands.
- Derive dataset identity from stable Bronze inventory plus rule versions.
- Publish atomic Parquet/report files and write the manifest last.

## Known limitations

- Header/footer detection examines only first/last non-empty lines and found no
  confirmed repeats in the 20-work live sample.
- Cleaning is not language-specific and quality bands are not measured OCR
  accuracy.
- Printed page parsing accepts decimal labels only.
- Multiple IIIF sequences, advanced page layout, columns, tables, handwriting,
  and image OCR are outside the current normalizer.
- The local API reads complete Parquet files and scans page details; it is not a
  large-corpus serving design.
- The browser caps one filtered page-list response at 500 and has no pagination
  controls.
- Bronze and Silver filesystem stores assume one writer per identity.
- Browser acceptance remains manual rather than an automated E2E suite.
- No chunks, tokenizer selection, embeddings, vector/sparse index, retrieval,
  answer generation, citations, evaluation, or working chat answers exist yet.

## Next phase

- Phase: [Phase 7 — Gold data layer and chunking experiments](building_phases/phase-07-gold-data-layer-and-chunking-experiments.md)
- Entry conditions satisfied:
  - a validated 20-work Silver dataset exists;
  - work/page contracts are source-independent and deterministic;
  - raw and clean OCR are available for comparison;
  - each page has ordered identity, quality, images, and exact lineage;
  - empty/suspicious pages remain visible;
  - repeat builds reuse unchanged input;
  - Parquet and manifest validation are offline and reproducible.
- First intended task: select the baseline embedding model’s tokenizer and
  define a versioned `ChunkingConfig` before implementing page-aware chunk
  accumulation.

## Next-chat reading order

1. [README](../README.md)
2. [Scope and evidence contract](scope-and-evidence-contract.md)
3. [Architecture](architecture.md)
4. [Phase 6 implementation guide](building_guides/phase-06-silver-normalization-and-ocr-cleaning.md)
5. [ADR-0006](adr/0006-canonical-work-page-schemas-and-conservative-ocr-cleaning.md)
6. [Phase 7 plan](building_phases/phase-07-gold-data-layer-and-chunking-experiments.md)
7. [Development and learning agreement](learning-guide-agreement.md)
