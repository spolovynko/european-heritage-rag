# Phase 2 build review

## Environment and repository setup

| Item | Value |
|---|---|
| Reviewed | 2026-07-21 |
| Result | Tested Python API baseline that runs locally and in Docker |
| Not included | RAG, ingestion, databases, or frontend |

This guide reviews the Phase 2 implementation. The
[Phase 2 plan](../building_phases/phase-02-environment-and-repository-setup.md)
contains the original objective and exit criteria.

## Frameworks and tools

| Technology | Why it is used |
|---|---|
| Python 3.12 | Runtime, typing, `StrEnum`, and modern language features |
| FastAPI | API routing, dependency injection, response validation, and OpenAPI |
| Uvicorn | Runs the FastAPI ASGI application |
| Pydantic | Defines and validates API response contracts |
| Pydantic Settings | Loads typed settings from environment variables and `.env` |
| Structlog | Creates structured log events and JSON production output |
| Python `logging` | Handles levels, stdout, root logging, and library integration |
| Typer | Provides the command-line interface and generated help |
| pytest | Runs behavior-focused automated tests |
| `httpx2` | Provides the transport used by FastAPI's test client |
| Ruff | Lints, sorts imports, and formats Python code |
| mypy | Strictly type-checks application source |
| `uv` | Manages Python, dependencies, locking, syncing, and command execution |
| Docker | Builds a reproducible API image |
| Docker Compose | Configures and runs the local API container |

## Application Python files

### `src/european_heritage_rag/__init__.py`

Marks `european_heritage_rag` as the main package and contains only the package
docstring. Executable CLI code is kept in `cli.py`.

### `src/european_heritage_rag/api/__init__.py`

Marks `api` as the HTTP adapter package. It is intentionally empty.

### `src/european_heritage_rag/api/contracts.py`

Uses Pydantic to define the public response shapes.

| Class | Explanation |
|---|---|
| `HealthResponse` | Returns `status`, service name, and installed version. `status` is restricted to `"ok"`. |
| `ReadinessResponse` | Extends `HealthResponse` with named readiness checks. |

Keeping contracts outside route code makes the API schema explicit and reusable.

### `src/european_heritage_rag/api/main.py`

Uses FastAPI to construct the API and Uvicorn to run the exported `app`.

| Function | Explanation |
|---|---|
| `get_liveness()` | Returns a typed response confirming that the API process is alive. It deliberately checks no external service. |
| `get_readiness(_settings)` | Uses FastAPI dependency injection to resolve settings, then reports the current configuration check as ready. |
| `lifespan()` | Configures logging and emits `application_started` before serving requests; emits `application_stopped` during shutdown. |
| `create_app()` | Creates FastAPI, attaches the lifespan, registers both health routes, and returns the application. |

Important module values:

| Value | Explanation |
|---|---|
| `_APPLICATION_VERSION` | Reads the version from installed package metadata, avoiding a second version constant. |
| `logger` | Named structured logger for application lifecycle events. |
| `app` | Module-level application imported by Uvicorn as `european_heritage_rag.api.main:app`. |

Current limitation: readiness proves configuration loading only. Later phases
should add checks when an index or database becomes required.

### `src/european_heritage_rag/core/__init__.py`

Marks `core` as the package for shared application infrastructure. It is
intentionally empty.

### `src/european_heritage_rag/core/config.py`

Uses Pydantic Settings for validated configuration and `lru_cache` for
process-wide reuse.

| Class or function | Explanation |
|---|---|
| `AppEnvironment` | Allows only `local`, `test`, and `production`. |
| `LogLevel` | Allows only supported Python logging levels. |
| `AppSettings` | Loads `APP_ENV` and `LOG_LEVEL`, applies safe defaults, ignores extra `.env` entries, and prevents mutation. |
| `get_settings()` | Creates settings on the first call and returns the cached instance afterward. |

`get_settings()` provides singleton-like behavior without a custom Singleton
class. Tests can call `get_settings.cache_clear()` when they need a fresh
environment read.

Current settings:

| Field | Environment variable | Default |
|---|---|---|
| `app_env` | `APP_ENV` | `local` |
| `log_level` | `LOG_LEVEL` | `INFO` |

### `src/european_heritage_rag/core/logging.py`

Uses Structlog for structured events and Python `logging` for handlers, levels,
and compatibility with Uvicorn and other libraries.

| Function | Explanation |
|---|---|
| `configure_logging(settings)` | Builds the processor chain, chooses console or JSON rendering, configures stdout, sets the root level, and connects Structlog to standard logging. |
| `get_logger(name, **initial_context)` | Returns a named structured logger with optional bound context. |

The shared processor chain adds context variables, logger name, level, UTC
timestamp, stack information, and formatted exceptions.

| Environment | Output |
|---|---|
| `local` or `test` | Readable console events |
| `production` | JSON events |

`configure_logging()` clears existing root handlers, so it belongs at the
application boundary. Phase 2 calls it from the FastAPI lifespan.

### `src/european_heritage_rag/cli.py`

Uses Typer to keep terminal interaction separate from the HTTP API.

| Function | Explanation |
|---|---|
| `cli()` | Root callback that keeps Typer in command-group mode. |
| `show_version()` | Implements `european-heritage-rag version` using installed package metadata. |
| `main()` | Starts the Typer application and acts as the console-script entry point. |

Future CLI functions should parse terminal input and delegate to application
services rather than implement retrieval or ingestion directly.

## Test Python files

