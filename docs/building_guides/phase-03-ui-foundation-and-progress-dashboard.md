# Phase 3 - UI foundation and progress dashboard

## 1. Phase at a glance

Phase 3 gave HeritageRAG its first browser interface.

At the end of this phase, the interface could:

- move between Chat, Ingestion, Data, Retrieval, and Evaluation views;
- adapt to desktop and mobile screen sizes;
- show sample records and sample OCR pages;
- display honest empty and not-yet-built states; and
- call the real backend readiness endpoint.

Most values were still clearly marked as demonstrations. The purpose was to
build the screen structure before connecting real ingestion and retrieval.

| Area | Choice made in Phase 3 |
|---|---|
| Frontend files | Browser-native HTML, CSS, and JavaScript |
| Build tool | Vite |
| Package manager | pnpm with a committed lockfile |
| Real backend request | `GET /health/ready` |
| Final delivery | FastAPI serves the built frontend and API from one origin |
| Docker build | Node builds the frontend; Python runs the final application |
| UI records and metrics | Clearly labelled demonstration data |
| Browser state | One small JavaScript state object |

Why we did not add React and TypeScript: the application had one page and a
small number of interactions. We first wanted real feature complexity to show
whether a framework was necessary.

Not included in Phase 3:

- real ingestion, search, retrieval, evaluation, or answer generation;
- automated browser end-to-end tests;
- a separate production frontend service;
- live progress through Server-Sent Events or WebSockets; and
- production CDN caching and compression.

## 2. Repository structure

The main Phase 3 files were:

```text
frontend/
|-- public/
|   `-- og.png
|-- app.js
|-- index.html
|-- package.json
|-- pnpm-lock.yaml
|-- pnpm-workspace.yaml
|-- README.md
|-- styles.css
`-- vite.config.js

src/european_heritage_rag/api/
`-- main.py

tests/api/
`-- test_frontend.py

Dockerfile
compose.yaml
.dockerignore
.gitignore

docs/adr/
|-- 0003-browser-native-ui-and-fastapi-delivery.md
`-- README.md
```

Two generated folders are not committed:

- `frontend/node_modules/` contains downloaded JavaScript packages.
- `frontend/dist/` contains the finished files produced by Vite.

Why: both folders can be rebuilt from committed source and lockfiles. Keeping
them out of Git avoids storing large generated files.

## 3. Runtime flow

### 3.1 Local frontend development

During frontend development, two servers run:

```text
Browser
  |
  | page and assets
  v
Vite at 127.0.0.1:5173
  |
  | forwards /health/ready
  v
FastAPI at 127.0.0.1:8000
```

What happens:

1. Vite serves the HTML, CSS, and JavaScript while we edit them.
2. Browser code requests the relative path `/health/ready`.
3. Vite forwards that request to FastAPI.

Why use a relative path: the browser does not need to know a different API URL
for development and the combined application. It always calls
`/health/ready`.

### 3.2 Production-style local and container delivery

The production-style flow is different because Vite is not left running:

```text
frontend source
      |
      | vite build
      v
frontend/dist
      |
      | served as static files
      v
FastAPI on port 8000
      |
      +-- /health/live
      +-- /health/ready
      `-- / and frontend assets
```

FastAPI registers API routes first and mounts the frontend at `/` afterward.
That order matters: the broad frontend mount must not hide `/health/live` or
`/health/ready`.

If `frontend/dist` does not exist, FastAPI still starts. Health endpoints still
work, but `/` returns `404` until the frontend is built.

### 3.3 Container build

The Dockerfile uses two build stages:

1. The Node stage installs locked pnpm packages and runs the Vite build.
2. The Python stage installs the backend and copies only `frontend/dist` from
   the first stage.

Why: Node and frontend development packages are needed to build the site, but
they are not needed to run the final application. The final container contains
Python plus the finished static files.

Compose still runs one `api` service on port 8000 and checks
`/health/ready` to decide whether it is healthy.

## 4. File-by-file implementation review

### 4.1 `frontend/index.html`

What: this file contains the page structure and accessible labels.

It defines:

- the sidebar and main area;
- navigation between the five views;
- the system-status button;
- ingestion cards and recent activity;
- the chat placeholder and example questions;
- the sample record list and OCR page viewer;
- empty retrieval and evaluation states; and
- buttons, forms, live regions, metadata, and the social-preview image.

