# Phase 3 — UI foundation and progress dashboard

## 1. Phase at a glance

Phase 3 created the first visible HeritageRAG application shell and connected
one part of it—the system-status indicator—to the real backend readiness API.

The implemented frontend uses browser-native HTML, CSS, and JavaScript with
Vite. This intentionally differs from the original React and TypeScript plan.
The current application has one page, a small interaction surface, and no
complex shared server state, so a component or state-management framework was
not yet justified.

The production-style application is delivered from one origin: Vite builds
static assets into `frontend/dist`, and FastAPI serves those assets alongside
the existing health endpoints.

| Area | Implemented choice |
|---|---|
| Frontend source | Browser-native HTML, CSS, and JavaScript |
| Development/build tool | Vite |
| Package manager | pnpm with a committed lockfile |
| Real API integration | `GET /health/ready` |
| Production-style delivery | FastAPI `StaticFiles` mount |
| Container delivery | Node frontend builder plus Python runtime stage |
| UI data | Explicitly labelled demonstration records and metrics |
| Client state | Small module-level JavaScript state object |

Deliberate exclusions:

- React, TypeScript, a client router, and a state-management framework.
- Real ingestion, retrieval, evaluation, and answer-generation data.
- Browser end-to-end test automation.
- Independent frontend deployment.
- Server-Sent Events or WebSocket progress updates.
- Production CDN caching and asset compression.

## 2. Repository structure

The meaningful Phase 3 implementation files are:

```text
frontend/
├── public/
│   └── og.png
├── app.js
├── index.html
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── README.md
├── styles.css
└── vite.config.js

src/european_heritage_rag/api/
└── main.py

tests/api/
└── test_frontend.py

Dockerfile
compose.yaml
.dockerignore
.gitignore

docs/adr/
├── 0003-browser-native-ui-and-fastapi-delivery.md
└── README.md
```

Generated directories are intentionally not committed:

- `frontend/node_modules/` contains installed frontend dependencies.
- `frontend/dist/` contains the Vite production build.

The frontend lockfile is committed so the dependency graph can be reproduced.

## 3. Runtime flow

### 3.1 Local frontend development

```text
Browser
  │
  ├── page and assets ──> Vite at 127.0.0.1:5173
  │
  └── /health/ready ───> Vite proxy
                              │
                              └──> FastAPI at 127.0.0.1:8000
```

The browser always requests the relative path `/health/ready`. During
development, `frontend/vite.config.js` proxies `/health` to FastAPI. No
environment-specific backend URL is embedded in the frontend.

### 3.2 Production-style local and container delivery

```text
frontend source
      │
      └── vite build
              │
              ▼
       frontend/dist
              │
              ▼
FastAPI health routes + root StaticFiles mount
              │
              ▼
      one origin on port 8000
```

FastAPI registers `/health/live` and `/health/ready` before mounting the built
frontend at `/`. Route order preserves the explicit API endpoints before the
root static application.

If `frontend/dist` does not exist, FastAPI still starts and serves its API
routes. The root URL returns `404` until frontend assets are built.

### 3.3 Container build

The Dockerfile contains two stages:

1. `frontend-builder` installs the locked pnpm dependencies and runs the Vite
   production build.
2. The Python runtime installs the locked backend and copies only
   `frontend/dist` from the builder.

Node, pnpm, frontend source, and frontend development dependencies are absent
from the final runtime stage.

Docker Compose still runs one `api` service. The service exposes port `8000`
and uses `/health/ready` for its health check.

## 4. File-by-file implementation review

### 4.1 `frontend/index.html`

`index.html` owns the semantic document structure. It defines:

- The responsive sidebar and main workspace.
- Navigation for Chat, Ingestion, Data, Retrieval, and Evaluation.
- The system-status control.
- The ingestion dashboard and recent-activity layout.
- The chat placeholder and sample question controls.
- The sample-record browser and OCR page viewer.
- Empty retrieval and not-yet-measured evaluation states.
- Accessible labels, live regions, buttons, and form controls.
- Social-preview metadata and the Open Graph image.

The ingestion and data values are marked as demonstration data. They establish
the presentation contract for later phases without claiming that a real
pipeline has run.

### 4.2 `frontend/styles.css`

`styles.css` owns the visual system and responsive behaviour. It contains:

- Reusable colour, spacing, border, and shadow variables.
- Desktop sidebar and workspace layouts.
- Responsive navigation for smaller screens.
- Metric cards, panels, progress indicators, and activity events.
- Chat, data-explorer, OCR, retrieval, and evaluation states.
- Focus, hover, loading, empty, success, warning, and error presentation.
- Mobile layout changes at the defined breakpoints.
- Reduced reliance on JavaScript for layout and presentation.

The stylesheet is deliberately independent of a component framework. Its size
is a known reason to reconsider component-scoped styling if the real UI grows
substantially.

### 4.3 `frontend/app.js`

`app.js` owns browser behaviour and the current client-side state.

Its main responsibilities are:

- Maintaining the active workspace and selected sample record.
- Opening and closing the mobile sidebar.
- Synchronising sidebar accessibility attributes.
- Fetching `/health/ready` with a browser-side timeout.
- Rendering online, offline, and checking health states.
- Searching and filtering demonstration records.
- Rendering record metadata and sample OCR pages.
- Moving between OCR pages.
- Filling chat suggestions and showing placeholder feedback.
- Displaying temporary user notifications.

The health request validates both HTTP success and the expected response
status. An `AbortController` cancels requests that exceed the client timeout.

The sample records remain isolated in one array at the top of the module. Later
phases can replace individual demonstration boundaries with API responses
without first redesigning the entire page.

The JavaScript uses JSDoc contracts for the real health response and sample
record shapes. These comments improve editor support but do not provide
TypeScript compile-time validation.

### 4.4 `frontend/package.json`

The package declares:

- A private frontend package.
- pnpm `11.15.1` as the expected package manager.
- ES modules.
- `dev`, `build`, and `preview` scripts.
- Vite as the only frontend development dependency.

No UI framework, router, test runner, or state library is installed.

### 4.5 `frontend/pnpm-lock.yaml` and `pnpm-workspace.yaml`

The lockfile records the resolved frontend dependency graph.

The workspace file defines the frontend directory as the only package and
allows the required esbuild installation step. Together these files allow
`pnpm install --frozen-lockfile` to reject dependency drift.

### 4.6 `frontend/vite.config.js`

The Vite configuration fixes the local frontend server at
`127.0.0.1:5173`.

Requests beginning with `/health` are forwarded to
`http://127.0.0.1:8000`. This proxy exists only for frontend development;
the production-style application uses FastAPI and therefore needs no proxy or
cross-origin configuration.

### 4.7 `frontend/README.md`

The frontend README explains:

- The separation between HTML, CSS, and JavaScript.
- How to start FastAPI and Vite in separate terminals.
- Why the relative health path works in development and production.
- How to produce a frontend build.
- Which values are demonstrations and which request is real.

The root README remains the product entry point; this file is a focused
frontend operating note.

### 4.8 `frontend/public/og.png`

The Open Graph image supports link previews for the prototype. Vite copies
public assets into the production output.

It is presentational and is not required for backend or RAG behaviour.

### 4.9 `src/european_heritage_rag/api/main.py`

The existing FastAPI application factory gained an injectable
`frontend_directory` parameter.

After registering the health routes, it checks whether that directory exists.
When present, it mounts:

```python
StaticFiles(directory=frontend_directory, html=True)
```

at `/`.

Injecting the path creates a clean test boundary. Tests can use temporary
assets without requiring an actual Vite build, while normal runtime uses
`frontend/dist`.

The conditional mount also keeps backend development independent of frontend
build state.

### 4.10 `tests/api/test_frontend.py`

The frontend-delivery tests use a temporary directory containing a small HTML
file and JavaScript asset.

They prove that:

- `/` serves HTML.
- A nested asset is served.
- `/health/ready` remains reachable after the root mount.
- Missing frontend assets do not prevent FastAPI from starting.
- Health routes remain available without a frontend build.

The tests do not run Vite and do not depend on `frontend/dist`.

### 4.11 `Dockerfile`

The Dockerfile now builds both application halves.

The frontend stage:

1. Uses Node.
2. Installs the pinned pnpm version.
3. Installs dependencies from the lockfile.
4. Runs `pnpm build`.

The runtime stage:

1. Uses Python 3.12.
2. Installs the backend from `uv.lock`.
3. Copies the generated frontend assets.
4. Runs as an unprivileged user.
5. Starts Uvicorn on port `8000`.

Only runtime requirements and built static assets reach the final stage.

### 4.12 `compose.yaml`

Compose continues to describe one service. The Phase 3 image:

- Builds from the root Dockerfile.
- Uses production logging and environment settings.
- Publishes port `8000`.
- Reports health through `/health/ready`.

There is no production Vite service, reverse proxy, database, or search engine
in this phase.

### 4.13 Ignore files

`.gitignore` excludes frontend dependencies and build output.

`.dockerignore` excludes local environments, caches, tests, documentation,
frontend dependencies, and previously generated frontend output from the
Docker build context. The container creates a fresh production build instead
of copying a developer's local `dist` directory.

## 5. API and state boundaries

### Real backend state

The only real frontend API request is:

```http
GET /health/ready
```

The response contains service identity, version, status, and readiness checks.

### Demonstration state

The following remain demonstrations:

- Ingestion work and page counts.
- Pipeline progress.
- Recent ingestion events.
- Catalogue records and OCR passages.
- Retrieval state.
- Evaluation results.
- Chat responses.

The interface labels them accordingly. Later phases replace each boundary
incrementally.

### Same-origin rule

Frontend requests use relative API paths. This preserves one browser contract
across:

- Vite development with a proxy.
- Local FastAPI static delivery.
- Docker Compose delivery.

## 6. Operational commands

Install locked frontend dependencies:

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

After building, serve the combined application:

```powershell
uv run uvicorn european_heritage_rag.api.main:app
```

Build and run the container application:

```powershell
docker compose build
docker compose up --detach --wait
```

Stop it:

```powershell
docker compose down
```

## 7. Verification

The Phase 3 closure checkpoint was repeated on 2026-07-22.

| Command or check | Property proved | Result |
|---|---|---|
| `uv sync --locked` | Backend dependencies reproduce from the lockfile | Passed |
| `uv run pytest` | Backend, configuration, CLI, logging, health, and frontend-delivery behaviour | 16 tests passed |
| `uv run ruff check .` | Python lint rules | Passed |
| `uv run ruff format --check .` | Python formatting | Passed |
| `uv run mypy src` | Strict backend type checking | Passed |
| `pnpm --dir frontend install --frozen-lockfile` | Frontend dependencies reproduce without lockfile drift | Passed |
| `pnpm --dir frontend build` | Vite production bundle | Passed |
| `docker compose build` | Multi-stage application image | Passed |
| `docker compose up --detach --wait` | Container startup and readiness health check | Passed |
| `GET /health/ready` | Combined runtime preserves the readiness API | HTTP 200 with `status=ok` |
| `GET /` | Combined runtime serves the frontend | HTTP 200 |
| `git diff --check` | No whitespace errors in the working diff | Passed |

Desktop and mobile interactions were also checked while the Phase 3 prototype
was built. Automated browser interaction tests remain deferred.

## 8. Review summary

Phase 3 is ready to keep as the visual and delivery foundation for ingestion.

Stable boundaries:

- Relative same-origin API paths.
- Vite as the frontend build boundary.
- FastAPI health routes registered before the root frontend mount.
- An injectable frontend directory for backend tests.
- One combined runtime image and one Compose service.
- Explicit separation between real and demonstration data.

Known limitations:

- The browser code is not statically typed.
- Large frontend files may become difficult to maintain as real features grow.
- There are no automated frontend unit or browser tests.
- The production-style local workflow requires a frontend build.
- FastAPI static delivery does not provide CDN caching or compression.
- The UI contains no real ingestion, retrieval, evaluation, or chat data yet.

Revisit the browser-native decision when real ingestion or chat state creates
repeated component boundaries, complex shared state, or enough API contracts
to justify React and TypeScript.

Phase 4 should replace only the ingestion dashboard's demonstration boundary
with real file-backed progress. It should not redesign the entire frontend.

## 9. Official references

- [Vite guide](https://vite.dev/guide/)
- [Vite production builds](https://vite.dev/guide/build)
- [Vite static assets](https://vite.dev/guide/assets.html)
- [pnpm install](https://pnpm.io/cli/install)
- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/)
- [Docker multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Compose services](https://docs.docker.com/reference/compose-file/services/)
