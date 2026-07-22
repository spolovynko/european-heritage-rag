# Phase 4 - Wellcome discovery and ingestion client

## 1. Phase at a glance

Phase 4 replaces the ingestion dashboard's sample numbers with a real,
resumable source traversal. HeritageRAG can now discover a bounded set of
English public-domain online books from Wellcome Catalogue API v2, retrieve
their IIIF Presentation 2 manifests, follow canvases in source order, and
reconstruct the available plain-text OCR for each canvas.

This is discovery and traversal, not the durable data lake. The run keeps
status and a small checkpoint on disk, but raw catalogue, manifest, annotation,
and OCR payloads remain a Phase 5 responsibility.

| Area | Implemented choice |
|---|---|
| Discovery source | Wellcome Catalogue API v2 |
| Page/provenance structure | IIIF Presentation 2 manifests and canvases |
| OCR source | IIIF annotation lists with plain-text content bodies |
| HTTP runtime | One reusable synchronous `httpx2.Client` |
| Resilience | Tenacity, bounded attempts, capped waits, `Retry-After` support |
| Validation | Narrow Pydantic v2 source and run-state models |
| Orchestration | Sequential per-work runner with failure isolation |
| Resume state | Atomic JSON status and checkpoint files |
| Operator entry point | Typer command `ingest wellcome` |
| Progress API | `GET /ingestion/status` |
| Browser progress | Three-second polling of real persisted state |
| Container state | Named volume at `/app/var/ingestion` |

Deliberate exclusions:

- Bronze storage of raw source payloads or reconstructed OCR.
- OCR cleaning, normalization, chunking, or search indexing.
- Parallel/asynchronous downloads.
- Canvas-level resume inside one work.
- French or Dutch discovery.
- A database or distributed job queue.
- Server-Sent Events or WebSockets.
- Catalogue-wide performance claims.

## 2. Repository structure

The meaningful Phase 4 files are:

```text
src/european_heritage_rag/
|-- api/main.py
|-- cli.py
|-- core/config.py
`-- sources/wellcome/
    |-- client.py
    |-- ingestion.py
    `-- models.py

tests/
|-- api/test_ingestion_status.py
|-- cli/test_cli.py
|-- fixtures/wellcome/
|   |-- catalogue_page.json
|   |-- iiif_manifest.json
|   `-- ocr_annotation_list.json
`-- sources/wellcome/
    |-- test_client.py
    |-- test_ingestion.py
    `-- test_models.py

frontend/
|-- app.js
|-- index.html
`-- styles.css

Dockerfile
compose.yaml
.env.example

docs/adr/
|-- 0004-wellcome-api-and-iiif-ingestion-strategy.md
`-- README.md
```

Runtime state is generated under `var/ingestion/` and ignored by Git:

```text
var/ingestion/
|-- wellcome-status.json
`-- wellcome-checkpoint.json
```

## 3. Runtime flow

```text
CLI: ingest wellcome
        |
        v
WellcomeIngestionRunner
        |
        | discover_works(limit, query, language)
        v
Wellcome Catalogue API v2 ---- follows nextPage ----+
        |                                            |
        +-- local eligibility validation <-----------+
        |
        v
eligible works in catalogue order
        |
        | one work at a time
        v
IIIF manifest -> first sequence -> ordered canvases
        |                              |
        |                              +-- no OCR reference -> text=None
        v
ordered annotation lists -> ordered plain-text lines
        |
        +-- update status after each event
        `-- replace checkpoint after each processed work

