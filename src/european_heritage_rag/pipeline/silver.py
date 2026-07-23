"""Offline Bronze-to-Silver transformation and quality reporting."""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from statistics import fmean
from typing import Final, Literal

from pydantic import AnyHttpUrl

from european_heritage_rag.domain.silver import (
    OcrQualityBand,
    PageQualityFlag,
    SilverContributor,
    SilverLineage,
    SilverPage,
    SilverQualityReport,
    SilverWork,
    WorkQualityFlag,
    WorkQualitySummary,
)
from european_heritage_rag.pipeline.bronze import (
    BronzeResourceRecord,
    BronzeResourceType,
    BronzeRunManifest,
    BronzeRunStatus,
)
from european_heritage_rag.pipeline.bronze_store import BronzeFilesystemStore
from european_heritage_rag.pipeline.bronze_validation import validate_bronze_run
from european_heritage_rag.pipeline.header_footer import detect_repeated_boundaries
from european_heritage_rag.pipeline.ocr_cleaning import (
    OcrLine,
    clean_ocr_lines,
    cleaning_change_ratio,
    parse_ocr_line,
    raw_text_from,
    symbol_ratio,
    word_count,
)
from european_heritage_rag.sources.wellcome.client import manifest_url_for
from european_heritage_rag.sources.wellcome.models import (
    CatalogueWork,
    IiifCanvas,
    IiifManifest,
    OcrAnnotationList,
)

SILVER_SCHEMA_VERSION: Final[Literal[1]] = 1
CLEANING_VERSION = "ocr-cleaning-v1"
HEADER_FOOTER_VERSION = "repeated-boundaries-v1"
QUALITY_VERSION = "quality-rules-v1"


class SilverTransformError(RuntimeError):
    """Raised when validated Bronze cannot be mapped without losing lineage."""


@dataclass(frozen=True, slots=True)
class SilverTransformResult:
    """Canonical rows and quality evidence before persistence."""

    dataset_id: str
    bronze_run_id: str
    bronze_inventory_sha256: str
    works: tuple[SilverWork, ...]
    pages: tuple[SilverPage, ...]
    quality_report: SilverQualityReport


@dataclass(frozen=True, slots=True)
class _PageInput:
    """One canvas and its source OCR before work-level cleaning."""

    work_id: str
    canvas: IiifCanvas
    sequence_number: int
    lines: tuple[OcrLine, ...]
    annotation_records: tuple[BronzeResourceRecord, ...]
    annotation_urls: tuple[AnyHttpUrl, ...]
    non_text_annotation_count: int


