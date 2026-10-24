"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Tests for the Procurement Orchestrator deterministic workflow.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from procurement_orchestrator.a2a_client import (
    BID_COLLECTION_AGENT,
    OFFER_EVALUATION_AGENT,
    PURCHASE_ORDER_AGENT,
    DownstreamAgentError,
)
from procurement_orchestrator.config import Settings
from procurement_orchestrator.pipeline import ProcurementOrchestratorWorkflowAgent


class FakeProcurementAgentClient:  # pylint: disable=too-few-public-methods
    """Fake downstream A2A client with configurable evaluation responses."""

    def __init__(self, decisions: list[str] | None = None) -> None:
        """Initialize the fake client."""

        self.decisions = decisions or ["selected_offer"]
        self.collect_calls: list[dict[str, Any]] = []
        self.evaluate_calls: list[dict[str, Any]] = []
        self.purchase_order_calls: list[dict[str, Any]] = []

    async def collect_bids(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Return a deterministic bid collection response."""

        self.collect_calls.append({"payload": payload, "timeout": timeout})
        part = payload["parts"][0]
        offer = _offer(payload["request_id"], part)
        return {
            "request_id": payload["request_id"],
            "status": "completed",
            "part_results": [
                {
                    "part_id": part["part_id"],
                    "material_code": part["material_code"],
                    "status": "offers_collected",
                    "identified_suppliers": [
                        {
                            "supplier_id": "SUP-001",
                            "supplier_name": "VoltEdge Components",
                            "api_endpoint": "mock://suppliers/SUP-001/offers",
                            "region": "EU",
                            "selection_reason": "MCP candidate.",
                        }
                    ],
                    "offers": [offer],
                    "supplier_responses": [
                        {
                            "supplier_id": "SUP-001",
                            "supplier_name": "VoltEdge Components",
                            "bid_request_id": "BIDREQ-001",
                            "status": "offer_received",
                            "error": {"code": "", "message": ""},
                        }
                    ],
                }
            ],
            "evaluation_requests": [
                {
                    "request_id": payload["request_id"],
                    "plant_code": part["plant_code"],
                    "material_code": part["material_code"],
                    "material_description": part["material_description"],
                    "quantity": part["quantity"],
                    "unit_of_measure": part["unit_of_measure"],
                    "currency": payload["currency"],
                    "required_delivery_date": part["required_delivery_date"],
                    "evaluation_policy_id": payload["evaluation_policy_id"],
                    "offers": [offer],
                }
            ],
            "message": "Collected one offer.",
        }

    async def evaluate_offers(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Return configured evaluation decisions."""

        self.evaluate_calls.append({"payload": payload, "timeout": timeout})
        decision = self.decisions.pop(0)
        if decision == "no_valid_offers":
            return {
                "request_id": payload["request_id"],
                "decision": {
                    "status": "no_valid_offers",
                    "selected_offer": _empty_offer(),
                    "reasons": ["No offer matched the policy."],
                },
                "explanation": "No valid offer.",
            }
        return {
            "request_id": payload["request_id"],
            "decision": {
                "status": "selected_offer",
                "selected_offer": payload["offers"][0],
                "reasons": [],
            },
            "explanation": "Selected the best offer.",
        }

    async def create_purchase_order(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Return a deterministic purchase order response."""

        self.purchase_order_calls.append({"payload": payload, "timeout": timeout})
        purchase_order_id = payload.get("purchase_order_id") or "PO-2026-000001"
        return {
            "request_id": payload["request_id"],
            "status": "registered",
            "purchase_order": {
                "purchase_order_id": purchase_order_id,
                "external_reference": f"ERP-{purchase_order_id}",
                "registered_at": "2026-05-28T15:00:00Z",
            },
            "message": "Registered.",
            "error": {"code": "", "message": ""},
        }


def _settings() -> Settings:
    """Build test settings."""

    root = Path(__file__).resolve().parents[3]
    return Settings(
        agent_port=8003,
        agent_api_key="secret",
        bid_collection_agent_url="http://127.0.0.1:8000",
        offer_evaluation_agent_url="http://127.0.0.1:8001",
        purchase_order_agent_url="http://127.0.0.1:8002",
        request_schema_file=(
            root / "specs/schemas/procurement-orchestration-request.schema.json"
        ),
        event_schema_file=(
            root / "specs/schemas/procurement-orchestration-event.schema.json"
        ),
        response_schema_file=(
            root / "specs/schemas/procurement-orchestration-response.schema.json"
        ),
    )


def _request(auto_create_purchase_order: bool = True) -> str:
    """Build a valid orchestration request."""

    return json.dumps(
        {
            "request_id": "REQ-2026-0001",
            "requested_by": "operator@example.com",
            "currency": "EUR",
            "evaluation_policy_id": "standard-urgent-procurement-v1",
            "response_deadline": "2026-05-29T12:00:00Z",
            "auto_create_purchase_order": auto_create_purchase_order,
            "max_rebid_attempts": 2,
            "timeouts": {
                "bid_collection_seconds": 300,
                "offer_evaluation_seconds": 120,
                "purchase_order_seconds": 120,
                "total_seconds": 1800,
            },
            "sourcing_constraints": {
                "max_suppliers_per_part": 1,
                "allowed_regions": ["EU"],
                "preferred_supplier_ids": [],
            },
            "parts": [
                {
                    "part_id": "PART-001",
                    "plant_code": "DE-MUN",
                    "material_code": "EV-BAT-MOD-001",
                    "material_description": "High Density Battery Module",
                    "quantity": 10,
                    "unit_of_measure": "EA",
                    "required_delivery_date": "2026-06-15",
                }
            ],
        }
    )


@pytest.mark.anyio
async def test_orchestrator_creates_purchase_order() -> None:
    """Run the happy path through all downstream agents."""

    client = FakeProcurementAgentClient()
    hook = _RecordingHook()
    business_hook = _RecordingBusinessTelemetryHook()
    agent = ProcurementOrchestratorWorkflowAgent(
        _settings(),
        agent_client=client,
        hooks=[hook, business_hook],
    )

    events = [event async for event in agent.run(_request())]

    assert hook.after_success == [True]
    assert hook.after_agent_ids == ["procurement-orchestrator"]
    streamed = [json.loads(event.reasoning) for event in events[:-1]]
    final = json.loads(events[-1].final_message)
    assert streamed[0]["event_type"] == "accepted"
    assert final["status"] == "completed_with_purchase_orders"
    assert final["part_results"][0]["status"] == "purchase_order_created"
    assert len(client.collect_calls) == 1
    assert len(client.evaluate_calls) == 1
    assert len(client.purchase_order_calls) == 1
    assert "purchase_order_id" not in client.purchase_order_calls[0]["payload"]
    assert business_hook.purchase_orders == [
        {
            "plant_code": "DE-MUN",
            "total_amount": 1400.0,
            "currency": "EUR",
            "price_deviation_percent": 0.0,
            "shipping_percentage": 7.1429,
        }
    ]


@pytest.mark.anyio
async def test_orchestrator_retries_when_no_valid_offer() -> None:
    """Retry bid collection and evaluation after no valid offer."""

    client = FakeProcurementAgentClient(decisions=["no_valid_offers", "selected_offer"])
    agent = ProcurementOrchestratorWorkflowAgent(_settings(), agent_client=client)

    events = [event async for event in agent.run(_request())]

    streamed = [json.loads(event.reasoning) for event in events[:-1]]
    final = json.loads(events[-1].final_message)
    assert "rebid_requested" in {event["event_type"] for event in streamed}
    assert final["part_results"][0]["attempts_used"] == 2
    assert final["status"] == "completed_with_purchase_orders"
    assert len(client.collect_calls) == 2
    assert len(client.evaluate_calls) == 2


@pytest.mark.anyio
async def test_orchestrator_skips_purchase_order_when_requested() -> None:
    """Stop after winner selection when auto purchase order creation is disabled."""

    client = FakeProcurementAgentClient()
    agent = ProcurementOrchestratorWorkflowAgent(_settings(), agent_client=client)

    events = [event async for event in agent.run(_request(False))]

    final = json.loads(events[-1].final_message)
    assert final["status"] == "completed_without_purchase_orders"
    assert final["part_results"][0]["status"] == "winner_selected"
    assert not client.purchase_order_calls


@pytest.mark.anyio
async def test_orchestrator_runs_locus_hooks_for_validation_error() -> None:
    """Run Locus lifecycle hooks when orchestration validation fails."""

    hook = _RecordingHook()
    agent = ProcurementOrchestratorWorkflowAgent(
        _settings(),
        agent_client=FakeProcurementAgentClient(),
        hooks=[hook],
    )

    with pytest.raises(ValidationError):
        async for _event in agent.run("{}"):
            pass

    assert hook.after_success == [False]
    assert hook.after_error_counts == [1]


class FailingProcurementAgentClient(FakeProcurementAgentClient):
    """Fake client whose N-th call of one method raises a downstream error."""

    def __init__(
        self,
        failing_method: str,
        error: DownstreamAgentError,
        failing_call_number: int = 1,
    ) -> None:
        """Initialize the failing fake client.

        Args:
            failing_method: ``collect_bids``, ``evaluate_offers``, or
                ``create_purchase_order``.
            error: Error raised by the failing call.
            failing_call_number: Which call of ``failing_method`` fails, from 1.
        """

        super().__init__(decisions=["selected_offer", "selected_offer"])
        self.failing_method = failing_method
        self.error = error
        self.failing_call_number = failing_call_number
        self.calls_by_method: dict[str, int] = {}

    def _fail_if_selected(self, method: str) -> None:
        """Raise the configured error when this call is the failing one."""

        self.calls_by_method[method] = self.calls_by_method.get(method, 0) + 1
        is_failing_call = self.calls_by_method[method] == self.failing_call_number
        if method == self.failing_method and is_failing_call:
            raise self.error

    async def collect_bids(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Fail or delegate to the deterministic fake."""

        self._fail_if_selected("collect_bids")
        return await super().collect_bids(payload, timeout)

    async def evaluate_offers(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Fail or delegate to the deterministic fake."""

        self._fail_if_selected("evaluate_offers")
        return await super().evaluate_offers(payload, timeout)

    async def create_purchase_order(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Fail or delegate to the deterministic fake."""

        self._fail_if_selected("create_purchase_order")
        return await super().create_purchase_order(payload, timeout)


class MalformedBidCollectionClient(FakeProcurementAgentClient):
    """Fake client whose Bid Collection Agent breaks the response contract."""

    async def collect_bids(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Return a response that does not match CollectBidsResponse."""

        self.collect_calls.append({"payload": payload, "timeout": timeout})
        return {"request_id": payload["request_id"], "unexpected": True}


@pytest.mark.anyio
async def test_bid_collection_timeout_fails_the_part_without_raising() -> None:
    """A downstream timeout ends the part and the workflow still completes."""

    client = FailingProcurementAgentClient(
        "collect_bids", DownstreamAgentError.timeout(BID_COLLECTION_AGENT, 300)
    )
    hook = _RecordingHook()
    agent = ProcurementOrchestratorWorkflowAgent(
        _settings(), agent_client=client, hooks=[hook]
    )

    events = [event async for event in agent.run(_request())]

    streamed = [json.loads(event.reasoning) for event in events[:-1]]
    final = json.loads(events[-1].final_message)
    part_result = final["part_results"][0]
    assert final["status"] == "failed"
    assert part_result["status"] == "failed"
    assert part_result["error"]["code"] == "BID_COLLECTION_TIMEOUT"
    assert part_result["purchase_order"]["status"] == "skipped"
    assert streamed[-2]["event_type"] == "part_failed"
    assert streamed[-2]["payload"]["error_code"] == "BID_COLLECTION_TIMEOUT"
    assert streamed[-1]["event_type"] == "workflow_failed"
    assert not client.evaluate_calls
    assert hook.after_success == [True]


@pytest.mark.anyio
async def test_failed_part_does_not_stop_the_next_part() -> None:
    """One failed part next to a successful one gives a partial result."""

    client = FailingProcurementAgentClient(
        "evaluate_offers",
        DownstreamAgentError.failed(OFFER_EVALUATION_AGENT),
        failing_call_number=2,
    )
    agent = ProcurementOrchestratorWorkflowAgent(_settings(), agent_client=client)

    events = [event async for event in agent.run(_two_part_request())]

    final = json.loads(events[-1].final_message)
    statuses = [result["status"] for result in final["part_results"]]
    assert final["status"] == "partial"
    assert statuses == ["purchase_order_created", "failed"]
    assert final["part_results"][1]["error"]["code"] == "OFFER_EVALUATION_FAILED"
    assert final["part_results"][1]["bid_collection"]["offers_count"] == 1


@pytest.mark.anyio
async def test_purchase_order_failure_is_not_retried() -> None:
    """A Purchase Order Agent failure gives purchase_order_failed once."""

    client = FailingProcurementAgentClient(
        "create_purchase_order",
        DownstreamAgentError.failed(PURCHASE_ORDER_AGENT),
    )
    agent = ProcurementOrchestratorWorkflowAgent(_settings(), agent_client=client)

    events = [event async for event in agent.run(_request())]

    final = json.loads(events[-1].final_message)
    part_result = final["part_results"][0]
    assert part_result["status"] == "purchase_order_failed"
    assert part_result["purchase_order"]["status"] == "failed"
    assert part_result["error"]["code"] == "PURCHASE_ORDER_FAILED"
    assert part_result["evaluation"]["status"] == "selected_offer"
    assert client.calls_by_method["create_purchase_order"] == 1


@pytest.mark.anyio
async def test_malformed_bid_collection_response_fails_the_part() -> None:
    """A response that breaks the contract is reported as invalid."""

    client = MalformedBidCollectionClient()
    agent = ProcurementOrchestratorWorkflowAgent(_settings(), agent_client=client)

    events = [event async for event in agent.run(_request())]

    final = json.loads(events[-1].final_message)
    part_result = final["part_results"][0]
    assert part_result["status"] == "failed"
    assert part_result["error"]["code"] == "BID_COLLECTION_INVALID_RESPONSE"


@pytest.mark.anyio
async def test_streamed_event_sequences_are_unique_and_increasing() -> None:
    """Every streamed event has the next sequence number, also on failures."""

    client = FailingProcurementAgentClient(
        "evaluate_offers",
        DownstreamAgentError.failed(OFFER_EVALUATION_AGENT),
        failing_call_number=2,
    )
    agent = ProcurementOrchestratorWorkflowAgent(_settings(), agent_client=client)

    events = [event async for event in agent.run(_two_part_request())]

    sequences = [json.loads(event.reasoning)["sequence"] for event in events[:-1]]
    assert sequences == list(range(1, len(sequences) + 1))


def _two_part_request() -> str:
    """Build a valid orchestration request with two parts."""

    request = json.loads(_request())
    second_part = dict(request["parts"][0])
    second_part["part_id"] = "PART-002"
    second_part["material_code"] = "EV-INV-002"
    second_part["material_description"] = "Traction Inverter"
    request["parts"].append(second_part)
    return json.dumps(request)


def _offer(request_id: str, part: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic supplier offer."""

    return {
        "offer_id": f"OFF-{request_id}-{part['part_id']}-SUP-001",
        "supplier_id": "SUP-001",
        "supplier_name": "VoltEdge Components",
        "parts_cost": 1300.0,
        "shipping_cost": 100.0,
        "price": 1400.0,
        "currency": "EUR",
        "delivery_date": "2026-06-14",
        "quality_score": 92,
        "reliability_score": 90,
        "valid_until": "2026-06-05",
    }


def _empty_offer() -> dict[str, Any]:
    """Build an empty selected offer placeholder."""

    return {
        "offer_id": "",
        "supplier_id": "",
        "supplier_name": "",
        "parts_cost": 0,
        "shipping_cost": 0,
        "price": 0,
        "currency": "",
        "delivery_date": "",
        "quality_score": 0,
        "reliability_score": 0,
        "valid_until": "",
    }


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


class _RecordingBusinessTelemetryHook(_RecordingHook):
    """Record business telemetry calls for assertions."""

    def __init__(self) -> None:
        """Initialize recorded telemetry calls."""

        super().__init__()
        self.purchase_orders: list[dict[str, Any]] = []

    def record_purchase_order_created(
        self,
        *,
        plant_code: str,
        total_amount: float,
        currency: str,
        price_deviation_percent: float | None,
        shipping_percentage: float | None,
    ) -> None:
        """Record one business purchase order metric call."""

        self.purchase_orders.append(
            {
                "plant_code": plant_code,
                "total_amount": total_amount,
                "currency": currency,
                "price_deviation_percent": price_deviation_percent,
                "shipping_percentage": shipping_percentage,
            }
        )
