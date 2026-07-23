# Phase 7 implementation guide: Gold data layer and chunking experiments

## 1. Phase at a glance

Phase 7 turns validated Silver pages into retrieval-ready Gold chunks. A Gold
chunk is a bounded passage that a later search index can embed and return while
still proving which work and pages supplied its text.

In simple language:

- Bronze is the source receipt.
- Silver is the organized book and page record.
- Gold is the set of searchable passage cards cut from those pages.

The difficult part is not merely cutting text. Each card must fit the model,
remain readable, remember page ownership, expose repeated context, and be
reproducible.

Technically, this phase adds:

- a pinned fast tokenizer adapter for `BAAI/bge-m3`;
- three versioned 300/500/800-token chunking profiles;
- page-aware structural splitting with a hard tokenizer fallback;
- exact chunk-side and Silver-side page character spans;
- explicit overlap, adjacency, quality inheritance, and exclusions;
- strict immutable Gold Pydantic contracts;
- deterministic dataset and chunk IDs;
- Zstandard-compressed Parquet output with nested page spans;
- atomic manifest-last publication and content receipts;
- validation against both the pinned tokenizer and parent Silver dataset;
- JSON and Markdown construction-statistics reports;
- `gold build`, `gold inspect`, and `gold validate` commands;
- bounded read-only `/gold` API routes;
- a browser Gold explorer with profile comparison and evidence inspection;
- dedicated Gold and Hugging Face cache container volumes; and
- unit, integration, live-data, browser, and container verification.

Deliberately excluded:

- embeddings and an embedding-model runtime;
- a sparse or vector index;
- hybrid retrieval, reranking, or query processing;
- a “best” chunk-size decision;
- answer generation and citation validation;
- page-level language inference;
- aggressive OCR repair or new header/footer rules; and
- retrieval-quality claims. This phase measures construction, not relevance.

## 2. Vocabulary

| Term | Plain-language meaning | Technical meaning in this phase |
|---|---|---|
| Token | A model-sized text piece | One ID produced by the exact pinned BGE-M3 tokenizer |
| Fast tokenizer | A tokenizer that remembers positions | Hugging Face tokenizer implementation with character offset mappings |
| Target | Preferred chunk size | Point after which the greedy accumulator normally closes |
| Hard maximum | Size that may never be exceeded | Stored `maximum_token_count`, verified by recounting every chunk |
| Structural fragment | A readable candidate piece | Page text split at paragraph gaps or sentence-ending punctuation |
| Hard split | Safety fallback | Token-offset division of a structural fragment that cannot fit |
| Overlap | Repeated context | Tokenizer-aligned suffix copied into the next chunk |
| Page span | Exact page ownership | Page identity plus source/chunk half-open character ranges |
| Half-open range | Start included, end excluded | Python-style `[start, end)` offsets that compose without ambiguity |
| Adjacency | Neighbour links | `previous_chunk_id` and `next_chunk_id` within one work |
| Exclusion | Recorded omission | Work/page that cannot form Gold text, with an explicit reason |
| Profile | One controlled experiment | Complete versioned target/maximum/overlap/tokenizer policy |
| Gold manifest | Experiment receipt | Parent Silver hash, full config, scope, output hashes, and counts |
| Inflation | Total extra model input | `(emitted - unique source) / unique source`, including overlap, per-chunk special tokens, and rendered boundaries |

## 3. Phase 7 contract

### 3.1 What a Gold chunk guarantees

Every `GoldChunk` guarantees:

1. it belongs to one deterministic Gold and Silver dataset;
2. its text is non-empty;
3. its `content_sha256` matches that text;
4. its exact pinned-tokenizer count is stored;
5. the count does not exceed the profile maximum;
6. it belongs to one unambiguously English, licensed work;
7. its page spans are ordered and lie inside the chunk;
8. its first/last page fields agree with those spans;
9. its overlap prefix is explicit;
10. its previous/next links agree with work-local order; and
11. it carries the metadata and quality observations needed by retrieval and
    inspection.

In plain language, a chunk is not an anonymous paragraph. It is a small,
self-describing evidence package.

### 3.2 Why page spans are nested

One chunk may contain:

```text
end of canvas 10

all of canvas 11

start of canvas 12
```

