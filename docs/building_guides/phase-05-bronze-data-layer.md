# Phase 5 implementation guide: Bronze data layer

## 1. Phase at a glance

Phase 5 turns temporary Wellcome downloads into an auditable raw dataset.

In simple terms, Phase 4 could read a book from Wellcome, but forgot the source
files after the run. Phase 5 gives the pipeline a durable evidence cupboard:
every selected catalogue work, IIIF manifest, and OCR annotation list is stored
before any cleaning takes place.

Technically, the phase adds an immutable filesystem data layer, a validated run
manifest, SHA-256 integrity receipts, atomic writes, resumable orchestration,
offline validation, operator commands, read-only HTTP endpoints, a browser
explorer, and a persistent container volume.

No new Python or JavaScript dependency was required. The implementation uses
the existing Pydantic, Typer, FastAPI, pytest, Vite, and browser-native stack
plus Python standard-library filesystem and hashing functions.

Deliberately excluded:

- OCR cleanup and canonical work/page models, which belong to Silver;
- Parquet, which begins in Phase 6;
- cloud object storage and a generic storage interface;
- concurrent ingestion writers;
- search, embeddings, retrieval, and answer generation.

## 2. Vocabulary

| Term | Simple explanation | Technical meaning here |
|---|---|---|
| Bronze | The untouched evidence cupboard | Raw or losslessly decoded source JSON plus provenance |
| Resource | One downloaded source file | Catalogue work, IIIF manifest, or OCR annotation list |
| Run | One bounded acquisition attempt | A stable run ID, parameters, timestamps, resources, counts, and failures |
| Manifest | The run's receipt book | A validated JSON ledger named `run-manifest.json` |
| Provenance | Where the data came from | Source URL, acquisition time, run, resource type, work ID, and path |
| Content hash | A fingerprint of file bytes | Lowercase SHA-256 stored in the manifest |
| Atomic write | Show all of a file or none of it | Write and `fsync` a temporary sibling, then replace the final path |
| Idempotent resume | Repeating safely | Same run and options produce no duplicate or changed resource inventory |
| Offline replay | Reuse without the source API | Parse and validate stored Bronze files without contacting Wellcome |

## 3. Repository structure

```text
src/european_heritage_rag/
├── api/
│   ├── bronze.py
│   └── main.py
├── pipeline/
│   ├── bronze.py
│   ├── bronze_run.py
│   ├── bronze_store.py
│   └── bronze_validation.py
├── sources/wellcome/
│   ├── client.py
│   ├── ingestion.py
│   └── models.py
└── cli.py

tests/
├── api/test_bronze_api.py
├── pipeline/
│   ├── test_bronze.py
│   ├── test_bronze_run.py
│   ├── test_bronze_store.py
│   └── test_bronze_validation.py
└── sources/wellcome/
    ├── test_client.py
    └── test_ingestion.py

data/bronze/                  # generated and ignored
frontend/                     # live Bronze explorer
Dockerfile
compose.yaml
```

One live run has this shape:

```text
data/bronze/wellcome/
└── ingestion_date=2026-07-23/
    └── run_id=0e96cc69c1cf4124bf61e1bf2242a4ca/
        ├── run-manifest.json
        └── works/
            └── <work-id>/
                ├── work.json
                ├── manifest.json
                └── annotations/
                    └── 000000-00-<source-url-hash>.json
```

The directory names are portable POSIX-style identities in the manifest.
`BronzeFilesystemStore` translates them into `Path` objects for Windows or
Linux only at the filesystem boundary.

## 4. Runtime flow

```text
CLI ingest command
  → create/resume Phase 4 checkpoint
  → create/resume BronzeRunRecorder
  → discover selected catalogue works
      → capture lossless work JSON
      → atomic resource write
      → atomic manifest receipt update
  → traverse each work
      → capture exact manifest bytes
      → capture each exact annotation-list response
      → atomic resource + receipt updates
  → mark work complete or append failure
  → write terminal run manifest

Later, without Wellcome:
  CLI/API/browser/Phase 6
    → load validated run manifest
    → resolve declared resources
    → verify size + SHA-256 + JSON source shape
```

The resource is written before its receipt is added to the manifest. This order
is intentional: a crash may leave an unlisted complete file, which validation
can report, but it cannot leave a manifest claiming that a missing file was
successfully stored.

## 5. Step-by-step implementation review

### Step 1 — Define identities and portable paths

#### 1.1 Add the configurable Bronze root

`AppSettings.bronze_data_directory` defaults to `data/bronze` and is exposed as
`BRONZE_DATA_DIRECTORY`.

