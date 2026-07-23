# Phase 2 build review

## Environment and repository setup

| Item | Value |
|---|---|
| Reviewed | 2026-07-21 |
| Result | A tested Python API that runs locally and in Docker |
| Not included | RAG, ingestion, databases, or a frontend |

This guide explains what we built in Phase 2, why each part exists, and how the
parts work together. The
[Phase 2 plan](../building_phases/phase-02-environment-and-repository-setup.md)
contains the original goal and completion rules.

The simple result is: Phase 2 gave the project a reliable foundation. It can
load configuration, produce logs, expose health endpoints, run a CLI command,
execute automated checks, and start inside Docker.

## Frameworks and tools

| Technology | What it does here |
|---|---|
| Python 3.12 | Runs the backend code and provides modern typing features |
| FastAPI | Defines HTTP endpoints and checks their response shapes |
| Uvicorn | Starts the FastAPI web server |
| Pydantic | Describes and validates structured Python data |
| Pydantic Settings | Reads configuration from environment variables and `.env` |
| Structlog | Produces logs with named fields instead of unstructured sentences |
| Python `logging` | Controls log levels and connects library logs to Structlog |
| Typer | Creates the terminal command and its help screen |
| pytest | Runs automated behavior checks |
| `httpx2` | Supplies the HTTP transport used by FastAPI's test client |
| Ruff | Finds common Python problems and checks formatting |
| mypy | Checks that Python values match their declared types |
| `uv` | Manages Python, dependencies, the lockfile, and project commands |
| Docker | Builds one repeatable application image |
| Docker Compose | Starts and checks that image locally |

These tools have separate jobs. For example, FastAPI defines the API, Uvicorn
runs it, and Pydantic checks the data that the API returns.

## Application Python files

### `src/european_heritage_rag/__init__.py`

What: this file marks `european_heritage_rag` as the main Python package.

Why: Python needs a clear package boundary. The file contains no executable
logic, so importing the package does not accidentally start the application.

How: runnable CLI code lives in `cli.py`, and HTTP code lives in `api/`.

### `src/european_heritage_rag/api/__init__.py`

What: this file marks `api` as the package that handles HTTP requests.

Why: it gives API code a clear home without putting behavior in the package
initializer.

### `src/european_heritage_rag/api/contracts.py`

What: this file defines the exact JSON shapes returned by the health endpoints.

| Class | Plain-language meaning |
|---|---|
| `HealthResponse` | Returns `status`, service name, and installed version. The status can only be `"ok"`. |
| `ReadinessResponse` | Returns the same fields plus named readiness checks. |

Why: an exact response shape makes the API predictable. If route code returns the
wrong type or leaves out a required field, validation exposes the mistake.

How: FastAPI uses these Pydantic classes both to validate responses and to
describe them in the generated OpenAPI documentation.

### `src/european_heritage_rag/api/main.py`

What: this is the main HTTP application module.

| Function | What it does |
|---|---|
| `get_liveness()` | Confirms that the Python process is running. It does not check external services. |
| `get_readiness(_settings)` | Confirms that the application can load its current configuration. |
| `lifespan()` | Configures logging at startup and records startup/shutdown events. |
| `create_app()` | Creates FastAPI, attaches startup behavior, and registers the health routes. |

Important module values:

| Value | Why it exists |
|---|---|
| `_APPLICATION_VERSION` | Reads the installed package version so we do not maintain a second version string. |
| `logger` | Gives this module a named structured logger. |
| `app` | Gives Uvicorn the application object it must run. |

How a request works:

```text
Browser or test
      |
      | GET /health/ready
      v
FastAPI route
      |
      | loads settings
      v
ReadinessResponse -> JSON response
```

Current limitation: readiness only proves that configuration can be loaded.
Later phases should add database or index checks when those services exist.

### `src/european_heritage_rag/core/__init__.py`

What: this marks `core` as the package for shared application setup.

Why: configuration and logging are needed by several entry points, so they do
not belong only to the HTTP API or only to the CLI.