A start/end label alone says only the broad range. `page_spans` says exactly
which chunk characters and which Silver source characters belong to each page.
That lets a later citation renderer show the correct pages and lets an
inspector compare the passage to the original page image.

### 3.3 Gold scope

A normal build has `scope = full`: all eligible works in the selected Silver
dataset are considered.

`--work-id` creates `scope = selected_works`, with that ID recorded in the
manifest and included in dataset identity. It is useful for a quick experiment
without pretending the result is a full-corpus snapshot.

## 4. Repository structure

```text
src/european_heritage_rag/
├── api/
│   ├── gold.py
│   └── main.py
├── core/
│   └── config.py
├── domain/
│   ├── __init__.py
│   └── gold.py
├── pipeline/
│   ├── chunking.py
│   ├── gold.py
│   ├── gold_store.py
│   └── tokenization.py
└── cli.py

tests/
├── api/test_gold_api.py
├── domain/test_gold_models.py
├── pipeline/
│   ├── gold_test_support.py
│   ├── test_chunking.py
│   ├── test_gold_store.py
│   └── test_tokenization.py
├── test_cli.py
└── test_config.py

frontend/
├── app.js
├── index.html
├── styles.css
└── vite.config.js

data/gold/                         # generated and ignored
└── wellcome/
    └── dataset_id=<sha256>/
        ├── chunks.parquet
        ├── statistics.json
        ├── statistics.md
        └── gold-manifest.json

.env.example
Dockerfile
compose.yaml
pyproject.toml
uv.lock
```

## 5. Runtime flow

```text
gold build --silver-dataset-id <id> --all-profiles
  → locate the complete Silver manifest
  → validate Silver files, rows, schemas, and relationships offline
  → load the exact pinned fast tokenizer
  → verify tokenizer family, revision, and maximum
  → repeat for each named profile
      → hash Silver manifest + complete config + scope
      → derive deterministic Gold dataset ID
      → select all or requested work rows
      → exclude ambiguous-language or incomplete-rights works
      → sort each work's pages by canvas sequence
      → record empty-clean-text pages and break the text run
      → divide non-empty pages at structural gaps
      → hard-split any oversized fragment at tokenizer offsets
      → greedily accumulate toward the target under the hard maximum
      → copy a tokenizer-aligned trailing overlap
      → merge a short tail backward only when safe
      → render exact page ranges and token counts
      → attach stable IDs, adjacency, metadata, and quality flags
      → require complete eligible-page coverage
      → calculate construction statistics
      → write Parquet/JSON/Markdown atomically
      → write the Gold manifest last
      → validate files, rows, recounts, links, and Silver provenance
  → report created or reused
```

The operation does not call Wellcome and does not generate embeddings. The only
possible network action is the tokenizer's first download from Hugging Face;
later runs can use its cache.

## 6. Step-by-step implementation

### Step 1 — Review the evidence and experiment boundary

The Phase 6 output was reviewed before choosing a chunk policy:

- 20 Silver works;
- 1,670 canonical pages;
- 87 pages with no OCR;
- one work labelled both `eng` and `ger`;
- page order, labels, images, quality flags, and lineage already present; and
- no paragraph breaks in the current cleaned live corpus, although the Silver
  contract can preserve them.

Why this matters:

- Empty pages require an explicit gap policy.
- Work-level multilingual metadata is not enough for safe page-level selection.
- A sentence fallback is necessary because current OCR often has no paragraph
  separators.
- Gold can reuse page/images/rights instead of rediscovering them.

The implementation therefore starts from the actual Silver contract rather
than from an abstract text list.

### Step 2 — Add the tokenizer runtime and configuration

`transformers` was added to `pyproject.toml`, and `uv.lock` records the exact
resolved dependency graph. PyTorch is not installed because Phase 7 loads
tokenizer assets only.

The shared configuration adds:

```dotenv
GOLD_DATA_DIRECTORY=data/gold
```

`AppSettings.gold_data_directory` gives the CLI, API, tests, and container one
source of truth.

The Hugging Face cache is configured separately in Compose as:

```text
HF_HOME=/app/var/huggingface
```

The cache is not Gold data. It is a reusable external model artifact and gets
its own volume.

### Step 3 — Wrap the tokenizer behind a small boundary

`pipeline/tokenization.py` defines the `TokenBoundary` protocol. The chunker
depends on four operations:

