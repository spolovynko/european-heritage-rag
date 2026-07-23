# Phase 4 - Wellcome discovery and ingestion client

## 1. Phase at a glance

Phase 4 taught HeritageRAG how to find books at Wellcome and read their
available OCR in page order.

In simple terms, the program can now:

1. ask Wellcome for a small list of suitable books;
2. find the page map for each book;
3. visit each page in order;
4. collect the OCR text attached to that page;
5. record progress after every book; and
6. continue a matching run after an interruption.

This phase does not save the books or OCR as a reusable dataset. It only proves
that we can find and traverse them correctly. Phase 5 will store the raw source
data in the Bronze layer.

### Important terms

| Term | Simple meaning in this project |
|---|---|
| Catalogue API | Wellcome's machine-readable list of works and their metadata |
| IIIF | A standard way for libraries to describe digital objects such as scanned books |
| Manifest | A JSON document that describes one digital book and its ordered pages |
| Canvas | IIIF's page-like unit; usually one scanned page or image |
| OCR | Text that software has read from a scanned page |
| Annotation list | A JSON document that connects OCR text to a canvas |
| Checkpoint | A small save point used to continue an interrupted run |
| Dry run | Discovery only; it does not request manifests or OCR |
| Bronze layer | The future unchanged copy of source responses and acquisition facts |

### Main technical choices

| Area | Choice made in Phase 4 |
|---|---|
| Book discovery | Wellcome Catalogue API v2 |
| Page order | IIIF Presentation 2 manifests and canvases |
| OCR source | IIIF annotation lists containing plain text |
| HTTP requests | One reusable synchronous `httpx2.Client` |
| Temporary failures | Tenacity retries with limited attempts and waits |
| JSON validation | Small Pydantic models containing only fields we use |
| Processing order | One work at a time |
| Resume data | Two small JSON files written safely to disk |
| Operator command | `european-heritage-rag ingest wellcome` |
| Progress API | `GET /ingestion/status` |
| Dashboard updates | Poll the status API every three seconds |
| Docker persistence | Named volume mounted at `/app/var/ingestion` |

Not included in Phase 4:

- storing raw catalogue, manifest, annotation, or OCR responses;
- cleaning OCR text;
- splitting text into retrieval chunks;
- search or vector indexing;
- parallel downloads;
- resuming in the middle of one book;
- French or Dutch discovery;
- a job database or distributed workers; and
- live push updates through Server-Sent Events or WebSockets.

## 2. Repository structure

The main Phase 4 files are:

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
|-- styles.css
`-- vite.config.js

.env.example
Dockerfile
compose.yaml

docs/adr/
|-- 0004-wellcome-api-and-iiif-ingestion-strategy.md
`-- README.md
```

The application creates these local state files while it runs:

```text
var/ingestion/
|-- wellcome-status.json
`-- wellcome-checkpoint.json
```

They are ignored by Git because they describe one local run.

- `wellcome-status.json` is the latest progress shown by the API and dashboard.
- `wellcome-checkpoint.json` contains the minimum information needed to resume.

Neither file contains the actual source records or OCR corpus.

## 3. Runtime flow

The full flow is:

```text
CLI command
    |
    v
Discover eligible works from Wellcome Catalogue API
    |
    v
Check each result against our rules
    |
    v
Process one work at a time
    |
    +--> request its IIIF manifest
    |        |
    |        v
    |    read canvases in order
    |        |
    |        v
    |    request each OCR annotation list
    |        |
    |        v
    |    keep plain-text OCR lines in source order
    |
    +--> write status and checkpoint
    |
    v
Move to the next work
```

The status reaches the browser through a separate read path:

```text
wellcome-status.json
        |
        | read by FastAPI
        v
GET /ingestion/status
        |
        | requested every three seconds
        v
Ingestion dashboard
```

The CLI is the writer. The API and browser only read the latest status.

## 4. Step-by-step build

This section follows the order in which we built Phase 4. Every step explains
what we did, why we needed it, and how it works.

### Step 0 - Review the phase boundary

#### What we did

We read the learning agreement, Phase 4 plan, Phase 3 guide, and existing ADRs.
We turned the Phase 4 completion rules into concrete behavior:

- discover and traverse five works;
- do not crash when a page has no OCR;
- save enough information to resume;
- keep automated tests offline; and
- show real progress in the dashboard.

