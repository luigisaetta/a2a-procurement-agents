"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Tests for the recent purchase orders endpoint and its
                read-only A2A client.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from locus.a2a import Artifact, Task, TaskState, TaskStatus, TextPart

from conversational_procurement_intake.extraction import DeterministicIntakeExtractor
from conversational_procurement_intake.master_data import StaticMasterDataResolver
from conversational_procurement_intake.models import RecentPurchaseOrdersResponse
from conversational_procurement_intake.purchase_order_client import (
    A2APurchaseOrderReader,
    PurchaseOrderReadError,
)
from conversational_procurement_intake.server import build_app
from conversational_procurement_intake.service import IntakeApplicationService
from conversational_procurement_intake.session_store import (
    SessionEventBroker,
    SessionStore,
)


def _purchase_order(purchase_order_id: str) -> dict[str, Any]:
    """Return one purchase order record as sent by the Purchase Order Agent."""

    return {
        "purchase_order_id": purchase_order_id,
        "request_id": "REQ-20261024-153012-8B07D2",
        "offer_id": "OFF-001",
        "supplier_id": "SUP-001",
        "supplier_name": "VoltEdge Components",
        "plant_code": "IT-TOR",
        "material_code": "EV-DC-DC-009",
        "material_description": "High Voltage DC DC Converter",
        "quantity": 16.0,
        "unit_of_measure": "EA",
        "unit_price": 77.16,
        "total_amount": 1296.3,
        "currency": "EUR",
        "requested_delivery_date": "2027-07-25",
        "confirmed_delivery_date": "2027-07-22",
        "status": "registered",
        "external_reference": f"ERP-{purchase_order_id}",
        "registered_at": "2026-10-24T13:03:51Z",
        "created_at": "2026-10-24T13:03:51Z",
        "updated_at": "2026-10-24T13:03:51Z",
    }


def _agent_response(status: str = "completed") -> dict[str, Any]:
    """Return a ListRecentPurchaseOrdersResponse payload."""

    failed = status == "failed"
    return {
        "status": status,
        "limit": 10,
        "purchase_orders": [] if failed else [_purchase_order("PO-2026-000002")],
        "message": "Read failed." if failed else "Returned 1 purchase orders.",
        "error": {
            "code": "STORAGE_UNAVAILABLE" if failed else "",
            "message": (
                "Purchase orders could not be read from storage." if failed else ""
            ),
        },
    }


class FakePurchaseOrderReader:  # pylint: disable=too-few-public-methods
    """Fake reader that records the requested limit."""

    def __init__(self, error: PurchaseOrderReadError | None = None) -> None:
        """Initialize the fake with an optional error to raise."""

        self.error = error
        self.limits: list[int] = []

    async def list_recent_purchase_orders(
        self, limit: int
    ) -> RecentPurchaseOrdersResponse:
        """Return one purchase order or raise the configured error."""

        self.limits.append(limit)
        if self.error is not None:
            raise self.error
        return RecentPurchaseOrdersResponse.model_validate(_agent_response())


def _client(reader: FakePurchaseOrderReader) -> TestClient:
    """Build the HTTP app with in-memory services and the fake reader."""

    service = IntakeApplicationService(
        session_store=SessionStore(),
        event_broker=SessionEventBroker(),
        extractor=DeterministicIntakeExtractor(StaticMasterDataResolver()),
        orchestrator_client=None,  # type: ignore[arg-type]
    )
    return TestClient(build_app(service=service, purchase_order_reader=reader))


def test_endpoint_returns_recent_purchase_orders_with_default_limit() -> None:
    """Without a limit the endpoint asks for 10 purchase orders."""

    reader = FakePurchaseOrderReader()

    response = _client(reader).get("/purchase-orders")

    assert response.status_code == 200
    assert reader.limits == [10]
    assert (
        response.json()["purchase_orders"][0]["purchase_order_id"] == "PO-2026-000002"
    )


@pytest.mark.parametrize("limit", [0, 101, "ten"])
def test_endpoint_rejects_an_invalid_limit(limit: Any) -> None:
    """A limit outside 1..100 is rejected before calling the agent."""

    reader = FakePurchaseOrderReader()

    response = _client(reader).get("/purchase-orders", params={"limit": limit})

    assert response.status_code == 422
    assert not reader.limits


def test_endpoint_returns_502_when_purchase_orders_cannot_be_read() -> None:
    """A read failure becomes HTTP 502 with the safe message."""

    reader = FakePurchaseOrderReader(
        PurchaseOrderReadError("Purchase orders could not be read.")
    )

    response = _client(reader).get("/purchase-orders", params={"limit": 5})

    assert response.status_code == 502
    assert response.json() == {"detail": "Purchase orders could not be read."}


class FakeA2AClient:  # pylint: disable=too-few-public-methods
    """Fake Locus A2A client that returns a task or raises an error."""

    def __init__(self, outcome: Task | Exception) -> None:
        """Initialize the fake with the task to return or the error to raise."""

        self.outcome = outcome
        self.sent_payloads: list[dict[str, Any]] = []

    async def send_message(self, message: Any, *, timeout: float) -> Task:
        """Record the request payload and return or raise the outcome."""

        del timeout
        self.sent_payloads.append(message.parts[0].data)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _task(payload: Any) -> Task:
    """Build a completed A2A task whose text artifact holds ``payload``."""

    return Task(
        id="task-1",
        contextId="context-1",
        status=TaskStatus(state=TaskState.completed),
        artifacts=[
            Artifact(
                artifactId="artifact-1", parts=[TextPart(text=json.dumps(payload))]
            )
        ],
    )


async def _read_with(outcome: Task | Exception) -> tuple[Any, FakeA2AClient]:
    """Read recent purchase orders through a fake A2A client."""

    reader = A2APurchaseOrderReader("http://purchase-order-agent.test", "secret")
    fake_client = FakeA2AClient(outcome)
    # pylint: disable-next=protected-access
    reader._client = fake_client
    return await reader.list_recent_purchase_orders(3), fake_client


@pytest.mark.anyio
async def test_reader_sends_the_read_operation_and_parses_the_response() -> None:
    """The reader calls the read skill and returns the validated response."""

    response, fake_client = await _read_with(_task(_agent_response()))

    assert fake_client.sent_payloads == [
        {"operation": "list_recent_purchase_orders", "limit": 3}
    ]
    assert response.purchase_orders[0].supplier_name == "VoltEdge Components"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "outcome",
    [
        httpx.ConnectError("connection refused"),
        RuntimeError("A2A error -32603: internal error"),
        _task({"unexpected": True}),
        _task(_agent_response("failed")),
    ],
)
async def test_reader_raises_a_safe_error_on_failure(outcome: Task | Exception) -> None:
    """Unreachable agents, invalid responses, and failed reads all raise."""

    with pytest.raises(PurchaseOrderReadError) as error_info:
        await _read_with(outcome)

    assert "connection refused" not in str(error_info.value)
