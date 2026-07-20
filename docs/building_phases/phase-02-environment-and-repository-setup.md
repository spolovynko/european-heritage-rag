# Phase 2 — Environment and repository setup

## Objective

Create a reproducible development environment and the smallest runnable backend. Avoid installing the full future stack before it is required.

## What we will learn

- Python dependency locking with `uv`.
- Environment-based configuration.
- Package layout and imports.
- Docker Compose basics.
- The difference between liveness and readiness.
- Basic automated quality checks.

## Development steps

1. Create the GitHub repository `european-heritage-rag`.
2. Initialize Git and create the root Python application using Python 3.12 and `uv`.
3. Add the initial dependencies only:
   - FastAPI
   - Uvicorn
   - Pydantic Settings
   - Typer
   - Structlog
4. Add development dependencies:
   - pytest
   - Ruff
   - mypy
5. Create a minimal settings model that reads environment variables.
6. Create `.env.example` without real credentials.
7. Implement:
   - `GET /health/live`
   - `GET /health/ready`
8. Add a small CLI entry point such as `european-heritage-rag version`.
9. Configure Ruff, mypy, and pytest in `pyproject.toml`.
10. Add a minimal Docker Compose file. Initially it may contain only backend development support; Qdrant is added when indexing begins and PostgreSQL when conversations begin.
11. Document setup and run commands in the README.

## Typical local commands

```powershell
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run uvicorn european_heritage_rag.api.main:app --reload
```

Exact paths will be adjusted to the repository layout created in this phase.

## UI work

None beyond confirming that the backend is reachable from a browser.

## Verification

- A clean clone can run `uv sync` successfully.
- The lockfile is committed.
- The health endpoint returns a typed JSON response.
- Tests and static checks pass.
- No secrets are tracked by Git.

## Exit criteria

- Backend starts with one documented command.
- All development checks pass.
- Repository structure is small and explained.

## Required ADR

`ADR-0002: Python, dependency management, and initial repository structure`

Decision questions:

- Why Python 3.12?
- Why `uv`?
- Why place the Python backend at the repository root and the later frontend in `frontend/`?
- Why progressively add dependencies?

---
