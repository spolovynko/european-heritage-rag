# Phase 3 — UI foundation and progress dashboard

## Objective

Build the visual shell before ingestion so every later pipeline phase can expose visible progress and inspectable intermediate data.

## What we will learn

- React component structure.
- TypeScript API contracts.
- Separating UI state from backend state.
- Designing diagnostic interfaces for data pipelines.
- Mock-first UI development.

## Development steps

1. Create the React and TypeScript frontend with Vite.
2. Establish a deliberately small structure:
   - `pages/`
   - `components/`
   - `api/`
   - `types/`
3. Create three initial screens:
   - Chat shell.
   - Pipeline dashboard.
   - Data explorer.
4. Create a navigation layout and basic responsive styling.
5. Use static typed mock data for:
   - Ingestion run status.
   - Work counts.
   - Page counts.
   - Errors.
   - Sample metadata record.
   - Sample OCR page.
6. Add a typed API client with one backend status request.
7. Replace one mock widget with real backend health information.
8. Add loading, empty, and error states from the beginning.
9. Add a frontend type-check and production-build command.
10. Document how to run backend and frontend together.

## Initial UI layout

```text
┌──────────────────────────────────────────────────────────────┐
│ HeritageRAG                                    System status │
├──────────────┬───────────────────────────────────────────────┤
│ Chat         │ Pipeline dashboard                            │
│ Ingestion    │                                               │
│ Data         │ Works  Pages  Failures  Last run              │
│ Retrieval    │                                               │
│ Evaluation   │ Progress and recent events                    │
└──────────────┴───────────────────────────────────────────────┘
```

## Verification

- Frontend runs with one command.
- Frontend production build succeeds.
- Backend health appears in the UI.
- Mock data is isolated and can later be replaced easily.
- No state-management framework is added without need.

## Exit criteria

- The application has a navigable visual shell.
- Later phases have clear locations for progress and inspection.
- The chat UI visibly exists even though it is not yet connected to RAG.

## Required ADR

`ADR-0003: React UI architecture and early diagnostic dashboard`

Decision questions:

- Why build the UI before ingestion?
- Why React, TypeScript, and Vite?
- Why start with typed mock data?
- Why avoid a large component or state framework initially?

---
