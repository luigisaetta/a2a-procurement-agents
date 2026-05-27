"""
Tests for Offer Evaluation Agent pipeline checks.

Author: L. Saetta
Date Last Modified: 2026-05-27
License: MIT
Description:    Verifies response parsing and technical consistency checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from test_client import load_jsonc

from offer_evaluation_agent.models import (
    EvaluationDecision,
    EvaluateOffersRequest,
    EvaluateOffersResponse,
    SelectedOfferPayload,
    SupplierOffer,
)
from offer_evaluation_agent.pipeline import (
    OfferEvaluationWorkflowAgent,
    _extract_json_object,
)


def _request() -> EvaluateOffersRequest:
    return EvaluateOffersRequest(
        request_id="REQ-2026-0001",
        plant_code="PLANT-01",
        material_code="MAT-12345",
        material_description="Industrial pump replacement kit",
        quantity=10,
        unit_of_measure="EA",
        currency="EUR",
        required_delivery_date="2026-06-15",
        evaluation_policy_id="standard-urgent-procurement-v1",
        offers=[
            SupplierOffer(
                offer_id="OFF-001",
                supplier_id="SUP-001",
                supplier_name="Supplier A",
                price=12000.0,
                currency="EUR",
                delivery_date="2026-06-10",
                quality_score=92,
                reliability_score=88,
                valid_until="2026-06-01",
            )
        ],
    )


def test_extract_json_object_from_plain_json() -> None:
    """Accept a raw JSON object response."""

    raw = '{"request_id": "REQ-1"}'
    assert _extract_json_object(raw) == raw


def test_extract_json_object_from_text() -> None:
    """Extract JSON from a response that includes surrounding text."""

    assert _extract_json_object('Here: {"request_id": "REQ-1"} done') == (
        '{"request_id": "REQ-1"}'
    )


def test_sample_payload_has_expected_winner() -> None:
    """Load the sample JSONC payload and verify its expected structure."""

    sample_path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "sample-evaluate-offers-request.jsonc"
    )
    payload = load_jsonc(sample_path)

    assert payload["request_id"] == "REQ-2026-0001"
    assert len(payload["offers"]) == 3
    assert payload["offers"][1]["offer_id"] == "OFF-002"
    assert payload["offers"][2]["delivery_date"] > payload["required_delivery_date"]


def test_consistency_accepts_source_offer() -> None:
    """Accept a selected offer only when it matches the input offer."""

    request = _request()
    response = EvaluateOffersResponse(
        request_id=request.request_id,
        decision=EvaluationDecision(
            status="selected_offer",
            selected_offer=SelectedOfferPayload.model_validate(
                request.offers[0].model_dump(mode="json")
            ),
            reasons=[],
        ),
        explanation="Supplier A was selected.",
    )
    agent = OfferEvaluationWorkflowAgent.__new__(OfferEvaluationWorkflowAgent)

    agent.validate_consistency(request, response)


def test_consistency_rejects_modified_selected_offer() -> None:
    """Reject LLM output that changes selected offer details."""

    request = _request()
    modified = request.offers[0].model_copy(update={"price": 1.0})
    response = EvaluateOffersResponse(
        request_id=request.request_id,
        decision=EvaluationDecision(
            status="selected_offer",
            selected_offer=SelectedOfferPayload.model_validate(
                modified.model_dump(mode="json")
            ),
            reasons=[],
        ),
        explanation="Supplier A was selected.",
    )
    agent = OfferEvaluationWorkflowAgent.__new__(OfferEvaluationWorkflowAgent)

    with pytest.raises(ValueError, match="Selected offer details do not match"):
        agent.validate_consistency(request, response)


def test_consistency_rejects_no_valid_without_reasons() -> None:
    """Reject no-valid-offers decisions that omit reasons."""

    request = _request()
    response = EvaluateOffersResponse(
        request_id=request.request_id,
        decision=EvaluationDecision(
            status="no_valid_offers",
            selected_offer=_empty_selected_offer(),
            reasons=[],
        ),
        explanation="No supplier offer was selected.",
    )
    agent = OfferEvaluationWorkflowAgent.__new__(OfferEvaluationWorkflowAgent)

    with pytest.raises(ValueError, match="must include at least one reason"):
        agent.validate_consistency(request, response)


def _empty_selected_offer() -> SelectedOfferPayload:
    """Return the placeholder selected offer for no-valid-offers responses."""

    return SelectedOfferPayload(
        offer_id="",
        supplier_id="",
        supplier_name="",
        price=0,
        currency="",
        delivery_date="",
        quality_score=0,
        reliability_score=0,
        valid_until="",
    )
