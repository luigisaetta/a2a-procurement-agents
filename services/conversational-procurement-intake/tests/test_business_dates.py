"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Tests for relative date resolution and date validation in the
                conversational intake layer.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from conversational_procurement_intake.business_clock import BUSINESS_TIMEZONE
from conversational_procurement_intake.extraction import (
    CandidateIntakeFields,
    DeterministicIntakeExtractor,
    ExtractionResult,
    build_extraction_result,
)
from conversational_procurement_intake.master_data import StaticMasterDataResolver

# 08:00 in Rome is 06:00 UTC.
NOW = datetime(2026, 10, 24, 8, 0, tzinfo=BUSINESS_TIMEZONE)

REQUEST_START = "We need 10 high density battery modules for Munich. "


async def _extract(text: str) -> ExtractionResult:
    """Run the deterministic extractor on 2026-10-24."""

    extractor = DeterministicIntakeExtractor(
        StaticMasterDataResolver(), clock=lambda: NOW
    )
    return await extractor.extract(text, "operator@example.com", "REQ-TEST-0001")


async def _ground(candidate: CandidateIntakeFields) -> ExtractionResult:
    """Validate candidate fields, as produced by the LLM, on 2026-10-24."""

    return await build_extraction_result(
        candidate,
        StaticMasterDataResolver(),
        "operator@example.com",
        "REQ-TEST-0001",
        NOW,
    )


def _llm_candidate(
    required_delivery_date: date, response_deadline: datetime
) -> CandidateIntakeFields:
    """Build complete candidate fields with the given dates."""

    return CandidateIntakeFields(
        material_reference="high density battery module",
        plant_reference="Munich",
        quantity=10,
        required_delivery_date=required_delivery_date,
        response_deadline=response_deadline,
    )


@pytest.mark.anyio
async def test_today_means_the_current_business_date() -> None:
    """A deadline "today" uses the clock date, not a fixed demo date."""

    result = await _extract(
        REQUEST_START + "Delivery by November 20. Bid deadline is today at 17:00."
    )

    request = result.orchestration_request
    assert request is not None
    assert request.response_deadline == datetime(2026, 10, 24, 17, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_dates_without_year_resolve_to_their_next_occurrence() -> None:
    """On 2026-10-24, June 15 and May 29 already passed, so they mean 2027."""

    result = await _extract(REQUEST_START + "By June 15. Bid deadline May 29 at 12.")

    request = result.orchestration_request
    assert request is not None
    assert request.parts[0].required_delivery_date == date(2027, 6, 15)
    assert request.response_deadline == datetime(2027, 5, 29, 12, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_dates_in_the_past_are_rejected_with_a_reason() -> None:
    """Past ISO dates are removed and asked again, saying why."""

    result = await _extract(
        REQUEST_START + "The required delivery date is 2026-07-25. "
        "The bid response deadline is 2026-06-15 at 17:00 UTC."
    )

    assert result.orchestration_request is None
    assert result.missing_fields == [
        "parts[0].required_delivery_date",
        "response_deadline",
    ]
    assert result.message.startswith(
        "The bid response deadline 2026-06-15 17:00 UTC is in the past. "
        "The required delivery date 2026-07-25 is in the past. "
    )
    assert "Which bid response deadline should I use?" in result.message


@pytest.mark.anyio
async def test_delivery_before_the_deadline_is_rejected() -> None:
    """A delivery date before the bid deadline cannot be awarded in time."""

    result = await _ground(
        _llm_candidate(date(2026, 11, 10), datetime(2026, 11, 20, 17, 0, tzinfo=UTC))
    )

    assert result.orchestration_request is None
    assert result.missing_fields == ["parts[0].required_delivery_date"]
    assert result.message.startswith(
        "The required delivery date 2026-11-10 is before the bid response "
        "deadline 2026-11-20 17:00 UTC."
    )


@pytest.mark.anyio
@pytest.mark.parametrize("delivery_text", ["By June 31.", "By Friday 3."])
async def test_impossible_or_unknown_dates_are_asked_again(delivery_text: str) -> None:
    """An impossible day or unknown month is a missing value, not a crash."""

    result = await _extract(
        REQUEST_START + delivery_text + " Bid deadline November 2 at 12."
    )

    assert result.orchestration_request is None
    assert result.missing_fields == ["parts[0].required_delivery_date"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("deadline_hour", "is_accepted"),
    [(7, True), (5, False)],
)
async def test_deadline_without_timezone_is_read_as_utc(
    deadline_hour: int, is_accepted: bool
) -> None:
    """At 06:00 UTC, a naive 07:00 deadline is future and 05:00 is past."""

    naive_deadline = datetime(2026, 10, 24, deadline_hour, 0)

    result = await _ground(_llm_candidate(date(2026, 11, 20), naive_deadline))

    assert (result.orchestration_request is not None) is is_accepted


@pytest.mark.anyio
async def test_delivery_without_year_is_counted_from_the_deadline() -> None:
    """On 2026-06-20 the deadline moves to 2027, and delivery follows it."""

    extractor = DeterministicIntakeExtractor(
        StaticMasterDataResolver(),
        clock=lambda: datetime(2026, 6, 20, 8, 0, tzinfo=BUSINESS_TIMEZONE),
    )

    result = await extractor.extract(
        REQUEST_START + "Required delivery date is July 25. "
        "Bid response deadline is June 15 at 17:00 UTC.",
        "operator@example.com",
        "REQ-TEST-0001",
    )

    request = result.orchestration_request
    assert request is not None
    assert request.response_deadline == datetime(2027, 6, 15, 17, 0, tzinfo=UTC)
    assert request.parts[0].required_delivery_date == date(2027, 7, 25)
