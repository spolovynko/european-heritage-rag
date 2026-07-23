"""Command-line interface for HeritageRAG."""

from importlib.metadata import version
from typing import Annotated

import typer

from european_heritage_rag.core.config import get_settings
from european_heritage_rag.pipeline.bronze_store import (
    BronzeFilesystemStore,
    BronzeManifestIdentityError,
)
from european_heritage_rag.pipeline.bronze_validation import validate_bronze_run
from european_heritage_rag.pipeline.chunking import chunking_profiles
from european_heritage_rag.pipeline.gold import (
    GoldTransformError,
    transform_silver_dataset,
)
from european_heritage_rag.pipeline.gold_store import (
    GoldContentConflictError,
    GoldFilesystemStore,
    validate_gold_dataset,
)
from european_heritage_rag.pipeline.silver import (
    SilverTransformError,
    transform_bronze_run,
)
from european_heritage_rag.pipeline.silver_store import (
    SilverFilesystemStore,
    validate_silver_dataset,
)
from european_heritage_rag.pipeline.tokenization import PinnedTokenizer
from european_heritage_rag.sources.wellcome.ingestion import run_wellcome_ingestion

_DISTRIBUTION_NAME = "european-heritage-rag"

app = typer.Typer(
    name="european-heritage-rag",
    help="Operate and inspect the HeritageRAG application.",
    no_args_is_help=True,
)
ingest_app = typer.Typer(
    help="Discover and traverse external heritage sources.",
    no_args_is_help=True,
)
bronze_app = typer.Typer(
    help="Inspect and validate immutable raw source runs.",
    no_args_is_help=True,
)
silver_app = typer.Typer(
    help="Build, inspect, and validate canonical Silver datasets.",
    no_args_is_help=True,
)
gold_app = typer.Typer(
    help="Build, inspect, and validate retrieval-ready Gold chunks.",
    no_args_is_help=True,
)
app.add_typer(ingest_app, name="ingest")
app.add_typer(bronze_app, name="bronze")
app.add_typer(silver_app, name="silver")
app.add_typer(gold_app, name="gold")


@app.callback()
def cli() -> None:
    """Provide HeritageRAG command-line operations."""


@app.command("version")
def show_version() -> None:
    """Print the installed HeritageRAG version."""

    typer.echo(version(_DISTRIBUTION_NAME))


@ingest_app.command("wellcome")
def ingest_wellcome(
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            min=1,
            max=100,
            help="Maximum eligible works to discover.",
        ),
    ] = 5,
    query: Annotated[
        str | None,
        typer.Option(
            "--query",
            help="Optional Wellcome full-text discovery query.",
        ),
    ] = None,
    language: Annotated[
        str,
        typer.Option(
            "--language",
            help="Discovery language; Phase 4 supports eng only.",
        ),
    ] = "eng",
    resume: Annotated[
        bool,
        typer.Option(
            "--resume",
            help="Continue the matching Wellcome checkpoint.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Discover works without requesting manifests or OCR.",
        ),
    ] = False,
) -> None:
    """Discover and sequentially traverse public-domain Wellcome books."""

    if resume and dry_run:
        raise typer.BadParameter("--resume and --dry-run cannot be used together")
    if language != "eng":
        raise typer.BadParameter("--language must be eng during Phase 4")

    try:
        result = run_wellcome_ingestion(
            get_settings(),
            limit=limit,
            query=query,
            language=language,
            resume=resume,
            dry_run=dry_run,
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    except Exception as error:
        typer.echo(f"Wellcome ingestion failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Run: {result.run_id}")
    typer.echo(f"Status: {result.status}")
    typer.echo(f"Works: {result.works_completed}/{result.works_discovered}")
    typer.echo(f"Pages traversed: {result.pages_downloaded}")
    typer.echo(f"Missing OCR pages: {result.missing_ocr_pages}")
    typer.echo(f"Retries: {result.retry_count}; failures: {result.failure_count}")


@bronze_app.command("inspect")
def inspect_bronze(
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="Show one run in detail; omit to list every run.",
        ),
    ] = None,
) -> None:
    """Show Bronze runs, counts, failures, paths, and source URLs."""

    settings = get_settings()
    store = BronzeFilesystemStore(settings.bronze_data_directory)
    if run_id is None:
        manifests = store.list_manifests()
        if not manifests:
            typer.echo("No Bronze runs found.")
            return
        for summary in manifests:
            typer.echo(
                f"{summary.identity.run_id} | {summary.status.value} | "
                f"{summary.completed_work_count}/"
                f"{summary.discovered_work_count} works | "
                f"{len(summary.resources)} resources | "
                f"{len(summary.failures)} failure records"
            )
        return

    selected_manifest = store.find_manifest(run_id)
    if selected_manifest is None:
        typer.echo(f"Bronze run not found: {run_id}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Run: {selected_manifest.identity.run_id}")
    typer.echo(f"Status: {selected_manifest.status.value}")
    typer.echo(f"Started: {selected_manifest.started_at.isoformat()}")
    typer.echo(
        f"Works: {selected_manifest.completed_work_count}/"
        f"{selected_manifest.discovered_work_count}"
    )
    typer.echo(
        f"Canvases: {selected_manifest.canvas_count}; "
        f"annotations: {selected_manifest.annotation_count}; "
        f"missing OCR: {selected_manifest.missing_ocr_page_count}"
    )
    typer.echo(f"Resources: {len(selected_manifest.resources)}")
    for record in selected_manifest.resources:
        typer.echo(
            f"- {record.relative_path} | {record.content_sha256} | {record.source_url}"
        )
    unresolved = [
        failure for failure in selected_manifest.failures if failure.resolved_at is None
    ]
    typer.echo(f"Unresolved failures: {len(unresolved)}")
    for failure in unresolved:
        typer.echo(f"- {failure.source_url} | {failure.message}")


