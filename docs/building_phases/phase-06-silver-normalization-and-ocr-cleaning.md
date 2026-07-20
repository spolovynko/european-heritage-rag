# Phase 6 — Silver normalization and OCR cleaning

## Objective

Transform heterogeneous raw records into validated canonical works and pages while preserving the original OCR and complete provenance.

## What we will learn

- Canonical data modelling.
- Schema validation.
- OCR-cleaning trade-offs.
- Data-quality reporting.
- Columnar storage with Parquet.
- Why normalization must not destroy source information.

## Development steps

1. Add Polars and PyArrow.
2. Define canonical `Work` and `Page` models.
3. Create `works.parquet` with fields such as:
   - `work_id`
   - `title`
   - `contributors`
   - `production_date`
   - `subjects`
   - `genres`
   - `language`
   - `license`
   - `source_url`
   - `iiif_manifest_url`
   - `source_content_hash`
4. Create `pages.parquet` with fields such as:
   - `work_id`
   - `page_id`
   - `page_number`
   - `sequence_number`
   - `raw_text`
   - `clean_text`
   - `ocr_quality`
   - `image_url`
   - `annotation_url`
5. Implement small pure cleaning functions:
   - Unicode normalization.
   - HTML removal.
   - Whitespace normalization.
   - OCR-line joining.
   - Conservative dehyphenation.
   - Empty-page detection.
6. Detect repeated headers and footers across pages of the same work.
7. Preserve `raw_text`; never replace it with cleaned text.
8. Add quality flags rather than silently discarding suspicious pages.
9. Produce a machine-readable and human-readable quality report.
10. Run first on five works, then on 20–25 works to discover anomalies.

## UI work

Create a side-by-side page inspector:

- Page image.
- Raw OCR.
- Cleaned text.
- Detected header/footer.
- Quality flags.
- Work metadata.

Add aggregate charts or simple counters for empty pages, average words per page, languages, and processing failures.

## Tests

- Unicode normalization.
- Hyphenated line joining.
- Paragraph preservation.
- Repeated header detection.
- Empty page.
- Invalid or missing metadata.
- Exact Bronze-to-Silver lineage.

## Exit criteria

- Silver datasets are valid Parquet files.
- Every Silver row links to its Bronze source.
- Raw and cleaned OCR can be compared.
- Cleaning quality is visible rather than assumed.
- Transformation is deterministic.

## Required ADR

`ADR-0006: Canonical work/page schemas and conservative OCR cleaning`

Decision questions:

- Why separate works and pages?
- Why store raw and cleaned text?
- Why Parquet?
- Which OCR corrections are safe to automate?

---
