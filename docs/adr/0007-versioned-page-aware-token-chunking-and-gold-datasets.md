# ADR-0007: Versioned page-aware token chunking and Gold datasets

- Status: Accepted
- Date: 2026-07-23
- Phase: Phase 7 — Gold data layer and chunking experiments

## Context

Silver provides validated, source-independent work and page records. It
preserves raw OCR, a conservative `clean_text` view, page order, source labels,
images, rights, quality flags, and exact Bronze lineage. Retrieval cannot use a
whole book as one search unit, so Phase 7 must turn those pages into bounded
passages without breaking the evidence contract.

This phase must answer six durable questions:

1. Which tokenizer defines a “token”?
2. How do chunks respect both readable text structure and the model limit?
3. How is page provenance retained when one chunk crosses several pages?
4. How are repeated context, empty pages, short tails, and ambiguous languages
   handled?
5. How are chunking experiments made reproducible and comparable?
6. What may Phase 7 conclude before labelled retrieval evaluation exists?

The result must:

- be built entirely offline from a validated Silver dataset;
- use the tokenizer of the planned embedding family rather than words or
  characters as a proxy;
- guarantee that every emitted chunk fits its declared maximum;
- retain exact Silver page ownership and source/chunk character ranges;
- keep every eligible non-empty page represented in at least one chunk;
- expose exclusions rather than silently discarding evidence;
- produce stable identities from stable evidence and versioned configuration;
- publish immutable, inspectable files with integrity receipts;
- support three explicit chunk-size experiments; and
- avoid declaring a winning size before Phase 10 retrieval evaluation.

## Decision

### 1. Use the BAAI/bge-m3 fast tokenizer at an immutable revision

Gold uses `BAAI/bge-m3` as the tokenizer family for the initial chunking
experiments. It is loaded through Hugging Face Transformers at commit:

```text
5617a9f61b028005a4858fdac845db406aefb181
```

The adapter requires:

- a fast tokenizer, because page-safe splitting needs character offset
  mappings;
- the exact 40-character revision;
- `model_max_length == 8192`;
- special tokens to be counted for the final chunk limit; and
- no truncation or padding during counting.

Phase 7 installs the tokenizer runtime, not PyTorch and not the embedding model
weights. Embeddings remain Phase 8 work.

Why pin the commit? A model name is a moving label. Tokenizer files can change
without the application code changing. An immutable revision makes a stored
token count reproducible.

### 2. Define three named, versioned profiles

The experiments are:

| Profile | Target | Hard maximum | Requested overlap | Minimum |
|---|---:|---:|---:|---:|
| `tokens-300-v1` | 300 | 360 | 30 | 50 |
| `tokens-500-v1` | 500 | 600 | 50 | 50 |
| `tokens-800-v1` | 800 | 960 | 80 | 50 |

The target is where greedy accumulation normally closes a chunk. The hard
maximum is the invariant that may never be exceeded. The difference lets the
chunker keep a complete sentence-like fragment when it still fits, instead of
cutting every passage at an exact arbitrary position.

Requested overlap is about 10% of the target. It repeats the tokenizer-aligned
tail of one chunk at the start of the next chunk in the same uninterrupted
work run.

The minimum is a diagnostic and tail-merge threshold, not permission to delete
small evidence. A short final chunk is merged backward only if the merged
chunk still fits the hard maximum. Otherwise the short chunk remains and is
counted.

### 3. Chunk Silver `clean_text` and inherit Silver boundary decisions

Gold consumes `SilverPage.clean_text`. It does not clean raw OCR again and
does not run a second header/footer policy.

The manifest records:

```text
input_text_field = clean_text
header_footer_policy = use_silver_clean_text
```

This keeps responsibility clear:

- Silver owns evidence-preserving OCR normalization;
- Gold owns retrieval-unit construction.

Changing cleaning or header/footer rules creates a different Silver manifest,
which in turn creates a different Gold identity.

### 4. Preserve page order and use structural boundaries before hard splitting

Within each work, pages are sorted by `sequence_number`. Text is first divided
at:

- blank-paragraph gaps; or
- whitespace following `.`, `!`, or `?`.

The chunker greedily combines those fragments while the current chunk is below
its target and the candidate remains within the hard maximum.

If one structural fragment is too large, the fast tokenizer's character
offsets divide it into non-empty model-safe slices. This is the compulsory
fallback that makes the hard maximum true even for a very long OCR sentence.

Fragments from the same page are joined with a space. A change of page is
rendered with two newline characters so the page transition remains visible.

### 5. Treat an empty Silver page as a hard boundary

A page whose `clean_text` is empty creates no chunk text and is recorded as a
page exclusion. It also terminates the current chunking run.

Gold does not join text from page 10 directly to page 12 as if page 11 did not
exist. This prevents a citation range from visually bridging known missing OCR.

The empty Silver page remains in Silver. Gold's exclusion says why it is not a
searchable passage.

### 6. Keep exact page spans inside every chunk

Each `GoldChunk` includes one ordered `ChunkPageSpan` per contributing page:

