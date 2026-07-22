# ADR-0004: Wellcome API and IIIF ingestion strategy

- Status: Accepted
- Date: 2026-07-22
- Phase: Phase 4 - Wellcome discovery and ingestion client

## Context

HeritageRAG needs a repeatable way to find digitised Wellcome books and map
their OCR back to ordered page-like units. Phase 4 is the source-integration
boundary: it must discover eligible works, follow their IIIF Presentation
manifests, retrieve per-canvas OCR annotations, survive temporary HTTP
failures, and expose enough durable progress to resume an interrupted run.

The source boundary must also remain narrower than the later data pipeline.
Phase 5 owns durable Bronze copies of source payloads. Phase 4 may validate and
traverse source responses, but it must not quietly invent a second raw-data
store.

The decision therefore answers four main questions:

- Why use supported APIs instead of scraping collection pages?
- Why begin with catalogue API harvesting instead of the daily snapshot?
- Why restrict the first corpus to online public-domain books?
- Why keep traversal sequential rather than adding broad concurrency?

## Decision

### Discover works through Wellcome Catalogue API v2

HeritageRAG requests the `works` endpoint with these source filters:

```text
workType=a
availabilities=online
items.locations.license=pdm
items.locations.locationType=iiif-presentation
languages=eng
include=items,languages
```

The client follows `nextPage` URLs in source order until it has collected the
requested limit. It then checks the same eligibility rules locally. Local
validation protects the ingestion contract if an API response contains a
mixed or incomplete record; it is not a replacement for the server filters.

The CLI bounds one run to 1-100 eligible works. English is the only accepted
language in this phase because the evaluation contract has not yet defined a
reviewed multilingual baseline.

### Use IIIF Presentation 2 for page order and OCR references

For each eligible catalogue work, the client selects a public-domain digital
location whose type is `iiif-presentation`. It retrieves the manifest, uses
the first/default sequence, and traverses its canvases in their declared
order.

Each canvas is treated as the current page-like provenance unit. The client
follows every `otherContent` annotation-list reference in source order and
keeps only annotation bodies that explicitly contain `cnt:ContentAsText` in
`text/plain` format. Lines are joined with newline characters without OCR
cleaning or content rewriting.

A canvas with no annotation list, an empty annotation list, or no supported
text body becomes a valid page with `text=None`. A referenced annotation list
that fails to load is a work failure, because silently treating a failed
request as missing OCR would hide a source-access problem.

### Use narrow tolerant Pydantic source models

Models include only fields needed by discovery, manifest traversal, OCR
reconstruction, and provenance. Unknown source fields are ignored so unrelated
API additions do not break ingestion. Required structural discriminators,
identifiers, and URLs are still validated.

Optional fields reflect observed source variants. For example, physical
locations may have no URL, and non-text IIIF annotation bodies may omit
`@type`. Eligibility and OCR extraction remain strict even though parsing is
tolerant of those unrelated variants.

### Use one reusable synchronous HTTP client with bounded retries

One `httpx2.Client` owns connection pooling, redirects, the JSON accept header,
the configured User-Agent, and separate connect, read, write, and pool
timeouts. The same request path is used for catalogue pages, manifests, and
annotation lists.

Tenacity retries network errors and HTTP 408, 429, 500, 502, 503, and 504.
Numeric `Retry-After` values are respected up to the configured maximum;
otherwise capped exponential backoff is used. Permanent client errors such as
400 and 404 are not retried. Attempts and maximum waits are configuration
values with safe defaults that may be overridden through environment
variables.

Work traversal is sequential in Phase 4. This creates a predictable request
rate, makes checkpoint behavior easy to reason about, and avoids multiplying
load on Wellcome before corpus size and rate behavior are measured.

### Separate the HTTP client from ingestion orchestration

The HTTP client discovers and traverses source objects. A separate runner owns
run status, per-work failure isolation, checkpoints, dry runs, and resume
behavior.

The runner writes two atomic JSON files under the configured ingestion-state
directory:

- `wellcome-status.json` is the operator-facing snapshot used by the API and
  dashboard.
- `wellcome-checkpoint.json` is the minimal resume state: run identity, option
  fingerprint, completed work IDs, counters, and failures.

The resume fingerprint is derived from limit, normalized query, and language.
A resume request must match it. Completed works are skipped; failed works are
attempted again. A checkpoint is replaced after each processed work. One work
failure is recorded and the run continues; discovery failure ends the run.

Dry-run mode performs catalogue discovery only, writes live status, and does
not create or change a resume checkpoint. Status keeps the latest 20 events.
Neither file contains raw catalogue, manifest, annotation, or OCR payloads.

### Expose progress through CLI, API, and polling UI

The operational command is:

```text
european-heritage-rag ingest wellcome
```

It supports `--limit`, `--query`, `--language`, `--resume`, and `--dry-run`.
FastAPI exposes the same persisted status at `GET /ingestion/status`. The
browser polls that endpoint every three seconds and renders the current work,
discovered/completed works, traversed canvases, missing OCR count, retries,
failures, and recent events.

Polling is sufficient for a single local ingestion process and a small status
document. Streaming transport is deliberately deferred.

### Persist container state in a named volume

The runtime image creates a writable `/app/var/ingestion` directory before it
switches to the unprivileged application user. Docker Compose mounts a named
volume there, so status and checkpoints survive container replacement.