wellcome-status.json ---- GET /ingestion/status ---- browser polling
wellcome-checkpoint.json ---- --resume ---- skip completed/retry failed works
```

All external JSON passes through Pydantic before traversal. Source responses
are not written to a corpus directory in this phase.

## 4. Step-by-step build

This section follows the same order used while building the phase. Each step
states what was built, why it exists, and how it was checked.

### Step 0 - Review the phase contract and existing architecture

Goal: identify what Phase 4 must add without crossing into Phase 5.

Substeps:

1. Read the learning agreement, Phase 4 plan, Phase 3 guide, and existing ADRs.
2. Preserve the current Python 3.12, `uv`, `src` layout, FastAPI application
   factory, Typer CLI, Vite frontend, and one-service container.
3. Convert the phase exit criteria into observable behaviors:
   - five works can be discovered and traversed;
   - missing OCR does not crash a work;
   - an interrupted run has durable resume state;
   - automated tests never require the live Wellcome API;
   - the dashboard displays real status.
4. Keep raw source persistence out of scope because Phase 5 defines Bronze
   identity, checksums, versioning, and replay.

Why: the phase plan is an intended design, while the guide records the tested
implementation. Reviewing the boundaries first prevents a source client from
turning into an unplanned storage pipeline.

### Step 1 - Define dependencies and environment-driven settings

Goal: create one validated configuration contract for every Wellcome request
and for the local state directory.

Substeps:

1. Add `tenacity` for explicit retry behavior. The existing `httpx2` runtime is
   used for HTTP, and pytest-httpx2/respx support offline request tests.
2. Add these `AppSettings` fields:
   - catalogue base URL;
   - User-Agent;
   - connect, read, write, and pool timeouts;
   - maximum attempts;
   - maximum retry wait;
   - ingestion state directory.
3. Give every field a safe local default while allowing the matching
   environment variable to override it. For example,
   `WELLCOME_READ_TIMEOUT_SECONDS=45` overrides the default without editing
   code.
4. Validate bounds with Pydantic so zero/negative timeouts and unreasonable
   retry settings fail during configuration loading.

Why: defaults are not hard-coded deployment decisions. They are documented
fallback values in a typed settings object; environment variables remain the
runtime control surface.

### Step 2 - Model only the Wellcome fields currently needed

Goal: turn external JSON into small typed objects before business logic uses
it.

Substeps:

1. Model catalogue identifiers, licences, digital locations, items, works,
   and paginated result pages.
2. Model IIIF manifests, sequences, canvases, annotation-list references,
   annotation lists, annotations, and annotation bodies.
3. Add internal `TraversedWork` and `TraversedPage` result models.
4. Ignore unknown source fields so harmless API additions do not break the
   client.
5. Keep structural type markers strict, such as `sc:Manifest`, `sc:Canvas`, and
   `sc:AnnotationList`.
6. Reflect real source variants:
   - physical locations may have no URL;
   - image annotation bodies may omit `@type`;
   - eligibility still requires one PDM IIIF location with a URL;
   - OCR extraction still accepts only `cnt:ContentAsText` and `text/plain`.

Why: parsing should tolerate unrelated source content without relaxing the
rules that define an eligible work or a usable OCR line.

### Step 3 - Build representative offline fixtures and model tests

Goal: understand the response shapes and create deterministic examples before
network behavior is implemented.

Substeps:

1. Add a catalogue result containing an eligible book and an ineligible work.
2. Add a two-canvas IIIF manifest where one canvas has OCR and one does not.
3. Add an annotation list with two ordered OCR lines.
4. Prove the fixtures parse and preserve canvas/line order.
5. Prove unknown fields are ignored and incorrect manifest types are rejected.
6. Add regression variants found during the live smoke test: a physical
   location without a URL and a picture annotation body without `@type`.

Why: fixtures document the subset of each external format that the code relies
on, while tests separate model mistakes from HTTP mistakes.

### Step 4 - Implement the Wellcome HTTP and IIIF client

Goal: provide one resilient source adapter that can discover and fully
traverse a work.

#### Step 4.1 - Create the reusable HTTP client

1. Construct one context-managed `httpx2.Client`.
2. Apply the configured base URL, User-Agent, JSON accept header, redirects,
   and four timeout values.
3. Reuse its connection pool for catalogue, manifest, and OCR requests.

#### Step 4.2 - Define retry behavior

1. Retry network/request exceptions.
2. Retry only HTTP 408, 429, 500, 502, 503, and 504.
3. Do not retry permanent responses such as 400 or 404.
4. Respect a numeric `Retry-After` header, capped by configuration.
5. Fall back to capped exponential waits when the header is absent or invalid.
6. Count every actual retry wait for status reporting.

#### Step 4.3 - Discover eligible works

1. Send the server-side filters listed in ADR-0004.
2. Request `items,languages`, because local validation needs those fields.
3. Follow absolute `nextPage` links.
4. Preserve catalogue result order.
5. Re-check work type, online availability, language, PDM licence, IIIF
   location type, and URL locally.
6. Stop when the requested number of eligible works is reached or pagination
   ends.

#### Step 4.4 - Select and retrieve the manifest

1. Find the first digital location that is both PDM and IIIF Presentation.
2. Retrieve and validate the manifest through the same retry path.
3. Require a default sequence; report a clear structure error if none exists.
4. Traverse the first sequence's canvases in declared order.

#### Step 4.5 - Reconstruct OCR per canvas

1. Follow every `otherContent` reference in its declared order.
2. Retrieve and validate every referenced annotation list.
3. Keep only supported plain-text content bodies.
4. Preserve line order and join lines with `\n` without cleaning.
5. Store canvas index, canvas URL, label, annotation URLs, source lines, and
   joined text in `TraversedPage`.
6. Use `text=None` when a canvas has no usable OCR.
7. Fail the work if a referenced OCR list cannot be retrieved; do not disguise
   a 404 as legitimately missing OCR.

Why: catalogue discovery and IIIF traversal are one external-source concern,
but the client does not own run state or durable storage.

### Step 5 - Add orchestration, status, checkpoints, and resume

Goal: make a multi-work run observable and safely restartable.

Substeps:

1. Define `IngestionStatus` for CLI/API/UI state and `IngestionCheckpoint` for
   minimal resume state.
2. Atomically replace JSON files through a temporary sibling file, avoiding a
   partially written status document.
3. Create a stable SHA-256 fingerprint from limit, normalized query, and
   language.
4. Start a fresh run with a unique run ID, or require an existing matching
   fingerprint for `--resume`.
5. Discover first, then traverse works sequentially.
6. Checkpoint after every completed or failed work.
7. On resume, skip completed work IDs and retry failed work IDs.
8. Record one work's terminal exception, continue with later works, and finish
   as `completed_with_failures` when necessary.
9. Treat discovery failure as a failed run because no reliable work list
   exists to process.
10. Count missing OCR pages separately from failures.
11. Retain only the latest 20 operator events.
12. Implement dry-run as catalogue-only discovery with status updates and no
    checkpoint changes.

Why: work-granular state is enough to meet the phase's interruption criterion
without introducing a database or pretending that Phase 4 stores corpus data.

### Step 6 - Expose operations through CLI, API, UI, and Docker

Goal: make the traversal usable by an operator and visible in the existing
application shell.

#### Step 6.1 - CLI

Add:

```powershell
uv run european-heritage-rag ingest wellcome
```

Options:

- `--limit`: maximum eligible works, 1-100, default 5.
- `--query`: optional catalogue query.
- `--language`: currently `eng` only.
- `--resume`: continue the matching checkpoint.
- `--dry-run`: discover only; do not fetch manifests or OCR.

`--resume` and `--dry-run` are mutually exclusive. The command prints the run
ID, final state, work counts, traversed canvases, missing OCR, retries, and
failures.

#### Step 6.2 - API

Register `GET /ingestion/status` before the root static mount. It loads the
current file on every request and returns a typed idle response when no status
file exists.

#### Step 6.3 - Browser dashboard

Replace only the ingestion panel's mock boundary. The browser:

1. requests `/ingestion/status` immediately;
2. polls every three seconds;
3. cancels a request after 3.5 seconds;
4. prevents overlapping polls;
5. renders work/page/missing/failure/retry counts, current work, stages, recent
   events, and attention state;
6. creates event elements with `textContent`, not source-derived HTML;
7. shows a safe unavailable state when polling fails.

The rest of the Phase 3 explorer remains demonstration UI. The New run button
shows the CLI command because the browser does not start server-side jobs in
this phase.

#### Step 6.4 - Container state

1. Create `/app/var/ingestion` in the image.
2. Give the unprivileged application user ownership.
3. Mount the `ingestion-state` named volume through Compose.
4. Keep the API and ingestion command in the same Phase 4 image.

Why: the CLI remains the explicit write/operation boundary, while the API and
UI are read-only views of the same persisted status.

### Step 7 - Verify offline first, then use a bounded live smoke test

Goal: prove behavior without making the test suite dependent on an external
service.

Substeps:

1. Mock every automated Wellcome request.
2. Test two-page pagination, retryable failures, numeric `Retry-After`, invalid
   retry headers, permanent errors, local eligibility, canvas order, missing
   OCR, and referenced annotation failures.
3. Test dry-run, atomic status/checkpoint behavior, per-work failure
   continuation, resume skipping, retry of failures, and fingerprint mismatch.
4. Test CLI defaults/options/validation and the idle/saved status API.
5. Run all Python quality gates and build the Vite bundle.
6. Inspect the real dashboard on desktop and at 390 pixels wide; verify that it
   has no horizontal scrolling or console warnings/errors.
7. Run catalogue-only discovery for five `cholera` works.
8. Traverse exactly five works, inspect missing OCR as a nonfailure, and resume
   from the same checkpoint after correcting real source-model variants.
9. Build and start the Compose application, exercise root/health/status, and
   run one containerized dry run to prove named-volume write permissions.

Why: mocked tests own repeatability. The small live run is compatibility
evidence against the current source, not a test dependency or a performance
benchmark.

## 5. File-by-file implementation review

### 5.1 `core/config.py`

Adds validated Wellcome request controls and `ingestion_state_directory` to
the existing frozen settings object. Field defaults support zero-setup local
development. Pydantic Settings maps environment variables to the same names,
case-insensitively, and the root `.env` file remains supported.

`.env.example` lists every Phase 4 setting and its local default so deployment
configuration is discoverable without reading Python source.

### 5.2 `sources/wellcome/models.py`

Defines the narrow external JSON contract and the internal traversed work/page
contract. External aliases match source names such as `workType`, `nextPage`,
`@id`, `@type`, and `otherContent`. Tuples and frozen models make parsed source
objects immutable.

### 5.3 `sources/wellcome/client.py`

Owns source-specific HTTP behavior. Its small public surface is:

- `fetch_catalogue_page()`;
- `discover_works()`;
- `fetch_manifest()`;
- `fetch_annotation_list()`;
- `traverse_work()`;
- `retry_count` and `close()`.

Pure helpers isolate retry classification, `Retry-After` parsing, eligibility,
manifest URL selection, and OCR-line filtering.

### 5.4 `sources/wellcome/ingestion.py`

Owns run behavior rather than HTTP details. `IngestionClient` is a Protocol, so
orchestration tests use a deterministic fake client. `IngestionStateStore`
owns JSON paths and replacement writes. `WellcomeIngestionRunner` owns the run
state machine. `run_wellcome_ingestion()` is the production composition root.

### 5.5 `cli.py`

Adds a nested Typer application under `ingest`. CLI validation catches invalid
option combinations before calling the runner, while runner validation keeps
the rule intact for non-CLI callers.

### 5.6 `api/main.py`

Adds the read-only status route before the frontend static mount. Dependency
injection supplies settings, which lets tests point the route at temporary
state without changing global files.

### 5.7 `frontend/index.html`, `app.js`, and `styles.css`

The ingestion markup now has stable `data-ingestion-*` render targets. The
JavaScript polls and renders the typed JSON shape defensively. The CSS retains
the existing visual design while adapting panel headers and stage rows for
small screens and clipping decorative overflow at the document boundary.

### 5.8 `Dockerfile` and `compose.yaml`

The image now prepares the state directory before switching to UID 10001.
Compose names the image `phase4` and attaches a persistent named volume. The
one-service architecture and readiness health check remain unchanged.

### 5.9 Tests and fixtures

- `test_models.py` checks fixture parsing, ordering, ignored fields, strict
  discriminators, and observed optional variants.
- `test_client.py` checks request configuration, retries, pagination,
  eligibility, traversal, missing OCR, and terminal source errors.
- `test_ingestion.py` checks dry runs, checkpoints, failure isolation, resume,
  and fingerprint protection.
- `test_ingestion_status.py` checks idle and persisted API responses.
- `test_cli.py` checks the nested command and its option contract.

No automated test calls Wellcome.

## 6. Operational guide

### 6.1 Inspect command help

```powershell
uv run european-heritage-rag ingest wellcome --help
```

### 6.2 Discover without manifests or OCR

```powershell
uv run european-heritage-rag ingest wellcome --limit 5 --query cholera --dry-run
```

Use this to verify catalogue filters and count eligible works. It updates the
status file but deliberately leaves the checkpoint untouched.

### 6.3 Traverse a small run

```powershell
uv run european-heritage-rag ingest wellcome --limit 5 --query cholera
```

This requests catalogue pages, manifests, and referenced annotation lists.
It records control state only; it does not build the Phase 5 corpus.

### 6.4 Resume the same run

```powershell
uv run european-heritage-rag ingest wellcome --limit 5 --query cholera --resume
```

Limit, normalized query, and language must match the checkpoint. Completed
works are skipped; previously failed works are tried again.

### 6.5 Override request policy through environment variables

PowerShell example:

```powershell
$env:WELLCOME_READ_TIMEOUT_SECONDS = "45"
$env:WELLCOME_MAX_ATTEMPTS = "5"
uv run european-heritage-rag ingest wellcome --limit 5
```

Useful configuration names are:

- `WELLCOME_CATALOGUE_BASE_URL`
- `WELLCOME_USER_AGENT`
- `WELLCOME_CONNECT_TIMEOUT_SECONDS`
- `WELLCOME_READ_TIMEOUT_SECONDS`
- `WELLCOME_WRITE_TIMEOUT_SECONDS`
- `WELLCOME_POOL_TIMEOUT_SECONDS`
- `WELLCOME_MAX_ATTEMPTS`
- `WELLCOME_MAX_RETRY_WAIT_SECONDS`
- `INGESTION_STATE_DIRECTORY`

### 6.6 View status directly

Start the combined application:

```powershell
pnpm --dir frontend build
uv run uvicorn european_heritage_rag.api.main:app
```

Then open:

- `http://127.0.0.1:8000/` for the dashboard;
- `http://127.0.0.1:8000/ingestion/status` for raw status JSON;
- `http://127.0.0.1:8000/docs` for the FastAPI schema.

