"""
Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    Runs a deterministic 20-case accuracy suite through the
                Offer Evaluation Agent workflow.
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
    enforce_policy_consistency,
)

CASES_FILE = Path(__file__).with_name("offer-evaluation-accuracy-cases.json")
REPORTS_DIR = Path(__file__).with_name("results")
RUN_LIVE_LLM_ENV = "OFFER_EVALUATION_RUN_LIVE_LLM"


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
    """Evaluate all accuracy cases and assert the final guarded winner."""

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


def test_live_llm_accuracy_report() -> None:
    """Record raw LLM accuracy before deterministic policy guardrails run."""

    if os.environ.get(RUN_LIVE_LLM_ENV) != "1":
        pytest.skip(f"Set {RUN_LIVE_LLM_ENV}=1 to run live LLM accuracy reporting.")

    try:
        settings = load_settings()
    except RuntimeError as exc:
        pytest.skip(f"Live LLM settings are not available: {exc}")

    agent = build_workflow_agent(settings)
    policy_text = settings.policy_file.read_text(encoding="utf-8")
    response_schema = settings.response_schema_file.read_text(encoding="utf-8")

    results = []
    for case in _load_cases():
        results.append(
            _evaluate_live_case(
                case,
                agent,
                policy_text,
                response_schema,
            )
        )

    report = _build_live_llm_report(settings, results)
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / "latest-llm-accuracy-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    assert report["guarded_error_count"] == 0, json.dumps(
        [result for result in results if not result["guarded_correct"]],
        indent=2,
    )


def _evaluate_live_case(
    case: dict[str, Any],
    agent: OfferEvaluationWorkflowAgent,
    policy_text: str,
    response_schema: str,
) -> dict[str, Any]:
    """Evaluate one case with the raw LLM and deterministic guardrail."""

    request = EvaluateOffersRequest.model_validate(case["request"])
    expected = case["expected"]
    llm_response = _run_raw_llm_evaluator(
        agent,
        request,
        policy_text,
        response_schema,
    )
    guarded_response = enforce_policy_consistency(request, llm_response)

    raw_status, raw_offer_id = _outcome_from_model(llm_response)
    guarded_status, guarded_offer_id = _outcome_from_model(guarded_response)
    raw_correct = _matches_expected(raw_status, raw_offer_id, expected)
    guarded_correct = _matches_expected(
        guarded_status,
        guarded_offer_id,
        expected,
    )
    return {
        "case_id": case["case_id"],
        "expected_status": expected["status"],
        "expected_offer_id": expected["offer_id"],
        "raw_llm_status": raw_status,
        "raw_llm_offer_id": raw_offer_id,
        "raw_llm_correct": raw_correct,
        "guarded_status": guarded_status,
        "guarded_offer_id": guarded_offer_id,
        "guarded_correct": guarded_correct,
    }


async def _run_offer_evaluator(request: EvaluateOffersRequest) -> dict[str, Any]:
    """Run a request through the Offer Evaluation Agent workflow."""

    # pylint: disable=protected-access
    agent = OfferEvaluationWorkflowAgent.__new__(OfferEvaluationWorkflowAgent)
    agent._settings = _settings()
    agent._decision_agent = _AlwaysNoValidDecisionAgent(request.request_id)
    agent._hook_orchestrator = HookOrchestrator([])

    events = [event async for event in agent.run(request.model_dump_json())]
    return json.loads(events[-1].final_message)


def _run_raw_llm_evaluator(
    agent: OfferEvaluationWorkflowAgent,
    request: EvaluateOffersRequest,
    policy_text: str,
    response_schema: str,
) -> EvaluateOffersResponse:
    """Run only the LLM evaluator step, before policy guardrails."""

    # pylint: disable=protected-access
    llm_prompt = agent._build_llm_prompt(request, policy_text, response_schema)
    result = agent._decision_agent.run_sync(llm_prompt)
    return agent._parse_response(result.parsed, result.message)


def _outcome_from_model(response: EvaluateOffersResponse) -> tuple[str, str | None]:
    """Return comparable status and selected offer id from a response model."""

    decision = response.decision
    offer_id = (
        decision.selected_offer.offer_id
        if decision.status == "selected_offer"
        else None
    )
    return decision.status, offer_id


def _matches_expected(
    status: str,
    offer_id: str | None,
    expected: dict[str, Any],
) -> bool:
    """Compare a response outcome with the expected fixture outcome."""

    return status == expected["status"] and offer_id == expected["offer_id"]


def _build_live_llm_report(
    settings: Settings,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the persisted live LLM accuracy report."""

    case_count = len(results)
    raw_error_count = sum(not result["raw_llm_correct"] for result in results)
    guarded_error_count = sum(not result["guarded_correct"] for result in results)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "model_id": settings.oci_model_id,
        "case_count": case_count,
        "raw_llm_error_count": raw_error_count,
        "raw_llm_accuracy": (case_count - raw_error_count) / case_count,
        "guarded_error_count": guarded_error_count,
        "guarded_accuracy": (case_count - guarded_error_count) / case_count,
        "cases": results,
    }


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
