# ADR-0006: Canonical work/page schemas and conservative OCR cleaning

- Status: Accepted
- Date: 2026-07-23
- Phase: Phase 6 — Silver normalization and OCR cleaning

## Context

Bronze preserves raw Wellcome catalogue, IIIF manifest, and OCR annotation-list
evidence. Later retrieval code should not need to understand those three source
shapes, but normalization must not erase the evidence needed to audit a page,
compare cleaning behavior, or produce exact citations.

Phase 6 therefore has to answer four central questions:

1. Why separate work metadata from page evidence?
2. Why retain both raw and cleaned OCR?
3. Why use Parquet for the canonical dataset?
4. Which OCR corrections are safe enough to automate without human review?

The solution must also:

- replay a validated Bronze run without network access;
- preserve empty and suspicious pages;
- reconcile every consumed OCR annotation with the Bronze inventory;
- expose quality as evidence, not as an unmeasured accuracy claim;
- produce the same derived identity from the same stable input and algorithm
  versions;
- remain understandable at the 5-to-500-work project scale; and
- provide enough lineage for Phase 7 chunks and later page citations.

## Decision

### 1. Use separate canonical `SilverWork` and `SilverPage` contracts

Store work-level bibliographic facts once in `works.parquet` and page-level
image/OCR facts once in `pages.parquet`. Link pages to works through `work_id`.

`SilverWork` owns titles, contributors, production, subjects, genres,
languages, licence, source URLs/hashes, quality flags, and catalogue/manifest
lineage.

`SilverPage` owns canvas sequence and label, conservative printed-page parsing,
raw and clean OCR, image URLs, annotation URLs, quality observations, and
manifest/annotation lineage.

Every IIIF canvas produces a page row, including a canvas with no OCR.

### 2. Preserve raw OCR and store cleaned OCR as a separate value

`raw_text` reconstructs source OCR lines in source order with newline
separators. It is never overwritten.

`clean_text` is a derived view produced by versioned pure functions. The page
also stores counts, detected boundary lines, a cleaning-change ratio, and flags
describing applied transformations.

This means a developer or researcher can always compare:

```text
source annotation list → raw_text → clean_text
```

### 3. Automate only conservative, explainable OCR cleanup

Version one may:

- normalize Unicode to NFC;
- remove HTML tags through a parser and decode entities;
- collapse horizontal whitespace inside a line;
- join ordinary OCR line wraps while preserving blank-line paragraph breaks;
- dehyphenate only when a line-ending hyphen is followed by a lowercase
  continuation; and
- remove a header/footer only when the same normalized boundary is repeated on
  at least three pages and at least 15% of the non-empty pages in one work.

Version one must not:

- correct spelling;
- modernize historical language;
- translate;
- infer missing words or characters;
- rewrite text with a language model;
- merge across blank paragraph boundaries;
- interpret columns or tables; or
- discard a page because its OCR looks poor.

Applied cleaning remains visible through flags such as
`dehyphenation_applied`, `html_removed`, `header_detected`, and
`footer_detected`.

### 4. Use explainable flags and broad review bands

Store finite page and work quality flags instead of silently deleting or
repairing suspicious records.

The page bands are:

- `missing` when cleaned OCR is empty;
- `needs_review` when a review heuristic such as very short text, high symbol
  ratio, or large cleaning change fires; and
- `usable` otherwise.

These are triage categories. They are explicitly not OCR accuracy estimates.
A machine-readable JSON report and human-readable Markdown report aggregate the
same facts.

### 5. Use Parquet with explicit schemas

Persist canonical works and pages as Zstandard-compressed Parquet using Polars.
Declare all fields explicitly, including nested contributor and lineage
structures. Use PyArrow during validation to inspect the physical field names
independently.

Parquet is the canonical tabular interchange for Silver. JSON remains the
format for the small dataset manifest and quality report.

### 6. Make derived identity depend on stable evidence and rule versions

Hash the stable Bronze run parameters, completed IDs, and sorted resource
ID/path/content-hash inventory. Do not include mutable acquisition or file
timestamps.

Derive `dataset_id` from that Bronze inventory plus:

- Silver schema version;
- cleaning version;
- header/footer version; and
- quality-rule version.

Derive each `page_id` from work ID and canvas URL.

Rebuilding unchanged evidence with unchanged versions must reuse the existing
validated dataset. A changed input or changed rule version must produce another
dataset identity.

### 7. Require exact row-level Bronze lineage

Every work stores catalogue and manifest lineage. Every page stores manifest
lineage plus every OCR annotation resource that contributed to it.

Each lineage item contains Bronze resource ID, resource type, portable relative
path, source URL, and content SHA-256.

The transformer fails if annotation records cannot be reconciled by canvas
position, annotation position, and source URL. It does not ignore unexpected
Bronze evidence.

### 8. Publish files atomically and the manifest last

Write each Parquet/report output to a synchronized temporary sibling and
atomically replace the final file. Hash and size the four outputs, then write
`silver-manifest.json` last.

Only directories with a valid manifest are listed as complete datasets.
Offline validation checks file integrity, schemas, Pydantic row contracts,
unique IDs, page-to-work relationships, and count reconciliation.

### 9. Keep the first store and inspection path local and read-only

Use one concrete `SilverFilesystemStore` until a remote deployment creates a
real second implementation.

Expose Typer build/inspect/validate commands and bounded FastAPI read routes.
The page-list route returns summaries and caps a request at 500 rows; full OCR
is returned only for one selected page.