The API process and CLI must resolve the same state directory. With the default
configuration, run both from the repository root.

### 6.7 Run through Docker Compose

```powershell
docker compose up --detach --build --wait
docker compose exec api european-heritage-rag ingest wellcome --limit 5 --query cholera --dry-run
docker compose down
```

Compose preserves the named ingestion volume when containers are replaced or
`docker compose down` is used. Removing the named volume deletes its persisted
status and checkpoint, so treat that as a deliberate cleanup operation.

## 7. Verification evidence

The Phase 4 closure gate was run on 2026-07-22.

| Command or check | Property proved | Result |
|---|---|---|
| `uv sync --locked` | Locked backend dependency graph | Passed; 43 packages checked |
| `uv run pytest` | Backend, client, orchestration, CLI, and API behavior | 53 tests passed |
| `uv run ruff check .` | Python lint rules | Passed |
| `uv run ruff format --check .` | Python formatting | 22 files formatted |
| `uv run mypy src` | Strict source type checking | Passed; 13 source files |
| `pnpm --dir frontend build` | Production frontend bundle | Passed |
| Desktop browser check | Real status render and console diagnostics | 5/5 works, 246 canvases, 14 missing OCR, 0 failures; no warnings/errors |
| 390 px browser check | Responsive ingestion panel | No horizontal scrolling |
| Five-work live smoke | Current Wellcome compatibility | 5 completed, 246 canvases, 14 without OCR, 0 retries, 0 failures |
| `docker compose config --quiet` | Valid Compose model | Passed |
| `docker compose build` | Phase 4 multi-stage image | Passed |
| `docker compose up --detach --wait` | Container startup and readiness | Healthy |
| `GET /` | Combined frontend delivery | HTTP 200 |
| `GET /health/ready` | Container readiness API | HTTP 200, `status=ok` |
| `GET /ingestion/status` | Idle state before first volume run | HTTP 200, `status=idle` |
| Containerized one-work dry run | Network access and unprivileged volume writes | Passed; one work discovered |
| `git diff --check` | Working diff whitespace | Passed |

