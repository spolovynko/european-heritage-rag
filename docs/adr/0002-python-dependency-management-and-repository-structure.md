# ADR-0002: Python, dependency management, and repository structure

- Status: Accepted
- Date: 2026-07-21
- Phase: Phase 2 — Environment and repository setup

## Context

HeritageRAG needs a reproducible development environment and a small runnable
backend before data ingestion or RAG dependencies are introduced. The project
also expects a frontend in a later phase, so the initial layout must leave room
for it without creating a premature multi-application repository.

Phase 2 must decide:

- the Python baseline;
- how Python, dependencies, and the lockfile are managed;
- where backend code and tests live;
- which dependencies belong in the initial environment; and
- how the backend is run consistently in a container.

## Decision

### Python 3.12 baseline

The backend uses Python 3.12 as its development and container baseline and
declares:

```toml
requires-python = ">=3.12"
```

Python 3.12 provides a modern typing and standard-library baseline while
remaining supported by the selected API, validation, testing, and future data
libraries. The project does not claim compatibility with a newer Python
version until its checks have been run on that version.

### `uv` for project and dependency management

`uv` manages:

- the local Python selection through `.python-version`;
- project metadata and direct dependencies in `pyproject.toml`;
- exact dependency resolution in `uv.lock`;
- the local virtual environment;
- dependency-group separation; and
- execution of project commands.

`uv.lock` is committed. Local and automated verification use `--locked` so a
stale lockfile fails instead of changing silently.

Runtime dependencies live in `[project].dependencies`. pytest, Ruff, mypy, and
test transports live in the `dev` dependency group and are excluded from the
container with `--no-dev`.

### Root backend with a `src` layout

The Python backend remains at the repository root:

```text
pyproject.toml
src/european_heritage_rag/
tests/
```

It is not nested under `backend/`. There is currently one backend, so another
directory would add navigation and configuration without separating multiple
applications.

The future frontend will use a sibling `frontend/` directory. It can maintain
its own package manager and configuration without moving the established Python
package.

The `src` layout separates importable application code from repository files
and tests. Tests are organized by concern under `tests/` and are not installed
as part of the package.

### Dependencies are added progressively

Only dependencies used by implemented code are installed. Phase 2 includes the
API, settings, logging, CLI, and quality tools. Vector databases, relational
databases, model clients, ingestion libraries, and frontend packages are added
only when a later phase implements their consumer.

This keeps lockfile changes, configuration, failure modes, and learning scope
traceable to a concrete feature.

### Minimal container baseline

The root `Dockerfile` builds the API from the committed lockfile, excludes the
development dependency group, installs the project non-editably, and runs as a
non-root user.

The root `compose.yaml` initially contains one API service and its readiness
health check. It does not contain a database or named volume before application
code requires one.

## Alternatives considered

### Python 3.11 or an older baseline

This would support more existing environments, but the project is new and does
not need legacy compatibility. Starting at 3.12 reduces the supported-version
matrix while keeping broad library support.

### Always target the newest Python release

This would expose new language features sooner, but future data and ML
dependencies may not support a new interpreter immediately. Newer versions can
be adopted after the locked environment and checks pass on them.

### `pip` with requirements files

This is widely understood, but it would separate package metadata, direct
requirements, development groups, environment creation, and locking across
multiple commands or files. `uv` provides one project workflow and a committed
cross-platform lockfile.

### Poetry or PDM

Both can manage modern Python projects and lock dependencies. `uv` was chosen
for its small command surface, fast resolver, Python management, and direct use
of standard `pyproject.toml` project metadata.

### Put the backend under `backend/`

This would make frontend/backend symmetry visible immediately, but there is no
second backend application to isolate. The extra level would complicate root
commands, paths, and Docker context without providing a current boundary.

### Install the planned RAG stack immediately

This could make later imports available sooner, but would add unused packages,
services, configuration, and version conflicts. It would also make it harder to
explain which phase required each dependency.

### Add PostgreSQL and a vector database to Compose now

This would demonstrate a multi-service stack, but no Phase 2 code consumes
those services. Unused infrastructure would produce maintenance work without
validating application behavior.

## Consequences

### Positive

- A clean clone can reproduce the environment from `uv.lock`.
- Runtime and development dependencies have an explicit boundary.
- The package layout remains small and conventional.
- The later frontend can be added without relocating backend code.
- Each new dependency can be traced to an implemented phase.
- Local and container execution use the same project metadata and lockfile.
- Compose remains understandable until another service is genuinely required.

### Negative or accepted trade-offs

- Python versions below 3.12 cannot run the project.
- Contributors must install or learn `uv`.
- `uv.lock` is specific to the selected dependency-management workflow.
- Root-level backend configuration may need reconsideration if the repository
  later contains multiple Python services.
- Progressive installation moves some integration work into later phases.
- The Phase 2 Compose stack does not yet represent the eventual RAG system.

## Validation

The decision is validated by the following repository evidence:

1. `.python-version`, `pyproject.toml`, and `uv.lock` define the environment.
2. `uv lock --check` confirms that the manifest and lockfile agree.
3. `uv sync --locked` reproduces the local environment.
4. pytest, Ruff, and strict mypy checks pass through `uv run --locked`.
5. `european-heritage-rag version` runs through the declared console script.
6. Docker builds the application from the locked production dependency set.
7. Docker Compose starts the API and reaches the readiness health check.

Implementation details and commands are recorded in the
[Phase 2 build review](../building_guides/phase-02-environment-and-repository-setup.md).

## Revisit when

Revisit this decision when:

- the minimum Python version needs to move forward;
- a required dependency is incompatible with `uv` or the chosen Python version;
- the repository gains multiple independently deployed Python services;
- frontend tooling creates a reason to introduce a formal workspace layout;
- production deployment requires immutable image digests or a multi-stage image;
  or
- a database or vector store has an implemented application consumer.
