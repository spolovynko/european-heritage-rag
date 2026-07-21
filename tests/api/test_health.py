"""Tests for operational health endpoints."""

from collections.abc import Iterator
from importlib.metadata import version
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from european_heritage_rag.api.main import create_app

_DISTRIBUTION_NAME = "european-heritage-rag"


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide a fresh API instance for each test."""

    with TestClient(create_app()) as test_client:
        yield test_client


def test_liveness_returns_expected_response(client: TestClient) -> None:
    """Liveness should expose stable service identity and version."""

    response = client.get("/health/live")

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ok",
        "service": "HeritageRAG",
        "version": version(_DISTRIBUTION_NAME),
    }


def test_readiness_returns_configuration_check(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ok",
        "service": "HeritageRAG",
        "version": version(_DISTRIBUTION_NAME),
        "checks": {"configuration": "ok"},
    }


def test_application_logs_lifecycle_events() -> None:
    with patch("european_heritage_rag.api.main.logger") as logger_mock:
        with TestClient(create_app()):
            pass

        logged_events = [
            logged_call.args[0] for logged_call in logger_mock.info.call_args_list
        ]

    assert logged_events == [
        "application_started",
        "application_stopped",
    ]