#### Why

The important boundary was between Phase 4 and Phase 5. Phase 4 should learn
how to fetch and understand Wellcome data. Phase 5 should decide how raw data
is named, stored, checked, and replayed.

If we stored source payloads now, we would create a Bronze format before making
its design decisions.

#### How to think about it

Phase 4 is the reader and run controller. Phase 5 will be the archive.

### Step 1 - Add dependencies and settings

#### What we did

We used the existing `httpx2` package for HTTP and added Tenacity for retry
control. We added settings for:

- Wellcome catalogue base URL;
- User-Agent;
- connect timeout;
- read timeout;
- write timeout;
- connection-pool timeout;
- maximum attempts;
- maximum wait between attempts; and
- local status/checkpoint directory.

The same settings and defaults are listed in `.env.example`.

#### Why

Network behavior should not be scattered through the client code. A developer
or deployment can change a timeout or User-Agent without editing Python.

Defaults are not locked deployment values. They are safe fallback values.
Environment variables can replace them, for example:

```powershell
$env:WELLCOME_READ_TIMEOUT_SECONDS = "45"
```

#### How it works

Pydantic Settings reads the environment and validates each value. Invalid
values, such as a zero timeout or too many retry attempts, fail early during
settings creation.

### Step 2 - Create small models for source JSON

#### What we did

We added Pydantic models for only the data needed now:

- catalogue pages, works, items, locations, licences, and languages;
- IIIF manifests, sequences, canvases, and annotation-list links;
- OCR annotations and their text bodies; and
- our internal `TraversedWork` and `TraversedPage` results.

#### Why

External JSON should be checked before traversal code trusts it. At the same
time, Wellcome responses contain many fields that Phase 4 does not use.
Copying every field would create unnecessary work and make our code depend on
more source details.

#### How it works

The models follow two rules:

1. Required structure is strict. A manifest must identify itself as an IIIF
   manifest, and required IDs must be valid.
2. Unused fields are ignored. A new unrelated field from Wellcome will not
   break the client.

The live source showed two useful examples:

- a physical location may have no URL;
- a picture annotation body may have no `@type`.

The models accept those unrelated variants, but the business rules remain
strict. A work is eligible only when it has a PDM IIIF URL, and OCR is accepted
only when it is explicitly plain text.

### Step 3 - Add offline fixtures and model tests

#### What we did

We added three small JSON examples:

1. a catalogue page with eligible and ineligible works;
2. a two-canvas manifest where one canvas has OCR and one does not; and
3. an annotation list containing two OCR lines.

Tests prove that the models:

- parse these examples;
- keep canvas and line order;
- ignore fields we do not use;
- reject the wrong IIIF object type;
- allow a physical location without a URL; and
- allow a non-text picture body without `@type`.

#### Why

Fixtures make source behavior repeatable. They let us learn and test the JSON
shape without asking the live Wellcome service every time.

#### How to think about it

A fixture is a controlled example, not a fake claim about the entire API. Live
smoke tests later check whether the examples still match current source data.

### Step 4 - Build the Wellcome client

The client owns communication with Wellcome. It does not own run checkpoints
or the dashboard.

#### Step 4.1 - Reuse one HTTP client

What we did:

1. Create one context-managed `httpx2.Client`.
2. Apply the base URL, User-Agent, JSON header, redirects, and four timeouts.
3. Reuse the same connection pool for catalogue, manifest, and OCR requests.

Why: opening a new connection setup for every page is wasteful. One client also
ensures that every source request follows the same policy.

#### Step 4.2 - Retry only temporary problems

What we retry:

- network/request errors; and
- HTTP 408, 429, 500, 502, 503, and 504.

What we do not retry:

- permanent client responses such as 400 and 404.

How waiting works:

1. If the server gives a numeric `Retry-After`, use it up to our configured
   maximum.
2. Otherwise, use an increasing exponential wait up to that maximum.
3. Stop after the configured number of attempts.
4. Count every retry wait so it appears in status.

Why: retrying can solve a temporary overload or network interruption. It will
not fix a bad URL or invalid request, so repeating permanent errors only adds
delay and load.

#### Step 4.3 - Discover eligible works

The catalogue request uses these filters:

```text
workType=a
availabilities=online
items.locations.license=pdm
items.locations.locationType=iiif-presentation
languages=eng
include=items,languages
```

Simple meaning:

- `workType=a`: books/monographs for this initial source slice;
- `online`: a digital item is available;
- `pdm`: it carries the Public Domain Mark;
- `iiif-presentation`: it has a page manifest we can traverse;
- `eng`: it belongs to the English baseline; and
- `include=items,languages`: return the fields needed for our own check.

The API filters first. The client then checks every returned work locally. This
second check protects our eligibility rules if a response is incomplete or
mixed.

If Wellcome provides `nextPage`, the client follows it and preserves result
order. It stops when it has enough eligible works or there are no more pages.

#### Step 4.4 - Retrieve the manifest

For one eligible work, the client:

1. selects a digital location that is PDM and IIIF Presentation;
2. requests its manifest through the same retry system;
3. validates the JSON;
4. uses the first/default sequence; and
5. visits its canvases in declared order.

If no sequence exists, the client reports a clear structure error. Without a
sequence, it cannot know the page order.

#### Step 4.5 - Rebuild the page OCR

For each canvas, the client:

1. reads each `otherContent` annotation-list URL in order;
2. downloads and validates the annotation list;
3. keeps only `cnt:ContentAsText` bodies in `text/plain` format;
4. keeps the OCR lines in their original order;
5. joins the lines with `\n` without cleaning them; and
6. stores the canvas index, URL, label, annotation URLs, lines, and joined text.

Two cases must stay separate:

- No OCR is available: the page is valid and receives `text=None`.
- An advertised OCR URL fails: the work fails because a source request did not
  succeed.

Why: silently treating a broken URL as missing OCR would hide a real ingestion
problem.

### Step 5 - Add run status, checkpoints, and resume

The Wellcome client handles one source operation. The ingestion runner handles
the whole multi-work job.

#### What we did

We created:

- `IngestionStatus`: information for the CLI, API, and dashboard;
- `IngestionCheckpoint`: the minimum data required to resume;
- `IngestionStateStore`: reads and safely replaces the JSON files; and
- `WellcomeIngestionRunner`: controls discovery and work processing.

#### How a new run works

1. Check the options.
2. Create a unique run ID.
3. Create an option fingerprint from limit, query, and language.
4. Write the starting status and checkpoint.
5. Discover works.
6. Process one work at a time.
7. After each work, replace the checkpoint.
8. Finish as `completed` or `completed_with_failures`.

#### What is a fingerprint?

It is a SHA-256 value made from the options that define the work list:

- limit;
- normalized query; and
- language.

It is not a security secret. It is a reliable comparison value. Resume is
allowed only when the current options produce the same fingerprint.

#### How resume works

1. Load the existing checkpoint.
2. Confirm that its fingerprint matches the current options.
3. Discover the same limited work list again.
4. Skip IDs already marked complete.
5. Try previously failed or unfinished works again.

The checkpoint is work-level. If the process stops halfway through one book,
resume starts that book again from its manifest.

#### How failures work

- A discovery failure ends the run because there is no reliable work list.
- A single work failure is recorded, but later works still run.
- A missing-OCR page is counted separately and does not fail the work.
- Status keeps only the latest 20 events so the file stays small.

#### How files are written safely

The store first writes a temporary file beside the real file. It then replaces
the real file with the completed temporary file. This reduces the chance that
the API reads a half-written JSON document.

#### How dry-run works

Dry-run performs catalogue discovery and updates status. It does not request
manifests or OCR, and it does not create or change the resume checkpoint.

### Step 6 - Connect CLI, API, dashboard, and Docker

#### Step 6.1 - CLI command

The command is:

```powershell
uv run european-heritage-rag ingest wellcome
```

| Option | Meaning |
|---|---|
| `--limit` | Maximum eligible works, from 1 to 100; default is 5 |
| `--query` | Optional Wellcome search text |
| `--language` | Language filter; Phase 4 accepts only `eng` |
| `--resume` | Continue the matching checkpoint |
| `--dry-run` | Discover works but do not request manifests or OCR |

`--resume` and `--dry-run` cannot be used together. One continues a saved full
run; the other deliberately creates no resume checkpoint.

