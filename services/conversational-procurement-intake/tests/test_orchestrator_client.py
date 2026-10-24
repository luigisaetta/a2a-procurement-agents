"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Tests for failure detection in the orchestrator A2A stream.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any

import pytest

from conversational_procurement_intake.models import (
    PartOrchestrationRequest,
    ProcurementOrchestrationRequest,
    SourcingConstraints,
)
from conversational_procurement_intake.orchestrator_client import (
    A2AOrchestratorClient,
    OrchestratorStreamError,
)

SUBMITTED_TASK_EVENT = {
    "kind": "task",
    "id": "task-1",
    "contextId": "context-1",
    "status": {"state": "submitted"},
}


class FakeStreamingA2AClient:  # pylint: disable=too-few-public-methods
    """Fake Locus A2A client that replays recorded stream events."""

    def __init__(self, raw_events: list[dict[str, Any]]) -> None:
        """Initialize the fake with the events to stream."""

        self.raw_events = raw_events

    async def send_message_streaming(
        self, _message: Any, *, timeout: float
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield the recorded events."""

        del timeout
        for raw_event in self.raw_events:
            yield raw_event


def _client(raw_events: list[dict[str, Any]]) -> A2AOrchestratorClient:
    """Build an orchestrator client backed by the fake A2A stream."""

    client = A2AOrchestratorClient("http://orchestrator.test", "secret")
    # pylint: disable-next=protected-access
    client._client = FakeStreamingA2AClient(raw_events)
    return client


def _request() -> ProcurementOrchestrationRequest:
    """Build a minimal valid orchestration request."""

    return ProcurementOrchestrationRequest(
        request_id="REQ-2026-0001",
        requested_by="operator@example.com",
        currency="EUR",
        evaluation_policy_id="standard-urgent-procurement-v1",
        response_deadline=datetime(2026, 5, 29, 12, 0, tzinfo=UTC),
        auto_create_purchase_order=True,
        sourcing_constraints=SourcingConstraints(
            max_suppliers_per_part=3, allowed_regions=["EU"]
        ),
        parts=[
            PartOrchestrationRequest(
                part_id="PART-001",
                plant_code="DE-MUN",
                material_code="EV-BAT-MOD-001",
                material_description="High Density Battery Module",
                quantity=10,
                unit_of_measure="EA",
                required_delivery_date=date(2026, 6, 15),
            )
        ],
    )


async def _consume(client: A2AOrchestratorClient) -> list[Any]:
    """Consume the whole workflow stream."""

    return [item async for item in client.run_workflow(_request())]


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["failed", "canceled", "rejected"])
async def test_failed_task_state_raises(state: str) -> None:
    """A status update in a terminal failure state stops the relay."""

    client = _client(
        [
            SUBMITTED_TASK_EVENT,
            {"kind": "status-update", "taskId": "task-1", "status": {"state": state}},
        ]
    )

    with pytest.raises(OrchestratorStreamError, match=state):
        await _consume(client)


@pytest.mark.anyio
async def test_json_rpc_error_envelope_raises() -> None:
    """A JSON-RPC error yielded by Locus as a stream event stops the relay."""

    client = _client([{"error": {"code": -32603, "message": "internal error"}}])

    with pytest.raises(OrchestratorStreamError, match="-32603"):
        await _consume(client)


@pytest.mark.anyio
async def test_working_and_completed_states_do_not_raise() -> None:
    """Normal task states are not treated as failures."""

    client = _client(
        [
            SUBMITTED_TASK_EVENT,
            {"kind": "status-update", "status": {"state": "working"}},
            {"kind": "status-update", "status": {"state": "completed"}},
        ]
    )

    assert not await _consume(client)
