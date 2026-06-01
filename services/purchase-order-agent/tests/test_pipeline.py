"""
Tests for Purchase Order Agent workflow.

Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    Verifies request validation and deterministic registration output.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

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


def test_po_system_registers_purchase_order_without_supplied_id() -> None:
    """Allocate a deterministic fake purchase order id when omitted."""

    payload = _payload()
    payload.pop("purchase_order_id")
    request = CreatePurchaseOrderRequest.model_validate(payload)
    response = PurchaseOrderSystemClient().register_purchase_order(request)

    assert response.status == "registered"
    assert response.purchase_order.purchase_order_id.startswith("PO-")
    assert response.purchase_order.external_reference == (
        f"ERP-{response.purchase_order.purchase_order_id}"
    )


def test_mysql_po_system_persists_with_database_sequence() -> None:
    """Persist a purchase order through the MySQL backend."""

    connection = _FakeConnection(sequence_value=42)
    payload = _payload()
    payload.pop("purchase_order_id")
    request = CreatePurchaseOrderRequest.model_validate(payload)
    client = PurchaseOrderSystemClient(
        storage_backend="mysql",
        connection_factory=lambda: connection,
    )

    response = client.register_purchase_order(request)

    assert response.status == "registered"
    assert response.purchase_order.purchase_order_id == "PO-2026-000042"
    assert response.purchase_order.external_reference == "ERP-PO-2026-000042"
    assert response.purchase_order.registered_at.endswith("Z")
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed
    assert connection.inserted_purchase_order is not None
    inserted_purchase_order = cast(tuple[Any, ...], connection.inserted_purchase_order)
    # pylint: disable-next=unsubscriptable-object
    assert inserted_purchase_order[0] == "PO-2026-000042"


def test_mysql_po_system_returns_existing_idempotent_registration() -> None:
    """Return an existing row for duplicate idempotent requests."""

    payload = _payload()
    existing = _existing_purchase_order_row(payload)
    connection = _FakeConnection(existing_purchase_order=existing)
    request = CreatePurchaseOrderRequest.model_validate(payload)
    client = PurchaseOrderSystemClient(
        storage_backend="mysql",
        connection_factory=lambda: connection,
    )

    response = client.register_purchase_order(request)

    assert response.status == "registered"
    assert response.purchase_order.purchase_order_id == "PO-2026-0001"
    assert response.purchase_order.external_reference == "ERP-PO-2026-0001"
    assert connection.inserted_purchase_order is None


def test_mysql_po_system_rejects_idempotency_conflict() -> None:
    """Return a failed response when duplicate content conflicts."""

    payload = _payload()
    existing = _existing_purchase_order_row(payload)
    existing["quantity"] = 5
    connection = _FakeConnection(existing_purchase_order=existing)
    request = CreatePurchaseOrderRequest.model_validate(payload)
    client = PurchaseOrderSystemClient(
        storage_backend="mysql",
        connection_factory=lambda: connection,
    )

    response = client.register_purchase_order(request)

    assert response.status == "failed"
    assert response.error.code == "IDEMPOTENCY_CONFLICT"
    assert connection.rollbacks == 1
    assert connection.inserted_purchase_order is None


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


def _existing_purchase_order_row(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a persisted purchase order row matching a payload."""

    line_item = payload["line_items"][0]
    return {
        "purchase_order_id": payload.get("purchase_order_id", "PO-2026-000001"),
        "request_id": payload["request_id"],
        "offer_id": payload["source_offer"]["offer_id"],
        "supplier_id": payload["supplier"]["supplier_id"],
        "supplier_name": payload["supplier"]["supplier_name"],
        "plant_code": payload["plant_code"],
        "material_code": line_item["material_code"],
        "material_description": line_item["material_description"],
        "quantity": line_item["quantity"],
        "unit_of_measure": line_item["unit_of_measure"],
        "unit_price": line_item["unit_price"],
        "total_amount": payload["source_offer"]["price"],
        "currency": payload["source_offer"]["currency"],
        "requested_delivery_date": line_item["requested_delivery_date"],
        "confirmed_delivery_date": line_item["confirmed_delivery_date"],
        "external_reference": f"ERP-{payload.get('purchase_order_id', 'PO-2026-000001')}",
        "registered_at": datetime(2026, 6, 1, 12, 0, 0),
    }


class _FakeConnection:
    """Small DB-API fake for MySQL wrapper tests."""

    def __init__(
        self,
        *,
        sequence_value: int = 1,
        existing_purchase_order: dict[str, Any] | None = None,
    ) -> None:
        """Initialize fake connection state."""

        self.sequence_value = sequence_value
        self.existing_purchase_order = existing_purchase_order
        self.inserted_purchase_order: tuple[Any, ...] | None = None
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, dictionary: bool = False):
        """Return a fake cursor."""

        return _FakeCursor(self, dictionary)

    def commit(self) -> None:
        """Record a commit."""

        self.commits += 1

    def rollback(self) -> None:
        """Record a rollback."""

        self.rollbacks += 1

    def close(self) -> None:
        """Record connection close."""

        self.closed = True


class _FakeCursor:
    """Small DB-API cursor fake for MySQL wrapper tests."""

    def __init__(self, connection: _FakeConnection, dictionary: bool) -> None:
        """Initialize fake cursor state."""

        self._connection = connection
        self._dictionary = dictionary
        self._last_query = ""

    def __enter__(self):
        """Enter cursor context."""

        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """Exit cursor context."""

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        """Record query execution and insert parameters."""

        self._last_query = " ".join(query.split()).lower()
        if self._last_query.startswith("insert into purchase_orders"):
            self._connection.inserted_purchase_order = params

    def fetchone(self):
        """Return fake rows based on the previous query."""

        if "from purchase_orders" in self._last_query and self._dictionary:
            return self._connection.existing_purchase_order
        if "last_insert_id" in self._last_query:
            return (self._connection.sequence_value,)
        return None
