"""HTTP client for the Wellcome Collection APIs."""

import json
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from types import TracebackType
from typing import Self

import httpx2
from pydantic import AnyHttpUrl
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from european_heritage_rag.core.config import AppSettings
from european_heritage_rag.pipeline.bronze import SILVER_READY_WELLCOME_INCLUDE
from european_heritage_rag.sources.wellcome.models import (
    CatalogueWork,
    CatalogueWorksPage,
    IiifManifest,
    OcrAnnotationList,
    RawWellcomeResource,
    TraversedPage,
    TraversedWork,
)

_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
RawResourceObserver = Callable[[RawWellcomeResource], None]


class WellcomeStructureError(ValueError):
    """Raised when a valid source response lacks required traversal structure."""


def is_retryable_error(exception: BaseException) -> bool:
    """Return whether a failed request should be attempted again."""

    if isinstance(exception, httpx2.RequestError):
        return True

    if isinstance(exception, httpx2.HTTPStatusError):
        return exception.response.status_code in _RETRYABLE_STATUS_CODES

    return False


def retry_after_seconds(retry_state: RetryCallState) -> float | None:
    """Return a valid numeric Retry-After delay from the last response."""

    outcome = retry_state.outcome
    if outcome is None or not outcome.failed:
        return None

    exception = outcome.exception()
    if not isinstance(exception, httpx2.HTTPStatusError):
        return None

    header = exception.response.headers.get("Retry-After")
    if header is None:
        return None

    try:
        delay = float(header)
    except ValueError:
        return None

    return delay if delay >= 0 else None


def is_eligible_work(work: CatalogueWork, *, language: str) -> bool:
    """Return whether a work satisfies the local ingestion contract."""

    if work.work_type.id != "a":
        return False

    if "online" not in {availability.id for availability in work.availabilities}:
        return False

    if language not in {work_language.id for work_language in work.languages}:
        return False

    return any(
        location.location_type.id == "iiif-presentation"
        and location.url is not None
        and location.licence is not None
        and location.licence.id == "pdm"
        for item in work.items
        for location in item.locations
    )


def manifest_url_for(work: CatalogueWork) -> str | None:
    """Return the public-domain IIIF Presentation URL for an eligible work."""

    for item in work.items:
        for location in item.locations:
            if (
                location.location_type.id == "iiif-presentation"
                and location.url is not None
                and location.licence is not None
                and location.licence.id == "pdm"
            ):
                return str(location.url)

    return None


def ocr_lines_from(annotation_list: OcrAnnotationList) -> tuple[str, ...]:
    """Return supported plain-text OCR resources without cleaning their text."""

    return tuple(
        annotation.resource.chars
        for annotation in annotation_list.resources
        if annotation.resource.resource_type == "cnt:ContentAsText"
        and annotation.resource.format == "text/plain"
        and annotation.resource.chars is not None
    )