At the end, the CLI prints the run ID, status, work counts, canvases traversed,
missing OCR, retries, and failures.

#### Step 6.2 - Status API

FastAPI now exposes:

```http
GET /ingestion/status
```

The route reads `wellcome-status.json` for every request. Before the first run,
it returns a valid idle status instead of an error.

The route is registered before the broad frontend mount so `/` cannot hide it.

#### Step 6.3 - Browser dashboard

Phase 4 replaced only the ingestion view's sample progress. Other explorer,
retrieval, evaluation, and chat data remains demonstration content.

The browser:

1. requests status as soon as it starts;
2. asks again every three seconds;
3. cancels a request after 3.5 seconds;
4. prevents two status requests from overlapping;
5. updates works, pages, missing OCR, failures, retries, current work, stages,
   recent events, and attention text; and
6. shows an unavailable state if the API cannot be reached.

Event text is inserted with `textContent`. This means source-provided titles or
errors are displayed as text, not interpreted as HTML.

The New run button shows the CLI command. The browser does not start ingestion
jobs in this phase.

#### Step 6.4 - Docker state

The image creates `/app/var/ingestion` and gives the unprivileged application
user permission to write there.

Compose mounts a named volume at that path. Replacing the API container does
not remove its status or checkpoint.

Why: a checkpoint is only useful if normal container replacement does not
erase it.

### Step 7 - Test offline and then run a small live check

#### Automated checks

Every automated Wellcome request is mocked. Tests cover:

- two-page catalogue pagination;
- temporary retry behavior;
- numeric and invalid `Retry-After` values;
- permanent errors that must not retry;
- local eligibility checking;
- manifest and canvas order;
- OCR line order;
- pages with no OCR;
- a broken referenced annotation URL;
- dry-run and checkpoint behavior;
- one-work failure while later works continue;
- resume skipping and retrying;
- fingerprint mismatch;
- CLI validation; and
- idle and saved API status.

Why mock automated tests: they must be fast and repeatable even when Wellcome
or the network is unavailable.

#### Live checks

After offline checks passed, we used a deliberately small live query:

1. Discover five `cholera` works with dry-run.
2. Traverse those five works.
3. Inspect real source variants and add regression tests for them.
4. Resume the matching checkpoint.
5. Confirm the final status in the browser.

Why only five: the goal was compatibility evidence, not bulk harvesting or a
speed benchmark.

#### Container checks

We also built and started the Compose application, checked root/health/status,
and ran one containerized dry-run. This proved that the unprivileged process
can write status into the named volume.

## 5. File-by-file implementation review

### 5.1 `core/config.py` and `.env.example`

What: these files define and document the Wellcome request settings and state
directory.

Why: runtime policy can be changed through environment variables instead of
editing source code.

How: Pydantic loads, validates, and freezes the settings. `.env.example` shows
every available name and default.

### 5.2 `sources/wellcome/models.py`

What: this file describes the parts of Wellcome and IIIF JSON that Phase 4
uses, plus the page/work objects returned by traversal.

Why: source data is checked at one boundary instead of spreading dictionary
lookups throughout the code.

How: aliases connect Python names to JSON names such as `workType`, `nextPage`,
`@id`, `@type`, and `otherContent`. Parsed source objects are frozen so later
code cannot silently change them.

### 5.3 `sources/wellcome/client.py`

What: this file communicates with Wellcome.

Its main operations are:

- fetch one catalogue page;
- discover eligible works;
- fetch one IIIF manifest;
- fetch one OCR annotation list; and
- traverse one complete work.

Small helper functions decide whether an error is temporary, parse
`Retry-After`, check eligibility, find a manifest URL, and select OCR lines.

Why: all Wellcome-specific request and traversal rules stay in one file.

### 5.4 `sources/wellcome/ingestion.py`

What: this file controls the complete run.

| Part | Job |
|---|---|
| `IngestionClient` | Describes the client behavior the runner needs, which makes fake clients easy to use in tests |
| `IngestionStateStore` | Reads and safely replaces status/checkpoint JSON |
| `WellcomeIngestionRunner` | Controls discovery, sequential work processing, failure handling, and resume |
| `run_wellcome_ingestion()` | Creates the real client and store, then starts the runner |

Why separate this from `client.py`: HTTP rules and job-control rules change for
different reasons and can be tested independently.

