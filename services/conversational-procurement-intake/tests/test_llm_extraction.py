"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Tests for LLM-backed conversational intake extraction.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from conversational_procurement_intake.extraction import CandidateIntakeFields
from conversational_procurement_intake.llm_extraction import LLMIntakeExtractor
from conversational_procurement_intake.master_data import StaticMasterDataResolver


class FakeLLMClient:  # pylint: disable=too-few-public-methods
    """Fake structured LLM client returning a configured candidate."""

    def __init__(self, candidate: CandidateIntakeFields) -> None:
        """Initialize the fake client."""

        self.candidate = candidate

    async def extract_candidate(self, text: str) -> CandidateIntakeFields:
        """Return the configured candidate."""

        _ = text
        return self.candidate


@pytest.mark.anyio
async def test_llm_extractor_builds_grounded_request() -> None:
    """Ground LLM candidate fields through master data before final JSON."""

    extractor = LLMIntakeExtractor(
        FakeLLMClient(
            CandidateIntakeFields(
                material_reference="high density battery module",
                plant_reference="Munich",
                quantity=10,
                required_delivery_date=date(2026, 6, 15),
                response_deadline=datetime(2026, 5, 29, 12, 0, tzinfo=UTC),
                auto_create_purchase_order=True,
                max_suppliers_per_part=3,
                allowed_regions=["EU"],
            )
        ),
        StaticMasterDataResolver(),
    )

    result = await extractor.extract(
        "We need 10 high density battery modules for Munich by June 15. "
        "Bid deadline May 29 at 12.",
        "operator@example.com",
        12,
    )

    request = result.orchestration_request
    assert request is not None
    assert request.request_id == "REQ-2026-0012"
    assert request.parts[0].part_id == "PART-001"
    assert request.parts[0].material_code == "EV-BAT-MOD-001"
    assert request.parts[0].plant_code == "DE-MUN"


@pytest.mark.anyio
async def test_llm_extractor_reports_missing_fields_from_candidate() -> None:
    """Return clarification when the LLM marks missing mandatory data."""

    extractor = LLMIntakeExtractor(
        FakeLLMClient(
            CandidateIntakeFields(
                material_reference="high density battery module",
                plant_reference="Munich",
                quantity=10,
                required_delivery_date=date(2026, 6, 15),
                missing_fields=["response_deadline"],
                clarification_question="Which bid response deadline should I use?",
            )
        ),
        StaticMasterDataResolver(),
    )

    result = await extractor.extract(
        "User conversation text.",
        "operator@example.com",
        12,
    )

    assert result.orchestration_request is None
    assert "response_deadline" in result.missing_fields
    assert result.message == "Which bid response deadline should I use?"


@pytest.mark.anyio
async def test_llm_extractor_does_not_fill_empty_candidate_fields() -> None:
    """Keep the LLM responsible for extraction in default mode."""

    extractor = LLMIntakeExtractor(
        FakeLLMClient(
            CandidateIntakeFields(
                material_reference="",
                plant_reference="",
                quantity=None,
                required_delivery_date=None,
                response_deadline=None,
                missing_fields=[
                    "parts[0].material_code",
                    "parts[0].plant_code",
                    "parts[0].quantity",
                    "parts[0].required_delivery_date",
                    "response_deadline",
                ],
            )
        ),
        StaticMasterDataResolver(),
    )

    result = await extractor.extract(
        "We need 10 high density battery modules for the Munich plant by "
        "June 15. Bid deadline today at 17:00. Ask up to 3 European "
        "suppliers and create the purchase order automatically.",
        "operator@example.com",
        12,
    )

    assert result.orchestration_request is None
    assert result.missing_fields == [
        "parts[0].material_code",
        "parts[0].plant_code",
        "parts[0].quantity",
        "parts[0].required_delivery_date",
        "response_deadline",
    ]


@pytest.mark.anyio
async def test_llm_extractor_normalizes_region_aliases() -> None:
    """Normalize natural-language region aliases before orchestration."""

    extractor = LLMIntakeExtractor(
        FakeLLMClient(
            CandidateIntakeFields(
                material_reference="high density battery module",
                plant_reference="Munich",
                quantity=10,
                required_delivery_date=date(2026, 6, 15),
                response_deadline=datetime(2026, 5, 29, 17, 0, tzinfo=UTC),
                auto_create_purchase_order=True,
                max_suppliers_per_part=3,
                allowed_regions=["Europe"],
            )
        ),
        StaticMasterDataResolver(),
    )

    result = await extractor.extract(
        "We need 10 high density battery modules for the Munich plant by "
        "June 15. Bid deadline today at 17:00. Ask up to 3 European "
        "suppliers and create the purchase order automatically.",
        "operator@example.com",
        12,
    )

    request = result.orchestration_request
    assert request is not None
    assert request.sourcing_constraints.allowed_regions == ["EU"]


@pytest.mark.anyio
async def test_llm_extractor_rejects_unevidenced_quantity() -> None:
    """Reject LLM quantities that are not supported by the conversation."""

    extractor = LLMIntakeExtractor(
        FakeLLMClient(
            CandidateIntakeFields(
                material_reference="battery modules",
                plant_reference="Munich",
                quantity=15,
                required_delivery_date=date(2026, 6, 15),
                response_deadline=datetime(2026, 5, 29, 17, 0, tzinfo=UTC),
                auto_create_purchase_order=True,
                max_suppliers_per_part=3,
                allowed_regions=["EU"],
            )
        ),
        StaticMasterDataResolver(),
    )

    result = await extractor.extract(
        "We need battery modules for the Munich plant as soon as possible. "
        "Required delivery date is June 15. Bid deadline is today at 17:00. "
        "Ask up to 3 European suppliers and create the purchase order "
        "automatically.",
        "operator@example.com",
        13,
    )

    assert result.orchestration_request is None
    assert result.missing_fields == ["parts[0].quantity"]
    assert result.message == "What quantity do you need?"