The browser inspector presents the same quality and lineage evidence rather
than calculating a second interpretation in JavaScript.

## Alternatives considered

### One denormalized row per page

Repeating title, contributors, subjects, and licence on every page would make a
single file convenient for simple analysis. It was rejected because it wastes
space, risks inconsistent repeated metadata, and confuses work facts with page
evidence.

### One nested JSON document per work

Nested pages would resemble a IIIF manifest and preserve hierarchy. It was
rejected as the canonical analytical contract because page filtering,
statistics, chunk generation, and independent page validation are clearer in a
flat page table with an explicit work key.

### Replace raw OCR with cleaned OCR

This would reduce storage and remove ambiguity for consumers. It was rejected
because cleaning errors would become irreversible and reviewers could not tell
what the source actually returned.

### Keep only raw OCR and clean during chunking

This would postpone a decision, but every later experiment could apply
different undocumented cleanup. It was rejected so cleaning rules, version,
quality evidence, and output identity are fixed before chunk comparison.

### Aggressive spelling correction or language-model cleanup

It could produce more fluent text and perhaps improve retrieval. It was
rejected for the baseline because historical spelling may be meaningful, model
rewrites can hallucinate, and no labelled evaluation currently proves that the
benefit outweighs source distortion.

### Always join a trailing hyphen

This would repair more split words but would also corrupt true hyphenated
compounds and page-end punctuation. The lowercase-continuation rule is less
complete but safer and visible through a flag.

### Remove the first and last line of every page as header/footer

This would be simple but would delete real content on title pages, short pages,
and works without running headers. The chosen work-level repetition threshold
prefers false negatives over destructive false positives.

### CSV or JSON Lines

They are easy to inspect but do not represent nested lineage/contributors or
stable types as well, use more space, and require repeated parsing of large OCR
strings. Parquet provides typed columnar reads and compression.

### SQLite

SQLite could enforce foreign keys and provide indexed API queries. It was not
selected as the canonical derived artifact because Parquet is portable for
later offline experiments and avoids turning a reproducible dataset build into
mutable database state. SQLite remains an option for a future serving layer.

### A distributed data framework

Spark or a workflow platform would support much larger corpora. It was rejected
because the measured 20-work dataset is processed locally in seconds and the
additional runtime would hide the transformations the project is meant to
teach.

### Timestamp-based dataset directories

Timestamps are easy to generate but make identical rebuilds look different.
Content-and-version identity makes idempotency testable.

### Publish the manifest before the data files

This could announce progress but would let readers observe an apparently
complete dataset with missing files. The manifest-last rule provides a simple
completion contract.

## Consequences

### Positive

- Retrieval and chunking code receives source-independent work/page records.
- No automated cleanup destroys the raw comparison view.
- Empty and suspicious canvases remain visible and countable.
- Every row can be traced to exact Bronze files and content hashes.
- Rule changes naturally create another versioned dataset identity.
- Repeated builds are idempotent and do not create timestamp-only copies.
- Parquet is compact, typed, and convenient for later batch experiments.
- Quality decisions can be inspected in CLI, JSON, Markdown, API, and browser.
- The implementation remains small enough to explain function by function.

### Negative or accepted trade-offs

- Work/page consumers must join on `work_id`.
- Storing both raw and clean OCR uses more space.
- Conservative cleaning leaves known OCR errors in place.
- Header/footer detection may miss real boundaries; the 20-work acceptance
  sample confirmed none at the version-one threshold.
- Quality bands do not measure OCR character or word accuracy.
- Parquet files are immutable snapshots rather than transactional row stores.
- Nested Parquet structs are less convenient in some simple tools.
- Local API reads currently load full Parquet files and scan page detail.
- The filesystem assumes one writer per deterministic dataset.
- Algorithm version constants must be updated intentionally when behavior
  changes.

## Validation

The decision is accepted because:

- 115 tests pass across source models, domain contracts, cleaning, boundary
  detection, transformation, storage, CLI, and API;
- Ruff format/lint and strict mypy pass;
- the Vite production build, Compose configuration, and Phase 6 image build
  pass;
- a legacy five-work Bronze run transformed into 5 works and 300 pages, proving
  backward-compatible replay;
- a fresh enriched five-work run transformed into 5 works and 246 pages with
  real contributor and production data;
- a 20-work run validated all 1,710 Bronze resources and transformed into 20
  works and 1,670 pages;
- the 20-work Silver output contains lineage and images for every page and
  reconciles 1,454 usable, 129 review, and 87 missing pages;
- a repeated 20-work build reused dataset
  `73eb5f4fd79ded1e68dd8a341e0f5270924619777eea3f4523b19b6b3718c5d5`;
- the browser compared a dehyphenated page’s 354-character raw OCR with its
  352-character clean OCR and reported no console errors; and
- the unprivileged container became healthy with a dedicated Silver volume.

## Revisit when

Reconsider this decision when:

- labelled OCR examples support measured accuracy thresholds;
- labelled repeated-boundary pages justify changing the first/last-line or 15%
  rules;
- French or Dutch cleaning needs evaluated language-specific behavior;
- Phase 7 proves another canonical field is required for citation-safe chunks;
- Parquet API scans exceed measured latency goals;
- concurrent publication or remote object storage is required;
- layout-aware reading order, tables, or multiple IIIF sequences enter scope;
  or
- an evaluated aggressive cleanup experiment improves retrieval without
  violating the evidence contract.