### 5.5 `cli.py`

What: adds `ingest wellcome` under the existing Typer command group.

Why: the CLI is the explicit way to start a source run. It validates terminal
options and delegates the real work to the ingestion runner.

The runner also validates important rules so a future non-CLI caller cannot
bypass them.

### 5.6 `api/main.py`

What: adds the read-only status endpoint.

Why: the browser needs progress, but it should not read local files directly.
FastAPI turns the saved model into a stable JSON response.

Settings are supplied through FastAPI's dependency system. Tests can therefore
point the endpoint at a temporary directory.

### 5.7 `frontend/index.html`, `app.js`, `styles.css`, and `vite.config.js`

What changed:

- HTML gained named `data-ingestion-*` places for real values.
- JavaScript polls and renders the status response.
- CSS supports the real event content on desktop and small screens.
- Vite forwards `/ingestion` requests during frontend development.

Why: the existing Phase 3 view could be connected without rebuilding the
whole frontend.

### 5.8 `Dockerfile` and `compose.yaml`

What changed:

- the image creates a writable ingestion state folder;
- Compose uses the Phase 4 image name; and
- a named volume stores status and checkpoints.

The application still uses one service and the same readiness check.

### 5.9 Tests and fixtures

| File | Main behavior checked |
|---|---|
| `test_models.py` | JSON parsing, order, ignored fields, strict types, and real optional variants |
| `test_client.py` | Request setup, retries, pagination, eligibility, traversal, missing OCR, and source failures |
| `test_ingestion.py` | Dry-run, checkpoints, failure isolation, resume, and fingerprint protection |
| `test_ingestion_status.py` | Idle and saved status API responses |
| `test_cli.py` | Command options and validation |

No automated test calls the live Wellcome service.

## 6. Operational guide

### 6.1 Read the command help

```powershell
uv run european-heritage-rag ingest wellcome --help
```

Use this first when you forget an option or its default.

### 6.2 Discover without requesting book pages

```powershell
uv run european-heritage-rag ingest wellcome --limit 5 --query cholera --dry-run
```

What it does: asks only the catalogue for five eligible works.

What it does not do: request manifests, request OCR, or change the checkpoint.

### 6.3 Traverse a small run

```powershell
uv run european-heritage-rag ingest wellcome --limit 5 --query cholera
```

What it does: discovers works, requests their manifests, follows canvases and
OCR lists, and writes progress/checkpoint state.

What it does not do: save the source JSON and OCR as the Phase 5 corpus.

### 6.4 Resume the same run

```powershell
uv run european-heritage-rag ingest wellcome --limit 5 --query cholera --resume
```

Use exactly the same limit, query, and language. Completed works are skipped.
Failed or unfinished works are tried again.

### 6.5 Change request settings

PowerShell example:

```powershell
$env:WELLCOME_READ_TIMEOUT_SECONDS = "45"
$env:WELLCOME_MAX_ATTEMPTS = "5"
uv run european-heritage-rag ingest wellcome --limit 5
```

Available Phase 4 environment variables:

- `WELLCOME_CATALOGUE_BASE_URL`
- `WELLCOME_USER_AGENT`
- `WELLCOME_CONNECT_TIMEOUT_SECONDS`
- `WELLCOME_READ_TIMEOUT_SECONDS`
- `WELLCOME_WRITE_TIMEOUT_SECONDS`
- `WELLCOME_POOL_TIMEOUT_SECONDS`
- `WELLCOME_MAX_ATTEMPTS`
- `WELLCOME_MAX_RETRY_WAIT_SECONDS`
- `INGESTION_STATE_DIRECTORY`

### 6.6 View progress

Build the frontend and start FastAPI:

```powershell
pnpm --dir frontend build
uv run uvicorn european_heritage_rag.api.main:app
```

Then open:

- `http://127.0.0.1:8000/` for the visual dashboard;
- `http://127.0.0.1:8000/ingestion/status` for the status JSON; or
- `http://127.0.0.1:8000/docs` for the API documentation.

Important: the CLI and API must use the same ingestion state directory. With
default settings, run both from the repository root.

### 6.7 Run with Docker Compose

```powershell
docker compose up --detach --build --wait
docker compose exec api european-heritage-rag ingest wellcome --limit 5 --query cholera --dry-run
docker compose down
```