Why: code should not scatter a hard-coded root, and the container needs a
different absolute path. In plain language, this is the address of the evidence
cupboard.

#### 1.2 Define run identity

`BronzeRunIdentity` combines:

- source (`wellcome`);
- UTC ingestion date; and
- safe run ID.

It calculates `wellcome/ingestion_date=.../run_id=...`. Pydantic rejects path
separators and unsafe identifiers before they reach the filesystem.

#### 1.3 Define resource identity

`BronzeResourceIdentity` determines both `resource_id` and `relative_path`.
Catalogue works and manifests have one fixed identity per work. OCR annotations
also include canvas and annotation position plus a source-URL hash.

Why: deterministic identity is the basis of idempotency. The same logical input
maps to the same place.

### Step 2 — Define the run ledger

#### 2.1 Model acquisition parameters

`WellcomeBronzeParameters` records the exact bounded discovery options:
limit, query, language, work type, online availability, Public Domain Mark,
IIIF location type, and included catalogue fields.

#### 2.2 Model resource receipts

`BronzeResourceRecord` stores:

- logical identity and resource type;
- work and optional canvas/annotation indices;
- portable path;
- source URL and acquisition time;
- SHA-256 and byte length; and
- returned content type.

Its model validator rebuilds the identity and rejects a forged or inconsistent
path.

#### 2.3 Model failures

`BronzeFailureRecord` preserves URL, work, resource type, exception type,
message, occurrence time, and optional resolution time. Resolution cannot
precede occurrence.

#### 2.4 Model manifest consistency

`BronzeRunManifest` validates the whole ledger, not only individual fields. For
example:

- a terminal run requires `finished_at`;
- completed count must match unique completed IDs;
- completed work must have a work and manifest resource;
- annotation count must equal stored annotation resources;
- completed status cannot retain unresolved failures; and
- failed status must have an unresolved failure.

Simple explanation: the receipt book is not accepted if its totals contradict
its line items.

### Step 3 — Make raw storage immutable and crash-safe

#### 3.1 Hash exact stored content

`sha256_hex()` hashes the bytes that will exist on disk, not a later Python
object. Identical bytes get the same digest; one changed byte changes the
fingerprint with overwhelming probability.

#### 3.2 Write through a temporary sibling

The store:

1. creates parent directories;
2. opens a uniquely named `.tmp` file in exclusive-create mode;
3. writes all bytes;
4. flushes Python's buffer;
5. calls `os.fsync`;
6. replaces the final path; and
7. removes any leftover temporary file in `finally`.

The final name therefore never points to a half-written response.

#### 3.3 Enforce immutable resource behavior

If a destination exists:

- an equal hash returns `BronzeWriteDisposition.UNCHANGED`;
- a different hash raises `BronzeContentConflictError`.

Run manifests are the deliberate exception: they are mutable ledgers, but each
version is still replaced atomically as a complete JSON document.

#### 3.4 Keep the store concrete

`BronzeFilesystemStore` owns filesystem concerns such as `Path`, directory
creation, reads, and replacement. No object-store interface exists because
there is only one implementation and no current cloud requirement.

### Step 4 — Coordinate run progress and retry history

#### 4.1 Start or reopen a ledger

`BronzeRunRecorder.start()` either creates a new running manifest or reopens the
matching manifest for resume. Resume requires the same identity and parameters.

#### 4.2 Commit each resource receipt immediately

`record_resource()` writes the payload, deduplicates the receipt by resource ID,
recalculates the annotation total, and atomically writes the new ledger.

#### 4.3 Mark work completion

`record_work_success()` adds a work ID once, increases canvas and missing-OCR
counts once, and resolves prior failures for that work.

#### 4.4 Preserve failure history

`record_failure()` appends rather than overwrites. A successful retry adds a
resolution timestamp to the earlier record. This retains the fact that the
failure happened while distinguishing it from current work.

#### 4.5 Finish honestly

The recorder writes `completed`, `completed_with_failures`, or `failed` with a
finish time. Pydantic consistency rules prevent status/count/failure
contradictions.

### Step 5 — Capture source payloads before narrow modelling

#### 5.1 Introduce the raw-resource event

`RawWellcomeResource` carries source type, work ID, URL, bytes, acquisition
time, content type, and optional canvas coordinates. It is a small value object
used at the client/ingestion boundary.

#### 5.2 Capture selected catalogue works losslessly

The client keeps the HTTP response and decodes the full JSON page. For every
validated selected work, it serializes the corresponding original result
object, retaining source fields that the narrow `CatalogueWork` model does not
know about.

This is lossless JSON data, though it does not preserve the source page's
original whitespace.

