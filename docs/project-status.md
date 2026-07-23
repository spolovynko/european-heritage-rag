# Project status

## Current state

- Last completed phase: Phase 7 — Gold data layer and chunking experiments
- Next phase: Phase 8 — embeddings and Qdrant indexing
- Current branch: `main`
- Largest persisted Bronze corpus: 20 works, 1,670 canvases, and 1,710
  immutable resources
- Parent Silver dataset:
  `73eb5f4fd79ded1e68dd8a341e0f5270924619777eea3f4523b19b6b3718c5d5`
- Parent Silver size: 20 works and 1,670 pages
- Active Gold experiments: 300, 500, and 800 target tokens
- Gold scope: 19 unambiguously English works and 1,464 non-empty pages
- Active index version: None
- Last successful closure gate: complete Phase 7 Python, frontend, live-data,
  browser, and container verification on 2026-07-23

## Completed capabilities

### Product, environment, and browser foundation

- Product scope, evidence contract, supported questions, abstention rules, and
  future evaluation goals are documented.
- Python 3.12, `uv`, Pydantic settings, structured logging, FastAPI, Typer,
  Ruff, mypy, pytest, Vite, pnpm, Docker, and Compose are reproducible.
- A responsive browser-native diagnostic application is built with same-origin
  API calls and served by FastAPI.

### Wellcome discovery and Bronze evidence

- Bounded English public-domain Wellcome discovery and sequential IIIF
  traversal use timeouts, classified retries, atomic progress, and work-level
  resume.
- Bronze preserves catalogue work JSON, exact IIIF manifests, exact OCR
  annotation-list responses, source URLs, paths, sizes, and SHA-256 receipts.
- Immutable atomic resource writes, append-only failure history, complete run
  manifests, offline validation, CLI/API inspection, and the Bronze explorer
  remain operational.

### Silver canonical data

- Strict immutable contracts define canonical works, pages, contributors,
  lineage, quality reports, file receipts, manifests, and validation.
- Work metadata is stored once; page OCR, labels, images, quality, and
  annotation evidence are stored per canvas.
- Raw OCR is retained and conservative clean OCR is stored separately.
- Empty pages remain explicit records.
- Polars/PyArrow Parquet schemas, atomic publication, content hashes,
  deterministic IDs, exact Bronze lineage, and offline validation are in place.

### Gold retrieval-ready data

- `GOLD_DATA_DIRECTORY` configures the generated Gold root.
- `BAAI/bge-m3` tokenizer assets are loaded at immutable revision
  `5617a9f61b028005a4858fdac845db406aefb181`.
- The adapter requires a fast tokenizer, exact character offsets, and the
  expected 8,192-token model maximum.
- Tokenizer-only Transformers support is installed; embedding weights and
  PyTorch are not Phase 7 dependencies.
- Named `tokens-300-v1`, `tokens-500-v1`, and `tokens-800-v1` configs preserve
  target, maximum, overlap, minimum, tokenizer, language, input field, and
  algorithm version.
- Structural-first, page-aware chunking uses sentence/paragraph gaps before a
  compulsory tokenizer-offset hard split.
- Empty Silver pages form hard boundaries and explicit exclusions.
- Overlap is tokenizer-aligned and recorded by token count and prefix character
  boundary.
- Every chunk has exact nested page IDs, canvas order/labels, image URLs, and
  source/chunk character ranges.
- Work metadata, rights, source URLs, and inherited Silver quality flags are
  denormalized into each retrieval row.
- Work-local chunk indexes, previous/next IDs, chunk content hashes, and dataset
  identities are deterministic.
- Every eligible non-empty Silver page must appear in at least one Gold span.

### Gold publication and validation

- Polars writes an explicit nested schema to Zstandard-compressed
  `chunks.parquet`.
- JSON and Markdown statistics expose distributions, page breadth, overlap,
  inflation, and explicit exclusions.
- Each output is synchronized and atomically replaced, then recorded by byte
  length and SHA-256.
