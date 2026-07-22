FROM node:24-alpine AS frontend-builder

WORKDIR /frontend

RUN npm install --global pnpm@11.15.1

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.30 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1

WORKDIR /app

COPY --from=frontend-builder /frontend/dist ./frontend/dist

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/var/ingestion \
    && chown -R appuser:appuser /app/var
USER appuser

EXPOSE 8000

CMD ["uvicorn", "european_heritage_rag.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