### `tests/api/test_health.py`

| Fixture or test | Explanation |
|---|---|
| `client()` | Creates `TestClient` as a context manager so FastAPI startup and shutdown run. |
| `test_liveness_returns_expected_response()` | Verifies the liveness status, content type, and full response contract. |
| `test_readiness_returns_configuration_check()` | Verifies the readiness status and configuration check. |
| `test_application_logs_lifecycle_events()` | Replaces the logger with a mock and verifies startup and shutdown event order. |

### `tests/cli/test_cli.py`

| Test | Explanation |
|---|---|
| `test_version_command_prints_installed_version()` | Verifies successful dispatch and exact version output. |
| `test_help_lists_available_commands()` | Verifies help output and command discovery. |

### `tests/config/test_config.py`

| Test | Explanation |
|---|---|
| `test_settings_use_safe_defaults()` | Verifies local environment and INFO logging defaults. |
| `test_environment_variables_override_defaults()` | Verifies environment values replace defaults. |
| `test_invalid_environment_is_rejected()` | Verifies unsupported environments fail validation. |
| `test_settings_provider_reuses_single_instance()` | Verifies the cached provider returns the same object. |
| `test_settings_cannot_be_modified_after_creation()` | Verifies settings are frozen. |

### `tests/logging/test_logging.py`

| Fixture or test | Explanation |
|---|---|
| `restore_logging_state()` | Preserves and restores global logging state around each test. |
| `test_local_logging_uses_readable_structured_output()` | Verifies local console rendering and structured fields. |
| `test_production_logging_uses_json_output()` | Verifies production JSON and parseable fields. |
| `test_logging_filters_events_below_configured_level()` | Verifies root-level filtering. |
| `test_standard_library_logs_use_configured_renderer()` | Verifies built-in logging uses the shared pipeline. |

Test directories have no `__init__.py`. In particular, a package named
`tests/logging` would otherwise risk shadowing Python's built-in `logging`
module during test collection.

## `uv` management review

| File | Responsibility |
|---|---|
| `.python-version` | Selects Python 3.12 locally. |
| `pyproject.toml` | Declares the project, direct dependencies, dev group, CLI entry point, build backend, and tool settings. |
| `uv.lock` | Records the complete resolved dependency graph. |

Runtime libraries belong in `[project].dependencies`. pytest, Ruff, mypy, and
`httpx2` belong in the development dependency group because the running API
does not need them.

| Command | Purpose |
|---|---|
| `uv add <package>` | Add a runtime dependency and update the lock. |
| `uv add --dev <package>` | Add a development dependency and update the lock. |
| `uv lock --check` | Verify that the lock matches `pyproject.toml`. |
| `uv sync --locked` | Reproduce the locked local environment. |
| `uv run --locked <command>` | Run inside the managed environment without changing a stale lock. |

Commit `pyproject.toml` and `uv.lock` together after dependency changes. Do not
edit resolved dependencies in `uv.lock` manually.

`uv_build` is the Python package build backend. It is separate from the `uv`
executable installed locally or copied into Docker.

## Docker review

`Dockerfile` defines how the API image is built.

| Step | Purpose |
|---|---|
| Python 3.12 slim base | Provides the Linux Python runtime. |
| Pinned `uv` copy | Adds `uv` without an installer script. |
| Copy lock and project files first | Allows Docker to reuse the dependency layer. |
| `uv sync --locked --no-dev` | Installs exact runtime dependencies only. |
| Copy `src` and sync non-editably | Installs the application as a deployment artifact. |
| Add `.venv/bin` to `PATH` | Makes Uvicorn directly executable. |
| Switch to `appuser` | Prevents the server from running as root. |
| Exec-form `CMD` | Starts Uvicorn and receives container signals correctly. |

`.dockerignore` excludes the host virtual environment, Git data, caches, local
`.env`, tests, and documentation from the build context.

Current trade-offs: image tags are not pinned by immutable digest, `uv` remains
in the runtime image, and `phase2` is a milestone tag rather than a release
tagging strategy.

## Docker Compose review

`compose.yaml` defines how the image runs locally.

| Setting | Purpose |
|---|---|
| `build` | Uses the repository root and root Dockerfile. |
| `image` | Names the local image `european-heritage-rag:phase2`. |
| `environment` | Selects production JSON logging at INFO level. |
| `ports` | Publishes container port 8000 on localhost port 8000. |
| `healthcheck` | Calls `/health/ready` inside the container. |

Compose intentionally contains only the API. Databases and volumes should be
added only when application code needs them.

| Command | Purpose |
|---|---|
| `docker compose config --quiet` | Validate the resolved Compose configuration. |
| `docker compose up --build --detach` | Build and start the API in the background. |
| `docker compose ps` | Inspect container and health state. |
| `docker compose logs api` | Read API output. |
| `docker compose down` | Remove the Compose container and network. |

## Verification

```powershell
uv lock --check
uv sync --locked
uv run --locked pytest -v
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
docker compose config --quiet
docker compose up --build --detach
docker compose ps
docker compose down
git diff --check
```

## Official references

- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI dependency injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Pydantic settings](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)
- [Structlog and standard logging](https://www.structlog.org/en/stable/standard-library.html)
- [`uv` locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [`uv` in Docker](https://docs.astral.sh/uv/guides/integration/docker/)
- [Dockerfile reference](https://docs.docker.com/reference/dockerfile/)
- [Docker Compose services](https://docs.docker.com/reference/compose-file/services/)
