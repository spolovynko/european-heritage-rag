# Phase 15 — Observability, CI/CD, and production deployment

## Objective

Make the system deployable, diagnosable, recoverable, and version-aware without changing the understandable local development experience.

## What we will learn

- Container builds.
- CI/CD gates.
- Logs, metrics, and traces.
- Production configuration.
- Data and index version rollouts.
- Scheduled ingestion.
- Backups and recovery.
- Cost and latency monitoring.

## Development steps

1. Add production Dockerfiles for the root Python backend and the `frontend/` application.
2. Run containers as non-root users.
3. Add liveness and readiness health checks.
4. Configure production settings through environment variables or a secret manager.
5. Add structured logs with request, conversation, retrieval, and ingestion trace IDs.
6. Instrument:
   - HTTP calls.
   - Retrieval stages.
   - Reranking.
   - LLM calls.
   - Database queries.
7. Track operational metrics:
   - Ingestion success rate.
   - Empty OCR rate.
   - Indexed chunks.
   - Search latency.
   - Reranker latency.
   - Answer latency.
   - Zero-result rate.
   - Abstention rate.
   - Citation coverage.
   - LLM tokens and cost.
8. Create GitHub Actions for:
   - Dependency lock validation.
   - Linting.
   - Type checking.
   - Unit and integration tests.
   - Retrieval regression fixture.
   - Frontend type check and build.
   - Container builds.
9. Move large Bronze, Silver, and Gold artefacts to object storage in production.
10. Use persistent or managed Qdrant and PostgreSQL.
11. Introduce index aliases or equivalent version switching.
12. Validate a new index before switching traffic.
13. Schedule incremental ingestion.
14. Define backup and restore procedures.
15. Perform a basic load test.
16. Write a deployment runbook.

## UI work

Add an operations view restricted to appropriate users:

- Service status.
- Active versions.
- Recent ingestion/indexing runs.
- Error rates.
- Latency.
- Retrieval and answer usage.

## Exit criteria

- A clean deployment can be produced from committed code and configuration.
- CI blocks known regressions.
- Active data and model versions are visible.
- Backup and rollback procedures are documented and tested at least once.
- A public demo has rate limits and safe secret handling.

## Required ADR

`ADR-0015: Deployment topology, observability, and versioned index rollout`

Decision questions:

- Which services run separately in production?
- Where are raw data, Qdrant, and PostgreSQL hosted?
- How is a new index released and rolled back?
- Which signals are required to diagnose a bad answer?

---