- count text with or without special tokens;
- return content-token character offsets;
- divide an oversized string into model-safe text spans; and
- return a tokenizer-aligned trailing suffix.

`PinnedTokenizer` implements that protocol with:

```text
model: BAAI/bge-m3
revision: 5617a9f61b028005a4858fdac845db406aefb181
expected model maximum: 8192
fast tokenizer required: yes
```

The import of Transformers is lazy. Commands such as `bronze inspect` do not
load the tokenizer runtime or emit unrelated model warnings.

Why an adapter instead of calling `AutoTokenizer` everywhere?

- Chunking logic remains testable with a deterministic fake tokenizer.
- Revision and model-limit checks exist in one place.
- Phase 8 can reuse the declared boundary.
- Tests can prove offset and splitting behavior without a network download.

### Step 4 — Define the three profiles

`chunking_profiles()` returns immutable `ChunkingConfig` values:

```text
tokens-300-v1: target 300, maximum 360, overlap 30
tokens-500-v1: target 500, maximum 600, overlap 50
tokens-800-v1: target 800, maximum 960, overlap 80
```

All use minimum 50, exact English-only eligibility, `clean_text`, and
`page-aware-token-v1`.

Pydantic rejects:

- target above maximum;
- maximum above tokenizer capacity;
- overlap at or above target; and
- minimum at or above target.

The profile ID contains `v1` because even a small behavior change should be a
new experiment rather than an invisible rewrite.

### Step 5 — Define strict immutable Gold models

`domain/gold.py` defines:

- `ChunkingConfig`;
- `ChunkPageSpan`;
- `GoldChunk`;
- `GoldExclusion`;
- `GoldStatistics`;
- `GoldFileRecord`;
- `GoldDatasetManifest`; and
- validation issue/report records.

They use `extra="forbid"` and `frozen=True`. Unknown fields, invalid hashes,
bad URLs, contradictory counts, unordered spans, content-hash mismatches, and
invalid manifest scope fail at the boundary.

This is intentionally defensive. Gold is the last canonical artifact before
indexing; a malformed row should not be embedded and discovered later through
a broken citation.

### Step 6 — Select eligible work and page evidence

`transform_silver_dataset()` first runs the full Silver validator. It then
checks the tokenizer's model, revision, and maximum against the profile.

Gold v1 accepts only:

```python
work.language_ids == ("eng",)
```

It also requires both licence ID and licence URL.

Excluded works remain in Silver and are listed in Gold statistics. For the
acceptance dataset, one `eng,ger` work was excluded because no page-level
language labels exist.

Every accepted page with non-empty `clean_text` is eligible. An empty page is:

- recorded as a page exclusion;
- omitted from chunk text; and
- used as a hard boundary.

The acceptance result has:

- 19 contributing works;
- 1,464 contributing pages;
- one excluded ambiguous-language work; and
- 82 excluded empty pages inside eligible works.

The multilingual work's pages are not counted again as page exclusions because
the work-level reason already explains their omission.

### Step 7 — Create structural fragments per page

`_page_fragments()` works on one page at a time. It looks for:

- two or more newlines; or
- whitespace following `.`, `!`, or `?`.

These are simple, explainable boundaries. No language model or external
sentence parser changes the evidence.

Each structural span is then passed to
`tokenizer.split_to_model_limit(maximum - overlap)`.

Why subtract requested overlap? It reserves enough space for the repeated
prefix when a large fragment starts a following chunk.

If the structural span is too long, tokenizer offsets divide it. Leading and
trailing whitespace is trimmed while source offsets are adjusted, so the text
and provenance still agree.

### Step 8 — Greedily accumulate toward the target

`_chunk_fragment_run()` walks fragments in source order.

For each candidate:

1. render current fragments plus the candidate;
2. count with special tokens;
3. append when current is below target and candidate remains under maximum;
4. otherwise finalize the current draft;
5. select its requested trailing overlap; and
6. start the next draft with overlap plus the new fragment.

If overlap plus the new fragment would exceed the maximum, overlap is dropped
for that boundary. The hard maximum is more important than requested context.

This is a greedy algorithm: it makes one forward pass and does not globally
optimize all boundaries. That keeps the behavior deterministic and easy to
explain.

### Step 9 — Handle short tails without losing evidence

After one uninterrupted run is chunked, the final draft is compared with the
50-token minimum.

