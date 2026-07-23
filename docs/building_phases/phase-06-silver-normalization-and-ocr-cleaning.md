# Phase 6 — Silver normalization and OCR cleaning

## Objective

Transform validated Bronze source records into deterministic canonical works
and pages while preserving raw OCR, exact Bronze lineage, and visible cleaning
quality.

Plain-language outcome: organize the raw evidence without hiding where it came
from or pretending that automated OCR cleanup is perfect.

## Entry criteria

Before Phase 6 starts:

- at least one complete Bronze run exists;
- its manifest and every declared resource validate offline;
- catalogue work, IIIF manifest, and annotation-list shapes can be parsed;
- page canvases and missing OCR remain visible;
- source URL, resource path, byte length, and SHA-256 are available; and
- repeated Bronze validation does not require another Wellcome request.

## What we will learn

- Canonical data modelling and source/domain separation.
- Schema and cross-field validation with Pydantic.
- Safe versus destructive OCR cleanup.
- Work-scoped repeated header/footer detection.
- Deterministic derived-data identity and algorithm versioning.
- Columnar storage with Polars, PyArrow, and Parquet.
- Atomic derived-dataset publication.
- Machine- and human-readable quality reporting.
- Why quality flags are evidence, not measured accuracy.
- How every derived row remains traceable to raw source receipts.

## Deliberate exclusions

Phase 6 does not:

- create chunks or select chunk size;
- tokenize text;
- create embeddings or a vector index;
- correct spelling or modernize historical language;
- use a language model to rewrite OCR;
- discard empty or suspicious pages;
- add layout analysis for tables or columns;
- add distributed processing; or
- claim measured OCR accuracy.

## Ordered implementation path

### Step 1 — Review and lock the input evidence contract

Substeps:

1. Read the Phase 5 guide, Bronze models, storage, validation, fixtures, and
   live manifest.
2. Confirm one work and one page can be reconstructed offline.
3. List which metadata fields Silver needs but the current catalogue include
   does not capture.
4. Keep legacy Bronze include values valid.
5. Define exact acceptance datasets: fixture, 5 works, then 20–25 works.

Expected files:

- `pipeline/bronze.py`
- `sources/wellcome/models.py`
- `sources/wellcome/client.py`
- `sources/wellcome/ingestion.py`
- Wellcome fixtures and tests

Why: a canonical layer can select source data, but it cannot safely invent
source data that was never acquired.

Checkpoint: enriched source fixtures parse, new discovery requests ask for the
required fields, and legacy Bronze manifests still validate.

### Step 2 — Add the smallest required data tools and configuration

Substeps:

1. Add Polars for explicit frames and Parquet writes.
2. Add PyArrow for independent physical schema inspection.
3. Lock both dependencies with `uv`.
4. Add `SILVER_DATA_DIRECTORY` with a local default.
5. Verify environment override and path behavior.

Expected files:

- `pyproject.toml`
- `uv.lock`
- `core/config.py`
- `.env.example`
- configuration tests

Why: all Silver producers and readers need one data root, and Parquet behavior
must be reproducible from the lockfile.

Checkpoint: locked dependency sync and configuration tests pass.

### Step 3 — Define canonical work, page, lineage, and quality contracts

Substeps:

1. Define strict immutable `SilverWork` and `SilverPage` models.
2. Separate work-level metadata from page-level evidence.
3. Define nested contributor and lineage contracts.
4. Define page and work quality enums.
5. Define quality-report, file-receipt, dataset-manifest, and validation-report
   contracts.
6. Add uniqueness, count, URL, hash, and cross-field invariants.

Expected files:

- `domain/__init__.py`
- `domain/silver.py`
- `tests/domain/test_silver_models.py`

Why: later transforms, storage, API, and chunking need one agreed contract and
must reject inconsistent records early.

Checkpoint: valid examples pass and contradictory OCR/quality records fail.

### Step 4 — Reconstruct the untouched raw OCR view

Substeps:

1. Parse IIIF fragment selectors into an `OcrLine` value.
2. Preserve source line order.
3. Join source lines with newline separators only.
4. Keep blank lines and empty annotation lists visible.
5. Test raw reconstruction independently of cleaning.

Expected files:

- `pipeline/ocr_cleaning.py`
- `tests/pipeline/test_ocr_cleaning.py`

Why: cleanup needs an immutable comparison baseline.

Checkpoint: raw output exactly reflects ordered fixture line text.

### Step 5 — Implement conservative pure OCR-cleaning functions

Substeps:

1. Normalize Unicode to NFC.
2. Remove HTML with a parser and decode entities.
3. Normalize horizontal spaces without erasing paragraph breaks.
4. Join ordinary OCR line wraps.
5. Dehyphenate only before a lowercase continuation.
6. Preserve blank-line paragraph boundaries.
7. Return change counts rather than only final text.
8. Calculate word count, symbol ratio, and cleaning-change ratio.

Expected files:

- `pipeline/ocr_cleaning.py`
- `tests/pipeline/test_ocr_cleaning.py`

Why: small pure functions are explainable, deterministic, and easy to test
against destructive edge cases.

