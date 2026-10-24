"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Runs the 20-case accuracy suite for the Offer Evaluation Agent.
                The offline test checks that the workflow returns the LLM
                decision unchanged; the opt-in live test measures how often
                the configured LLM makes the expected decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
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

from offer_evaluation_agent.config import Settings, load_settings
from offer_evaluation_agent.models import (
    EvaluateOffersRequest,
    EvaluateOffersResponse,
)
from offer_evaluation_agent.pipeline import (
    OfferEvaluationWorkflowAgent,
    build_workflow_agent,
)

CASES_FILE = Path(__file__).with_name("offer-evaluation-accuracy-cases.json")
REPORTS_DIR = Path(__file__).with_name("results")
RUN_LIVE_LLM_ENV = "OFFER_EVALUATION_RUN_LIVE_LLM"

PLACEHOLDER_OFFER = {
    "offer_id": "",
    "supplier_id": "",
    "supplier_name": "",
    "price": 0,
    "currency": "",
    "delivery_date": "",
    "quality_score": 0,
    "reliability_score": 0,
    "valid_until": "",
}


def _load_cases() -> list[dict[str, Any]]:
    """Load accuracy cases from the dedicated JSON fixture."""

    return json.loads(CASES_FILE.read_text(encoding="utf-8"))


def _settings() -> Settings:
    """Build local settings for the offline accuracy workflow test."""

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
async def test_workflow_returns_the_llm_decision_for_every_case() -> None:
    """Feed each expected decision as the LLM answer; it must come back unchanged.

    This checks, without a live LLM, that the workflow never overrides the LLM
    decision and that every recorded expected decision passes the technical
    consistency checks.
    """

    failures = []
    for case in _load_cases():
        request = EvaluateOffersRequest.model_validate(case["request"])
        agent = _offline_agent(_ExpectedDecisionAgent(case, request))

        response = await _run_workflow(agent, request)

        status, offer_id = _outcome(response)
        expected = case["expected"]
        if status != expected["status"] or offer_id != expected["offer_id"]:
            failures.append({"case_id": case["case_id"], "actual": [status, offer_id]})

    assert not failures, json.dumps(failures, indent=2)


@pytest.mark.anyio
async def test_live_llm_accuracy_report() -> None:
    """Send every case to the configured LLM and report its accuracy."""

    if os.environ.get(RUN_LIVE_LLM_ENV) != "1":
        pytest.skip(f"Set {RUN_LIVE_LLM_ENV}=1 to run live LLM accuracy reporting.")

    try:
        settings = load_settings()
    except RuntimeError as exc:
        pytest.skip(f"Live LLM settings are not available: {exc}")

    agent = build_workflow_agent(settings)
    results = [await _evaluate_live_case(case, agent) for case in _load_cases()]

    report = _build_live_llm_report(settings, results)
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / "latest-llm-accuracy-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    assert report["error_count"] == 0, json.dumps(
        [result for result in results if not result["correct"]],
        indent=2,
    )


async def _evaluate_live_case(
    case: dict[str, Any],
    agent: OfferEvaluationWorkflowAgent,
) -> dict[str, Any]:
    """Evaluate one case with the live LLM through the full workflow."""

    request = EvaluateOffersRequest.model_validate(case["request"])
    expected = case["expected"]
    technical_error = ""
    try:
        status, offer_id = _outcome(await _run_workflow(agent, request))
    # A rejected or failed LLM answer is a wrong case, not a crash of the report.
    except Exception as exc:  # pylint: disable=broad-exception-caught
        status, offer_id = "error", None
        technical_error = f"{type(exc).__name__}: {exc}"

    return {
        "case_id": case["case_id"],
        "expected_status": expected["status"],
        "accepted_offer_ids": _accepted_offer_ids(expected),
        "llm_status": status,
        "llm_offer_id": offer_id,
        "technical_error": technical_error,
        "correct": _matches_expected(status, offer_id, expected),
    }


def _offline_agent(decision_agent: Any) -> OfferEvaluationWorkflowAgent:
    """Build a workflow agent that uses a fake decision agent instead of OCI."""

    # pylint: disable=protected-access
    agent = OfferEvaluationWorkflowAgent.__new__(OfferEvaluationWorkflowAgent)
    agent._settings = _settings()
    agent._decision_agent = decision_agent
    agent._hook_orchestrator = HookOrchestrator([])
    return agent


async def _run_workflow(
    agent: OfferEvaluationWorkflowAgent, request: EvaluateOffersRequest
) -> dict[str, Any]:
    """Run one request through the workflow and return the final response."""

    events = [event async for event in agent.run(request.model_dump_json())]
    return json.loads(events[-1].final_message)


def _outcome(response: dict[str, Any]) -> tuple[str, str | None]:
    """Return the decision status and selected offer id of a response."""

    decision = response["decision"]
    if decision["status"] != "selected_offer":
        return decision["status"], None
    return decision["status"], decision["selected_offer"]["offer_id"]


def _accepted_offer_ids(expected: dict[str, Any]) -> list[str | None]:
    """Return every offer id the policy accepts as a correct winner."""

    return expected.get("accepted_offer_ids", [expected["offer_id"]])


def _matches_expected(
    status: str,
    offer_id: str | None,
    expected: dict[str, Any],
) -> bool:
    """Compare a decision with the expected outcome of a case."""

    return status == expected["status"] and offer_id in _accepted_offer_ids(expected)


def _build_live_llm_report(
    settings: Settings,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the persisted live LLM accuracy report."""

    case_count = len(results)
    error_count = sum(not result["correct"] for result in results)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "model_id": settings.oci_model_id,
        "case_count": case_count,
        "error_count": error_count,
        "accuracy": (case_count - error_count) / case_count,
        "cases": results,
    }


class _ExpectedDecisionAgent:  # pylint: disable=too-few-public-methods
    """Fake LLM that answers with the expected decision recorded for a case."""

    def __init__(self, case: dict[str, Any], request: EvaluateOffersRequest) -> None:
        """Prepare the expected decision for one case."""

        expected = case["expected"]
        if expected["status"] == "selected_offer":
            offer = next(
                offer
                for offer in request.offers
                if offer.offer_id == expected["offer_id"]
            )
            decision = {
                "status": "selected_offer",
                "selected_offer": offer.model_dump(mode="json"),
                "reasons": [],
            }
        else:
            decision = {
                "status": "no_valid_offers",
                "selected_offer": PLACEHOLDER_OFFER,
                "reasons": ["Recorded expected decision: no offer is eligible."],
            }
        self._response = EvaluateOffersResponse(
            request_id=request.request_id,
            decision=decision,
            explanation=f"Recorded expected decision for {case['case_id']}.",
        )

    def run_sync(self, _prompt: str):
        """Return the expected decision as a Locus AgentResult-like object."""

        return SimpleNamespace(parsed=self._response, message="")
