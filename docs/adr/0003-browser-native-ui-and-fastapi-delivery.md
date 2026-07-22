# ADR-0003: Browser-native UI foundation and same-origin FastAPI delivery

- Status: Accepted
- Date: 2026-07-22
- Phase: Phase 3 — UI foundation and progress dashboard

## Context

HeritageRAG needs a visible application shell before ingestion and retrieval are
implemented. Later phases must have stable places to show pipeline progress,
intermediate data, retrieval diagnostics, evaluation results, and eventual chat
responses. Building that shell early lets those workflows be designed around
inspectability instead of adding diagnostics after the pipeline is complete.

The Phase 3 plan originally anticipated React, TypeScript, and typed mock data.
The implemented prototype instead uses browser-native HTML, CSS, and JavaScript
with Vite. It already provides the navigation, responsive visual system,
dashboard workspaces, explicit demonstration data, interaction states, and a
real readiness request needed to validate the product structure.

The phase must therefore decide:

- whether to introduce a component and state framework before real workflow
  complexity exists;
- how HTML, styling, and behavior remain understandable and replaceable;
- how the browser reaches the existing FastAPI health contract;
- how local and container execution serve the same application; and
- how the frontend build remains testable without hiding API routes.

## Decision

### Build the diagnostic shell before ingestion

The UI foundation is built before the ingestion pipeline. It establishes
visible workspaces for chat, ingestion, data inspection, retrieval, and
evaluation while those capabilities are still demonstrations.

Demonstration values must remain visibly non-production data. They validate
layout, navigation, loading, empty, success, and error presentation; they do not
claim that ingestion or retrieval metrics have been measured.

Each later phase will replace the relevant demonstration boundary with a real
API contract instead of redesigning the whole shell.

### Use separated browser-native source files with Vite

The current frontend uses:

```text
frontend/index.html
frontend/styles.css
frontend/app.js
```

HTML owns document structure, CSS owns presentation and responsive behavior,
and JavaScript owns interactions, demonstration state, and API requests. The
three concerns are not embedded into one generated file.

Vite remains the frontend development and production-build tool. The frontend
package declares a pinned pnpm version, uses the committed lockfile, and builds
static assets into `frontend/dist`.

React, TypeScript, a client router, and a state-management framework are not
introduced in this baseline. The current interface has one page, a small event
surface, and no repeated server-backed feature model that requires those
abstractions. This is an intentional divergence from the initial Phase 3 plan,
not a claim that browser-native JavaScript is the final UI architecture.

### Use a same-origin API contract

Browser requests use relative paths, beginning with:

```text
/health/ready
```

Vite proxies `/health` to the local FastAPI server during frontend development.
For the production-style local and container workflows, FastAPI serves the
built frontend and the API from the same origin.

This avoids environment-specific API URLs and cross-origin configuration in the
initial application. A deployed browser and the local browser use the same
request path.

### Mount the built frontend after API routes

The FastAPI application factory accepts a frontend directory and mounts it at
`/` with `StaticFiles(..., html=True)` only when that directory exists.

The static mount is registered after `/health/live` and `/health/ready`. Route
ordering therefore preserves the explicit API endpoints before the catch-all
root mount.

The directory is injectable so tests can use temporary HTML and asset files.
When no frontend build exists, FastAPI still starts and its API routes remain
available; `/` returns a normal not-found response.

### Produce one runtime image with a multi-stage build

The Dockerfile uses two responsibilities:

1. A Node and pnpm builder installs the locked frontend dependencies and runs
   the Vite production build.
2. The Python runtime installs the backend from `uv.lock` and copies only the
   generated `frontend/dist` assets from the frontend builder.

Node, pnpm, frontend source, and frontend development dependencies do not become
runtime requirements of the final Python image.

Docker Compose continues to expose one `api` service on port 8000. There is no
separate production Vite container, reverse proxy, or frontend network service
in this phase.

## Alternatives considered