Measured live run:

```text
Run ID: 6a16979c880b43debb7378dfce145762
Query: cholera
Requested works: 5
Discovered works: 5
Completed works: 5
Canvases traversed: 246
Canvases without OCR: 14
Retry waits: 0
Terminal failures: 0
Final status: completed
```

These numbers describe one bounded compatibility run. They are not retrieval,
answer-quality, throughput, or catalogue-coverage metrics.

## 8. Troubleshooting

### Resume says the options do not match

Use the same `--limit`, `--query`, and `--language` as the original run. Start
a new run without `--resume` if you intentionally want different discovery
options.

### Resume says no checkpoint exists

Dry runs do not create checkpoints. Run a non-dry ingestion first and ensure
the CLI is using the expected `INGESTION_STATE_DIRECTORY`.

### A canvas has no OCR

This is expected source variation. It increments `missing_ocr_pages` and keeps
the work successful. A failed referenced OCR request is different: it records
a work failure.

### The dashboard remains idle while the CLI runs

Confirm the API and CLI use the same working directory or explicitly set the
same absolute `INGESTION_STATE_DIRECTORY` for both processes.

### A retryable request keeps failing

The client stops after `WELLCOME_MAX_ATTEMPTS`. The terminal error is recorded
against the work, and a later matching `--resume` can attempt that work again.