#### 5.3 Capture exact IIIF bytes

Manifest and annotation-list observers receive `response.content` before the
validated models are used for traversal. These files are byte-identical to the
HTTP response used by the run.

#### 5.4 Preserve the old traversal boundary

`traverse_work()` remains a simple wrapper around
`traverse_work_with_resources()`. Existing callers get the original typed
result, while ingestion can subscribe to raw-resource events.

### Step 6 — Integrate Bronze with resumable ingestion

#### 6.1 Create the production store

`run_wellcome_ingestion()` constructs `BronzeFilesystemStore` from settings and
passes the installed pipeline version into the runner.

#### 6.2 Keep dry runs dry

Catalogue-only `--dry-run` still performs discovery and dashboard reporting but
does not create a Bronze run. Bronze represents acquired reusable source data,
not a planning request.

#### 6.3 Use one observer for all source responses

The runner maps `RawWellcomeResource` events to validated
`BronzeResourceIdentity` objects and sends them to `BronzeRunRecorder`.

#### 6.4 Reconcile resume state

On `--resume`, the runner reuses Phase 4 checkpoint identity and the matching
Bronze manifest. Completed work IDs and counters are restored. Already
completed works are skipped, while failed work can be retried.

#### 6.5 Record failures at the source boundary

HTTP and traversal failures are mapped to the most specific known URL and
resource type. The run can complete with failures without losing successful
works.

### Step 7 — Prove integrity and offline replay

`validate_bronze_run()` walks the manifest inventory and checks:

- the manifest parses and its claimed identity matches its directory partitions;
- every declared resource exists;
- byte length matches;
- SHA-256 matches;
- content is valid JSON;
- JSON still validates as the expected Wellcome source shape;
- no undeclared JSON files exist below the run directory; and
- no temporary files remain.

The validator never calls Wellcome. Passing it proves that Phase 6 can begin
from local Bronze data.

### Step 8 — Add operator inspection surfaces

#### 8.1 CLI

The Typer `bronze` group provides:

```shell
uv run european-heritage-rag bronze inspect
uv run european-heritage-rag bronze inspect --run-id <run-id>
uv run european-heritage-rag bronze validate
uv run european-heritage-rag bronze validate --run-id <run-id>
```

`inspect` lists runs or prints one run's counts, resource paths, hashes, URLs,
and unresolved failures. `validate` exits nonzero when integrity problems exist,
which makes it usable in automation.

#### 8.2 Read-only API

`api/bronze.py` exposes:

- `GET /bronze/runs`;
- `GET /bronze/runs/{run_id}`; and
- `GET /bronze/runs/{run_id}/resources/{resource_id}`.

The resource endpoint accepts a manifest resource ID, never a disk path. This
prevents a caller from asking the server to read an arbitrary local file.

### Step 9 — Replace sample UI data with the real Bronze explorer

The Data workspace now:

- selects the newest run by default;
- shows status, completed/discovered works, resources, and failures;
- lists unresolved failure details;
- searches resource IDs, paths, and work IDs;
- filters catalogue works, IIIF manifests, and OCR annotations;
- shows byte length, acquisition time, SHA-256, and source link; and
- pretty-prints decoded stored JSON.

The frontend uses text nodes for source-controlled data rather than inserting
remote HTML. The Vite development proxy forwards `/bronze` to FastAPI.

### Step 10 — Make local and container operation durable

#### 10.1 Ignore generated corpus data

`data/` is excluded from Git. Manifests contain source material and generated
run state, not application source.

#### 10.2 Prepare the image

The unprivileged image creates and assigns `/app/data/bronze` to UID 10001.

#### 10.3 Persist with Compose

Compose sets `BRONZE_DATA_DIRECTORY=/app/data/bronze` and mounts the
`bronze-data` named volume there. Replacing the container therefore does not
remove the Bronze corpus.

## 6. File-by-file review

| File | Responsibility |
|---|---|
| `pipeline/bronze.py` | Immutable identities, enums, receipts, failures, parameters, and whole-manifest invariants |
| `pipeline/bronze_store.py` | Filesystem paths, SHA-256, atomic writes, immutable conflict detection, manifest load/list/find, safe resource reads |
| `pipeline/bronze_run.py` | Progressing ledger, receipt commits, completed-work accounting, retry history, terminal state |
| `pipeline/bronze_validation.py` | Offline file, hash, JSON, source-shape, inventory, and temp-file validation |
| `sources/wellcome/models.py` | Raw resource event value object |
| `sources/wellcome/client.py` | Captures source responses before narrow validation while preserving existing discovery/traversal results |
| `sources/wellcome/ingestion.py` | Wires source events to Bronze and reconciles resume/failure state |
| `cli.py` | Human operator inspect and validate commands |
| `api/bronze.py` | Read-only, manifest-addressed browser API |
| `api/main.py` | Registers Bronze routes before the frontend fallback |
| `frontend/*` | Real run/resource explorer and responsive provenance preview |
| `core/config.py`, `.env.example` | Local/container Bronze root configuration |
| `Dockerfile`, `compose.yaml` | Unprivileged writable path and persistent named volume |

