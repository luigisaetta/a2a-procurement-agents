"""
Tests for Purchase Order Agent workflow.

Author: L. Saetta
Date Last Modified: 2026-05-31
License: MIT
Description:    Verifies request validation and deterministic registration output.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from locus.agent.hook_orchestrator import HookOrchestrator
from locus.core.events import TerminateEvent
from pydantic import ValidationError

from purchase_order_agent.models import CreatePurchaseOrderRequest
from purchase_order_agent.pipeline import PurchaseOrderWorkflowAgent
from purchase_order_agent.po_system import PurchaseOrderSystemClient


def _payload() -> dict:
    """Return a valid purchase order request payload."""

    return {
        "request_id": "REQ-2026-0001",
        "purchase_order_id": "PO-2026-0001",
        "plant_code": "PLANT-01",
        "supplier": {
            "supplier_id": "SUP-002",
            "supplier_name": "Northern Industrial Supply",
        },
        "line_items": [
            {
                "material_code": "MAT-12345",
                "material_description": "Industrial pump replacement kit",
                "quantity": 10,
                "unit_of_measure": "EA",
                "unit_price": 1180.0,
                "currency": "EUR",
                "requested_delivery_date": "2026-06-15",
                "confirmed_delivery_date": "2026-06-12",
            }
        ],
        "source_offer": {
            "offer_id": "OFF-002",
            "price": 11800.0,
            "currency": "EUR",
        },
    }


def test_po_system_registers_purchase_order() -> None:
    """Return a deterministic successful registration response."""

    request = CreatePurchaseOrderRequest.model_validate(_payload())
    response = PurchaseOrderSystemClient().register_purchase_order(request)

    assert response.request_id == "REQ-2026-0001"
    assert response.status == "registered"
    assert response.purchase_order.purchase_order_id == "PO-2026-0001"
    assert response.purchase_order.external_reference == "ERP-PO-2026-0001"
    assert response.purchase_order.registered_at.endswith("Z")
    assert response.error.code == ""


def test_request_validation_rejects_negative_quantity() -> None:
    """Reject invalid purchase order quantities."""

    payload = _payload()
    payload["line_items"][0]["quantity"] = -1

    with pytest.raises(ValidationError):
        CreatePurchaseOrderRequest.model_validate(payload)


def test_sample_payload_is_valid() -> None:
    """Load the sample payload and verify its expected structure."""

    sample_path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "sample-create-purchase-order-request.json"
    )
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    request = CreatePurchaseOrderRequest.model_validate(payload)

    assert request.request_id == "REQ-2026-0001"
    assert request.purchase_order_id == "PO-2026-0001"
    assert request.supplier.supplier_id == "SUP-002"
    assert request.source_offer.offer_id == "OFF-002"


def test_pipeline_returns_json_response() -> None:
    """Run the deterministic pipeline and return a JSON response."""

    # pylint: disable=protected-access
    agent = PurchaseOrderWorkflowAgent.__new__(PurchaseOrderWorkflowAgent)
    agent._po_system_client = PurchaseOrderSystemClient()
    agent._hook_orchestrator = HookOrchestrator([])

    events = asyncio.run(_collect_events(agent.run(json.dumps(_payload()))))
    final_event = events[-1]

    assert isinstance(final_event, TerminateEvent)
    response = json.loads(final_event.final_message)
    assert response["status"] == "registered"
    assert response["purchase_order"]["external_reference"] == "ERP-PO-2026-0001"


def test_pipeline_runs_locus_hooks_for_success() -> None:
    """Run Locus lifecycle hooks around a successful workflow."""

    hook = _RecordingHook()
    # pylint: disable=protected-access
    agent = PurchaseOrderWorkflowAgent.__new__(PurchaseOrderWorkflowAgent)
    agent._po_system_client = PurchaseOrderSystemClient()
    agent._hook_orchestrator = HookOrchestrator([hook])

    asyncio.run(_collect_events(agent.run(json.dumps(_payload()))))

    assert hook.before_prompts == [json.dumps(_payload())]
    assert hook.after_success == [True]
    assert hook.after_agent_ids == ["purchase-order-agent"]


def test_pipeline_runs_locus_hooks_for_validation_error() -> None:
    """Run Locus lifecycle hooks when workflow validation fails."""

    hook = _RecordingHook()
    payload = _payload()
    payload["line_items"][0]["quantity"] = -1
    # pylint: disable=protected-access
    agent = PurchaseOrderWorkflowAgent.__new__(PurchaseOrderWorkflowAgent)
    agent._po_system_client = PurchaseOrderSystemClient()
    agent._hook_orchestrator = HookOrchestrator([hook])

    with pytest.raises(ValidationError):
        asyncio.run(_collect_events(agent.run(json.dumps(payload))))

    assert hook.after_success == [False]
    assert hook.after_error_counts == [1]


async def _collect_events(async_events):
    """Collect async workflow events into a list."""

    return [event async for event in async_events]


class _RecordingHook:
    """Record Locus lifecycle hook calls for assertions."""

    def __init__(self) -> None:
        """Initialize recorded hook call lists."""

        self.before_prompts: list[str] = []
        self.after_success: list[bool] = []
        self.after_agent_ids: list[str | None] = []
        self.after_error_counts: list[int] = []

    async def on_before_invocation(self, prompt, state):
        """Record before-invocation calls."""

        self.before_prompts.append(prompt)
        return state

    async def on_after_invocation(self, state, success):
        """Record after-invocation calls."""

        self.after_success.append(success)
        self.after_agent_ids.append(state.agent_id)
        self.after_error_counts.append(len(state.errors))