### The UI says progress is unavailable

Check `GET /ingestion/status`, the API process, and browser console/network
diagnostics. The UI intentionally keeps the last safe shape instead of
inventing progress when polling fails.

## 9. Review summary

Phase 4 is complete as a bounded Wellcome discovery and traversal layer.

Stable boundaries:

- Catalogue API filters plus local eligibility validation.
- IIIF canvas order as the current page-like source order.
- Exact OCR line preservation at ingestion time.
- One reusable request policy for every source URL.
- HTTP/source concerns separated from orchestration concerns.
- Work-level atomic checkpoint and resume behavior.
- CLI writes; API and browser read persisted status.
- Offline fixtures and mocked HTTP tests as the regression baseline.
- Sequential traversal until measurement justifies concurrency.

Known limitations to carry forward:

- Raw source data is not stored or replayable yet.
- Resume repeats an interrupted work from its manifest.
- File state supports one local writer, not distributed workers.
- Printed page numbering is not normalized.
- OCR is preserved but not cleaned.
- Only English PDM online books are eligible.
- Browser polling is not an automated end-to-end test suite.
- `Retry-After` HTTP dates are not parsed.

Phase 5 should consume these source contracts and add immutable Bronze
payloads, deterministic paths, checksums, acquisition metadata, and replay
without changing the source responses.

## 10. Official references

- [Wellcome Collection catalogue API documentation](https://developers.wellcomecollection.org/docs/catalogue)
- [Wellcome Collection catalogue API reference](https://developers.wellcomecollection.org/api/catalogue)
- [Connecting Wellcome APIs together](https://developers.wellcomecollection.org/docs/examples/connecting-the-apis-together)
- [Wellcome Collection datasets](https://developers.wellcomecollection.org/docs/datasets)
- [IIIF Presentation API 2.1](https://iiif.io/api/presentation/2.1/)
- [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/)
- [Tenacity documentation](https://tenacity.readthedocs.io/)
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)
- [Typer options](https://typer.tiangolo.com/tutorial/options/)
- [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/)
