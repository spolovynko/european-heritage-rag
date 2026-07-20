# Phase 5 — Bronze data layer

## Objective

Persist raw source responses unchanged and make ingestion reproducible, auditable, resumable, and inspectable.

## What we will learn

- Append-only raw data design.
- Data lineage.
- Content hashing.
- Idempotency.
- Run manifests.
- The difference between ingestion and transformation.

## Development steps

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

## UI work

Add Bronze inspection:

- Run list.
- Run status and duration.
- Work and page counts.
- Failure list.
- Raw work JSON preview.
- Raw OCR annotation preview.
- Source link.

## Tests

- Atomic write behaviour.
- Stable hash for identical content.
- Changed hash for changed content.
- Repeated ingestion does not duplicate a completed work.
- Failed resource remains retryable.

## Exit criteria

- A five-work ingestion is fully represented in Bronze.
- Every stored file has provenance.
- Re-running creates no unintended duplicates.
- Raw data can be reprocessed without calling Wellcome again.

## Required ADR

`ADR-0005: Append-only Bronze storage and idempotent ingestion`

Decision questions:

- Why keep Bronze unchanged?
- Why use the local filesystem first?
- Why content hashes?
- What qualifies as an idempotent rerun?

---
