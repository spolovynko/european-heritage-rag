# Phase 4 — Wellcome discovery and ingestion client

## Objective

Build a small, resilient client that discovers digitised public-domain Wellcome works and retrieves catalogue records, IIIF manifests, and OCR annotations.

## What we will learn

- REST pagination.
- HTTP timeouts and retries.
- IIIF Presentation manifests.
- Per-page OCR annotations.
- Rate-conscious ingestion.
- Checkpointing and resumable work.

## Development steps

1. Add HTTPX, Tenacity, and respx.
2. Create typed source models for only the fields currently needed.
3. Implement a Wellcome client with:
   - Configurable base URL.
   - Timeouts.
   - Retry policy.
   - User-Agent.
   - Pagination.
4. Implement work discovery using:
   - `workType=a`
   - `availabilities=online`
   - `items.locations.license=pdm`
5. Extract each work's IIIF Presentation URL.
6. Retrieve the IIIF manifest.
7. Traverse canvases in sequence order.
8. Extract OCR annotation-list URLs from page canvases.
9. Retrieve OCR annotations and reconstruct page lines.
10. Add an ingestion CLI:
    - `--limit`
    - `--query`
    - `--language`
    - `--resume`
    - `--dry-run`
11. Begin with one known work fixture.
12. Run a five-work live smoke test.

## UI work

Replace ingestion mock data with a small in-memory or file-backed job status endpoint. Initially use polling every few seconds. Show:

- Current work.
- Works discovered.
- Works completed.
- Pages downloaded.
- Retry and failure counts.
- Recent ingestion events.

Streaming progress can replace polling later when the behaviour is stable.

## Tests

- Pagination across two mocked pages.
- Retry after a transient error.
- No retry for a permanent invalid request.
- Manifest with OCR annotations.
- Manifest without OCR annotations.
- Work with no public-domain digital location.

## Exit criteria

- Five works can be discovered and traversed.
- The client handles missing OCR without crashing.
- An interrupted run can identify where it stopped.
- Tests do not call the live API.
- The UI shows real ingestion progress.

## Required ADR

`ADR-0004: Wellcome API and IIIF ingestion strategy`

Decision questions:

- Why use the API rather than scraping?
- Why start with API harvesting rather than the daily snapshot?
- Why filter to public-domain online books?
- Why bound concurrency?

---