@bronze_app.command("validate")
def validate_bronze(
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="Validate one run; omit to validate every run.",
        ),
    ] = None,
) -> None:
    """Verify Bronze files, hashes, JSON shapes, and manifest coverage."""

    settings = get_settings()
    store = BronzeFilesystemStore(settings.bronze_data_directory)
    if run_id is None:
        manifest_paths = store.manifest_paths()
    else:
        manifest_paths = tuple(
            path
            for path in store.manifest_paths()
            if path.parent.name.removeprefix("run_id=") == run_id
        )
        if not manifest_paths:
            typer.echo(f"Bronze run not found: {run_id}", err=True)
            raise typer.Exit(code=1)

    if not manifest_paths:
        typer.echo("No Bronze runs found.")
        return

    invalid = False
    for path in manifest_paths:
        try:
            manifest = store.load_manifest_path(path)
        except (OSError, ValueError, BronzeManifestIdentityError) as error:
            invalid = True
            typer.echo(
                f"{path}: invalid manifest ({type(error).__name__}: {error})",
                err=True,
            )
            continue
        report = validate_bronze_run(store, manifest)
        typer.echo(
            f"{report.run_id}: "
            f"{'valid' if report.is_valid else 'invalid'} "
            f"({report.checked_resource_count} resources checked)"
        )
        for issue in report.issues:
            invalid = True
            location = issue.relative_path or "run"
            typer.echo(
                f"- {issue.code} | {location} | {issue.message}",
                err=True,
            )

    if invalid:
        raise typer.Exit(code=1)


@silver_app.command("build")
def build_silver(
    bronze_run_id: Annotated[
        str,
        typer.Option(
            "--bronze-run-id",
            help="Completed Bronze run to transform entirely offline.",
        ),
    ],
) -> None:
    """Build or reuse one deterministic Silver dataset."""

    settings = get_settings()
    bronze_store = BronzeFilesystemStore(settings.bronze_data_directory)
    bronze_manifest = bronze_store.find_manifest(bronze_run_id)
    if bronze_manifest is None:
        typer.echo(f"Bronze run not found: {bronze_run_id}", err=True)
        raise typer.Exit(code=1)
    try:
        transformed = transform_bronze_run(bronze_store, bronze_manifest)
        published = SilverFilesystemStore(settings.silver_data_directory).publish(
            transformed
        )
    except (OSError, ValueError, SilverTransformError) as error:
        typer.echo(f"Silver build failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    action = "created" if published.created else "reused"
    typer.echo(f"Dataset: {published.manifest.dataset_id}")
    typer.echo(f"Status: {action}")
    typer.echo(f"Bronze run: {published.manifest.bronze_run_id}")
    typer.echo(
        f"Works: {published.manifest.work_count}; "
        f"pages: {published.manifest.page_count}"
    )


@silver_app.command("inspect")
def inspect_silver(
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id",
            help="Show one dataset in detail; omit to list complete datasets.",
        ),
    ] = None,
) -> None:
    """Show complete Silver datasets and their quality summary."""

    store = SilverFilesystemStore(get_settings().silver_data_directory)
    if dataset_id is None:
        manifests = store.list_manifests()
        if not manifests:
            typer.echo("No Silver datasets found.")
            return
        for listed_manifest in manifests:
            typer.echo(
                f"{listed_manifest.dataset_id} | "
                f"Bronze {listed_manifest.bronze_run_id} | "
                f"{listed_manifest.work_count} works | "
                f"{listed_manifest.page_count} pages"
            )
        return

    manifest = store.find_manifest(dataset_id)
    if manifest is None:
        typer.echo(f"Silver dataset not found: {dataset_id}", err=True)
        raise typer.Exit(code=1)
    quality = store.read_quality(dataset_id)
    typer.echo(f"Dataset: {manifest.dataset_id}")
    typer.echo(f"Bronze run: {manifest.bronze_run_id}")
    typer.echo(f"Works: {manifest.work_count}; pages: {manifest.page_count}")
    typer.echo(
        f"Empty OCR: {quality.empty_page_count}; "
        f"needs review: {quality.review_page_count}; "
        f"usable: {quality.usable_page_count}"
    )
    for record in manifest.files:
        typer.echo(
            f"- {record.name} | {record.byte_length} bytes | {record.content_sha256}"
        )