### Introduce React and TypeScript immediately

This matches the original roadmap and would provide components, typed props,
and a clearer migration path for complex client state. The current shell does
not yet have enough repeated, server-backed behavior to demonstrate that those
boundaries are necessary. Adding them now would increase tooling and migration
work before a real feature can validate the architecture.

React and TypeScript remain the expected reconsideration when real ingestion,
data exploration, or chat state makes browser-native modules difficult to
maintain.

### Run Vite as a separate production service

This would keep frontend and backend runtimes independent, but it would require
two processes, two service definitions, cross-origin or reverse-proxy routing,
and another production failure boundary. A static Phase 3 shell does not need a
long-running Node server.

### Keep the frontend on an external static host

External hosting is useful for previews and CDN delivery, but the earlier
frontend-only preview could not reach the local API as one application. Making
external hosting the required runtime would complicate local use and preserve a
second deployment path before it is needed.

### Render the UI with backend templates

Server-side templates could avoid a frontend build tool, but they would couple
the visual shell to Python rendering and make the eventual interactive client
migration harder. The current frontend is already a static browser application,
so FastAPI only needs to deliver its build artifacts.

### Combine HTML, CSS, and JavaScript into one file

This would simplify a very small prototype, but the dashboard is already large
enough that structure, presentation, and behavior need separate ownership.
Keeping them segregated also makes later framework migration easier to review.

## Consequences

### Positive

- Later pipeline phases have stable, visible locations for progress and
  diagnostics.
- The UI remains inspectable without introducing framework-specific concepts.
- Local and container users open one URL for both frontend and API.
- Relative API paths avoid initial cross-origin and environment-URL handling.
- Explicit API routes remain available before the root static mount.
- Tests can inject temporary frontend assets without requiring a Vite build.
- The API remains runnable when frontend assets have not been built.
- The final image contains static assets but no Node runtime.
- One Compose service preserves the small operational baseline from Phase 2.

### Negative or accepted trade-offs

- JavaScript data structures and API responses are not statically typed.
- The large HTML, CSS, and JavaScript files may become difficult to maintain as
  real features and repeated components grow.
- The production-style local workflow requires a frontend build before FastAPI
  can serve `/`.
- FastAPI serves static assets without the caching, compression, and geographic
  distribution of a dedicated CDN.
- `StaticFiles(html=True)` is sufficient for the current single-page shell but
  is not a general client-router fallback for arbitrary future routes.
- The relative `frontend/dist` path assumes local commands run from the
  repository root and the container uses `/app` as its working directory.
- A later React and TypeScript migration may replace much of the current browser
  code after it has served its prototyping purpose.

## Validation

The decision is validated by the following repository and runtime evidence:

1. `pnpm --dir frontend install --frozen-lockfile` reproduces frontend
   dependencies from `pnpm-lock.yaml`.
2. `pnpm --dir frontend build` produces `dist/index.html` and versioned assets.
3. The backend test suite includes temporary-directory coverage for the root
   page, an asset, preserved health routing, and missing frontend assets.
4. The complete Python suite passes with 16 tests, Ruff, and strict mypy.
5. A production-build TestClient request returns 200 for `/` and
   `/health/ready`.
6. The multi-stage Docker image builds the frontend and installs the Python
   project non-editably.
7. A standalone container returns 200 for the root page, JavaScript asset, and
   readiness endpoint.
8. Docker Compose starts the Phase 3 image and reports the API service healthy.

## Revisit when

Revisit this decision when:

- repeated UI elements need reusable component boundaries;
- real API models make compile-time contract checking valuable;
- ingestion, data exploration, retrieval, or chat introduces complex shared
  client state;
- client-side routing requires a deliberate history fallback;
- the frontend and API need independent deployment or scaling;
- production traffic requires CDN caching, compression, or immutable asset
  policies;
- multiple browser clients need a generated typed API client; or
- measured maintenance cost justifies migrating the prototype to React and
  TypeScript.
