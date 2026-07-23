# ADR-0005: Append-only Bronze storage and idempotent ingestion

- Status: Accepted
- Date: 2026-07-23
- Phase: Phase 5 — Bronze data layer

## Context

Phase 4 could discover Wellcome works and traverse their IIIF manifests and OCR
annotation lists, but the downloaded source evidence disappeared after the
process finished. Rebuilding any later dataset would therefore require another
network call and could silently produce different results if Wellcome changed.

The first durable layer needs to:

- preserve source information before cleaning or normalization;
- prove where and when each resource came from;
- survive interruption without presenting partial files as complete;
- resume a run without duplicating already completed resources;
- reveal source failures for retry; and
- remain small and understandable for a five-to-500-work portfolio dataset.

The important distinction is between an immutable resource and a progressing
run ledger. Raw resource files must never change at the same logical identity.
The run manifest must be replaced as work progresses so it can record the latest
complete inventory and terminal status.

## Decision

Store Bronze on the local filesystem under this partitioned convention:

```text
data/bronze/wellcome/
└── ingestion_date=YYYY-MM-DD/
    └── run_id=<run-id>/
        ├── run-manifest.json
        └── works/<work-id>/
            ├── work.json
            ├── manifest.json
            └── annotations/<canvas>-<annotation>-<url-hash>.json
```

The implementation makes the following decisions.

1. **Keep Bronze raw.** IIIF manifests and annotation lists are stored as the
   exact HTTP response bytes. A selected catalogue work is decoded and
   serialized losslessly so unknown source fields are retained, while unrelated
   results from the catalogue page are not copied into every work directory.
   Cleaning, OCR line joining, and canonical field selection belong to Silver.
2. **Use stable logical identities.** A catalogue work and manifest are
   identified by resource type plus work ID. An annotation also includes canvas
   index, annotation index, and a SHA-256 of its normalized source URL. This
   makes paths deterministic without trusting a source URL as a filesystem path.
3. **Use SHA-256 integrity receipts.** Every manifest resource record contains
   its source URL, acquisition timestamp, byte length, media type, portable
   relative path, and SHA-256 of the stored bytes.
4. **Expose files atomically.** Content is written to a unique temporary sibling,
   flushed and synchronized, then moved over the destination. A failed write
   leaves no partial final file. Mutable run manifests use the same complete-file
   replacement pattern.
5. **Make resource writes append-only.** Writing identical bytes to an existing
   identity returns `unchanged`. Writing different bytes to that same identity
   raises a content-conflict error instead of overwriting evidence.
6. **Define idempotent rerun narrowly.** Resuming the same run with the same
   acquisition parameters may update run timestamps and failure resolution, but
   it must keep the same resource IDs, paths, hashes, and completed-work
   inventory. Starting a new non-resume run intentionally creates a separate
   time-partitioned snapshot.
7. **Keep failure history.** Failed URLs, resource type, work ID, exception type,
   message, and occurrence time are appended to the manifest. A later successful
   retry marks earlier failures resolved rather than deleting them.
8. **Use one filesystem implementation now.** `BronzeFilesystemStore` is
   deliberately concrete. No generic storage interface is added until an
   object-store deployment creates a real second implementation.

## Alternatives considered

### Normalize directly into Silver

This would use less disk space and fewer modules, but it would make cleaning
mistakes irreversible and prevent later transformations from replaying the
original evidence. It was rejected because auditability is a product
requirement.

### Store only parsed Pydantic models

The Phase 4 source models intentionally select only the fields the traversal
needs. Serializing those models would discard unknown source fields and make
Bronze an accidental normalized layer. The implementation instead captures raw
bytes or losslessly decoded source JSON before narrow validation.

### Store whole catalogue response pages

This would preserve the exact page bytes but couple selected works to pagination
and duplicate unselected results. The chosen design stores each selected raw
work with the catalogue request URL as provenance. Whole-page archival can be
added if future replay needs pagination-level evidence.

### Use a database or object storage immediately

A database could provide transactions and object storage could scale cheaply,
but either would add services, credentials, and operational concepts that the
current local dataset does not require. The filesystem is visible, portable,
easy to inspect, and sufficient for the current single-writer workflow.

### Overwrite a changed resource during resume

This would make reruns convenient but would destroy the earlier observation
while leaving the same logical identity. The chosen conflict error forces a new
run when source content has changed.

### Use timestamps or file size as integrity checks

Both can change or collide without proving byte equality. SHA-256 provides a
stable content fingerprint and is available in Python's standard library.

## Consequences

### Positive

- Later transformations can run entirely offline from Bronze.
- Source changes and local corruption are detectable.
- Interrupted writes do not masquerade as valid JSON resources.
- Resume can skip completed works and retain a stable resource inventory.
- Every resource is traceable to a URL, time, hash, path, and run.
- The on-disk layout is understandable without a specialized data platform.
- CLI, API, and browser inspection all read the same validated manifest.

### Negative or accepted trade-offs

- The filesystem and file-backed manifest assume one ingestion writer per run.
- Replacing the manifest after each event is simple but becomes increasingly
  expensive as the resource list grows.
- JSON uses more storage than compressed or columnar formats.
- Catalogue work JSON is lossless at the data level, not byte-identical to the
  original catalogue page formatting.
- SHA-256 detects change but does not prove that the source itself was truthful.
- A new source version requires a new run rather than mutation in place.
- Object storage will require a new concrete store and different atomic-create
  semantics.

## Validation

The decision is accepted because:

- unit tests cover stable and changed hashes, atomic replacement failure,
  immutable conflicts, manifest consistency, resume, and offline validation;
- the complete suite passes with 95 tests;
- a live five-work run completed with 310 resources and zero failures;
- offline validation checked all 310 resources successfully;
- resume kept all 310 `(resource ID, path, hash)` tuples unchanged;
- the browser and CLI can inspect the same raw data; and
- the Phase 5 container runs unprivileged with a writable persistent Bronze
  volume.

## Revisit when

Reconsider this decision when:

- the portfolio corpus makes per-resource manifest replacement measurably slow;
- concurrent writers are required;
- deployment requires remote object storage or cross-host readers;
- catalogue page-level replay becomes necessary;
- retention or compliance rules require lifecycle policies; or
- the dataset needs compression without losing exact-source recovery.
