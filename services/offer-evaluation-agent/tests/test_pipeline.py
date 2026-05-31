"""
Tests for Offer Evaluation Agent pipeline checks.

Author: L. Saetta
Date Last Modified: 2026-05-31
License: MIT
Description:    Verifies response parsing and technical consistency checks.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from locus.agent.hook_orchestrator import HookOrchestrator
from pydantic import ValidationError

from test_client import load_jsonc

from offer_evaluation_agent.config import Settings
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
    enforce_policy_consistency,
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


def _settings() -> Settings:
    """Build test settings."""

    root = Path(__file__).resolve().parents[3]
    return Settings(
        oci_region="us-chicago-1",
        oci_auth="API_KEY",
        oci_model_id="openai.gpt-5",
        oci_compartment_id="ocid1.compartment.oc1..example",
        agent_port=8001,
        agent_api_key="secret",
        oci_profile="DEFAULT",
        oci_endpoint="https://example.com/openai/v1",
        policy_file=(
            root
            / "services/offer-evaluation-agent/policies"
            / "standard-urgent-procurement-v1.md"
        ),
        request_schema_file=root / "specs/schemas/evaluate-offers-request.schema.json",
        response_schema_file=root
        / "specs/schemas/evaluate-offers-response.schema.json",
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


def test_policy_guardrail_selects_valid_offer_when_llm_says_no_valid() -> None:
    """Correct false no-valid-offers decisions when eligible offers exist."""

    request = _request()
    response = EvaluateOffersResponse(
        request_id=request.request_id,
        decision=EvaluationDecision(
            status="no_valid_offers",
            selected_offer=_empty_selected_offer(),
            reasons=["No offer matched the policy."],
        ),
        explanation="No valid offer.",
    )

    guarded = enforce_policy_consistency(request, response)

    assert guarded.decision.status == "selected_offer"
    assert guarded.decision.selected_offer.offer_id == "OFF-001"
    assert guarded.decision.reasons == []


def test_policy_guardrail_selects_lowest_eligible_offer() -> None:
    """Correct selected offers that are valid but not policy-optimal."""

    request = _request().model_copy(
        update={
            "offers": [
                _request().offers[0],
                SupplierOffer(
                    offer_id="OFF-002",
                    supplier_id="SUP-002",
                    supplier_name="Supplier B",
                    price=9000.0,
                    currency="EUR",
                    delivery_date="2026-06-12",
                    quality_score=85,
                    reliability_score=86,
                    valid_until="2026-06-01",
                ),
            ]
        }
    )
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

    guarded = enforce_policy_consistency(request, response)

    assert guarded.decision.status == "selected_offer"
    assert guarded.decision.selected_offer.offer_id == "OFF-002"


@pytest.mark.anyio
async def test_pipeline_runs_locus_hooks_for_success() -> None:
    """Run Locus lifecycle hooks around a successful offer evaluation."""

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
    hook = _RecordingHook()
    # pylint: disable=protected-access
    agent = OfferEvaluationWorkflowAgent.__new__(OfferEvaluationWorkflowAgent)
    agent._settings = _settings()
    agent._decision_agent = _FakeDecisionAgent(response)
    agent._hook_orchestrator = HookOrchestrator([hook])

    events = [event async for event in agent.run(request.model_dump_json())]

    final = json.loads(events[-1].final_message)
    assert final["decision"]["status"] == "selected_offer"
    assert hook.after_success == [True]
    assert hook.after_agent_ids == ["offer-evaluation-agent"]


@pytest.mark.anyio
async def test_pipeline_runs_locus_hooks_for_validation_error() -> None:
    """Run Locus lifecycle hooks when offer request validation fails."""

    hook = _RecordingHook()
    # pylint: disable=protected-access
    agent = OfferEvaluationWorkflowAgent.__new__(OfferEvaluationWorkflowAgent)
    agent._settings = _settings()
    agent._decision_agent = _FakeDecisionAgent(None)
    agent._hook_orchestrator = HookOrchestrator([hook])

    with pytest.raises(ValidationError):
        async for _event in agent.run("{}"):
            pass

    assert hook.after_success == [False]
    assert hook.after_error_counts == [1]


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


class _FakeDecisionAgent:  # pylint: disable=too-few-public-methods
    """Fake Locus decision agent for pipeline tests."""

    def __init__(self, response: EvaluateOffersResponse | None) -> None:
        """Initialize the fake decision response."""

        self._response = response

    def run_sync(self, _prompt: str):
        """Return a fake Locus AgentResult-like object."""

        return SimpleNamespace(parsed=self._response, message="")


class _RecordingHook:
    """Record Locus lifecycle hook calls for assertions."""

    def __init__(self) -> None:
        """Initialize recorded hook call lists."""

        self.after_success: list[bool] = []
        self.after_agent_ids: list[str | None] = []
        self.after_error_counts: list[int] = []

    async def on_before_invocation(self, _prompt, state):
        """Return state unchanged from before-invocation."""

        return state

    async def on_after_invocation(self, state, success):
        """Record after-invocation calls."""

        self.after_success.append(success)
        self.after_agent_ids.append(state.agent_id)
        self.after_error_counts.append(len(state.errors))