If it is short, the chunker tries to append only its non-overlap content to the
previous draft. The merge is accepted only if the result remains within the
hard maximum.

If it cannot fit, the short chunk remains. The live data therefore has a small
number of chunks below 50 tokens. They are real, irreducible text segments,
not empty errors.

No short content is discarded.

### Step 10 — Render exact page provenance

`_render_fragments()` appends:

- one space between fragments from the same page;
- two newlines when the page changes.

While rendering, it records for each page:

- first and last character in the chunk;
- first and last character in Silver `clean_text`; and
- page/canvas/image identity.

Repeated overlap keeps its original page ownership. If the repeated prefix
comes from canvas 10, the new chunk's first span also points to canvas 10.

The browser inserts visible canvas-boundary markers without modifying the
persisted text.

### Step 11 — Attach chunk identity, links, and metadata

After all drafts in a work are rendered, each chunk receives a stable
`chunk_id`. Previous/next IDs can then be assigned in a second pass.

Every row copies retrieval-oriented work metadata:

- title;
- contributor labels and roles;
- production dates/labels;
- subjects and genres;
- language;
- rights;
- source and manifest URLs.

The union of all contributing Silver page flags becomes
`inherited_quality_flags`.

This denormalization is intentional. Silver stays normalized; Gold is
self-contained for the future index.

### Step 12 — Prove complete eligible-page coverage

After all work chunks are assembled, the transformer compares:

```text
all eligible non-empty Silver page IDs
against
all page IDs present in Gold page spans
```

Any missing page fails the build. Chunk count alone cannot prove that no page
was accidentally skipped.

Chunk IDs must also be globally unique, and the final tuple is sorted by
`work_id, chunk_index`.

### Step 13 — Calculate construction statistics

`GoldStatistics` reports:

- work/page/chunk counts;
- empty and short chunks;
- minimum, mean, median, p95, and maximum tokens;
- mean and maximum pages per chunk;
- requested and actual overlap;
- unique Silver source tokens;
- total emitted tokens;
- overlap ratio and output inflation;
- language counts; and
- every exclusion.

`statistics.json` is for programs. `statistics.md` is a directly readable
summary.

The report explicitly says these measurements do not select a winning profile.
For example, fewer chunks may reduce index size but may also hide a small
relevant passage inside a larger unit. Only retrieval evaluation can decide.

### Step 14 — Derive deterministic Gold identity

`gold_dataset_id()` canonicalizes and hashes:

```text
Silver dataset ID
+ exact Silver manifest SHA-256
+ Gold schema version
+ Gold pipeline version
+ complete ChunkingConfig
+ sorted selected-work scope
```

Including the Silver manifest hash is stronger than using the Silver directory
name alone. It binds Gold to the exact parent publication receipt.

Generated timestamp is deliberately excluded. Repeating unchanged work
produces the same identity.

### Step 15 — Write explicit Parquet and reports atomically

`GoldFilesystemStore` owns publication.

The explicit Parquet schema includes ordinary scalar/list metadata and a nested
list of page-span structs. Polars writes Zstandard compression and column
statistics.

Each file is:

1. written to a unique temporary sibling;
2. flushed and synchronized;
3. atomically replaced at its final path; and
4. measured by byte length and SHA-256.

The store writes `gold-manifest.json` only after:

- `chunks.parquet`;
- `statistics.json`; and
- `statistics.md`

are complete.

Only a directory with a valid manifest is listed as a complete dataset.

### Step 16 — Reuse valid existing output

Before writing, `publish()` checks for an existing manifest at the
deterministic path.

If it exists:

1. validate the complete dataset;
2. require the parent Silver manifest hash to match;
3. require the full chunking config to match; and
4. return `created=False`.

If the existing files are invalid or conflict with their identity, publication
fails. It does not overwrite suspicious content.

The live 500-token repeat build reported:

```text
Status: reused
Dataset: 4c6daefb4c70f52baaaa41e7505e290eac1ee583da9cdee2c282bc6e72a1322e
```

### Step 17 — Validate the complete Gold artifact

`validate_gold_dataset()` performs several layers:

