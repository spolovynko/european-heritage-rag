"""Filesystem persistence for immutable Bronze resources."""

import os
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from european_heritage_rag.pipeline.bronze import (
    BronzeResourceIdentity,
    BronzeResourceRecord,
    BronzeRunIdentity,
    BronzeRunManifest,
)


def sha256_hex(content: bytes) -> str:
    """Return the lowercase SHA-256 digest for exact stored bytes."""

    return sha256(content).hexdigest()


class BronzeWriteDisposition(StrEnum):
    """Possible successful outcomes of a Bronze resource write."""

    CREATED = "created"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class BronzeWriteResult:
    """Result and manifest receipt produced by one resource write."""

    disposition: BronzeWriteDisposition
    record: BronzeResourceRecord


class BronzeContentConflictError(RuntimeError):
    """Raised when an existing resource has unexpected content."""

    def __init__(
        self,
        path: Path,
        *,
        existing_sha256: str,
        incoming_sha256: str,
    ) -> None:
        self.path = path
        self.existing_sha256 = existing_sha256
        self.incoming_sha256 = incoming_sha256

        super().__init__(
            f"Bronze resource already exists with different content: {path}"
        )


class BronzeManifestIdentityError(RuntimeError):
    """Raised when a manifest is stored beneath another run identity."""

    def __init__(
        self,
        path: Path,
        *,
        expected: BronzeRunIdentity,
        actual: BronzeRunIdentity,
    ) -> None:
        self.path = path
        self.expected = expected
        self.actual = actual

        super().__init__(
            f"Bronze manifest identity does not match its directory: {path}"
        )


