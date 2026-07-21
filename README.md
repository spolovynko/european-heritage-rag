# HeritageRAG

HeritageRAG is an evidence-first assistant for exploring European medical,
scientific, social, and cultural history in digitised public-domain books from
the Wellcome Collection. It answers from retrieved passages, identifies the
work and page range supporting each substantial claim, and abstains when the
available corpus does not provide enough evidence.

The project has two goals: learn the engineering trade-offs of a real
retrieval-augmented generation (RAG) system and produce a small portfolio
project whose behaviour can be explained, tested, and defended.

## Project status

Phase 1 defined the product boundary, evidence contract, and evaluation goals.
Phase 2 established the reproducible Python environment, typed configuration,
structured logging, health API, CLI, automated checks, and container baseline.
Phase 3 is building the frontend shell and preparing to serve it from FastAPI.
No dataset has been ingested, and the application is not ready for end-user use.

## Who it is for

- **Historical researcher:** locates relevant passages and verifies them
  against digitised pages.
- **Student or educator:** asks focused historical questions and receives a
  concise, sourced explanation rather than an unsupported overview.
- **Technical reviewer or curator:** inspects retrieved chunks, provenance,
  citations, abstentions, and pipeline diagnostics.

## Supported question types

The planned English baseline supports:

- exact title, author, and publication-date lookup;
- subject and publication-period filtering within the indexed corpus;
- passage-level questions about what indexed works say;
- comparisons or summaries when every claim can be supported by retrieved
  passages;
- follow-up questions, after rewriting them into standalone retrieval queries;
- unanswerable or out-of-scope questions, which must produce an abstention.

French and Dutch are planned only after the English retrieval baseline has
been evaluated. Adding a language means evaluating retrieval and citation
behaviour for that language; translating the interface alone does not qualify.

## Evidence contract

1. Every substantial claim in an answer must be supported by retrieved
   evidence from the indexed corpus.
2. A valid citation identifies the work and the page or inclusive page range.
3. The cited chunk must have been returned for the current question and passed
   into the answer-generation context.
4. A model's background knowledge, a user's assertion, and earlier assistant
   messages are context, not evidence.
5. Missing, irrelevant, contradictory, or provenance-deficient evidence
   results in a partial answer with an explicit limitation or a full
   abstention—never a guess.
6. Bibliographic metadata may filter or identify candidate works, but a
   substantive answer still requires page-bearing evidence. If a title,
   contributor, or date cannot be verified on a retrieved bibliographic or
   title page, the assistant abstains from stating it as established fact.

The complete definitions, edge cases, and abstention rules are in
[Scope and evidence contract](docs/scope-and-evidence-contract.md).

## Trust and evaluation

The project will evaluate retrieval quality, citation coverage and validity,
abstention behaviour, and search latency against a versioned English evaluation
set. These are future release targets, not achieved results. The measurement
rules and target values are defined in the
[scope and evidence contract](docs/scope-and-evidence-contract.md).

## Example questions

Placeholders such as `[work]` and `[topic]` will be replaced with real entities
when the first corpus and evaluation set are selected.

| # | Example user question | Type | Answerability | Expected evidence |
|---:|---|---|---|---|
| 1 | Who wrote `[work]`, and when was it published? | Exact author/date lookup | Answerable when indexed | Retrieved title or bibliographic page showing the contributor and date |
| 2 | What is the exact title printed in `[work]`? | Exact title lookup | Answerable when indexed | Retrieved title page, cited by work and page |
| 3 | Which indexed books about public health were published from 1850 to 1899? | Subject and period filter | Answerable when matches exist | Catalogue filters to find candidates plus a page-bearing citation for every reported work |
| 4 | What measures does `[work]` recommend for preventing cholera? | Passage-level historical question | Answerable when discussed | One or more retrieved passages containing the recommendations |
| 5 | How does `[work]` describe the causes of tuberculosis? | Passage-level historical question | Answerable when discussed | Retrieved explanatory passage(s), preserving the source's historical viewpoint |
| 6 | Compare how `[work A]` and `[work B]` discuss sanitation. | Multi-work comparison | Answerable when both are indexed | Retrieved passages from both works; each comparative claim cites the relevant pages |
| 7 | What reasons did the author give for that recommendation? | Follow-up question | Answerable if the referent is clear | A standalone query derived from the conversation, followed by newly retrieved page evidence |
| 8 | Summarise the argument on pages 20–25 of `[work]`. | Page-constrained summary | Answerable when pages are indexed | Retrieved chunks wholly or partly covering pages 20–25 |
| 9 | Based on these books, what medicine should I take today? | Current medical advice | **Deliberately unanswerable** | Abstention; historical passages are not evidence for current clinical advice |
| 10 | What did the author privately think about an event never mentioned in the indexed works? | Absent/private information | **Deliberately unanswerable** | Abstention after retrieval finds no direct page-level support |

## Limitations

The initial product does not provide current medical advice, general web
search, claims about material outside the indexed corpus, image interpretation,
handwriting recognition, user document upload, non-public-domain content,
autonomous research, or exhaustive coverage of the Wellcome catalogue. It is
not a substitute for reading the original source or consulting a historian.

## Documentation

- [Scope and evidence contract](docs/scope-and-evidence-contract.md)
- [Architecture](docs/architecture.md)
- [Project status and next-phase handoff](docs/project-status.md)
- [Building phases roadmap](docs/building_phases/README.md)
- [ADR index](docs/adr/README.md)
- [ADR-0001: Project scope and evidence contract](docs/adr/0001-project-scope-and-evidence-contract.md)
- [ADR-0002: Python, dependency management, and repository structure](docs/adr/0002-python-dependency-management-and-repository-structure.md)
- [Building guides](docs/building_guides/README.md)
- [Development and learning agreement](docs/learning-guide-agreement.md)
