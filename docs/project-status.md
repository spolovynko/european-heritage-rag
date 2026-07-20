# Project status

## Current state

- Last completed phase: Phase 1 — Scope, evidence contract, and success criteria
- Current branch: `main`
- Dataset size: 0 works; no corpus has been selected or ingested
- Active index version: None
- Last successful command: PowerShell Phase 1 documentation contract check

## Completed capabilities

- Defined a standalone product statement and three user personas.
- Bounded the initial corpus to English, public-domain, digitised Wellcome books
  with usable OCR and page provenance.
- Defined supported exact lookup, filtered search, passage, comparison,
  follow-up, and unanswerable question behaviour.
- Defined substantial claims, valid evidence, valid page-level citations,
  partial answers, and mandatory abstention cases.
- Separated retrieval-quality goals from answer-quality goals.
- Recorded measurable but not-yet-achieved targets for Recall@10, citation
  coverage/validity/support, abstention, and search latency.
- Documented ten example questions with evidence expectations, including two
  deliberately unanswerable cases.
- Documented the deterministic two-step RAG boundary and low-fidelity chat,
  source-panel, and pipeline-dashboard sketch.
- Accepted ADR-0001 and indexed it.

## Verification results

- Tests: Not applicable; Phase 1 contains documentation and no application code.
- Linting: `git diff --check` passes for tracked edits; Markdown structure and
  repository-local links were checked with PowerShell.
- Manual checks: 10 example questions, 2 explicitly unanswerable examples, and
  an expected evidence entry for all 10.
- Metrics: Not measured. Every numeric value is labelled as an initial target.

## Important decisions

- [ADR-0001: Project scope and evidence contract](adr/0001-project-scope-and-evidence-contract.md)
- The initial answer contract requires page-bearing evidence even for
  bibliographic claims; metadata-only citations are a documented revisit point.
- English is an evaluated baseline. French and Dutch require their own reviewed
  evaluation slices before release.
- Retrieval and generation remain separate deterministic boundaries until an
  evaluated alternative justifies additional complexity.

## Known limitations

- No ingestion, search, generation, API, or frontend code exists yet.
- No corpus, evaluation set, index, model, prompt, or empirical baseline exists.
- OCR and printed-page/canvas mapping behaviour is specified but untested.
- The strict page-evidence rule may abstain on facts available only in catalogue
  metadata.
- Numeric success targets are hypotheses to tune after reproducible evaluation,
  not claims of product performance.

## Next phase

- Phase: Phase 2 — Environment and repository setup
- Entry conditions:
  - Phase 1 documentation is accepted.
  - Python 3.12 and `uv` availability can be checked locally.
  - No application capability is assumed from this documentation-only phase.
- First intended task: Create the smallest reproducible Python backend package,
  dependency lock, configuration model, and typed liveness/readiness endpoints.

## Next-chat reading order

1. [README](../README.md)
2. [Scope and evidence contract](scope-and-evidence-contract.md)
3. [Architecture](architecture.md)
4. [ADR-0001](adr/0001-project-scope-and-evidence-contract.md)
5. [Development and learning guide](adr/learning-guide-agreement.md)

