# Architecture Decision Records

Architecture Decision Records (ADRs) capture durable project decisions, their
alternatives, consequences, validation, and conditions for reconsideration.
They are not task logs. Accepted records are changed only to correct errors or
clarify wording; a later decision that replaces one should normally receive a
new number and mark the earlier record superseded.

## Index

| ADR | Status | Date | Decision |
|---|---|---|---|
| [ADR-0001: Project scope and evidence contract](0001-project-scope-and-evidence-contract.md) | Accepted | 2026-07-20 | Begin with English public-domain Wellcome books, require current-turn page evidence, and use deterministic two-step RAG as the evaluated baseline. |
| [ADR-0002: Python, dependency management, and repository structure](0002-python-dependency-management-and-repository-structure.md) | Accepted | 2026-07-21 | Use Python 3.12, `uv`, a root `src` layout, progressive dependencies, and a minimal one-service container baseline. |
| [ADR-0003: Browser-native UI foundation and same-origin FastAPI delivery](0003-browser-native-ui-and-fastapi-delivery.md) | Accepted | 2026-07-22 | Build the diagnostic UI before ingestion with separated browser-native assets and Vite, serve it from FastAPI on one origin, and defer React and TypeScript until real client complexity justifies migration. |

## Supporting documents

- [Scope and evidence contract](../scope-and-evidence-contract.md)
- [Architecture](../architecture.md)
- [Project status](../project-status.md)
- [Development and learning agreement](../learning-guide-agreement.md)
- [Building phases roadmap](../building_phases/README.md)
- [Building guides](../building_guides/README.md)

## Naming and status

Files use `NNNN-short-decision-title.md` with sequential numbers. Valid statuses
are Proposed, Accepted, Superseded, and Deprecated. Every phase produces at
least one ADR for a meaningful decision using the template in the development
and learning agreement.