| Layer | What it proves |
|---|---|
| File receipts | No declared output is missing or byte/hash changed |
| Temporary-file scan | No interrupted sibling remains |
| Polars schema | Logical Parquet types are exactly expected |
| PyArrow schema | Physical field names agree independently |
| Pydantic rows | Every nested row satisfies the Gold contract |
| Identity | Parent manifest hash, config, and scope reproduce the dataset ID |
| Token recount | Stored count equals the exact pinned tokenizer result |
| Adjacency | Indexes are contiguous and previous/next links are exact |
| Statistics | Manifest and report counts agree |
| Silver reconciliation | Every reference is a real eligible parent page |
| Coverage | Every eligible non-empty parent page appears in Gold |

The CLI caches one tokenizer per model/revision/maximum tuple while validating
multiple profiles. It does not reload identical assets three times.

### Step 18 — Add operator commands

Build the default 500-token profile:

```shell
uv run european-heritage-rag gold build \
  --silver-dataset-id <silver-id>
```

Build one explicit profile:

```shell
uv run european-heritage-rag gold build \
  --silver-dataset-id <silver-id> \
  --profile tokens-300-v1
```

Build all experiments:

```shell
uv run european-heritage-rag gold build \
  --silver-dataset-id <silver-id> \
  --all-profiles
```

Build one deterministic work-scoped snapshot:

```shell
uv run european-heritage-rag gold build \
  --silver-dataset-id <silver-id> \
  --profile tokens-500-v1 \
  --work-id <work-id>
```

Inspect and validate:

```shell
uv run european-heritage-rag gold inspect
uv run european-heritage-rag gold inspect --dataset-id <gold-id>
uv run european-heritage-rag gold validate
uv run european-heritage-rag gold validate --dataset-id <gold-id>
```

`--profile` and `--all-profiles` are mutually exclusive. Unknown Silver IDs,
unknown profile IDs, invalid parent datasets, tokenizer drift, and publication
conflicts produce a non-zero command result.

### Step 19 — Add bounded read-only API routes

The `/gold` router exposes:

| Method and path | Result |
|---|---|
| `GET /gold/datasets` | Newest-first complete manifests |
| `GET /gold/datasets/{id}` | One complete manifest and config |
| `GET /gold/datasets/{id}/statistics` | Construction measurements/exclusions |
| `GET /gold/datasets/{id}/works` | Represented works and chunk counts |
| `GET /gold/datasets/{id}/chunks` | Bounded summaries with work/offset/limit |
| `GET /gold/datasets/{id}/chunks/{chunk_id}` | Full text, spans, metadata, links |

The list endpoint caps `limit` at 500 and omits full text/page spans. The detail
endpoint returns the heavy evidence object only for one selected chunk.

All routes are registered before the frontend catch-all so `/gold` cannot be
mistaken for an HTML route.

### Step 20 — Add the Gold browser explorer

The Data workspace now has three layers:

```text
Bronze · source receipts
Silver · canonical records
Gold · retrieval chunks
```

The Gold view provides:

- dataset/profile selector;
- work, page, chunk, short, and empty totals;
- token distribution;
- overlap ratio and actual repeated tokens;
- explicit excluded work/page counts;
- work filter with per-work chunk counts;
- bounded chunk list;
- previous/next navigation;
- exact token count and canvas range;
- highlighted repeated prefix;
- work metadata and source/rights link;
- visible page-boundary labels in chunk text;
- each page's chunk/source character ranges;
- digitized source images; and
- expandable full payload/config.

Source data is inserted through `textContent` or text nodes. OCR cannot become
executable HTML.

When source labels are only `-`, the UI falls back to a clear canvas range such
as `canvases 3–7`.

The Vite development proxy forwards `/gold` to FastAPI.

### Step 21 — Add container persistence and cache boundaries

The image creates and grants UID 10001 ownership of:

```text
/app/data/gold
/app/var/huggingface
```

Compose sets:

```text
GOLD_DATA_DIRECTORY=/app/data/gold
HF_HOME=/app/var/huggingface
```

and mounts separate named volumes:

```text
gold-data
huggingface-cache
```

Gold snapshots and downloaded tokenizer assets have different lifecycles, so
they should not share one volume.

The image tag is `european-heritage-rag:phase7`.

### Step 22 — Verify from pure rules to live operation

Tests cover:

