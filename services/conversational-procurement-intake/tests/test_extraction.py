"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Tests for deterministic conversational intake extraction.
"""

from __future__ import annotations

import pytest

from conversational_procurement_intake.extraction import DeterministicIntakeExtractor
from conversational_procurement_intake.master_data import StaticMasterDataResolver


@pytest.mark.anyio
async def test_extractor_requests_missing_response_deadline() -> None:
    """Ask for clarification when a mandatory deadline is missing."""

    extractor = DeterministicIntakeExtractor(StaticMasterDataResolver())

    result = await extractor.extract(
        "We need 10 high density battery modules for Munich by June 15.",
        "operator@example.com",
        1,
    )

    assert result.orchestration_request is None
    assert "response_deadline" in result.missing_fields
    assert result.message == "Which bid response deadline should I use?"


@pytest.mark.anyio
async def test_extractor_builds_orchestration_request_with_defaults() -> None:
    """Build a valid orchestration request after all mandatory fields exist."""

    extractor = DeterministicIntakeExtractor(StaticMasterDataResolver())

    result = await extractor.extract(
        (
            "We need 10 high density battery modules for Munich by June 15. "
            "Bid deadline May 29 at 12. Ask up to 3 European suppliers and "
            "create the purchase order automatically."
        ),
        "operator@example.com",
        7,
    )

    request = result.orchestration_request
    assert request is not None
    assert request.request_id == "REQ-2026-0007"
    assert request.currency == "EUR"
    assert request.auto_create_purchase_order is True
    assert request.sourcing_constraints.allowed_regions == ["EU"]
    assert request.parts[0].part_id == "PART-001"
    assert request.parts[0].plant_code == "DE-MUN"
    assert request.parts[0].unit_of_measure == "EA"
    assert result.missing_fields == []
    assert {item.field for item in result.defaults_applied} >= {
        "currency",
        "evaluation_policy_id",
    }


@pytest.mark.anyio
async def test_extractor_does_not_use_delivery_day_as_quantity() -> None:
    """Do not infer quantity from dates in a clarification message."""

    extractor = DeterministicIntakeExtractor(StaticMasterDataResolver())

    result = await extractor.extract(
        (
            "We need battery modules for the Munich plant as soon as possible. "
            "Required delivery date is June 15. Bid deadline is today at 17:00. "
            "Ask up to 3 European suppliers and create the purchase order "
            "automatically."
        ),
        "operator@example.com",
        8,
    )

    assert result.orchestration_request is None
    assert "parts[0].quantity" in result.missing_fields
    assert result.message == "What quantity do you need?"


@pytest.mark.anyio
async def test_extractor_reads_quantity_from_units_clarification() -> None:
    """Accept quantity when the user provides it with units."""

    extractor = DeterministicIntakeExtractor(StaticMasterDataResolver())

    result = await extractor.extract(
        (
            "We need battery modules for the Munich plant as soon as possible. "
            "Quantity is 10 units. Required delivery date is June 15. "
            "Bid deadline is today at 17:00. Ask up to 3 European suppliers "
            "and create the purchase order automatically."
        ),
        "operator@example.com",
        9,
    )

    request = result.orchestration_request
    assert request is not None
    assert request.parts[0].quantity == 10
