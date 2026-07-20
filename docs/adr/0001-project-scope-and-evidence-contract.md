# ADR-0001: Project scope and evidence contract

- Status: Accepted
- Date: 2026-07-20
- Phase: Phase 1 — Scope, evidence contract, and success criteria

## Context

HeritageRAG ultimately aims to support multilingual exploration of historical
material, but retrieval and grounded generation cannot be evaluated against an
undefined domain. Before choosing prompts, models, chunk sizes, or storage, the
project needs an explicit answer boundary: which sources count, what evidence
supports a claim, what a citation must resolve to, and when the assistant must
stop rather than complete an answer from model memory.

The project also has a learning and portfolio goal. A reviewer must be able to
trace failures to retrieval or generation and understand why later complexity
was added.

## Decision

### Source and product boundary

The initial corpus will contain a progressively selected set of English,
public-domain, digitised books from the Wellcome Collection that have catalogue
metadata, page images, usable OCR, and sufficient provenance. Answers describe
what the active indexed corpus says; they do not claim exhaustive Wellcome or
historical coverage.

We chose Wellcome public-domain digitised books because they provide one
coherent and bounded source domain while still presenting realistic RAG
problems: catalogue metadata, page-oriented digital objects, OCR noise,
historical language, rights information, and inspectable original pages. Public
domain selection makes a small reproducible portfolio corpus more practical
and keeps rights filtering visible rather than implicit.

### Language sequence

English is the first retrieval and evaluation baseline. French and Dutch are
added only after English has a versioned evaluation set, measured retrieval
baseline, and citation validation. Starting with one language controls a major
variable while ingestion, OCR reconstruction, chunking, ranking, and evaluation
are still being learned. Each later language must have reviewed test cases and
per-language reporting; interface translation alone is not multilingual RAG.

### Evidence and citation contract

Every substantial answer claim must be supported by a page-aware chunk
retrieved for the current turn and included in answer context. A valid citation
identifies the work and inclusive page range and resolves to that retrieved
chunk. Previous assistant messages, user assertions, and model memory are not
evidence. Structured catalogue metadata may select candidate works, but it does
not replace page-bearing support in the initial answer contract.

Page-level citations were selected because work-level links are too coarse to
audit a claim. Page locators let a reader inspect the nearby text or image,
enable deterministic citation validation, align with page-aware chunking, and
make citation quality measurable. The trade-off is stricter data modelling:
printed page labels and image/canvas order must both be retained, and a missing
page mapping can force abstention.

When evidence is absent, irrelevant, contradictory, outside scope, missing
required provenance, or insufficient for the requested claim, the assistant
returns an explicit partial answer or abstention. It never fills the gap from
general model knowledge. Current medical advice always falls outside this
historical corpus contract.

### Deterministic baseline

The baseline uses two explicit application-controlled steps:

1. prepare the query, apply filters, retrieve/rank chunks, and construct a
   bounded evidence context;
2. generate an answer or abstention from that context, then deterministically
   validate citation membership and provenance before returning it.

We chose deterministic two-step RAG because retrieval inputs and outputs can be
recorded, retrieval and answer quality can be tested separately, failure causes
remain visible, and the generator cannot silently broaden the evidence source.
An agentic loop would introduce extra model decisions, latency, and failure
modes before the baseline is measured. It can be reconsidered later only by
comparison on the same evaluation set.

### Initial goals

The project adopts the following unmeasured targets:

- English Retrieval Recall@10 of at least 0.85 on answerable labelled cases;
- citation coverage and structural validity of 100%;
- citation support of at least 0.90;
- abstention accuracy of at least 0.90, with 100% abstention on clear
  current-medical-advice and outside-corpus cases; and
- warm p95 search latency through reranking of at most 1.5 seconds for top 10
  results on the portfolio corpus, excluding generation.

The first abstention evaluation set must contain at least 20 cases, including
at least 5 deliberately unanswerable cases. Results must record dataset, index,
configuration, hardware, and evaluation-set versions. Targets may be tuned by
a later ADR; they must not be presented as achieved before measurement.

## Alternatives considered

### Broad, multi-source historical question answering

This would cover more topics but provide no stable denominator for evaluation,
complicate rights and provenance, and blur whether failure came from corpus
coverage or retrieval. It is deferred until a single-source baseline works.

### English, French, and Dutch from the first ingestion

This better reflects the final multilingual aim, but OCR quality, tokenisation,
embeddings, query formulation, and ground truth would all vary at once. The
project would learn less from each failure. Language expansion is gated on a
measured English baseline instead.

### Work-level links or uncited fluent answers

Work-level links are easier to produce but force readers to search an entire
book and do not prove that the answer used a specific passage. Uncited answers
cannot meet the evidence-first product promise. Page-level locators are worth
the additional provenance work.

### Treat catalogue metadata as sufficient for all bibliographic answers

This would make exact lookups easier, but creates two citation contracts before
the core page-aware contract is implemented. The stricter initial rule requires
retrieved bibliographic/title-page evidence and abstains if it is unavailable.
Evaluation may later justify a separately labelled metadata citation type.

### Agentic retrieval and answer generation from the start

An agent could reformulate, retry, browse, or select tools dynamically, but it
would make the evidence boundary and failure attribution harder to inspect. It
is deferred until it demonstrates an evaluated improvement over the same
deterministic cases.

## Consequences

### Positive

- Scope, provenance, answerability, and abstention can be tested as contracts.
- Retrieval failures remain distinguishable from generation failures.
- Readers can inspect a claim near its original page and source.
- Rights, OCR, and page-mapping limitations surface early in data design.
- The English baseline provides a meaningful comparison for later languages.
- The architecture remains small enough to explain in a technical review.

### Negative or accepted trade-offs

- The product initially answers fewer questions and may abstain on a correct
  catalogue fact when page evidence is unavailable.
- English-only evaluation delays visible multilingual capability.
- Page mapping and claim-to-citation validation require additional data and
  tests.
- Public-domain and OCR requirements exclude otherwise relevant Wellcome works.
- A deterministic pipeline cannot autonomously recover from every weak query.
- The numeric targets are hypotheses until the first reproducible evaluation.

## Validation

This decision is validated first by documentation and later by measurements:

1. The root README contains ten example questions, including at least two
   deliberately unanswerable cases, with expected evidence for every case.
2. The scope document defines substantial claims, valid evidence, valid
   citations, partial answers, and abstention triggers.
3. The architecture keeps retrieval and generation outputs inspectable and
   validates citations against current-turn context.
4. A versioned English retrieval set measures Recall@10 independently of answer
   generation.
5. A separate answer/abstention evaluation measures the stated citation and
   abstention goals without reporting targets as achieved results.

See [Scope and evidence contract](../scope-and-evidence-contract.md) and
[Architecture](../architecture.md).

## Revisit when

Revisit this decision when English has a reproducible measured baseline; when a
reviewed French or Dutch evaluation slice is ready; when metadata-only
citations can be represented and evaluated without confusing page evidence;
when another collection has compatible rights and provenance; or when an
agentic experiment produces a material quality improvement on the same cases
that justifies its latency and complexity.