@silver_app.command("validate")
def validate_silver(
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id",
            help="Validate one dataset; omit to validate all complete datasets.",
        ),
    ] = None,
) -> None:
    """Verify Silver files, hashes, schemas, rows, and relationships."""

    store = SilverFilesystemStore(get_settings().silver_data_directory)
    manifests = (
        store.list_manifests()
        if dataset_id is None
        else tuple(
            manifest
            for manifest in (store.find_manifest(dataset_id),)
            if manifest is not None
        )
    )
    if dataset_id is not None and not manifests:
        typer.echo(f"Silver dataset not found: {dataset_id}", err=True)
        raise typer.Exit(code=1)
    if not manifests:
        typer.echo("No Silver datasets found.")
        return

    invalid = False
    for manifest in manifests:
        report = validate_silver_dataset(store, manifest)
        typer.echo(
            f"{manifest.dataset_id}: "
            f"{'valid' if report.is_valid else 'invalid'} "
            f"({manifest.work_count} works, {manifest.page_count} pages)"
        )
        for issue in report.issues:
            invalid = True
            typer.echo(
                f"- {issue.code} | {issue.filename or 'dataset'} | {issue.message}",
                err=True,
            )
    if invalid:
        raise typer.Exit(code=1)


@gold_app.command("build")
def build_gold(
    silver_dataset_id: Annotated[
        str,
        typer.Option(
            "--silver-dataset-id",
            help="Validated Silver dataset to chunk.",
        ),
    ],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            help="One named profile; defaults to tokens-500-v1.",
        ),
    ] = None,
    all_profiles: Annotated[
        bool,
        typer.Option(
            "--all-profiles",
            help="Build all three Phase 7 chunking experiments.",
        ),
    ] = False,
    work_id: Annotated[
        str | None,
        typer.Option(
            "--work-id",
            help="Build a separate deterministic snapshot for one work.",
        ),
    ] = None,
) -> None:
    """Build or reuse deterministic Gold chunks from one Silver dataset."""

    if profile is not None and all_profiles:
        raise typer.BadParameter("--profile and --all-profiles cannot be combined")
    profiles = chunking_profiles()
    selected_profile_ids = (
        tuple(profiles) if all_profiles else (profile or "tokens-500-v1",)
    )
    unknown = [item for item in selected_profile_ids if item not in profiles]
    if unknown:
        raise typer.BadParameter(
            f"unknown profile {unknown[0]}; choose from {', '.join(profiles)}"
        )

    settings = get_settings()
    silver_store = SilverFilesystemStore(settings.silver_data_directory)
    silver_manifest = silver_store.find_manifest(silver_dataset_id)
    if silver_manifest is None:
        typer.echo(
            f"Silver dataset not found: {silver_dataset_id}",
            err=True,
        )
        raise typer.Exit(code=1)
    gold_store = GoldFilesystemStore(settings.gold_data_directory)
    try:
        tokenizer = PinnedTokenizer()
        for profile_id in selected_profile_ids:
            transformed = transform_silver_dataset(
                silver_store,
                silver_manifest,
                config=profiles[profile_id],
                tokenizer=tokenizer,
                selected_work_ids=(work_id,) if work_id is not None else (),
            )
            published = gold_store.publish(
                transformed,
                silver_store=silver_store,
                tokenizer=tokenizer,
            )
            action = "created" if published.created else "reused"
            typer.echo(f"Dataset: {published.manifest.gold_dataset_id}")
            typer.echo(f"Status: {action}")
            typer.echo(f"Profile: {profile_id}")
            typer.echo(
                f"Works: {published.manifest.work_count}; "
                f"pages: {published.manifest.contributing_page_count}; "
                f"chunks: {published.manifest.chunk_count}"
            )
    except (
        GoldContentConflictError,
        GoldTransformError,
        OSError,
        ValueError,
    ) as error:
        typer.echo(f"Gold build failed: {error}", err=True)
        raise typer.Exit(code=1) from error