- `gold-manifest.json` is written last as the completeness marker.
- Existing valid deterministic snapshots are reused rather than rewritten.
- Validation checks file integrity, temporary files, Polars/PyArrow schemas,
  Pydantic rows, unique IDs, fresh pinned-tokenizer counts, exact adjacency,
  statistics, parent Silver references, and complete eligible-page coverage.

### Operator, API, browser, and container paths

- `gold build`, `gold inspect`, and `gold validate` support exact IDs.
- Build supports one profile, all profiles, and deterministic selected-work
  snapshots.
- Read-only `/gold` routes return manifests, statistics, represented works,
  bounded chunk summaries, and one full evidence chunk.
- The Data workspace now switches among Bronze, Silver, and Gold.
- The Gold inspector compares profiles, filters works, navigates adjacency,
  highlights overlap, shows page boundaries/images/ranges, and exposes the full
  payload.
- The image runs as UID 10001 and prepares `/app/data/gold` plus the Hugging
  Face cache. Compose persists each in its own named volume.
- ADR-0007 and the Phase 7 implementation guide record decisions, every build
  step, alternatives, measured results, operations, and limitations.

## Persisted Gold experiments

Parent Silver dataset:

```text
73eb5f4fd79ded1e68dd8a341e0f5270924619777eea3f4523b19b6b3718c5d5
```

| Profile | Gold dataset ID | Chunks |
|---|---|---:|
| `tokens-300-v1` | `341db4fa6ffec17bfea3197f66dbd21cb821239c06fcaf5ce56829562abe6487` | 1,952 |
| `tokens-500-v1` | `4c6daefb4c70f52baaaa41e7505e290eac1ee583da9cdee2c282bc6e72a1322e` | 1,174 |
| `tokens-800-v1` | `ca6aac6da0089368aa8dfed994987a3a1f93e855a8111443fc952d7fc1d4dbab` | 749 |

All three contain:

- 19 works;
- 1,464 contributing pages;
- zero empty chunks;
- zero chunks over their hard maximum;
- 539,993 unique source content tokens; and
- 83 exclusions: one ambiguous-language work and 82 empty pages in eligible
  works.

| Profile | Min / mean / median / p95 / max | Short | Mean / max pages | Overlap | Inflation |
|---|---|---:|---|---:|---:|
| `tokens-300-v1` | 3 / 308.06 / 312 / 352 / 360 | 9 | 1.76 / 5 | 9.55% | 11.36% |
| `tokens-500-v1` | 3 / 510.21 / 518 / 573 / 600 | 7 | 2.27 / 7 | 9.46% | 10.93% |
| `tokens-800-v1` | 3 / 798.39 / 818 / 876 / 957 | 7 | 3.04 / 8 | 9.45% | 10.74% |

These are construction measurements. No profile is selected as the retrieval
winner.

## Verification results

### Automated

- Tests: 131 passed.
- Format/lint: Ruff format check and Ruff check passed.
- Types: strict mypy reported no issues in 32 source files.
- Frontend: Vite production build passed.
- Compose: `docker compose config --quiet` passed.
- Git patch hygiene: `git diff --check` passed.

### Live data

- All three full-corpus profiles built from the exact Silver dataset above.
- All three passed Gold validation with fresh tokenizer recounts and parent
  Silver coverage.
- The 500-token repeat build returned the same dataset ID and `Status: reused`.
- The live maximums were 360/600/957 against limits 360/600/960.
- No eligible non-empty page was lost.

### Browser acceptance

- Listed all three profile snapshots and reconciled headline statistics.
- Switched from the 800-token to 500-token profile.
- Filtered work `d465a93c` to 55 chunks.
- Navigated work-local previous/next links.
- Selected a chunk with 80 overlap tokens and highlighted one repeated prefix.
- Displayed four exact page spans and four source images for that chunk.
- Corrected unclear missing-label presentation from `pages -–-` to a canvas
  range such as `canvases 3–7`.
- Browser console inspection found no warnings or errors.

