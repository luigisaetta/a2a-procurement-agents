"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Tests for intake session and request identifier generation.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from conversational_procurement_intake.session_store import (
    SessionStore,
    generate_identifier,
)

IDENTIFIER_PATTERN = r"{prefix}-\d{{8}}-\d{{6}}-[0-9A-F]{{6}}"


def test_generate_identifier_uses_utc_timestamp_and_random_suffix() -> None:
    """Identifiers carry the creation time and a 6-digit hex suffix."""

    created_at = datetime(2026, 10, 24, 15, 30, 12, tzinfo=UTC)

    identifier = generate_identifier("REQ", now=created_at)

    assert re.fullmatch(r"REQ-20261024-153012-[0-9A-F]{6}", identifier)


def test_generate_identifier_differs_within_the_same_second() -> None:
    """The random suffix separates identifiers created in the same second."""

    created_at = datetime(2026, 10, 24, 15, 30, 12, tzinfo=UTC)

    identifiers = {generate_identifier("REQ", now=created_at) for _ in range(100)}

    assert len(identifiers) == 100


@pytest.mark.anyio
async def test_new_store_does_not_reuse_identifiers() -> None:
    """A restarted intake layer (a new store) never reuses old identifiers."""

    first_run = SessionStore()
    restarted_run = SessionStore()

    old_session = await first_run.create("operator@example.com")
    new_session = await restarted_run.create("operator@example.com")

    assert re.fullmatch(
        IDENTIFIER_PATTERN.format(prefix="INTAKE"), new_session.session_id
    )
    assert re.fullmatch(IDENTIFIER_PATTERN.format(prefix="REQ"), new_session.request_id)
    assert new_session.session_id != old_session.session_id
    assert new_session.request_id != old_session.request_id