## Alternatives considered

### Scrape public collection pages

HTML pages are designed for people and may change presentation structure
without preserving a machine contract. Scraping would also duplicate links
and metadata already exposed through the catalogue and IIIF APIs. It is less
stable, less clear about request intent, and harder to test with narrow JSON
fixtures.

### Start from the daily catalogue snapshot

The snapshot is attractive for large, repeatable bulk harvesting and may be a
better source once the project needs a substantial or fully versioned corpus.
It adds download size, local filtering, snapshot versioning, and storage
operations that are unnecessary for the five-work learning baseline. API
harvesting keeps the first source slice observable and small.

### Accept all online licences and material types

This would enlarge coverage but weaken the initial rights boundary and mix
books with differently structured source objects. Public Domain Mark online
books give the first ingestion and evaluation baseline one defensible content
and provenance shape. Expansion requires an explicit rights and evaluation
decision.

### Add asynchronous or parallel canvas downloads now

Concurrency could reduce elapsed time for large books, but would require rate
limits, task cancellation, ordered result assembly, more complicated retries,
and concurrent checkpoint semantics. The five-work baseline does not justify
that complexity. Concurrency remains bounded at one active traversal.

### Keep progress only in process memory

In-memory state is simple but disappears on interruption and cannot be read by
another API process. Small atomic JSON files provide the required resume and
dashboard boundary without introducing a database.

### Store source responses during Phase 4

Persisting raw responses would begin the Bronze layer before its schema,
identity, checksums, and replay policy are defined. Phase 4 therefore retains
only minimal control state. Phase 5 will own raw immutable payload storage.

## Consequences

### Positive

- Discovery uses a supported, documented machine interface.
- IIIF supplies explicit canvas order and per-canvas OCR references.
- Narrow models reject broken required structure while tolerating unrelated
  source fields.
- One request policy applies consistently to every Wellcome URL.
- Missing OCR remains visible without failing an otherwise valid work.
- Checkpoints make interrupted runs identifiable and resumable per work.
- Per-work failures do not discard successful earlier traversal.
- Offline tests reproduce pagination, retries, source variants, traversal,
  checkpointing, CLI behavior, and status API behavior without live calls.
- The dashboard now reports persisted ingestion state instead of sample
  ingestion numbers.
- Container replacement does not erase status or checkpoint state.

### Negative or accepted trade-offs

- Sequential annotation downloads can be slow for large runs.
- A checkpoint is work-granular; interruption inside a book repeats that book.
- File-backed state assumes one writer and one shared filesystem.
- Numeric `Retry-After` is supported; HTTP-date parsing is deferred.
- The first IIIF sequence is assumed to be the intended reading sequence.
- Canvas order is page-like provenance, but printed-page labels are not yet
  normalized or guaranteed to be numeric.
- `pages_downloaded` currently means canvases traversed, not durable page
  payloads stored on disk.
- Dry-run status shows discovered works but zero completed works because no
  manifests are traversed.
- Raw responses and OCR are not yet replayable without the network; Phase 5
  must add that guarantee.

## Validation

Phase 4 was validated on 2026-07-22 with:

1. 53 offline Python tests covering API delivery, configuration, CLI, source
   models, retries, pagination, traversal, failures, status, checkpoints, and
   resume behavior.
2. Ruff lint and formatting checks plus strict mypy over 13 source files.
3. A Vite production build and desktop/mobile browser checks of the real
   ingestion dashboard, including a 390-pixel viewport and zero browser
   warnings or errors.
4. A live dry run that discovered five eligible `cholera` works without
   requesting manifests or OCR.
5. A live five-work traversal that completed all five works, traversed 246
   canvases, reported 14 canvases without OCR, performed zero retry waits, and
   recorded zero terminal failures.
6. A matching resume run that reused the checkpoint and completed successfully.
7. A Docker Compose build, healthy startup, HTTP 200 responses from `/` and
   `/health/ready`, an initially idle `/ingestion/status`, and a containerized
   one-work dry run that proved the unprivileged process can update the named
   ingestion volume.

The live source result is smoke-test evidence, not a claim of catalogue-wide
coverage or performance.

## Revisit when

Revisit this decision when:

- Phase 5 defines immutable Bronze storage and replay semantics;
- runs grow enough that sequential traversal becomes an observed bottleneck;
- Wellcome publishes a rate limit or a measured request budget requires a
  different concurrency policy;
- corpus selection is large enough to justify daily snapshot ingestion;
- licences or source types beyond public-domain books are approved;
- multilingual evaluation is ready;
- multiple writers or remote workers require transactional job state;
- interruption inside a work is costly enough to require canvas-level
  checkpoints;
- IIIF Presentation 3 or another OCR representation becomes part of the
  selected corpus; or
- the dashboard needs push updates rather than three-second polling.

## Official references

- [Wellcome Collection catalogue API documentation](https://developers.wellcomecollection.org/docs/catalogue)
- [Wellcome Collection catalogue API reference](https://developers.wellcomecollection.org/api/catalogue)
- [Connecting Wellcome APIs together](https://developers.wellcomecollection.org/docs/examples/connecting-the-apis-together)
- [Wellcome Collection datasets](https://developers.wellcomecollection.org/docs/datasets)
- [IIIF Presentation API 2.1](https://iiif.io/api/presentation/2.1/)