### Container acceptance

- `european-heritage-rag:phase7` built successfully.
- The image declares `appuser` and the container ran as UID 10001.
- The service became healthy.
- `/health/live` and `/health/ready` returned `ok`.
- `/gold/datasets` returned a successful empty list on the intentionally new
  Gold named volume.
- Compose was stopped without deleting the persistent named volumes.

## Important decisions

- [ADR-0001: Project scope and evidence contract](adr/0001-project-scope-and-evidence-contract.md)
- [ADR-0002: Python, dependency management, and repository structure](adr/0002-python-dependency-management-and-repository-structure.md)
- [ADR-0003: Browser-native UI foundation and same-origin FastAPI delivery](adr/0003-browser-native-ui-and-fastapi-delivery.md)
- [ADR-0004: Wellcome API and IIIF ingestion strategy](adr/0004-wellcome-api-and-iiif-ingestion-strategy.md)
- [ADR-0005: Append-only Bronze storage and idempotent ingestion](adr/0005-append-only-bronze-storage-and-idempotent-ingestion.md)
- [ADR-0006: Canonical work/page schemas and conservative OCR cleaning](adr/0006-canonical-work-page-schemas-and-conservative-ocr-cleaning.md)
- [ADR-0007: Versioned page-aware token chunking and Gold datasets](adr/0007-versioned-page-aware-token-chunking-and-gold-datasets.md)
- Use an immutable fast tokenizer revision and fail on tokenizer-limit drift.
- Prefer structural text boundaries but enforce a hard model-token maximum.
- Keep empty pages as explicit hard boundaries.
- Require exact page spans and complete eligible-page coverage.
- Exclude ambiguous work-level language rather than infer page language.
- Make overlap and its storage/index cost visible.
- Preserve all three experiments until retrieval evaluation selects one.
- Keep canonical Gold as immutable Parquet; indexes are downstream derivatives.

## Known limitations

- Sentence splitting uses simple punctuation/paragraph rules.
- Page-level language is unavailable; one `eng,ger` work is excluded.
- Empty OCR pages have no searchable passage.
- Several irreducible chunks remain below the 50-token diagnostic minimum.
- Chunking plus overlap increases model-token volume by about 11%, including
  special tokens and rendered boundaries.
- The local Gold API reads complete Parquet snapshots and scans chunk detail.
- The browser caps one chunk summary response at 500.
- Bronze, Silver, and Gold filesystem stores assume one writer per identity.
- Browser acceptance remains manual rather than an automated E2E suite.
- No embeddings, index, retrieval, reranking, query preparation, answer
  generation, citation validation, evaluation results, or working chat exists.
- Construction statistics do not establish retrieval quality.

## Next phase

- Phase: [Phase 8 — embeddings and Qdrant indexing](building_phases/phase-08-embeddings-and-qdrant-indexing.md)
- Entry conditions satisfied:
  - three valid full-corpus Gold experiments exist;
  - every row is model-token bounded;
  - exact tokenizer/config metadata is in each manifest;
  - stable chunk and dataset IDs exist;
  - every eligible page is covered;
  - page spans, images, rights, work metadata, and quality flags are available;
  - repeat builds are idempotent;
  - Parquet and parent-provenance validation are offline and reproducible.
- First intended task: select and pin the embedding model/runtime, require its
  tokenizer contract to match the chosen Gold profile, and define versioned
  embedding/index identities before generating vectors.

## Next-chat reading order

1. [README](../README.md)
2. [Scope and evidence contract](scope-and-evidence-contract.md)
3. [Architecture](architecture.md)
4. [Phase 7 implementation guide](building_guides/phase-07-gold-data-layer-and-chunking-experiments.md)
5. [ADR-0007](adr/0007-versioned-page-aware-token-chunking-and-gold-datasets.md)
6. [Phase 8 plan](building_phases/phase-08-embeddings-and-qdrant-indexing.md)
7. [Development and learning agreement](learning-guide-agreement.md)
