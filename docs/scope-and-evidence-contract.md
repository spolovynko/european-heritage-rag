# Scope and evidence contract

## Product contract

HeritageRAG helps people inspect what a bounded collection of digitised
public-domain Wellcome books says about European medical, scientific, social,
and cultural history. The assistant retrieves page-aware text, answers only
from that evidence, exposes its sources, and says when the corpus cannot support
an answer.

This is a corpus-exploration tool. It does not promise historical truth,
catalogue completeness, or expert advice. A cited passage shows what an indexed
source says; the answer must preserve that distinction when a source contains
dated, biased, or medically unsafe views.

## Initial corpus boundary

| Dimension | Phase 1 decision |
|---|---|
| Source | Wellcome Collection catalogue records and IIIF resources |
| Rights | Digitised books identified as public domain and carrying usable provenance |
| Content needed | Metadata, page images, and OCR sufficient to create page-aware text chunks |
| Topic | European medical, scientific, social, and cultural history represented in the selected books |
| Language | English baseline; French and Dutch only after the English baseline is evaluated |
| Development scale | 5–100 works, growing progressively |
| Portfolio scale | Approximately 250–500 works |
| Retrieval unit | Page-aware text chunk |
| Required provenance | Work ID, title, page range, source URL, and licence |

The corpus manifest will be the authority on what is actually indexed. The
assistant must describe results as coming from "the indexed corpus," not from
all Wellcome holdings or all historical literature.

## User personas and needs

### Historical researcher

Needs rapid passage discovery, precise page locators, source links, and enough
context to check interpretation against the original digitised work.

### Student or educator

Needs a clear synthesis of a focused question, with visible evidence and
honest limits. Historical medical statements must not be reframed as modern
recommendations.

### Technical reviewer or curator

Needs to inspect the query, filters, retrieved ranking, chunks supplied to the
generator, citation mappings, abstention reason, and active data/index version.

## Question policy

| Question type | Supported behaviour | Evidence needed |
|---|---|---|
| Exact title, author, or date | Find the relevant work and report only visible bibliographic facts | Retrieved title or bibliographic page containing the reported field |
| Subject and period filtering | Apply structured filters to the indexed corpus and return matching works | Filter provenance plus page-bearing evidence for each work named in the answer |
| Passage-level historical question | Describe or quote what a source says without presenting it as current truth | Directly relevant retrieved page chunks |
| Synthesis or comparison | Combine supported points and preserve disagreement or uncertainty | Relevant chunks for every work and every side of the comparison |
| Follow-up question | Resolve the conversational referent, form a standalone query, and retrieve again | Evidence newly retrieved for the current turn; history is not evidence |
| Unanswerable question | Explain that the indexed evidence is insufficient | No invented citation; optionally cite evidence that supports a limited partial answer |

## What counts as a substantial claim

A substantial claim is an externally checkable assertion about a work, person,
date, event, recommendation, cause, comparison, or interpretation. A sentence
may contain more than one claim and may therefore need more than one citation.

Navigation text, a transparent statement that the system found insufficient
evidence, and a description of the system's own limitations do not require a
historical-source citation. They must still be accurate descriptions of system
state.

## Valid evidence

Evidence is valid only when all of the following are true:

1. It belongs to a work in the active indexed corpus.
2. It is returned by retrieval for the current turn after the current filters
   are applied.
3. It is included in the bounded context sent to answer generation.
4. Its stored provenance contains a stable chunk ID, work ID, title, page start,
   page end, source URL, and licence.
5. Its text actually supports the nearby claim. Mere keyword overlap does not
   count as support.

User assertions, previous assistant messages, model pretraining, search traces
without content, and chunks from an earlier turn are not evidence. Conversation
history may help rewrite a follow-up query, but retrieval must establish the
evidence again for the current answer.

## Valid citations

A citation is valid when it:

- is attached to the claim or sentence it supports;
- identifies the work title and an inclusive page or page range;
- resolves to the exact retrieved chunk or chunks used for that claim;
- provides a source link when one is available; and
- does not overstate what the cited text supports.

Page labels printed in a work and image-sequence numbers can differ. The data
model must retain both when available, but the displayed locator must be stable
and unambiguous. The system must never invent a printed page number when the
source supplies only an image/canvas index.

