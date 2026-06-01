"""
Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    Runs a deterministic 20-case accuracy suite through the
                Offer Evaluation Agent workflow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from locus.agent.hook_orchestrator import HookOrchestrator

# pylint: disable=wrong-import-position, trailing-newlines
SERVICE_SRC = Path(__file__).resolve().parents[2] / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

from offer_evaluation_agent.config import Settings
from offer_evaluation_agent.models import (
    EvaluateOffersRequest,
    EvaluateOffersResponse,
)
from offer_evaluation_agent.pipeline import OfferEvaluationWorkflowAgent

CASES_FILE = Path(__file__).with_name("offer-evaluation-accuracy-cases.json")


def _load_cases() -> list[dict[str, Any]]:
    """Load accuracy cases from the dedicated JSON fixture."""

    return json.loads(CASES_FILE.read_text(encoding="utf-8"))


def _settings() -> Settings:
    """Build local settings for the accuracy workflow test."""

    root = Path(__file__).resolve().parents[4]
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


@pytest.mark.anyio
async def test_offer_evaluation_accuracy_suite() -> None:
    """Evaluate all accuracy cases and assert the expected selected winner."""

    results = []
    for case in _load_cases():
        request = EvaluateOffersRequest.model_validate(case["request"])
        response = await _run_offer_evaluator(request)
        decision = response["decision"]
        expected = case["expected"]
        actual_offer_id = (
            decision["selected_offer"]["offer_id"]
            if decision["status"] == "selected_offer"
            else None
        )
        passed = (
            decision["status"] == expected["status"]
            and actual_offer_id == expected["offer_id"]
        )
        results.append(
            {
                "case_id": case["case_id"],
                "expected_status": expected["status"],
                "expected_offer_id": expected["offer_id"],
                "actual_status": decision["status"],
                "actual_offer_id": actual_offer_id,
                "passed": passed,
            }
        )

    failures = [result for result in results if not result["passed"]]
    assert not failures, json.dumps(failures, indent=2)


async def _run_offer_evaluator(request: EvaluateOffersRequest) -> dict[str, Any]:
    """Run a request through the Offer Evaluation Agent workflow."""

    # pylint: disable=protected-access
    agent = OfferEvaluationWorkflowAgent.__new__(OfferEvaluationWorkflowAgent)
    agent._settings = _settings()
    agent._decision_agent = _AlwaysNoValidDecisionAgent(request.request_id)
    agent._hook_orchestrator = HookOrchestrator([])

    events = [event async for event in agent.run(request.model_dump_json())]
    return json.loads(events[-1].final_message)


class _AlwaysNoValidDecisionAgent:  # pylint: disable=too-few-public-methods
    """Return a deliberately weak LLM decision for guardrail accuracy testing."""

    def __init__(self, request_id: str) -> None:
        """Initialize the fake decision agent for one request."""

        self._request_id = request_id

    def run_sync(self, _prompt: str):
        """Return a no-valid-offers response before policy guardrails run."""

        response = EvaluateOffersResponse(
            request_id=self._request_id,
            decision={
                "status": "no_valid_offers",
                "selected_offer": {
                    "offer_id": "",
                    "supplier_id": "",
                    "supplier_name": "",
                    "price": 0,
                    "currency": "",
                    "delivery_date": "",
                    "quality_score": 0,
                    "reliability_score": 0,
                    "valid_until": "",
                },
                "reasons": ["The simulated evaluator did not select an offer."],
            },
            explanation="The simulated evaluator returned no valid offers.",
        )
        return SimpleNamespace(parsed=response, message="")