- contradictory config and chunk model invariants;
- immutable tokenizer revision/max checks and tokenizer-offset splits;
- stable chunk IDs and output;
- target/maximum bounds;
- page order and exact coverage;
- empty-page hard boundaries;
- hard splits for oversized text;
- overlap, short-tail merge, and adjacency;
- language exclusions and selected-work scope;
- deterministic dataset identity;
- Parquet schemas, hashes, atomic publication, reuse, and corruption;
- tokenizer recount and Silver provenance validation;
- CLI created/reused/error paths;
- API filtering, pagination, detail, and 404 behavior; and
- shared Gold directory configuration.

Live acceptance then builds all profiles from the 20-work Silver dataset,
validates each one, repeats a build, inspects the rendered browser, and runs the
production container.

## 7. File-by-file review

| Path | Responsibility |
|---|---|
| `domain/gold.py` | Immutable config, chunk, span, statistics, manifest, and validation contracts |
| `pipeline/tokenization.py` | Exact revision-pinned token counts, offsets, hard splits, and trailing overlap |
| `pipeline/chunking.py` | Profiles, page fragments, greedy accumulation, overlap, tail merge, spans, IDs, and adjacency |
| `pipeline/gold.py` | Silver validation, eligibility/exclusions, dataset identity, coverage proof, and statistics |
| `pipeline/gold_store.py` | Explicit Parquet schema, atomic publication, reuse, reads, reports, hashes, and full validation |
| `cli.py` | Gold build/inspect/validate operator workflow |
| `api/gold.py` | Bounded read-only manifest/statistics/work/chunk endpoints |
| `api/main.py` | Registers the Gold router before static frontend delivery |
| `core/config.py` / `.env.example` | Shared generated Gold root |
| `frontend/index.html` | Accessible Gold selector, counters, list, detail, spans, and payload structure |
| `frontend/app.js` | Dataset loads, filtering, adjacency, safe text rendering, overlap highlighting, and page cards |
| `frontend/styles.css` | Responsive Gold comparison and evidence presentation |
| `frontend/vite.config.js` | Development proxy for `/gold` |
| `Dockerfile` / `compose.yaml` | Phase 7 image, unprivileged directories, Gold and tokenizer-cache volumes |
| `pyproject.toml` / `uv.lock` | Tokenizer runtime and reproducible dependency resolution |
| Gold tests | Contract, algorithm, store, CLI, API, and tokenizer boundary evidence |

## 8. Tool and framework inventory

| Tool | Why it is used now |
|---|---|
| Hugging Face Transformers | Load the exact fast tokenizer and offset mappings |
| Pydantic | Reject invalid Gold configs, rows, spans, reports, and manifests |
| Polars | Build explicit typed frames and write compressed Parquet |
| PyArrow | Independently inspect physical Parquet fields |
| Typer | Provide reproducible operator commands |
| FastAPI | Expose bounded same-origin inspection endpoints |
| Browser-native JavaScript | Extend the diagnostic UI without an unnecessary framework migration |
| pytest | Prove pure boundaries and integrated publication with deterministic fixtures |
| Ruff and mypy | Enforce format/lint and strict source typing |
| Vite and pnpm | Build reproducible production frontend assets |
| Docker Compose | Prove the unprivileged runtime and separate persistent boundaries |

## 9. Live experiment results

### 9.1 Parent Silver dataset

```text
73eb5f4fd79ded1e68dd8a341e0f5270924619777eea3f4523b19b6b3718c5d5
```

It contains 20 works and 1,670 pages. Gold v1 includes 19 unambiguously English
works and 1,464 non-empty pages.

### 9.2 Gold dataset identities

| Profile | Gold dataset ID |
|---|---|
| `tokens-300-v1` | `341db4fa6ffec17bfea3197f66dbd21cb821239c06fcaf5ce56829562abe6487` |
| `tokens-500-v1` | `4c6daefb4c70f52baaaa41e7505e290eac1ee583da9cdee2c282bc6e72a1322e` |
| `tokens-800-v1` | `ca6aac6da0089368aa8dfed994987a3a1f93e855a8111443fc952d7fc1d4dbab` |

### 9.3 Measured construction properties

| Profile | Chunks | Min | Mean | Median | P95 | Max | Short |
|---|---:|---:|---:|---:|---:|---:|---:|
| `tokens-300-v1` | 1,952 | 3 | 308.06 | 312 | 352 | 360 | 9 |
| `tokens-500-v1` | 1,174 | 3 | 510.21 | 518 | 573 | 600 | 7 |
| `tokens-800-v1` | 749 | 3 | 798.39 | 818 | 876 | 957 | 7 |