Why: HTML describes what each part of the page means. It should not contain the
application's styling rules or most interaction logic.

The ingestion and data values were marked as demonstration values. They showed
how later real data would fit without claiming that a pipeline had run.

### 4.2 `frontend/styles.css`

What: this file controls how the application looks and responds to different
screen sizes.

It includes:

- shared colors, spacing, borders, and shadows;
- desktop and mobile layouts;
- sidebar behavior;
- metric cards, panels, progress bars, and event lists;
- chat, record, OCR, retrieval, and evaluation views; and
- focus, hover, loading, empty, success, warning, and error states.

Why: presentation stays separate from HTML structure and JavaScript behavior.
This makes each type of change easier to find.

Current trade-off: one large stylesheet is manageable for the prototype, but
repeated real components may later justify component-scoped styles.

### 4.3 `frontend/app.js`

What: this file handles browser interactions and the small amount of browser
state.

It can:

- change the active view;
- open and close the mobile sidebar;
- keep accessibility attributes in sync;
- call `/health/ready` with a timeout;
- render online, offline, and checking states;
- search and filter sample records;
- show one sample record and move through its OCR pages;
- place a suggested question in the chat box; and
- show short notification messages.

Why: HTML stays focused on structure while JavaScript handles events and state
changes.

The readiness request uses an `AbortController`. This cancels the request if
the backend does not answer within the browser timeout. The response must have
a successful HTTP status and contain `status: "ok"`.

Sample records live in one array at the top of the file. This created a clear
replacement point: later phases could replace one sample boundary at a time
with a real API response.

JSDoc comments describe the expected data shapes for editor help. They are
useful, but they do not provide the compile-time guarantees of TypeScript.

### 4.4 `frontend/package.json`

What: this file describes the frontend package and its commands.

It declares:

- a private package that should not be published;
- pnpm `11.15.1` as the expected package manager;
- JavaScript modules;
- `dev`, `build`, and `preview` commands; and
- Vite as the only development dependency.

Why: the Phase 3 frontend did not need a UI framework, router, state library,
or test runner.

### 4.5 `frontend/pnpm-lock.yaml` and `pnpm-workspace.yaml`

What: the lockfile records the exact frontend dependency versions. The
workspace file describes this frontend package and permits Vite's required
esbuild setup.

Why: `pnpm install --frozen-lockfile` can recreate the same package graph and
will fail if `package.json` and the lockfile disagree.

### 4.6 `frontend/vite.config.js`

What: this file configures the local Vite server.

How:

- Vite listens at `127.0.0.1:5173`.
- Requests beginning with `/health` are forwarded to FastAPI at port 8000.

Why: the proxy is only for development. When FastAPI serves the finished
frontend, browser and API already share one origin and no proxy is needed.

### 4.7 `frontend/README.md`

What: this is the focused operating note for frontend developers.

It explains how to run Vite and FastAPI, how relative API paths work, how to
build the frontend, and which values were real or demonstrations in Phase 3.

### 4.8 `frontend/public/og.png`

What: this image is used when a link to the prototype is shared.

Vite copies files from `public/` into the production build. The image is
presentational and has no effect on backend or RAG behavior.

### 4.9 `src/european_heritage_rag/api/main.py`

What changed: the FastAPI application factory gained a
`frontend_directory` argument.

How it works:

1. FastAPI registers the health routes.
2. It checks whether the frontend directory exists.
3. If it exists, FastAPI mounts it at `/` with HTML support.
4. If it does not exist, FastAPI keeps running without a root page.

Why the directory is an argument: tests can provide a temporary folder instead
of requiring a real Vite build.

### 4.10 `tests/api/test_frontend.py`

What: these tests create a temporary HTML file and JavaScript asset.

They prove that:

- `/` returns the temporary page;
- a nested frontend asset is served;
- `/health/ready` still works after the root mount;
- missing frontend files do not stop FastAPI; and
- health routes still work without a frontend build.

Why: backend tests should not need Node, Vite, or the generated `dist` folder.

### 4.11 `Dockerfile`

What changed: the Dockerfile now builds both the frontend and backend.

The frontend stage installs pnpm dependencies and runs `pnpm build`. The final
Python stage installs locked backend dependencies and copies the generated
frontend files.

Why: the same image can serve the API and browser application, while the final
runtime does not carry Node or frontend source code.

