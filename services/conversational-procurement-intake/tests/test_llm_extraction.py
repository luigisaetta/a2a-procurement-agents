"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Tests for LLM-backed conversational intake extraction.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from conversational_procurement_intake.business_clock import BUSINESS_TIMEZONE
from conversational_procurement_intake.extraction import CandidateIntakeFields
from conversational_procurement_intake.llm_extraction import (
    LLMIntakeExtractor,
    _build_prompt,
)
from conversational_procurement_intake.master_data import StaticMasterDataResolver

# The tests were written for this business date; a fixed clock keeps
# relative dates such as "June 15" or "today" stable over time.
DEMO_NOW = datetime(2026, 5, 29, 8, 0, tzinfo=BUSINESS_TIMEZONE)


def demo_clock() -> datetime:
    """Return the fixed business time used by these tests."""

    return DEMO_NOW


class FakeLLMClient:  # pylint: disable=too-few-public-methods
    """Fake structured LLM client returning a configured candidate."""

    def __init__(self, candidate: CandidateIntakeFields) -> None:
        """Initialize the fake client."""

        self.candidate = candidate
        self.received_today: date | None = None

    async def extract_candidate(self, text: str, today: date) -> CandidateIntakeFields:
        """Return the configured candidate and record the business date."""

        _ = text
        self.received_today = today
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
        clock=demo_clock,
    )

    result = await extractor.extract(
        "We need 10 high density battery modules for Munich by June 15. "
        "Bid deadline May 29 at 12.",
        "operator@example.com",
        "REQ-TEST-0012",
    )

    request = result.orchestration_request
    assert request is not None
    assert request.request_id == "REQ-TEST-0012"
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
        clock=demo_clock,
    )

    result = await extractor.extract(
        "We need 10 high density battery modules for Munich by June 15.",
        "operator@example.com",
        "REQ-TEST-0012",
    )

    assert result.orchestration_request is None
    assert "response_deadline" in result.missing_fields
    assert result.message == "Which bid response deadline should I use?"


@pytest.mark.anyio
async def test_llm_extractor_asks_all_missing_fields() -> None:
    """Do not preserve a single LLM question when multiple fields are missing."""

    extractor = LLMIntakeExtractor(
        FakeLLMClient(
            CandidateIntakeFields(
                material_reference="battery modules",
                plant_reference="Munich",
                quantity=None,
                required_delivery_date=None,
                response_deadline=None,
                clarification_question="Which bid response deadline should I use?",
                missing_fields=[
                    "parts[0].quantity",
                    "parts[0].required_delivery_date",
                    "response_deadline",
                ],
            )
        ),
        StaticMasterDataResolver(),
        clock=demo_clock,
    )

    result = await extractor.extract(
        "We need battery modules for the Munich plant as soon as possible.",
        "operator@example.com",
        "REQ-TEST-0012",
    )

    assert result.orchestration_request is None
    assert result.missing_fields == [
        "parts[0].quantity",
        "parts[0].required_delivery_date",
        "response_deadline",
    ]
    assert result.message == (
        "Please provide these missing details: What quantity do you need? "
        "What required delivery date should I use? "
        "Which bid response deadline should I use?"
    )


@pytest.mark.anyio
async def test_llm_extractor_grounds_empty_references_from_conversation_text() -> None:
    """Ground references from text without inventing other empty fields."""

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
        clock=demo_clock,
    )

    result = await extractor.extract(
        "We need 10 high density battery modules for the Munich plant by "
        "June 15. Bid deadline today at 17:00. Ask up to 3 European "
        "suppliers and create the purchase order automatically.",
        "operator@example.com",
        "REQ-TEST-0012",
    )

    assert result.orchestration_request is None
    assert result.missing_fields == [
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
        clock=demo_clock,
    )

    result = await extractor.extract(
        "We need 10 high density battery modules for the Munich plant by "
        "June 15. Bid deadline today at 17:00. Ask up to 3 European "
        "suppliers and create the purchase order automatically.",
        "operator@example.com",
        "REQ-TEST-0012",
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
        clock=demo_clock,
    )

    result = await extractor.extract(
        "We need battery modules for the Munich plant as soon as possible. "
        "Required delivery date is June 15. Bid deadline is today at 17:00. "
        "Ask up to 3 European suppliers and create the purchase order "
        "automatically.",
        "operator@example.com",
        "REQ-TEST-0013",
    )

    assert result.orchestration_request is None
    assert result.missing_fields == ["parts[0].quantity"]
    assert result.message == "What quantity do you need?"


def test_prompt_states_the_current_business_date() -> None:
    """The LLM prompt carries the real current date, not a fixed demo date."""

    prompt = _build_prompt("Bid deadline tomorrow.", date(2026, 10, 24))

    assert "Current date: 2026-10-24." in prompt
    assert "Timezone for relative business interpretation: Europe/Rome." in prompt
    assert "2026-05-29" not in prompt


@pytest.mark.anyio
async def test_llm_extractor_passes_the_clock_date_to_the_llm() -> None:
    """The extractor reads the clock once and gives its date to the LLM client."""

    llm_client = FakeLLMClient(CandidateIntakeFields())
    extractor = LLMIntakeExtractor(
        llm_client, StaticMasterDataResolver(), clock=demo_clock
    )

    await extractor.extract("We need parts.", "operator@example.com", "REQ-TEST-0014")

    assert llm_client.received_today == DEMO_NOW.date()


def _candidate_with_quantity_ten() -> CandidateIntakeFields:
    """Return the fields an LLM extracts from the Turin urgent request."""

    return CandidateIntakeFields(
        material_reference="high density battery module",
        plant_reference="Turin",
        quantity=10,
        required_delivery_date=date(2026, 11, 30),
        response_deadline=datetime(2026, 11, 15, 12, 0, tzinfo=UTC),
        max_suppliers_per_part=10,
        allowed_regions=["EU"],
    )


@pytest.mark.anyio
async def test_llm_extractor_keeps_quantity_after_an_adverb() -> None:
    """ "I need urgently 10 ..." is quantity evidence, not a reason to ask again."""

    extractor = LLMIntakeExtractor(
        FakeLLMClient(_candidate_with_quantity_ten()),
        StaticMasterDataResolver(),
        clock=demo_clock,
    )

    result = await extractor.extract(
        "I need urgently 10 high density battery modules to be delivered by end "
        "of november in Turin plant. Invite 10 eu suppliers bid must end before "
        "15 of november at 12 PM",
        "operator@example.com",
        "REQ-TEST-0015",
    )

    assert result.orchestration_request is not None
    assert result.orchestration_request.parts[0].quantity == 10


@pytest.mark.anyio
async def test_llm_extractor_accepts_a_plain_number_reply() -> None:
    """A supplier count is not a quantity, but a plain "10" reply is."""

    extractor = LLMIntakeExtractor(
        FakeLLMClient(_candidate_with_quantity_ten()),
        StaticMasterDataResolver(),
        clock=demo_clock,
    )
    first_message = (
        "Please source high density battery modules for the Turin plant by end "
        "of november. Invite 10 eu suppliers, bid ends 15 of november at 12 PM"
    )

    first = await extractor.extract(
        first_message, "operator@example.com", "REQ-TEST-0016"
    )
    after_reply = await extractor.extract(
        first_message + "\n10", "operator@example.com", "REQ-TEST-0016"
    )

    assert first.missing_fields == ["parts[0].quantity"]
    assert after_reply.orchestration_request is not None
    assert after_reply.orchestration_request.parts[0].quantity == 10