A catalogue record may be shown as supplementary provenance or used as a
filter, but it does not replace the page-bearing citation required by the
initial answer contract. This deliberately strict choice may cause abstention
when a fact exists only in metadata; that trade-off can be revisited with
evaluation evidence.

## Abstention and partial answers

The assistant must abstain when any of these conditions applies:

- the request is outside the product or language scope;
- no relevant evidence is retrieved;
- retrieved passages mention the topic but do not support the requested claim;
- sources materially conflict and the conflict cannot be represented safely;
- a required work, page locator, source URL, or rights field is missing;
- the user asks for current medical advice, diagnosis, or treatment;
- the question assumes coverage beyond the indexed corpus;
- the answer would require private, visual, or external knowledge unavailable
  in retrieved text; or
- the citation validator cannot map every substantial claim to retrieved
  evidence.

When only part of a question is supported, the assistant may answer that part,
cite it, and state precisely what could not be established. An abstention should
be useful but brief: say that the indexed evidence is insufficient, give the
reason when known, and suggest a narrower corpus-grounded query when possible.
It must not fill the gap with plausible model knowledge.

## Retrieval quality versus answer quality

These stages fail differently and must be evaluated separately:

```text
question -> filters/query -> ranked evidence -> bounded context -> answer -> citation validation
              RETRIEVAL QUALITY                ANSWER QUALITY
```

- **Retrieval quality** asks whether annotated relevant work pages appear high
  enough in the ranked results. Recall@10 is the initial primary measure. A
  generator cannot repair evidence that was never retrieved.
- **Answer quality** asks whether every substantial claim is entailed by the
  supplied evidence, citations map correctly, limitations are preserved, and
  the assistant abstains when required. Fluent prose is not proof of quality.

Failures will be labelled by stage so prompt changes are not used to hide
ingestion, OCR, chunking, filtering, or ranking problems.

## Initial success criteria

All targets are goals for later measured evaluation and may be revised through
an ADR after a reproducible baseline exists.

| Metric | Target | Evaluation rule |
|---|---:|---|
| Retrieval Recall@10 | >= 0.85 | Fraction of answerable English cases for which at least one manually relevant page/chunk is in the top 10 |
| Citation coverage | 100% | Fraction of substantial answer claims carrying one or more citations |
| Citation validity | 100% | Fraction of citations that resolve to current-turn retrieved context and expose work plus page range |
| Citation support | >= 0.90 | Fraction of cited claims judged entailed by the cited passage during manual or rubric-based review |
| Abstention accuracy | >= 0.90 | Correct answer/abstain decision across the abstention set |
| Safety/out-of-scope recall | 1.00 | All current-medical-advice and clearly outside-corpus cases abstain |
| Search latency | p95 <= 1.5 s | Warm end-to-end search through reranking for top 10; generation excluded |

The first dedicated abstention set must contain at least 20 cases, at least 5
of them unanswerable. It must cover absent facts, outside-corpus assumptions,
ambiguous follow-ups, missing provenance, and current medical advice. The ten
Phase 1 examples in the root README seed—not replace—the evaluation set.

Every metric report must include the evaluation-set version, corpus version,
index and retrieval configuration, hardware, run count, and latency percentile
method. Until such a report exists, project documentation must say “target” or
“not yet measured,” never “achieved.”

## Language expansion gate

English is a controlled baseline, not a statement that other languages are less
important. French or Dutch may be added after:

1. the English evaluation set and metric runner exist;
2. the English Recall@10 and citation validators have measured baselines;
3. language-specific OCR, tokenisation, embeddings, and queries can be tested;
4. a reviewed evaluation slice exists for the added language; and
5. per-language results are reported rather than hidden in an aggregate.

## Explicitly unsupported capabilities

- general or autonomous web browsing;
- factual answers based only on model memory;
- current medical diagnosis, treatment, or safety advice;
- claims about all Wellcome holdings or all European history;
- user-uploaded documents or arbitrary URLs;
- image-based interpretation, image embeddings, and handwriting recognition;
- multiple museum or library sources;
- non-public-domain or rights-unclear material;
- autonomous agents that select unbounded tools or sources;
- authoritative translation of sources; and
- large-scale distributed ingestion, microservices, or Kubernetes.

These are product boundaries, not permanent prohibitions. Each expansion needs
a concrete requirement, evaluation data, rights review where applicable, and a
recorded architecture decision.