### `src/european_heritage_rag/core/config.py`

What: this file defines all Phase 2 configuration and validates it when the
application starts.

| Class or function | What it does |
|---|---|
| `AppEnvironment` | Allows only `local`, `test`, and `production`. |
| `LogLevel` | Allows only supported Python log levels. |
| `AppSettings` | Reads settings, supplies defaults, ignores unrelated `.env` values, and prevents later changes. |
| `get_settings()` | Creates settings once and reuses the same object. |

Why: configuration should be changed outside the code. A developer can use a
`.env` file, while a container or deployment system can use environment
variables.

How reuse works: `lru_cache` stores the first `AppSettings` object. Later calls
return that object instead of repeatedly reading the environment. Tests call
`get_settings.cache_clear()` when they need a fresh configuration.

Current settings:

| Python field | Environment variable | Default |
|---|---|---|
| `app_env` | `APP_ENV` | `local` |
| `log_level` | `LOG_LEVEL` | `INFO` |

### `src/european_heritage_rag/core/logging.py`

What: this file creates one logging setup for our code, Uvicorn, and other
Python libraries.

| Function | What it does |
|---|---|
| `configure_logging(settings)` | Chooses the output format, sends logs to stdout, and applies the configured level. |
| `get_logger(name, **initial_context)` | Returns a logger with a name and optional fields that should appear in every event. |

Why: logs should be easy for people to read locally and easy for software to
process in production.

| Environment | Output |
|---|---|
| `local` or `test` | Readable console lines |
| `production` | One JSON object per event |

How: a shared processing chain adds the logger name, level, UTC time, context,
stack data, and formatted errors. `configure_logging()` replaces existing root
handlers, so it is called once at the application boundary.

### `src/european_heritage_rag/cli.py`

What: this file provides terminal commands separately from HTTP routes.

| Function | What it does |
|---|---|
| `cli()` | Keeps Typer in command-group mode. |
| `show_version()` | Implements `european-heritage-rag version`. |
| `main()` | Starts the Typer application. |

Why: developers and operators need a direct way to run project tasks without
going through a browser or writing an HTTP request.

How: `pyproject.toml` maps the command name `european-heritage-rag` to
`cli.main`. Future commands should read terminal options and call application
services; the CLI file itself should not contain ingestion or retrieval logic.

## Test Python files

The tests check behavior from the outside. They do not depend on a manually
running server.

### `tests/api/test_health.py`

| Fixture or test | What it proves |
|---|---|
| `client()` | Runs FastAPI startup and shutdown around each API test. |
| `test_liveness_returns_expected_response()` | The liveness endpoint returns the expected status, content type, and fields. |
| `test_readiness_returns_configuration_check()` | The readiness endpoint includes its configuration check. |
| `test_application_logs_lifecycle_events()` | Startup is logged before shutdown. |

### `tests/cli/test_cli.py`

| Test | What it proves |
|---|---|
| `test_version_command_prints_installed_version()` | The version command runs and prints the installed version. |
| `test_help_lists_available_commands()` | The help page can find and list the commands. |

### `tests/config/test_config.py`

| Test | What it proves |
|---|---|
| `test_settings_use_safe_defaults()` | Local and INFO are used when nothing overrides them. |
| `test_environment_variables_override_defaults()` | Environment variables replace defaults. |
| `test_invalid_environment_is_rejected()` | Unsupported environment names fail validation. |
| `test_settings_provider_reuses_single_instance()` | The settings provider reuses one object. |
| `test_settings_cannot_be_modified_after_creation()` | Runtime code cannot silently change settings. |

### `tests/logging/test_logging.py`

| Fixture or test | What it proves |
|---|---|
| `restore_logging_state()` | A test cannot leave global logging changed for the next test. |
| `test_local_logging_uses_readable_structured_output()` | Local logs are readable and still contain named fields. |
| `test_production_logging_uses_json_output()` | Production logs are valid JSON with the expected data. |
| `test_logging_filters_events_below_configured_level()` | Events below the chosen level are hidden. |
| `test_standard_library_logs_use_configured_renderer()` | Logs from normal Python libraries use the same output pipeline. |