All three have:

- 19 works;
- 1,464 contributing pages;
- zero empty chunks;
- zero chunks above their hard maximum;
- 539,993 unique content tokens before overlap; and
- 83 explicit exclusions: one work and 82 pages.

### 9.4 Page breadth and overlap cost

| Profile | Mean / max pages per chunk | Actual repeated tokens | Overlap ratio | Output inflation |
|---|---:|---:|---:|---:|
| `tokens-300-v1` | 1.76 / 5 | 57,435 | 9.55% | 11.36% |
| `tokens-500-v1` | 2.27 / 7 | 56,648 | 9.46% | 10.93% |
| `tokens-800-v1` | 3.04 / 8 | 56,501 | 9.45% | 10.74% |

The 800-token profile makes fewer, broader chunks. The 300-token profile makes
more, narrower chunks. Those facts affect index cost and context granularity,
but they do not prove relevance.

## 10. Verification evidence

### 10.1 Automated and build gates

```shell
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src
uv run pytest
pnpm --dir frontend build
docker compose config --quiet
docker compose build
```

Measured closure results:

- all 131 Python tests passed;
- Ruff format and lint passed;
- strict mypy passed;
- the Vite production build passed;
- Compose configuration passed; and
- `european-heritage-rag:phase7` built successfully.

The exact test/source counts are also recorded in
[`docs/project-status.md`](../project-status.md), which is updated after the
final closure run.

### 10.2 Live Gold build and validation

The command:

```shell
uv run european-heritage-rag gold build \
  --silver-dataset-id 73eb5f4fd79ded1e68dd8a341e0f5270924619777eea3f4523b19b6b3718c5d5 \
  --all-profiles
```

created all three identities in section 9.2.

`gold validate` passed for each dataset with:

- file/hash checks;
- exact Parquet schema;
- Pydantic row validation;
- fresh token recount;
- work-local adjacency;
- statistics reconciliation;
- exact Silver page reconciliation; and
- complete eligible-page coverage.

A repeated `tokens-500-v1` build returned the same ID and `Status: reused`.

### 10.3 Closure defect and artifact reconciliation

The adapter-level tokenizer test exposed an off-by-one error in the hard-split
path: an intermediate slice ended at `offsets[token_end]` instead of
`offsets[token_end - 1]`. That included the first token assigned to the next
slice and created an unconfigured one-token repetition.

The production adapter and deterministic test double were corrected. A fresh
in-memory transform was then compared with every persisted snapshot:

- the 300- and 500-token chunk text differed;
- the 800-token output was identical because its live data did not exercise
  the affected hard split.

The two affected pre-acceptance generated directories were moved aside,
rebuilt from the fixed code, validated, and compared through a repeat build.
Only after the replacements passed were the stale copies removed. The final
statistics in section 9 come from the corrected artifacts.

This matters operationally: passing token-limit validation alone was not enough
to prove correct boundaries. A small offset-level unit test found semantic
duplication that was still under the maximum.

### 10.4 Browser acceptance

The rendered browser:

- listed all three profiles and exact chunk totals;
- loaded and inspected the 800-token snapshot;
- reconciled 19 works, 1,464 pages, 749 chunks, and 7/0 short/empty;
- switched to the 500-token profile and reconciled 1,174 chunks;
- filtered work `d465a93c` to exactly 55 chunks;
- moved through previous/next adjacency;
- opened a chunk with 80 repeated tokens;
- highlighted that overlap as one visible prefix;
- showed four exact page spans and four source images for the selected chunk;
- displayed canvas fallbacks for missing printed labels; and
- produced no console warnings or errors.

The browser pass found the ambiguous `pages -–-` presentation and corrected it
to `canvases 3–7`.

### 10.5 Container acceptance

The production image:

- is tagged `european-heritage-rag:phase7`;
- declares `appuser` and ran as UID 10001;
- became healthy through `/health/ready`;
- returned `ok` from `/health/live` and `/health/ready`; and
- returned HTTP success with an empty array from `/gold/datasets` on a new,
  intentionally empty Gold volume.

The last point proves the route and volume boundary. Host-generated `data/gold`
is not silently copied into the named container volume.