@gold_app.command("inspect")
def inspect_gold(
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id",
            help="Show one dataset in detail; omit to list complete datasets.",
        ),
    ] = None,
) -> None:
    """Show complete Gold datasets and measured chunk statistics."""

    store = GoldFilesystemStore(get_settings().gold_data_directory)
    if dataset_id is None:
        manifests = store.list_manifests()
        if not manifests:
            typer.echo("No Gold datasets found.")
            return
        for manifest in manifests:
            typer.echo(
                f"{manifest.gold_dataset_id} | "
                f"{manifest.chunking_config.profile_id} | "
                f"Silver {manifest.silver_dataset_id} | "
                f"{manifest.work_count} works | "
                f"{manifest.chunk_count} chunks"
            )
        return

    selected_manifest = store.find_manifest(dataset_id)
    if selected_manifest is None:
        typer.echo(f"Gold dataset not found: {dataset_id}", err=True)
        raise typer.Exit(code=1)
    statistics = store.read_statistics(dataset_id)
    typer.echo(f"Dataset: {selected_manifest.gold_dataset_id}")
    typer.echo(f"Silver dataset: {selected_manifest.silver_dataset_id}")
    typer.echo(f"Profile: {selected_manifest.chunking_config.profile_id}")
    typer.echo(
        f"Works: {selected_manifest.work_count}; "
        f"pages: {selected_manifest.contributing_page_count}; "
        f"chunks: {selected_manifest.chunk_count}"
    )
    typer.echo(
        f"Tokens min/median/p95/max: {statistics.minimum_tokens}/"
        f"{statistics.median_tokens:.1f}/{statistics.p95_tokens:.1f}/"
        f"{statistics.maximum_tokens}"
    )
    typer.echo(
        f"Short: {statistics.short_chunk_count}; "
        f"overlap ratio: {statistics.overlap_ratio:.4f}; "
        f"exclusions: {len(statistics.exclusions)}"
    )
    for record in selected_manifest.files:
        typer.echo(
            f"- {record.name} | {record.byte_length} bytes | {record.content_sha256}"
        )


@gold_app.command("validate")
def validate_gold(
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id",
            help="Validate one dataset; omit to validate all complete datasets.",
        ),
    ] = None,
) -> None:
    """Verify Gold files, rows, token counts, adjacency, and provenance."""

    settings = get_settings()
    store = GoldFilesystemStore(settings.gold_data_directory)
    silver_store = SilverFilesystemStore(settings.silver_data_directory)
    manifests = (
        store.list_manifests()
        if dataset_id is None
        else tuple(
            manifest
            for manifest in (store.find_manifest(dataset_id),)
            if manifest is not None
        )
    )
    if dataset_id is not None and not manifests:
        typer.echo(f"Gold dataset not found: {dataset_id}", err=True)
        raise typer.Exit(code=1)
    if not manifests:
        typer.echo("No Gold datasets found.")
        return

    invalid = False
    tokenizers: dict[tuple[str, str, int], PinnedTokenizer] = {}
    for manifest in manifests:
        config = manifest.chunking_config
        tokenizer_key = (
            config.tokenizer_model,
            config.tokenizer_revision,
            config.tokenizer_maximum_length,
        )
        try:
            tokenizer = tokenizers.get(tokenizer_key)
            if tokenizer is None:
                tokenizer = PinnedTokenizer(
                    model_id=config.tokenizer_model,
                    revision=config.tokenizer_revision,
                    expected_maximum_length=config.tokenizer_maximum_length,
                )
                tokenizers[tokenizer_key] = tokenizer
            report = validate_gold_dataset(
                store,
                manifest,
                silver_store=silver_store,
                tokenizer=tokenizer,
            )
        except (OSError, ValueError) as error:
            invalid = True
            typer.echo(
                f"{manifest.gold_dataset_id}: tokenizer validation failed ({error})",
                err=True,
            )
            continue
        typer.echo(
            f"{manifest.gold_dataset_id}: "
            f"{'valid' if report.is_valid else 'invalid'} "
            f"({manifest.chunk_count} chunks, "
            f"{config.profile_id})"
        )
        for issue in report.issues:
            invalid = True
            typer.echo(
                f"- {issue.code} | {issue.filename or 'dataset'} | {issue.message}",
                err=True,
            )
    if invalid:
        raise typer.Exit(code=1)


def main() -> None:
    """Run the HeritageRAG command-line application."""

    app()
