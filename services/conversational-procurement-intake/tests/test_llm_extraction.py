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
        "User conversation text.",
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
