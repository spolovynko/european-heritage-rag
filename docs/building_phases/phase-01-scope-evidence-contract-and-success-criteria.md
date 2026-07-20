# Phase 1 — Scope, evidence contract, and success criteria

## Objective

Turn the project idea into a precise product and evidence contract. Define what the assistant can answer, what constitutes a valid citation, when it must abstain, and how success will be measured.

## What we will learn

- Why RAG projects need a bounded domain.
- The difference between retrieval quality and answer quality.
- Why citations and abstention must be designed before prompts.
- How measurable requirements guide later architecture.

## Development steps

1. Write the initial project statement and user personas.
2. Define supported question types:
   - Exact title, author, and date lookup.
   - Subject and period filtering.
   - Passage-level historical questions.
   - Follow-up questions.
   - Unanswerable questions.
3. Define the evidence contract:
   - Every substantial claim requires retrieved support.
   - Citations identify the work and page range.
   - The cited chunk must be among the retrieved context.
   - Answers must not use previous assistant statements as evidence.
4. Define initial language scope:
   - English baseline.
   - French and Dutch added after English retrieval is evaluated.
5. Define initial success targets. Treat them as goals to tune, not fabricated achievements:
   - Retrieval Recall@10 target.
   - Citation coverage target.
   - Abstention test set.
   - Search latency budget.
6. Create:
   - `README.md`
   - `docs/project-status.md`
   - `docs/architecture.md`
   - `docs/adr/README.md`

## UI work

Create only a low-fidelity sketch showing the intended chat, source panel, and pipeline dashboard. No frontend implementation is required yet.

## Verification

- Ten example user questions are documented.
- At least two examples are deliberately unanswerable.
- Every example specifies the expected evidence type.
- The project scope excludes unsupported capabilities clearly.

## Exit criteria

- The product statement is understandable without verbal explanation.
- Citation and abstention rules are explicit.
- Initial evaluation targets are documented.
- The next chat can understand the project using the repository documents alone.

## Required ADR

`ADR-0001: Project scope and evidence contract`

Decision questions:

- Why Wellcome public-domain digitised books?
- Why begin with English?
- Why require page-level citations?
- Why use deterministic two-step RAG as the baseline?

---
