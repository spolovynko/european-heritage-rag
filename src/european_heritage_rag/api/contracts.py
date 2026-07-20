"""Public request and response contracts for the HeritageRAG API."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response returned when the API process is alive."""

    status: Literal["ok"]
    service: str
    version: str


class ReadinessResponse(HealthResponse):
    """Response returned when the API is ready to serve requests."""

    checks: dict[str, Literal["ok"]]