The test folders do not contain `__init__.py`. This avoids creating a test
package named `logging`, which could hide Python's built-in `logging` module.

## `uv` management review

`uv` keeps Python and dependency setup repeatable.

| File | What it controls |
|---|---|
| `.python-version` | Chooses Python 3.12 for this repository. |
| `pyproject.toml` | Lists project information, direct dependencies, development tools, the CLI entry point, and tool settings. |
| `uv.lock` | Records the exact resolved dependency versions. |

Why both files matter: `pyproject.toml` says what the project directly needs.
`uv.lock` records the complete version set that was proven to work. Commit them
together after changing dependencies.

| Command | What to use it for |
|---|---|
| `uv add <package>` | Add a library needed while the application runs. |
| `uv add --dev <package>` | Add a library used only for development or tests. |
| `uv lock --check` | Confirm that the lockfile matches `pyproject.toml`. |
| `uv sync --locked` | Recreate the environment without changing the lockfile. |
| `uv run --locked <command>` | Run a command inside that locked environment. |

Do not edit resolved package entries in `uv.lock` by hand. `uv_build` is the
package-building backend; it is different from the `uv` terminal program.

## Docker review

Docker packages the application and its runtime into one image.

| Dockerfile step | Why we do it |
|---|---|
| Start from Python 3.12 slim | Use the required Python version without a large base image. |
| Copy a pinned `uv` executable | Install dependencies without downloading an installer script. |
| Copy dependency files first | Let Docker reuse the slow dependency layer when only source code changes. |
| Run `uv sync --locked --no-dev` | Install exact runtime packages but not test tools. |
| Copy and install `src` non-editably | Package the application as it will run in deployment. |
| Add `.venv/bin` to `PATH` | Allow the container to call Uvicorn directly. |
| Switch to `appuser` | Avoid running the web server with root privileges. |
| Use an exec-form `CMD` | Let Uvicorn receive stop signals correctly. |

`.dockerignore` keeps local environments, Git data, caches, `.env`, tests, and
documentation out of the build context.

Accepted Phase 2 limits: base images are not pinned by an exact unchanging digest,
`uv` remains in the final image, and `phase2` is a milestone name rather than a
long-term release-tag policy.

## Docker Compose review

Compose describes how to run the image locally.

| Setting | What it means |
|---|---|
| `build` | Build from this repository's root Dockerfile. |
| `image` | Name the local image `european-heritage-rag:phase2`. |
| `environment` | Use production JSON logs at INFO level. |
| `ports` | Make container port 8000 available at local port 8000. |
| `healthcheck` | Ask `/health/ready` whether the container is ready. |

Phase 2 intentionally has one API service. A database or volume should be
added only when application code actually needs it.

| Command | What it does |
|---|---|
| `docker compose config --quiet` | Checks that the Compose file is valid. |
| `docker compose up --build --detach` | Builds and starts the API in the background. |
| `docker compose ps` | Shows the running and health state. |
| `docker compose logs api` | Shows API logs. |
| `docker compose down` | Removes the container and its network. |

## Verification

Run these commands from the repository root:

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

What this proves:

- dependency files agree and can recreate the environment;
- application behavior passes its automated tests;
- Python style and type checks pass;
- the container can build, start, and report healthy; and
- the Git changes do not contain whitespace mistakes.

## Official references

- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI dependency injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Pydantic settings](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)
- [Structlog and standard logging](https://www.structlog.org/en/stable/standard-library.html)
- [`uv` locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [`uv` in Docker](https://docs.astral.sh/uv/guides/integration/docker/)
- [Dockerfile reference](https://docs.docker.com/reference/dockerfile/)
- [Docker Compose services](https://docs.docker.com/reference/compose-file/services/)
