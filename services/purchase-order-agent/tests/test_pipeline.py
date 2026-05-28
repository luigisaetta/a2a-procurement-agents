"""
Tests for Purchase Order Agent workflow.

Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Verifies request validation and deterministic registration output.
"""

from __future__ import annotations

import asyncio
import json

import pytest
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


def test_pipeline_returns_json_response() -> None:
    """Run the deterministic pipeline and return a JSON response."""

    # pylint: disable=protected-access
    agent = PurchaseOrderWorkflowAgent.__new__(PurchaseOrderWorkflowAgent)
    agent._po_system_client = PurchaseOrderSystemClient()

    events = asyncio.run(_collect_events(agent.run(json.dumps(_payload()))))
    final_event = events[-1]

    assert isinstance(final_event, TerminateEvent)
    response = json.loads(final_event.final_message)
    assert response["status"] == "registered"
    assert response["purchase_order"]["external_reference"] == "ERP-PO-2026-0001"


async def _collect_events(async_events):
    """Collect async workflow events into a list."""

    return [event async for event in async_events]