## 11. How to operate Phase 7

### Build and inspect locally

```shell
uv sync --locked
uv run european-heritage-rag gold build \
  --silver-dataset-id <silver-id> \
  --all-profiles
uv run european-heritage-rag gold inspect
uv run european-heritage-rag gold validate
```

### Run the browser explorer

```shell
pnpm --dir frontend build
uv run uvicorn european_heritage_rag.api.main:app \
  --host 127.0.0.1 \
  --port 8000
```

Open `http://127.0.0.1:8000`, choose **Data**, then
**Gold · retrieval chunks**.

### Operate inside Compose

```shell
docker compose up --detach --build
docker compose exec api european-heritage-rag gold build \
  --silver-dataset-id <silver-id> \
  --all-profiles
docker compose exec api european-heritage-rag gold validate
docker compose down
```

The Silver dataset must already exist in the Compose `silver-data` volume.
Tokenizer assets are downloaded into `huggingface-cache` and Gold output into
`gold-data`.

### Rebuild after a policy change

Do not edit an existing Gold manifest to represent new behavior.

1. change the relevant version/profile ID;
2. run the tests;
3. build a new Gold dataset;
4. compare both datasets; and
5. record a new ADR if the decision replaces this policy.

## 12. Review summary

### Ready to keep

- Exact revision-pinned tokenizer behavior.
- Model-token counts with special tokens included.
- Named profile configuration rather than magic constants.
- Structural-first splitting with a compulsory token hard limit.
- Empty pages as visible hard boundaries.
- Complete eligible-page coverage proof.
- Exact source/chunk page spans.
- Visible, measured, tokenizer-aligned overlap.
- Stable content/config identities and work-local adjacency.
- Denormalized retrieval metadata and inherited quality flags.
- Explicit exclusions instead of silent omission.
- Atomic Parquet/report publication and manifest-last completion.
- Parent-Silver validation and fresh token recount.
- Separate Gold and tokenizer-cache volumes.
- Bounded summary API plus detailed selected-chunk response.

### Current limitations

- The sentence boundary rule is punctuation-based and not an OCR-aware parser.
- BGE-M3 is a tokenizer decision for the experiment; Phase 8 must use the same
  tokenizer or create a new profile.
- Page-level language is unavailable, so one multilingual work is excluded.
- Empty OCR pages have no searchable text.
- Some genuine short chunks remain because merging would break the hard limit.
- Printed labels such as `-` require canvas fallbacks in the UI.
- Chunking plus overlap adds about 11% model-token volume; this includes
  per-chunk special tokens and rendered boundaries, not overlap alone.
- The local API reads and scans complete Parquet snapshots.
- The browser shows at most 500 chunk summaries for an unfiltered dataset.
- Publication assumes one writer per deterministic identity.
- Browser acceptance is manual rather than a committed automated E2E suite.
- No profile has been evaluated for retrieval relevance yet.
- No embeddings, index, retrieval trace, answer, or working chat exists.

### What Phase 8 receives

Phase 8 can now depend on:

- immutable complete Gold manifests;
- exact tokenizer/config metadata;
- model-bounded chunk text;
- stable IDs;
- filterable work metadata;
- page spans, images, rights, and source links;
- quality observations;
- profile-level statistics; and
- offline validation.

Phase 8 should add embedding generation and an index without changing the Gold
evidence contract in place.

### Revisit when

- an embedding model/tokenizer is selected or changed;
- labelled retrieval results compare the profiles;
- page-level language detection is available;
- OCR-aware sentence/layout parsing has measured evidence;
- short/title-page behavior measurably harms search;
- API scan latency exceeds a defined goal; or
- remote/concurrent publication is required.

## 13. Official references

- [BAAI/bge-m3 model repository](https://huggingface.co/BAAI/bge-m3)
- [Hugging Face tokenizer documentation](https://huggingface.co/docs/transformers/main_classes/tokenizer)
- [Hugging Face model revision loading](https://huggingface.co/docs/transformers/main_classes/model#transformers.PreTrainedModel.from_pretrained)
- [Polars `DataFrame.write_parquet`](https://docs.pola.rs/api/python/stable/reference/api/polars.DataFrame.write_parquet.html)
- [Apache Arrow Python Parquet documentation](https://arrow.apache.org/docs/python/parquet.html)
