# HeritageRAG frontend

The browser application keeps its concerns deliberately separate:

- `index.html` contains the semantic page structure.
- `styles.css` contains the responsive visual system.
- `app.js` contains navigation, sample records, API health, and interactions.

## Run locally

Start the backend from the repository root:

```powershell
uv run uvicorn european_heritage_rag.api.main:app --reload
```

In a second terminal, start the frontend:

```powershell
cd frontend
pnpm install
pnpm dev
```

Open `http://127.0.0.1:5173`. Vite forwards `/health` and `/ingestion` requests
to the backend on port `8000`. The browser uses these same relative paths when
FastAPI serves the built frontend, so the API contract does not change between
development and runtime.

## Verify the production build

```powershell
cd frontend
pnpm build
```

The system-health indicator calls `/health/ready`. The Phase 4 ingestion
dashboard calls `/ingestion/status` immediately and then every three seconds.
It displays persisted CLI-run status but does not start ingestion itself; use:

```powershell
uv run european-heritage-rag ingest wellcome --limit 5 --dry-run
```

Data explorer records, retrieval state, evaluation values, and chat answers
remain explicitly labelled demonstration or future behavior.