def bronze_inventory_sha256(manifest: BronzeRunManifest) -> str:
    """Fingerprint immutable resource inventory and source-defining parameters."""

    payload = {
        "identity": manifest.identity.model_dump(mode="json"),
        "parameters": manifest.parameters.model_dump(mode="json"),
        "completed_work_ids": sorted(manifest.completed_work_ids),
        "resources": sorted(
            (
                resource.resource_id,
                resource.relative_path,
                resource.content_sha256,
            )
            for resource in manifest.resources
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode()).hexdigest()


def silver_dataset_id(
    manifest: BronzeRunManifest,
    *,
    inventory_sha256: str | None = None,
) -> str:
    """Return stable identity for input inventory and transformation versions."""

    inventory = inventory_sha256 or bronze_inventory_sha256(manifest)
    payload = {
        "bronze_run_id": manifest.identity.run_id,
        "bronze_inventory_sha256": inventory,
        "silver_schema_version": SILVER_SCHEMA_VERSION,
        "cleaning_version": CLEANING_VERSION,
        "header_footer_version": HEADER_FOOTER_VERSION,
        "quality_version": QUALITY_VERSION,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode()).hexdigest()


def transform_bronze_run(
    store: BronzeFilesystemStore,
    manifest: BronzeRunManifest,
) -> SilverTransformResult:
    """Transform one complete, valid Bronze run entirely offline."""

    if manifest.status is not BronzeRunStatus.COMPLETED:
        raise SilverTransformError("Silver requires a completed Bronze run")

    validation = validate_bronze_run(store, manifest)
    if not validation.is_valid:
        codes = ", ".join(issue.code for issue in validation.issues)
        raise SilverTransformError(f"Bronze validation failed: {codes}")

    inventory_sha256 = bronze_inventory_sha256(manifest)
    dataset_id = silver_dataset_id(
        manifest,
        inventory_sha256=inventory_sha256,
    )
    resources_by_work: dict[str, list[BronzeResourceRecord]] = defaultdict(list)
    for resource in manifest.resources:
        resources_by_work[resource.work_id].append(resource)

    works: list[SilverWork] = []
    pages: list[SilverPage] = []
    for work_id in sorted(manifest.completed_work_ids):
        work, work_pages = _transform_work(
            store,
            manifest,
            resources_by_work[work_id],
            work_id=work_id,
            dataset_id=dataset_id,
        )
        works.append(work)
        pages.extend(work_pages)

    works_tuple = tuple(works)
    pages_tuple = tuple(
        sorted(pages, key=lambda page: (page.work_id, page.sequence_number))
    )
    report = build_quality_report(dataset_id, works_tuple, pages_tuple)
    return SilverTransformResult(
        dataset_id=dataset_id,
        bronze_run_id=manifest.identity.run_id,
        bronze_inventory_sha256=inventory_sha256,
        works=works_tuple,
        pages=pages_tuple,
        quality_report=report,
    )


def build_quality_report(
    dataset_id: str,
    works: tuple[SilverWork, ...],
    pages: tuple[SilverPage, ...],
) -> SilverQualityReport:
    """Aggregate transparent quality counts from canonical rows."""

    language_counts: Counter[str] = Counter()
    work_flag_counts: Counter[str] = Counter()
    for work in works:
        language_counts.update(work.language_ids or ("unknown",))
        work_flag_counts.update(flag.value for flag in work.quality_flags)

    page_flag_counts: Counter[str] = Counter()
    pages_by_work: dict[str, list[SilverPage]] = defaultdict(list)
    for page in pages:
        page_flag_counts.update(flag.value for flag in page.quality_flags)
        pages_by_work[page.work_id].append(page)

    work_summaries = tuple(
        WorkQualitySummary(
            work_id=work.work_id,
            page_count=len(work_pages := pages_by_work[work.work_id]),
            empty_page_count=sum(
                page.ocr_quality is OcrQualityBand.MISSING for page in work_pages
            ),
            review_page_count=sum(
                page.ocr_quality is OcrQualityBand.NEEDS_REVIEW for page in work_pages
            ),
            average_clean_word_count=(
                fmean(page.clean_word_count for page in work_pages)
                if work_pages
                else 0.0
            ),
        )
        for work in works
    )

    return SilverQualityReport(
        dataset_id=dataset_id,
        work_count=len(works),
        page_count=len(pages),
        empty_page_count=sum(
            page.ocr_quality is OcrQualityBand.MISSING for page in pages
        ),
        review_page_count=sum(
            page.ocr_quality is OcrQualityBand.NEEDS_REVIEW for page in pages
        ),
        usable_page_count=sum(
            page.ocr_quality is OcrQualityBand.USABLE for page in pages
        ),
        average_clean_word_count=(
            fmean(page.clean_word_count for page in pages) if pages else 0.0
        ),
        language_counts=dict(sorted(language_counts.items())),
        page_flag_counts=dict(sorted(page_flag_counts.items())),
        work_flag_counts=dict(sorted(work_flag_counts.items())),
        works=work_summaries,
    )


def _transform_work(
    store: BronzeFilesystemStore,
    manifest: BronzeRunManifest,
    resources: list[BronzeResourceRecord],
    *,
    work_id: str,
    dataset_id: str,
) -> tuple[SilverWork, tuple[SilverPage, ...]]:
    catalogue_record = _one_resource(
        resources,
        BronzeResourceType.CATALOGUE_WORK,
        work_id,
    )
    iiif_record = _one_resource(
        resources,
        BronzeResourceType.IIIF_MANIFEST,
        work_id,
    )
    catalogue = CatalogueWork.model_validate_json(
        _read_required(store, manifest, catalogue_record)
    )
    iiif_manifest = IiifManifest.model_validate_json(
        _read_required(store, manifest, iiif_record)
    )
    if catalogue.id != work_id:
        raise SilverTransformError(
            f"catalogue work ID {catalogue.id} does not match {work_id}"
        )
    if not iiif_manifest.sequences:
        raise SilverTransformError(f"work {work_id} has no IIIF sequence")

    annotation_records = [
        resource
        for resource in resources
        if resource.resource_type is BronzeResourceType.OCR_ANNOTATION_LIST
    ]
    page_inputs = tuple(
        _page_input(
            store,
            manifest,
            work_id,
            canvas,
            canvas_index=canvas_index,
            annotation_records=annotation_records,
        )
        for canvas_index, canvas in enumerate(iiif_manifest.sequences[0].canvases)
    )
    used_annotation_ids = {
        record.resource_id
        for page_input in page_inputs
        for record in page_input.annotation_records
    }
    all_annotation_ids = {record.resource_id for record in annotation_records}
    if used_annotation_ids != all_annotation_ids:
        unused = sorted(all_annotation_ids - used_annotation_ids)
        raise SilverTransformError(
            f"work {work_id} has unaccounted annotation resources: {unused}"
        )

    boundary_matches = detect_repeated_boundaries(
        tuple(page.lines for page in page_inputs)
    )
    label_counts = Counter(
        page.canvas.label
        for page in page_inputs
        if page.canvas.label.strip() and page.canvas.label != "-"
    )
    pages = tuple(
        _canonical_page(
            manifest_record=iiif_record,
            page_input=page_input,
            dataset_id=dataset_id,
            header_lines=boundary_matches.headers_by_page[index],
            footer_lines=boundary_matches.footers_by_page[index],
            duplicate_label=label_counts[page_input.canvas.label] > 1,
        )
        for index, page_input in enumerate(page_inputs)
    )
    work = _canonical_work(
        catalogue,
        iiif_manifest,
        dataset_id=dataset_id,
        catalogue_record=catalogue_record,
        iiif_record=iiif_record,
    )
    return work, pages


def _page_input(
    store: BronzeFilesystemStore,
    manifest: BronzeRunManifest,
    work_id: str,
    canvas: IiifCanvas,
    *,
    canvas_index: int,
    annotation_records: list[BronzeResourceRecord],
) -> _PageInput:
    records = sorted(
        (
            record
            for record in annotation_records
            if record.canvas_index == canvas_index
        ),
        key=lambda record: (
            record.annotation_index if record.annotation_index is not None else -1
        ),
    )
    references = canvas.other_content
    if len(records) != len(references):
        raise SilverTransformError(
            f"work {work_id} canvas {canvas_index} declares "
            f"{len(references)} annotations but Bronze stores {len(records)}"
        )

    lines: list[OcrLine] = []
    non_text_annotation_count = 0
    for annotation_index, (record, reference) in enumerate(
        zip(records, references, strict=True)
    ):
        if record.annotation_index != annotation_index:
            raise SilverTransformError(
                f"work {work_id} canvas {canvas_index} annotation order mismatch"
            )
        if str(record.source_url) != str(reference.id):
            raise SilverTransformError(
                f"work {work_id} canvas {canvas_index} annotation URL mismatch"
            )
        annotation_list = OcrAnnotationList.model_validate_json(
            _read_required(store, manifest, record)
        )
        for annotation in annotation_list.resources:
            body = annotation.resource
            if (
                body.resource_type == "cnt:ContentAsText"
                and body.format == "text/plain"
                and body.chars is not None
            ):
                lines.append(parse_ocr_line(body.chars, annotation.on))
            else:
                non_text_annotation_count += 1

    return _PageInput(
        work_id=work_id,
        canvas=canvas,
        sequence_number=canvas_index + 1,
        lines=tuple(lines),
        annotation_records=tuple(records),
        annotation_urls=tuple(reference.id for reference in references),
        non_text_annotation_count=non_text_annotation_count,
    )


def _canonical_work(
    work: CatalogueWork,
    manifest: IiifManifest,
    *,
    dataset_id: str,
    catalogue_record: BronzeResourceRecord,
    iiif_record: BronzeResourceRecord,
) -> SilverWork:
    location = next(
        (
            location
            for item in work.items
            for location in item.locations
            if location.location_type.id == "iiif-presentation"
            and location.licence is not None
            and location.licence.id == "pdm"
            and location.url is not None
        ),
        None,
    )
    expected_manifest_url = manifest_url_for(work)
    if location is None or expected_manifest_url is None:
        raise SilverTransformError(f"work {work.id} has no public-domain IIIF location")
    licence = location.licence
    if licence is None:
        raise SilverTransformError(f"work {work.id} has no licence receipt")

    flags: list[WorkQualityFlag] = []
    if not work.contributors:
        flags.append(WorkQualityFlag.MISSING_CONTRIBUTORS)
    if not work.production:
        flags.append(WorkQualityFlag.MISSING_PRODUCTION)
    if not work.subjects:
        flags.append(WorkQualityFlag.MISSING_SUBJECTS)
    if not work.genres:
        flags.append(WorkQualityFlag.MISSING_GENRES)
    if not work.languages:
        flags.append(WorkQualityFlag.MISSING_LANGUAGE)
    return SilverWork(
        dataset_id=dataset_id,
        work_id=work.id,
        title=work.title,
        alternative_titles=_unique(work.alternative_titles),
        contributors=tuple(
            SilverContributor(
                agent_id=contributor.agent.id,
                label=contributor.agent.label,
                roles=_unique(tuple(role.label for role in contributor.roles)),
                primary=contributor.primary,
            )
            for contributor in work.contributors
        ),
        production_dates=_unique(
            tuple(date.label for event in work.production for date in event.dates)
        ),
        production_labels=_unique(tuple(event.label for event in work.production)),
        subjects=_unique(tuple(subject.label for subject in work.subjects)),
        genres=_unique(tuple(genre.label for genre in work.genres)),
        language_ids=_unique(
            tuple(language.id for language in work.languages if language.id is not None)
        ),
        language_labels=_unique(
            tuple(
                language.label
                for language in work.languages
                if language.label is not None
            )
        ),
        licence_id=licence.id,
        licence_url=licence.url,
        source_url=AnyHttpUrl(f"https://wellcomecollection.org/works/{work.id}"),
        iiif_manifest_url=manifest.id,
        source_content_sha256=catalogue_record.content_sha256,
        iiif_manifest_content_sha256=iiif_record.content_sha256,
        quality_flags=tuple(flags),
        lineage=(
            _lineage(catalogue_record),
            _lineage(iiif_record),
        ),
    )


def _canonical_page(
    *,
    manifest_record: BronzeResourceRecord,
    page_input: _PageInput,
    dataset_id: str,
    header_lines: frozenset[str],
    footer_lines: frozenset[str],
    duplicate_label: bool,
) -> SilverPage:
    raw_text = raw_text_from(page_input.lines)
    cleaning = clean_ocr_lines(
        page_input.lines,
        header_lines=header_lines,
        footer_lines=footer_lines,
    )
    raw_words = word_count(raw_text)
    clean_words = word_count(cleaning.clean_text)
    change_ratio = cleaning_change_ratio(raw_text, cleaning.clean_text)
    image_resource = (
        page_input.canvas.images[0].resource if page_input.canvas.images else None
    )

    flags: list[PageQualityFlag] = []
    if not cleaning.clean_text.strip():
        flags.append(PageQualityFlag.EMPTY_OCR)
    elif clean_words < 20:
        flags.append(PageQualityFlag.VERY_SHORT_TEXT)
    if cleaning.clean_text and symbol_ratio(cleaning.clean_text) > 0.30:
        flags.append(PageQualityFlag.HIGH_SYMBOL_RATIO)
    if cleaning.html_removed_count:
        flags.append(PageQualityFlag.HTML_REMOVED)
    if cleaning.dehyphenation_count:
        flags.append(PageQualityFlag.DEHYPHENATION_APPLIED)
    if cleaning.removed_header_count:
        flags.append(PageQualityFlag.HEADER_DETECTED)
    if cleaning.removed_footer_count:
        flags.append(PageQualityFlag.FOOTER_DETECTED)
    if page_input.canvas.label == "-" or not page_input.canvas.label.strip():
        flags.append(PageQualityFlag.MISSING_PAGE_LABEL)
    if duplicate_label:
        flags.append(PageQualityFlag.DUPLICATE_PAGE_LABEL)
    if len(page_input.annotation_records) > 1:
        flags.append(PageQualityFlag.MULTIPLE_ANNOTATION_LISTS)
    if page_input.non_text_annotation_count:
        flags.append(PageQualityFlag.NON_TEXT_ANNOTATIONS)
    if image_resource is None:
        flags.append(PageQualityFlag.MISSING_IMAGE)
    if change_ratio > 0.30:
        flags.append(PageQualityFlag.LARGE_CLEANING_CHANGE)

    if PageQualityFlag.EMPTY_OCR in flags:
        quality = OcrQualityBand.MISSING
    elif any(
        flag
        in {
            PageQualityFlag.VERY_SHORT_TEXT,
            PageQualityFlag.HIGH_SYMBOL_RATIO,
            PageQualityFlag.LARGE_CLEANING_CHANGE,
        }
        for flag in flags
    ):
        quality = OcrQualityBand.NEEDS_REVIEW
    else:
        quality = OcrQualityBand.USABLE

    page_id = sha256(
        f"{page_input.work_id}\n{page_input.canvas.id}".encode()
    ).hexdigest()
    printed_page_number = (
        int(page_input.canvas.label) if page_input.canvas.label.isdecimal() else None
    )
    return SilverPage(
        dataset_id=dataset_id,
        page_id=page_id,
        work_id=page_input.work_id,
        canvas_id=page_input.canvas.id,
        sequence_number=page_input.sequence_number,
        page_label=page_input.canvas.label,
        printed_page_number=printed_page_number,
        raw_text=raw_text,
        clean_text=cleaning.clean_text,
        detected_headers=tuple(sorted(header_lines)),
        detected_footers=tuple(sorted(footer_lines)),
        ocr_quality=quality,
        quality_flags=tuple(flags),
        raw_line_count=len(page_input.lines),
        raw_word_count=raw_words,
        clean_word_count=clean_words,
        cleaning_change_ratio=change_ratio,
        image_url=image_resource.id if image_resource is not None else None,
        image_service_url=(
            image_resource.service.id
            if image_resource is not None and image_resource.service is not None
            else None
        ),
        annotation_urls=page_input.annotation_urls,
        lineage=(
            _lineage(manifest_record),
            *(_lineage(record) for record in page_input.annotation_records),
        ),
    )


def _one_resource(
    resources: list[BronzeResourceRecord],
    resource_type: BronzeResourceType,
    work_id: str,
) -> BronzeResourceRecord:
    matches = [
        resource for resource in resources if resource.resource_type is resource_type
    ]
    if len(matches) != 1:
        raise SilverTransformError(
            f"work {work_id} requires exactly one {resource_type.value} resource"
        )
    return matches[0]


def _read_required(
    store: BronzeFilesystemStore,
    manifest: BronzeRunManifest,
    record: BronzeResourceRecord,
) -> bytes:
    content = store.read_resource(manifest, record.resource_id)
    if content is None:
        raise SilverTransformError(f"missing Bronze resource {record.resource_id}")
    return content


def _lineage(record: BronzeResourceRecord) -> SilverLineage:
    return SilverLineage(
        resource_id=record.resource_id,
        resource_type=record.resource_type,
        relative_path=record.relative_path,
        source_url=record.source_url,
        content_sha256=record.content_sha256,
    )


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    """Preserve source order while removing exact duplicates and blanks."""

    return tuple(dict.fromkeys(value for value in values if value.strip()))
