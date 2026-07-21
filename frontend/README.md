# HeritageRAG frontend prototype

This Phase 3 prototype keeps its concerns deliberately separate:

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

Open `http://127.0.0.1:5173`. Vite forwards `/health` requests to the backend
on port `8000`. The browser uses this same path when FastAPI serves the built
frontend, so the API contract does not change between development and runtime.

## Verify the production build

```powershell
cd frontend
pnpm build
```

The ingestion counts and explorer records are explicitly labelled demo data.
Only the system-health indicator calls the real backend in this phase.