- stable `page_id`;
- canvas sequence and exact source page label;
- parsed printed page number when Silver has one;
- canvas and image URL;
- half-open character range inside the chunk;
- half-open character range inside Silver `clean_text`.

The chunk also carries the first/last sequence and label for convenient
filtering. Page spans are authoritative for citation rendering and source
inspection.

This is more precise than storing only `page_start` and `page_end`: a consumer
can show exactly which part of each page contributed to the passage.

### 7. Keep overlap tokenizer-aligned, visible, and measurable

Overlap is copied only between adjacent chunks from the same uninterrupted
work run. The copied suffix is selected using content-token offsets, so the
chunker does not cut through a token.

Every chunk records:

- `overlap_previous_token_count`;
- `overlap_prefix_char_end`;
- `previous_chunk_id`; and
- `next_chunk_id`.

The browser highlights the repeated prefix. Statistics report actual repeated
tokens, overlap ratio, and output-token inflation. Overlap is therefore not a
hidden cost.

### 8. Require unambiguous English work-level scope in version one

Gold v1 includes a work only when:

```text
language_ids == ("eng",)
```

It also requires complete licence provenance. The 20-work Silver dataset has
one `eng,ger` work but no page-level language labels. Guessing which pages are
English would violate the evidence-first policy, so the complete work is
excluded with an explicit reason.

This produces 19 contributing works. Multilingual support should be revisited
only when page-level language detection is added and evaluated.

### 9. Denormalize retrieval metadata into every chunk

A Gold row carries the title, contributor labels, production values, subjects,
genres, language, licence, source URL, and IIIF manifest URL needed by later
filtering, retrieval results, and citations.

This intentionally repeats work metadata. Gold is a retrieval-serving
contract, unlike normalized Silver. Repetition avoids a mandatory join in the
hot retrieval path and freezes the metadata used for one experiment.

The chunk also inherits the union of contributing Silver page quality flags.
Those flags are diagnostic metadata; they do not remove the chunk.

### 10. Make dataset and chunk identities deterministic

`gold_dataset_id` is SHA-256 over canonical JSON containing:

- Silver dataset ID;
- the exact Silver manifest SHA-256;
- Gold schema version;
- Gold pipeline version;
- the complete `ChunkingConfig`; and
- sorted selected work IDs for a partial experiment.

`chunk_id` is SHA-256 over stable work, page, profile, chunker, index, and
content-hash fields.

Generated time is metadata, not identity. Rebuilding the same input and rules
reuses the same valid dataset. A different profile, tokenizer revision, Silver
manifest, rule version, or selected-work scope produces a different ID.

### 11. Publish one immutable Parquet snapshot per experiment

The layout is:

```text
data/gold/wellcome/dataset_id=<gold-sha256>/
├── chunks.parquet
├── statistics.json
├── statistics.md
└── gold-manifest.json
```

`chunks.parquet` uses an explicit Polars schema with nested page-span structs
and Zstandard compression. PyArrow independently checks physical field names.

Each declared output is written to a unique temporary sibling, synchronized,
atomically replaced, and recorded with byte length and SHA-256. The manifest
is written last and is the completion marker.

### 12. Validate content, structure, token counts, and parent provenance

Offline Gold validation checks:

- manifest-declared files, byte lengths, and content hashes;
- absence of incomplete temporary files;
- exact Polars and PyArrow Parquet schemas;
- Pydantic round-trip validation of every row;
- a recomputed dataset identity from the parent hash, config, and scope;
- unique chunk IDs and manifest/config consistency;
- fresh token recounts using the pinned tokenizer;
- contiguous work-local indexes and exact previous/next links;
- statistics/manifest count reconciliation;
- every Gold page reference against its parent Silver row; and
- complete coverage of every eligible non-empty Silver page.

Validation requires the parent Silver dataset. A Gold snapshot is not accepted
as trustworthy merely because its Parquet file can be opened.

### 13. Expose operator, API, and browser inspection paths

Typer provides build, list/detail inspection, and full offline validation.
Build can run one named profile, all profiles, or a deterministic selected-work
snapshot.

FastAPI exposes complete manifests, statistics, represented works, bounded
chunk summaries, and one full chunk. Summary lists are capped at 500 and omit
full text/page spans.

The browser shows profile-level measurements, explicit exclusions, work
filtering, chunk adjacency, highlighted overlap, page boundaries, source
images, denormalized metadata, and the full JSON payload.

### 14. Do not select a winning profile in Phase 7

Phase 7 measures construction properties only. Chunk count, token
distribution, number of pages, and overlap cost are not retrieval relevance.

All three profiles remain valid candidates. Phase 10 must compare them on the
same labelled evaluation set using retrieval and citation metrics before an
active profile is selected.

## Alternatives considered

### Word or character counts

They are easy to implement but do not match the embedding model input. OCR
punctuation, Unicode, and subword splitting make those proxies unreliable.

### An unpinned model name

This is convenient but permits silent token-boundary drift. It was rejected
because stored limits and repeated builds must be independently reproducible.

### Use the embedding model during Phase 7

Loading model weights would test more of Phase 8, but chunk construction needs
only the tokenizer. It would add a heavier runtime and confuse chunking with
embedding generation.

