"""Tests for strict Gold chunk and dataset contracts."""

from hashlib import sha256

import pytest
from pydantic import ValidationError

from european_heritage_rag.domain.gold import ChunkingConfig
from european_heritage_rag.pipeline.chunking import chunking_profiles


def test_phase_profiles_have_expected_targets_and_overlap() -> None:
    """The three experiments should remain explicit and independently versioned."""

    profiles = chunking_profiles()

    assert tuple(profiles) == (
        "tokens-300-v1",
        "tokens-500-v1",
        "tokens-800-v1",
    )
    assert [
        (
            profile.target_token_count,
            profile.overlap_token_count,
        )
        for profile in profiles.values()
    ] == [(300, 30), (500, 50), (800, 80)]
    assert len({profile.profile_id for profile in profiles.values()}) == 3


def test_chunking_config_rejects_overlap_at_target() -> None:
    """Overlap must leave room for new evidence in the next chunk."""

    baseline = chunking_profiles()["tokens-300-v1"]

    with pytest.raises(ValidationError):
        ChunkingConfig(
            **{
                **baseline.model_dump(),
                "overlap_token_count": baseline.target_token_count,
            }
        )


def test_sha256_fixture_is_stable() -> None:
    """Test data uses a real 64-character content identity."""

    assert len(sha256(b"gold").hexdigest()) == 64