The tests follow the same responsibility boundaries:

- `test_bronze.py` proves identity, path, and manifest invariants.
- `test_bronze_store.py` proves hashing, immutable duplicate/conflict behavior,
  atomic writes, cleanup, and manifest replacement.
- `test_bronze_run.py` proves immediate receipts, retry resolution, and resume.
- `test_bronze_validation.py` proves offline replay and corruption/orphan
  detection.
- Wellcome client tests prove exact manifest/annotation bytes and unknown
  catalogue fields survive capture.
- Ingestion tests prove a complete Bronze run and unchanged resume inventory.
- CLI and API tests prove normal empty, success, and not-found behavior.

## 7. Verification

### Automated quality gate

```shell
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
pnpm --dir frontend build
docker compose config --quiet
docker compose build
```

Measured result on 2026-07-23:

- 95 tests passed;
- Ruff lint and format checks passed;
- mypy reported no issues in 19 source files;
- Vite production build passed;
- Compose configuration validation passed; and
- `european-heritage-rag:phase5` built successfully.

### Live five-work acceptance

```shell
uv run european-heritage-rag ingest wellcome --limit 5 --query cholera
uv run european-heritage-rag bronze validate \
  --run-id 0e96cc69c1cf4124bf61e1bf2242a4ca
uv run european-heritage-rag ingest wellcome \
  --limit 5 --query cholera --resume
```

Measured result:

| Measure | Result |
|---|---:|
| Works | 5/5 completed |
| Canvases traversed | 300 |
| Missing-OCR canvases | 6 |
| Annotation-list resources | 300 |
| Total immutable resources | 310 |
| Failure records | 0 |
| Offline validation | 310/310 valid |
| Run bytes including manifest | 5,188,796 |
| Resume inventory | 310 before, 310 after, identities/paths/hashes unchanged |

### Browser and container acceptance

- Desktop explorer loaded the live run and all 310 resources.
- Catalogue filter returned exactly five work resources.
- Stored JSON preview and source link loaded.
- No browser console warning or error was recorded.
- At 390 × 844, the explorer had no horizontal overflow and the run summary
  collapsed responsively.
- The Compose service became healthy, ran as UID 10001, returned HTTP 200 for
  the Bronze API, and had a writable `/app/data/bronze` named volume.

## 8. How to explain the design

Short nontechnical version:

> Bronze is a dated, read-only copy of what Wellcome returned. Each run has a
> receipt listing every file, where it came from, and a fingerprint that tells
> us if it changed. Files appear only after a complete write. Retrying the same
> run reuses matching files instead of duplicating them.

Short technical version:

> Phase 5 implements immutable, run-partitioned filesystem resources with
> deterministic identities, SHA-256 receipts, fsync-plus-replace atomic writes,
> a validated Pydantic run manifest, work-granular resume, structured retry
> history, and offline replay validation. The manifest is the mutable atomic
> ledger; declared resource files are append-only.

The most important design boundary:

> Ingestion preserves evidence; transformation interprets it. Bronze never
> cleans OCR. Silver may create normalized data, but it must retain lineage back
> to these Bronze hashes and source URLs.

## 9. Current limitations and revisit signals

- Single writer per run is assumed.
- The full manifest is rewritten after each event.
- Catalogue work capture preserves JSON fields but not original page whitespace.
- JSON is uncompressed.
- The API returns full manifests, so very large runs will eventually need
  summaries and pagination.
- The UI pretty-prints decoded JSON; the file hash remains the authority for
  exact bytes.
- Resource identity conflict requires a new run; no in-place source versioning
  exists.
- There is no automated browser end-to-end suite yet.

Revisit storage abstraction, manifest sharding, API pagination, and compression
only when corpus or deployment measurements justify them.

## 10. Official references

- [Python `hashlib`](https://docs.python.org/3/library/hashlib.html)
- [Python `os.replace`](https://docs.python.org/3/library/os.html#os.replace)
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)
- [Pydantic validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [Typer command groups](https://typer.tiangolo.com/tutorial/subcommands/)
- [FastAPI `APIRouter`](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Docker volumes](https://docs.docker.com/engine/storage/volumes/)