Checkpoint: Unicode, HTML, whitespace, paragraph, dehyphenation, and empty-page
tests pass.

### Step 6 — Detect repeated headers and footers at work scope

Substeps:

1. Normalize candidate boundary signatures.
2. Normalize changing digits in page-numbered running headers.
3. Reject punctuation-only or very short candidates.
4. Count only first and last non-empty page lines.
5. Require at least three occurrences and 15% of non-empty pages.
6. Return original page-specific matching lines for transparent removal.
7. Test repeated, non-repeated, and digit-varying examples.

Expected files:

- `pipeline/header_footer.py`
- `tests/pipeline/test_header_footer.py`

Why: one page cannot prove that a boundary line is boilerplate.

Checkpoint: only high-confidence repeated fixture boundaries are detected.

### Step 7 — Define deterministic Bronze and Silver identity

Substeps:

1. Hash stable Bronze parameters and sorted resource receipts.
2. Exclude mutable timestamps.
3. Version the Silver schema, cleaning, boundary, and quality rules.
4. Hash the input inventory and version set into `dataset_id`.
5. Hash work ID and canvas URL into `page_id`.
6. Test stability and change sensitivity.

Expected files:

- `pipeline/silver.py`
- `tests/pipeline/test_silver_transform.py`

Why: identical evidence and rules should reuse one dataset; changed evidence or
rules should not masquerade as the same result.

Checkpoint: repeated IDs match, and a declared version/input change changes the
dataset ID.

### Step 8 — Reconcile and transform Bronze offline

Substeps:

1. Require a complete Bronze manifest.
2. Run Bronze offline validation before mapping.
3. Require one catalogue record and one IIIF manifest per completed work.
4. Map every IIIF canvas in source sequence.
5. Match annotation records by canvas index, annotation index, and URL.
6. Fail if a Bronze annotation is unaccounted for.
7. Create one canonical work per completed work.
8. Create one canonical page per canvas, including empty OCR.
9. Map images, labels, printed numbers, metadata, hashes, and source URLs.
10. Attach exact lineage to every row.

Expected files:

- `pipeline/silver.py`
- `tests/pipeline/test_silver_transform.py`

Why: normalization is trustworthy only when no source resource disappears
silently.

Checkpoint: fixture output has the expected work/page counts, order, empty
page, IDs, metadata, and lineage.

### Step 9 — Calculate transparent quality evidence

Substeps:

1. Flag empty/short/high-symbol OCR.
2. Flag every applied cleaning action.
3. Flag source anomalies such as missing/duplicate labels, multiple annotation
   lists, non-text annotations, and missing images.
4. Flag missing work metadata.
5. Assign broad `missing`, `needs_review`, or `usable` bands.
6. Aggregate per-work and dataset counts.
7. Emit language, flag, average-word, and processing-failure summaries.
8. Keep the report rules versioned.

Expected files:

- `domain/silver.py`
- `pipeline/silver.py`
- related tests

Why: operators should see why a page was changed or queued for review.

Checkpoint: page-band totals reconcile exactly to page count.

### Step 10 — Publish Parquet and quality reports atomically

Substeps:

1. Declare exact Polars schemas, including nested structs.
2. Convert validated models into frames.
3. Write Zstandard-compressed Parquet with statistics.
4. Write JSON and Markdown quality reports.
5. Synchronize temporary siblings and replace final files atomically.
6. Record output sizes and SHA-256.
7. Write `silver-manifest.json` last.
8. Reuse an already valid deterministic dataset.

Expected files:

- `pipeline/silver_store.py`
- `tests/pipeline/test_silver_store.py`

Why: Parquet is useful only if files are typed, complete, attributable, and
safe to rebuild.

Checkpoint: all five files exist, schemas are exact, and a repeat publish
returns “reused.”

### Step 11 — Validate Silver without Bronze network access

Substeps:

1. Validate declared files, sizes, and hashes.
2. Detect temporary leftovers.
3. Inspect schemas with Polars and field names with PyArrow.
4. Round-trip every row through Pydantic.
5. Check unique work/page IDs.
6. Check every page’s `work_id`.
7. Reconcile manifest, Parquet, and quality counts.
8. Return structured issues rather than a bare Boolean.

Expected files:

- `pipeline/silver_store.py`
- `tests/pipeline/test_silver_store.py`

Why: Phase 7 needs to reject corrupt or inconsistent Silver input before
chunking.

Checkpoint: valid output passes and intentional corruption is reported.

### Step 12 — Add CLI build, inspect, and validate workflows

Substeps:

1. Add a `silver` Typer group.
2. Build one dataset from an exact Bronze run ID.
3. List or inspect complete datasets.
4. Validate one or all datasets.
5. Return non-zero status and useful messages for invalid/missing inputs.
6. Show whether a build was created or reused.

Expected files:

- `cli.py`
- `tests/cli/test_cli.py`

Why: the operator path must be repeatable without writing Python scripts.

Checkpoint: CLI tests and real local commands pass.

### Step 13 — Add bounded read-only API inspection

Substeps:

1. List complete dataset manifests.
2. Return one manifest.
3. List works.
4. List page summaries without full OCR.
5. Filter pages by work and quality flag.
6. Enforce offset and maximum limit.
7. Return one full page only when selected.
8. Return the quality report.
9. Register routes before frontend fallback.

Expected files:

- `api/silver.py`
- `api/main.py`
- `tests/api/test_silver_api.py`

Why: the browser needs Silver evidence without direct filesystem access or
unbounded text responses.

Checkpoint: list/filter/detail/quality and not-found API tests pass.

### Step 14 — Build the Silver browser inspector

Substeps:

1. Add accessible Bronze/Silver layer tabs.
2. Load the newest complete Silver dataset.
3. Display counts, average words, languages, and failures.
4. Filter by work and quality flag.
5. Show bounded page results and total matches.
6. Show page image and numbering.
7. Show work metadata and source link.
8. Compare raw and clean OCR side by side.
9. Show detected boundaries, quality flags, and exact lineage.
10. Add responsive styling and Vite `/silver` proxy.
11. Verify the rendered DOM, filters, source values, and console.

Expected files:

- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`
- `frontend/vite.config.js`

Why: visual comparison makes cleanup behavior reviewable instead of hidden in a
data file.

Checkpoint: a real page loads with matching image, metadata, raw/clean text,
flags, and lineage; filtering changes the dataset query; no console errors.

### Step 15 — Wire local and container persistence

Substeps:

1. Create `/app/data/silver` for the unprivileged runtime user.
2. Add the Silver environment setting.
3. Add a dedicated named volume.
4. Update the phase image tag.
5. Validate Compose configuration.
6. Build and start the production image.
7. Check health and the Silver route.

Expected files:

- `Dockerfile`
- `compose.yaml`

Why: derived data must survive container replacement independently of Bronze.

Checkpoint: the image builds, becomes healthy, and can access its Silver root.

### Step 16 — Run the complete acceptance ladder

Substeps:

1. Run Ruff format and lint.
2. Run strict mypy.
3. Run all pytest tests.
4. Build production frontend assets.
5. Replay an existing five-work Bronze run.
6. Run a fresh enriched five-work ingestion and Silver build.
7. Run a fresh 20–25-work ingestion and Silver build.
8. Validate all Bronze and Silver outputs offline.
9. Rebuild and prove dataset reuse.
10. Inspect anomaly counts rather than hiding them.
11. Exercise the rendered browser.
12. Build and health-check the container.

Why: fixtures prove rules; real data reveals source variation and operational
problems that fixtures do not.

Checkpoint: every exit criterion below has measured evidence.

### Step 17 — Close the learning record

Substeps:

1. Update the user-facing README.
2. Write the Phase 6 implementation guide from finished code.
3. Accept ADR-0006 and update the ADR index.
4. Update the building-guide index.
5. Update project status with exact commands, IDs, counts, limitations, and
   Phase 7 entry conditions.
6. Run final repository/document checks.
7. Leave Git review, staging, commit, and push to the learner unless explicitly
   delegated.

Expected files:

- `README.md`
- `docs/building_guides/phase-06-silver-normalization-and-ocr-cleaning.md`
- `docs/building_guides/README.md`
- `docs/adr/0006-canonical-work-page-schemas-and-conservative-ocr-cleaning.md`
- `docs/adr/README.md`
- `docs/project-status.md`

Why: durable documentation is the handoff between phase chats and the learner’s
interview-ready explanation.

## Verification commands

```shell
uv sync --locked
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src
uv run pytest
pnpm --dir frontend build
docker compose config --quiet
docker compose build

uv run european-heritage-rag bronze validate --run-id <run-id>
uv run european-heritage-rag silver build --bronze-run-id <run-id>
uv run european-heritage-rag silver inspect --dataset-id <dataset-id>
uv run european-heritage-rag silver validate --dataset-id <dataset-id>
```

## Exit criteria

Phase 6 is complete only when:

- `works.parquet` and `pages.parquet` are valid typed Parquet files;
- one canonical work exists per completed Bronze work;
- one canonical page exists per IIIF canvas, including empty OCR;
- every work and page carries exact Bronze lineage;
- raw and clean OCR are stored and visibly comparable;
- cleaning rules are conservative, pure, tested, and versioned;
- quality flags and reports make changes/anomalies visible;
- the dataset identity is deterministic;
- repeated builds reuse an unchanged complete dataset;
- offline validation catches integrity, schema, row, and relationship problems;
- CLI, API, browser, and container paths work;
- fixture, 5-work, and 20–25-work acceptance checks pass;
- the implementation guide, ADR, README, and project handoff are current; and
- no claim of measured OCR accuracy is made.

## Required ADR

[ADR-0006: Canonical work/page schemas and conservative OCR cleaning](../adr/0006-canonical-work-page-schemas-and-conservative-ocr-cleaning.md)

The ADR records:

- why work and page facts are separated;
- why raw and cleaned OCR coexist;
- why Parquet is the canonical Silver format;
- which cleanup is safe to automate;
- why quality is represented as flags and broad bands;
- why lineage is row-level and fail-closed;
- how dataset identity and atomic publication work; and
- which evidence would justify revisiting the decision.