### One fixed chunk size

It would be simpler but would turn an untested guess into architecture.
Publishing 300/500/800 profiles preserves a controlled experiment.

### Exact fixed-length token windows

They guarantee uniform length but routinely cut sentences and page transitions.
The selected algorithm prefers structural fragments while retaining a hard
token fallback.

### One chunk per page

It gives simple citations, but short front matter becomes tiny retrieval units
and long pages can exceed model limits. Page spans give citation precision
without forcing page size to equal retrieval size.

### Allow chunks to bridge empty OCR pages

This would reduce small chunks but would hide a known evidence gap. Empty pages
are kept as hard boundaries.

### Drop every chunk below 50 tokens

This reduces index noise but loses real title, colophon, or tail evidence.
Short chunks are merged only when safe and otherwise retained and measured.

### Infer English pages inside the `eng,ger` work

The source has only work-level language metadata in Silver. Unmeasured
inference would create invisible eligibility decisions, so v1 excludes the
ambiguous work explicitly.

### Store only start/end page labels

This is compact but cannot prove which characters came from which page,
especially when overlap repeats only a suffix. Exact nested spans were chosen.

### Normalize Gold into chunk and page-link tables

This reduces nested values but requires a join for every full retrieval result.
One immutable row is simpler at current scale and preserves a self-contained
evidence object.

### SQLite or a vector database as canonical Gold storage

Both could serve queries, but they mix immutable experiment construction with
mutable serving state. Parquet remains the canonical Gold artifact; Phase 8
may load it into an index.

### Timestamp-based experiment directories

They make every retry look different and cannot prove reuse. Content/config
identity was selected.

### Choose 500 tokens as the winner now

It is a plausible default but no labelled retrieval measurement supports it.
The CLI default is operational convenience, not an evaluation conclusion.

## Consequences

### Positive

- Every chunk is guaranteed to fit its configured embedding-model limit.
- The exact tokenizer and rules can be reconstructed from the manifest.
- Every eligible non-empty Silver page is represented and verifiable.
- Empty pages and ambiguous languages remain visible as explicit exclusions.
- Page citations can be rendered from exact source/chunk ranges.
- Overlap cost and content repetition are inspectable.
- Work metadata is immediately available to retrieval filters and results.
- All three experiments can coexist without overwriting one another.
- Repeated builds are idempotent and corruption fails closed.
- Phase 8 receives one typed, validated, retrieval-ready input contract.

### Negative or accepted trade-offs

- Fast tokenizer files must be downloaded once or available in the cache.
- Chunk metadata repeats work fields and increases Parquet size.
- Sentence detection is intentionally simple and can miss OCR punctuation.
- The selected tokenizer may later differ from a chosen embedding model; that
  change must create a new profile and dataset.
- Exact character spans add schema complexity.
- Chunking plus overlap increases model-token volume by about 11% on the
  acceptance data; that total includes per-chunk special tokens and rendered
  boundaries, not overlap alone.
- One ambiguous multilingual work is not searchable in Gold v1.
- Empty OCR pages are not searchable, although they remain preserved in
  Silver.
- Irreducible short chunks remain in the output.
- Local API reads scan the Parquet snapshot and are not a large-corpus serving
  design.
- Local publication assumes one writer per deterministic identity.

## Validation

The decision is accepted because:

- all 131 Python tests, Ruff format/lint, and strict mypy pass;
- all three live Gold datasets validate with fresh pinned-tokenizer recounts;
- every one of 1,464 eligible non-empty pages is represented;
- zero empty or over-limit chunks were emitted;
- a repeated 500-token build reused the same dataset ID;
- the Vite build and Compose configuration pass;
- the browser loaded all three profiles, filtered a work, navigated adjacency,
  highlighted an 80-token overlap, displayed four page images/spans for that
  chunk, and reported no console errors; and
- the Phase 7 image built, ran as UID 10001, became healthy, and served
  `/gold/datasets` from its dedicated volume.

The live profile measurements are:

| Profile | Chunks | Min / median / p95 / max | Short | Mean pages | Overlap | Inflation |
|---|---:|---|---:|---:|---:|---:|
| `tokens-300-v1` | 1,952 | 3 / 312 / 352 / 360 | 9 | 1.76 | 9.55% | 11.36% |
| `tokens-500-v1` | 1,174 | 3 / 518 / 573 / 600 | 7 | 2.27 | 9.46% | 10.93% |
| `tokens-800-v1` | 749 | 3 / 818 / 876 / 957 | 7 | 3.04 | 9.45% | 10.74% |

These are construction measurements, not retrieval-quality scores.

## Revisit when

Reconsider this decision when:

- Phase 8 chooses an embedding model with a different tokenizer or limit;
- Phase 10 provides labelled retrieval and citation results for these profiles;
- sentence/layout parsing can be evaluated against OCR-specific examples;
- page-level language identification is available and measured;
- title/front-matter or very short chunk behavior harms retrieval;
- repeated header/footer decisions change in Silver;
- exact Parquet scans exceed measured API latency goals;
- remote object storage or concurrent publication is required; or
- a new profile replaces this decision through a later ADR.