### 4.12 `compose.yaml`

What: Compose still describes one service.

The Phase 3 service:

- builds from the root Dockerfile;
- uses production logging at INFO level;
- exposes port 8000; and
- checks readiness through `/health/ready`.

Why: a separate Vite server, reverse proxy, database, or search service was not
needed yet.

### 4.13 Ignore files

`.gitignore` excludes installed frontend packages and generated build output.

`.dockerignore` excludes local environments, caches, tests, documentation,
installed frontend packages, and old local build output. Docker creates a fresh
frontend build instead of trusting files generated on the developer's machine.

## 5. API and state boundaries

### Real backend state

The only real browser request in Phase 3 was:

```http
GET /health/ready
```

It returned the service name, version, status, and configuration readiness.

### Demonstration state

These values were still examples:

- ingestion counts and events;
- catalogue records and OCR pages;
- retrieval results;
- evaluation results; and
- chat answers.

Why keep the difference visible: a polished screen must not make unbuilt
behavior look real.

### Same-origin rule

Browser code uses relative API paths. This gives the browser the same request
request rules in:

- Vite development, where the proxy forwards the call;
- local FastAPI delivery; and
- Docker Compose delivery.

## 6. Operational commands

Install the locked frontend packages:

```powershell
pnpm --dir frontend install --frozen-lockfile
```

Run backend and frontend development servers in separate terminals:

```powershell
uv run uvicorn european_heritage_rag.api.main:app --reload
pnpm --dir frontend dev
```

Build the frontend:

```powershell
pnpm --dir frontend build
```

Serve the built frontend and API together:

```powershell
uv run uvicorn european_heritage_rag.api.main:app
```

Build and start the container application:

```powershell
docker compose build
docker compose up --detach --wait
```

Stop it:

```powershell
docker compose down
```

## 7. Verification

The Phase 3 completion checks were repeated on 2026-07-22.

| Command or check | What it proved | Result |
|---|---|---|
| `uv sync --locked` | Backend dependencies can be recreated from the lockfile | Passed |
| `uv run pytest` | Configuration, CLI, logging, health, and frontend delivery work | 16 tests passed |
| `uv run ruff check .` | Python lint rules pass | Passed |
| `uv run ruff format --check .` | Python formatting is correct | Passed |
| `uv run mypy src` | Strict backend type checking passes | Passed |
| `pnpm --dir frontend install --frozen-lockfile` | Frontend packages match the lockfile | Passed |
| `pnpm --dir frontend build` | Vite can create the production files | Passed |
| `docker compose build` | The combined application image builds | Passed |
| `docker compose up --detach --wait` | The container starts and becomes healthy | Passed |
| `GET /health/ready` | The combined runtime keeps the API route | HTTP 200 with `status=ok` |
| `GET /` | FastAPI serves the frontend | HTTP 200 |
| `git diff --check` | The change set has no whitespace errors | Passed |

Desktop and mobile interactions were also checked manually. Automated browser
tests remained a future improvement.

## 8. Review summary

Phase 3 created a usable visual and delivery foundation for later features.

What should remain stable:

- browser requests use relative same-origin paths;
- Vite owns the frontend build;
- API routes are registered before the broad root frontend mount;
- tests can provide a temporary frontend directory;
- FastAPI still works when the frontend has not been built;
- one final image serves both frontend and backend; and
- sample data is clearly separated from real data.

Known limitations:

- browser code is not statically checked by TypeScript;
- large frontend files may become harder to maintain;
- there are no automated frontend unit or browser tests;
- local combined serving requires a frontend build first;
- FastAPI static serving is not a production CDN; and
- Phase 3 contains no real ingestion, retrieval, evaluation, or chat data.

When to reconsider browser-native JavaScript: when repeated components, shared
state, API response shapes, or client-side routing make the current files difficult
to understand. At that point, React and TypeScript may solve a measured
problem rather than an imagined one.

The handoff to Phase 4 was simple: replace only the ingestion dashboard's
sample boundary with real progress. Do not redesign the whole interface.

## 9. Official references

- [Vite guide](https://vite.dev/guide/)
- [Vite production builds](https://vite.dev/guide/build)
- [Vite static assets](https://vite.dev/guide/assets.html)
- [pnpm install](https://pnpm.io/cli/install)
- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/)
- [Docker multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Compose services](https://docs.docker.com/reference/compose-file/services/)