`docker compose down` removes the container and network but keeps the named
volume. Deleting that volume would delete its checkpoint and status, so volume
removal should always be intentional.

## 7. Verification evidence

The Phase 4 completion checks ran on 2026-07-22.

| Command or check | What it proved | Result |
|---|---|---|
| `uv sync --locked` | Backend packages match the lockfile | Passed; 43 packages checked |
| `uv run pytest` | Backend, source client, runner, CLI, and API behavior | 53 tests passed |
| `uv run ruff check .` | Python lint rules | Passed |
| `uv run ruff format --check .` | Python formatting | 22 files formatted |
| `uv run mypy src` | Strict source type checking | Passed; 13 source files |
| `pnpm --dir frontend build` | Vite can create the production frontend | Passed |
| Desktop browser check | The dashboard shows the real saved status | 5/5 works, 246 canvases, 14 missing OCR, 0 failures; no warnings/errors |
| 390 px browser check | The ingestion view fits a small screen | No horizontal scrolling |
| Five-work live check | The client works with current Wellcome responses | 5 complete, 246 canvases, 14 without OCR, 0 retries, 0 failures |
| `docker compose config --quiet` | The Compose file is valid | Passed |
| `docker compose build` | The Phase 4 image builds | Passed |
| `docker compose up --detach --wait` | The container starts and becomes ready | Healthy |
| `GET /` | The combined application serves the frontend | HTTP 200 |
| `GET /health/ready` | The combined application serves readiness | HTTP 200, `status=ok` |
| `GET /ingestion/status` | Status works before any volume run | HTTP 200, `status=idle` |
| Container dry-run | The unprivileged user can write to the named volume | Passed; one work discovered |
| `git diff --check` | The change set has no whitespace errors | Passed |

The measured live run was:

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

What these numbers mean: this one small run completed successfully against the
current source.

What they do not mean: they do not prove catalogue-wide coverage, speed,
retrieval quality, citation quality, or answer quality.

## 8. Troubleshooting

### Resume says the options do not match

Cause: limit, query, or language differs from the saved run.

Action: use the original options, or omit `--resume` to deliberately start a
new run.

### Resume says no checkpoint exists

Cause: no full run has created one, the state directory is different, or the
only previous command was a dry-run.

Action: run a normal ingestion and confirm `INGESTION_STATE_DIRECTORY`.

### A canvas has no OCR

Meaning: the canvas is valid, but no supported plain-text OCR was attached.

Result: `missing_ocr_pages` increases and the work can still succeed.

This is different from a referenced OCR URL returning an error. A failed URL
is recorded as a work failure.

### The dashboard stays idle while the CLI runs

Cause: the API and CLI are probably reading different relative directories.

Action: run both from the repository root or give both the same absolute
`INGESTION_STATE_DIRECTORY`.

### A temporary request keeps failing

The client stops after `WELLCOME_MAX_ATTEMPTS`. The final error is recorded for
that work. A later matching `--resume` can try the work again.

### The dashboard says progress is unavailable

Check `/ingestion/status`, the API process, and the browser network/console
output. The UI shows an honest unavailable state instead of inventing values.

## 9. Review summary

Phase 4 is complete. HeritageRAG can discover a small eligible source set,
traverse its IIIF canvases, read available OCR in order, report progress, and
resume at work level.

What should remain stable:

- use the Wellcome API rather than scraping pages;
- apply server filters and then validate eligibility locally;
- use IIIF canvas order as the current page-like order;
- preserve OCR lines exactly during ingestion;
- use one request and retry policy for every source URL;
- keep HTTP traversal separate from run control;
- checkpoint after each work;
- keep the CLI as writer and API/dashboard as readers;
- keep automated tests offline; and
- remain sequential until measurements justify concurrency.

Known limits:

- source payloads and OCR are not stored yet;
- an interrupted book starts again from its manifest;
- JSON state expects one local writer;
- printed page numbers are not normalized;
- OCR is not cleaned;
- only English PDM online books are accepted;
- browser polling has no automated end-to-end test suite; and
- HTTP-date `Retry-After` values are not parsed.

What Phase 5 should do next: store unchanged source payloads using stable paths,
checksums, and acquisition metadata so later phases can replay ingestion
without asking Wellcome again.

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