class BronzeFilesystemStore:
    """Store immutable Bronze resources beneath one local filesystem root."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def run_directory(self, run: BronzeRunIdentity) -> Path:
        """Return the operating-system directory for one Bronze run."""

        return self.root.joinpath(*run.relative_directory.parts)

    def manifest_path(self, run: BronzeRunIdentity) -> Path:
        """Return the run-manifest path for one Bronze run."""

        return self.run_directory(run) / "run-manifest.json"

    def resource_path(
        self,
        run: BronzeRunIdentity,
        resource: BronzeResourceIdentity,
    ) -> Path:
        """Return the operating-system path for one Bronze resource."""

        return self.run_directory(run).joinpath(*resource.relative_path.parts)

    def write_resource(
        self,
        *,
        run: BronzeRunIdentity,
        resource: BronzeResourceIdentity,
        content: bytes,
        acquired_at: datetime,
        content_type: str | None,
    ) -> BronzeWriteResult:
        """Atomically create one raw resource or recognize identical content."""

        if not content:
            raise ValueError("Bronze resource content cannot be empty")

        incoming_sha256 = sha256_hex(content)
        destination = self.resource_path(run, resource)

        record = BronzeResourceRecord(
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            work_id=resource.work_id,
            relative_path=resource.relative_path.as_posix(),
            source_url=resource.source_url,
            acquired_at=acquired_at,
            content_sha256=incoming_sha256,
            byte_length=len(content),
            content_type=content_type,
            canvas_index=resource.canvas_index,
            annotation_index=resource.annotation_index,
        )

        if destination.exists():
            self._ensure_existing_content_matches(
                destination,
                incoming_sha256=incoming_sha256,
            )
            return BronzeWriteResult(
                disposition=BronzeWriteDisposition.UNCHANGED,
                record=record,
            )

        created = self._write_bytes_atomically(
            destination,
            content,
            replace_existing=False,
        )

        return BronzeWriteResult(
            disposition=(
                BronzeWriteDisposition.CREATED
                if created
                else BronzeWriteDisposition.UNCHANGED
            ),
            record=record,
        )

    def write_manifest(self, manifest: BronzeRunManifest) -> Path:
        """Atomically create or replace one complete run manifest."""

        destination = self.manifest_path(manifest.identity)
        content = f"{manifest.model_dump_json(indent=2)}\n".encode()
        self._write_bytes_atomically(
            destination,
            content,
            replace_existing=True,
        )
        return destination

    def load_manifest(
        self,
        run: BronzeRunIdentity,
    ) -> BronzeRunManifest | None:
        """Load and validate a run manifest when one exists."""

        path = self.manifest_path(run)
        if not path.is_file():
            return None

        return self.load_manifest_path(path)

    def manifest_paths(self) -> tuple[Path, ...]:
        """Return every run-manifest path in portable directory order."""

        pattern = "wellcome/ingestion_date=*/run_id=*/run-manifest.json"
        return tuple(sorted(path for path in self.root.glob(pattern) if path.is_file()))

    def load_manifest_path(self, path: Path) -> BronzeRunManifest:
        """Load a manifest and verify its identity against its directory."""

        relative = path.relative_to(self.root)
        if len(relative.parts) != 4 or relative.name != "run-manifest.json":
            raise ValueError(f"invalid Bronze manifest path: {path}")

        source, date_partition, run_partition, _ = relative.parts
        date_prefix = "ingestion_date="
        run_prefix = "run_id="
        if not date_partition.startswith(date_prefix) or not run_partition.startswith(
            run_prefix
        ):
            raise ValueError(f"invalid Bronze manifest partitions: {path}")

        expected = BronzeRunIdentity.model_validate(
            {
                "source": source,
                "ingestion_date": date.fromisoformat(
                    date_partition.removeprefix(date_prefix)
                ),
                "run_id": run_partition.removeprefix(run_prefix),
            }
        )
        manifest = BronzeRunManifest.model_validate_json(path.read_bytes())
        if manifest.identity != expected:
            raise BronzeManifestIdentityError(
                path,
                expected=expected,
                actual=manifest.identity,
            )
        return manifest

    def list_manifests(self) -> tuple[BronzeRunManifest, ...]:
        """Load every valid manifest beneath the configured Bronze root."""

        manifests = [self.load_manifest_path(path) for path in self.manifest_paths()]
        return tuple(
            sorted(
                manifests,
                key=lambda manifest: manifest.started_at,
                reverse=True,
            )
        )

    def find_manifest(self, run_id: str) -> BronzeRunManifest | None:
        """Find one globally unique run ID."""

        matching_paths = [
            path
            for path in self.manifest_paths()
            if path.parent.name.removeprefix("run_id=") == run_id
        ]
        if not matching_paths:
            return None
        if len(matching_paths) > 1:
            raise RuntimeError(f"duplicate Bronze run ID found: {run_id}")
        return self.load_manifest_path(matching_paths[0])

    def read_resource(
        self,
        manifest: BronzeRunManifest,
        resource_id: str,
    ) -> bytes | None:
        """Read one manifest-declared resource without accepting a disk path."""

        record = next(
            (
                candidate
                for candidate in manifest.resources
                if candidate.resource_id == resource_id
            ),
            None,
        )
        if record is None:
            return None

        identity = BronzeResourceIdentity(
            resource_type=record.resource_type,
            work_id=record.work_id,
            source_url=record.source_url,
            canvas_index=record.canvas_index,
            annotation_index=record.annotation_index,
        )
        return self.resource_path(manifest.identity, identity).read_bytes()

    def _write_bytes_atomically(
        self,
        destination: Path,
        content: bytes,
        *,
        replace_existing: bool,
    ) -> bool:
        """Write complete bytes before exposing or replacing a final file."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")

        try:
            with temporary_path.open("xb") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            if not replace_existing and destination.exists():
                self._ensure_existing_content_matches(
                    destination,
                    incoming_sha256=sha256_hex(content),
                )
                return False

            self._replace(temporary_path, destination)
        finally:
            temporary_path.unlink(missing_ok=True)

        return True

    def _ensure_existing_content_matches(
        self,
        path: Path,
        *,
        incoming_sha256: str,
    ) -> None:
        """Accept identical content and reject an immutable-file conflict."""

        existing_sha256 = sha256_hex(path.read_bytes())

        if existing_sha256 != incoming_sha256:
            raise BronzeContentConflictError(
                path,
                existing_sha256=existing_sha256,
                incoming_sha256=incoming_sha256,
            )

    def _replace(self, temporary_path: Path, destination: Path) -> None:
        """Atomically expose a completely written temporary file."""

        temporary_path.replace(destination)