class WellcomeClient:
    """Retrieve and validate source data from Wellcome Collection."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        timeout = httpx2.Timeout(
            connect=settings.wellcome_connect_timeout_seconds,
            read=settings.wellcome_read_timeout_seconds,
            write=settings.wellcome_write_timeout_seconds,
            pool=settings.wellcome_pool_timeout_seconds,
        )

        self._http = httpx2.Client(
            base_url=str(settings.wellcome_catalogue_base_url),
            headers={
                "Accept": "application/json",
                "User-Agent": settings.wellcome_user_agent,
            },
            timeout=timeout,
            follow_redirects=True,
        )
        self._maximum_retry_wait_seconds = settings.wellcome_max_retry_wait_seconds
        self._fallback_wait = wait_exponential(
            multiplier=1,
            max=self._maximum_retry_wait_seconds,
        )
        self._retry_count = 0
        self._retrying = Retrying(
            sleep=sleep,
            stop=stop_after_attempt(settings.wellcome_max_attempts),
            wait=self._wait_before_retry,
            retry=retry_if_exception(is_retryable_error),
            before_sleep=self._record_retry,
            reraise=True,
        )

    def __enter__(self) -> Self:
        """Enter the client context."""

        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close network resources when leaving the context."""

        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""

        self._http.close()

    @property
    def retry_count(self) -> int:
        """Return the number of retry waits performed by this client."""

        return self._retry_count

    def fetch_catalogue_page(
        self,
        *,
        url: str = "works",
        params: Mapping[str, str | int] | None = None,
    ) -> CatalogueWorksPage:
        """Retrieve and validate one catalogue results page."""

        page, _, _ = self._fetch_catalogue_page_with_response(
            url=url,
            params=params,
        )
        return page

    def _fetch_catalogue_page_with_response(
        self,
        *,
        url: str = "works",
        params: Mapping[str, str | int] | None = None,
    ) -> tuple[CatalogueWorksPage, httpx2.Response, datetime]:
        """Return one parsed page together with its exact HTTP response."""

        response = self._retrying(
            self._get,
            url,
            params=params,
        )
        acquired_at = datetime.now(UTC)
        return (
            CatalogueWorksPage.model_validate_json(response.content),
            response,
            acquired_at,
        )

    def discover_works(
        self,
        *,
        limit: int,
        query: str | None = None,
        language: str = "eng",
        raw_resource_observer: RawResourceObserver | None = None,
    ) -> tuple[CatalogueWork, ...]:
        """Discover eligible works in catalogue order up to a fixed limit."""

        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        if language != "eng":
            raise ValueError("only English discovery is supported")

        params: dict[str, str | int] = {
            "workType": "a",
            "availabilities": "online",
            "items.locations.license": "pdm",
            "items.locations.locationType": "iiif-presentation",
            "languages": language,
            "include": SILVER_READY_WELLCOME_INCLUDE,
            "pageSize": limit,
        }
        if query:
            params["query"] = query

        page, response, acquired_at = self._fetch_catalogue_page_with_response(
            params=params
        )
        discovered: list[CatalogueWork] = []

        while True:
            raw_results = _raw_catalogue_results(response)
            if len(raw_results) != len(page.results):
                raise WellcomeStructureError(
                    "catalogue raw and validated result counts do not match"
                )

            for work, raw_content in zip(page.results, raw_results, strict=True):
                if not is_eligible_work(work, language=language):
                    continue

                if raw_resource_observer is not None:
                    raw_resource_observer(
                        RawWellcomeResource(
                            resource_type="catalogue_work",
                            work_id=work.id,
                            source_url=AnyHttpUrl(str(response.url)),
                            content=raw_content,
                            acquired_at=acquired_at,
                            content_type=response.headers.get("content-type"),
                        )
                    )
                discovered.append(work)
                if len(discovered) == limit:
                    return tuple(discovered)

            if page.next_page is None:
                return tuple(discovered)

            page, response, acquired_at = self._fetch_catalogue_page_with_response(
                url=str(page.next_page)
            )

    def fetch_manifest(self, url: str) -> IiifManifest:
        """Retrieve and validate one IIIF Presentation 2 manifest."""

        response = self._retrying(self._get, url, params=None)
        return IiifManifest.model_validate_json(response.content)

    def fetch_annotation_list(self, url: str) -> OcrAnnotationList:
        """Retrieve and validate one IIIF OCR annotation list."""

        response = self._retrying(self._get, url, params=None)
        return OcrAnnotationList.model_validate_json(response.content)

    def traverse_work(self, work: CatalogueWork) -> TraversedWork:
        """Retrieve a work's manifest and reconstruct page OCR in source order."""

        return self.traverse_work_with_resources(work)

    def traverse_work_with_resources(
        self,
        work: CatalogueWork,
        *,
        raw_resource_observer: RawResourceObserver | None = None,
    ) -> TraversedWork:
        """Traverse one work while exposing source bytes before validation."""

        manifest_url = manifest_url_for(work)
        if manifest_url is None:
            raise WellcomeStructureError(
                f"work {work.id} has no public-domain IIIF Presentation location"
            )

        manifest_response = self._retrying(
            self._get,
            manifest_url,
            params=None,
        )
        manifest_acquired_at = datetime.now(UTC)
        if raw_resource_observer is not None:
            raw_resource_observer(
                RawWellcomeResource(
                    resource_type="iiif_manifest",
                    work_id=work.id,
                    source_url=AnyHttpUrl(str(manifest_response.url)),
                    content=manifest_response.content,
                    acquired_at=manifest_acquired_at,
                    content_type=manifest_response.headers.get("content-type"),
                )
            )
        manifest = IiifManifest.model_validate_json(manifest_response.content)
        if not manifest.sequences:
            raise WellcomeStructureError(
                f"manifest for work {work.id} has no default sequence"
            )

        pages: list[TraversedPage] = []
        for canvas_index, canvas in enumerate(manifest.sequences[0].canvases):
            lines: list[str] = []

            for annotation_index, annotation_reference in enumerate(
                canvas.other_content
            ):
                annotation_response = self._retrying(
                    self._get,
                    str(annotation_reference.id),
                    params=None,
                )
                annotation_acquired_at = datetime.now(UTC)
                if raw_resource_observer is not None:
                    raw_resource_observer(
                        RawWellcomeResource(
                            resource_type="ocr_annotation_list",
                            work_id=work.id,
                            source_url=AnyHttpUrl(str(annotation_response.url)),
                            content=annotation_response.content,
                            acquired_at=annotation_acquired_at,
                            content_type=annotation_response.headers.get(
                                "content-type"
                            ),
                            canvas_index=canvas_index,
                            annotation_index=annotation_index,
                        )
                    )
                annotation_list = OcrAnnotationList.model_validate_json(
                    annotation_response.content
                )
                lines.extend(ocr_lines_from(annotation_list))

            page_text = "\n".join(lines)
            pages.append(
                TraversedPage(
                    canvas_index=canvas_index,
                    canvas_id=canvas.id,
                    label=canvas.label,
                    annotation_list_urls=tuple(
                        reference.id for reference in canvas.other_content
                    ),
                    ocr_lines=tuple(lines),
                    text=page_text or None,
                )
            )

        return TraversedWork(
            work_id=work.id,
            title=work.title,
            manifest_url=manifest.id,
            pages=tuple(pages),
        )

    def _get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None,
    ) -> httpx2.Response:
        """Perform one GET attempt and raise unsuccessful HTTP responses."""

        response = self._http.get(url, params=params)
        response.raise_for_status()

        return response

    def _wait_before_retry(self, retry_state: RetryCallState) -> float:
        """Prefer Retry-After, otherwise use capped exponential backoff."""

        server_delay = retry_after_seconds(retry_state)
        if server_delay is not None:
            return min(server_delay, self._maximum_retry_wait_seconds)

        return float(self._fallback_wait(retry_state))

    def _record_retry(self, _: RetryCallState) -> None:
        """Count each retry immediately before its wait is applied."""

        self._retry_count += 1


def _raw_catalogue_results(response: httpx2.Response) -> tuple[bytes, ...]:
    """Losslessly decode selected work objects without using narrow models."""

    payload = json.loads(response.content)
    if not isinstance(payload, dict):
        raise WellcomeStructureError("catalogue response is not a JSON object")
    results = payload.get("results")
    if not isinstance(results, list):
        raise WellcomeStructureError(
            "catalogue response does not contain a results list"
        )
    return tuple(
        json.dumps(
            result,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        for result in results
    )
