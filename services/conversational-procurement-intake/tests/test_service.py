"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Tests for intake session state and orchestration event relay.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest

from conversational_procurement_intake.extraction import DeterministicIntakeExtractor
from conversational_procurement_intake.master_data import StaticMasterDataResolver
from conversational_procurement_intake.models import (
    ConfirmSessionRequest,
    ProcurementOrchestrationEvent,
    ProcurementOrchestrationRequest,
    ProcurementOrchestrationResponse,
    StartSessionRequest,
    UserMessageRequest,
)
from conversational_procurement_intake.orchestrator_client import (
    OrchestrationStreamItem,
)
from conversational_procurement_intake.service import IntakeApplicationService
from conversational_procurement_intake.session_store import (
    SessionEventBroker,
    SessionStore,
)


class FakeOrchestratorClient:  # pylint: disable=too-few-public-methods
    """Fake orchestrator client that streams one event and one final response."""

    async def run_workflow(
        self, request: ProcurementOrchestrationRequest
    ) -> AsyncIterator[OrchestrationStreamItem]:
        """Yield deterministic orchestration stream items."""

        yield OrchestrationStreamItem(
            kind="event",
            event=ProcurementOrchestrationEvent(
                orchestration_id=f"ORCH-{request.request_id}",
                request_id=request.request_id,
                sequence=1,
                timestamp=datetime(2026, 5, 29, 10, 0, tzinfo=UTC),
                event_type="accepted",
                status="accepted",
                message="Procurement orchestration accepted and started.",
                payload={"parts_count": len(request.parts)},
            ),
        )
        await asyncio.sleep(0)
        yield OrchestrationStreamItem(
            kind="completed",
            response=ProcurementOrchestrationResponse(
                orchestration_id=f"ORCH-{request.request_id}",
                request_id=request.request_id,
                status="completed_without_purchase_orders",
                started_at=datetime(2026, 5, 29, 10, 0, tzinfo=UTC),
                completed_at=datetime(2026, 5, 29, 10, 1, tzinfo=UTC),
                part_results=[],
                message="Workflow completed.",
                error={"code": "", "message": ""},
            ),
        )


def _service() -> IntakeApplicationService:
    """Build a test application service."""

    return IntakeApplicationService(
        session_store=SessionStore(),
        event_broker=SessionEventBroker(),
        extractor=DeterministicIntakeExtractor(StaticMasterDataResolver()),
        orchestrator_client=FakeOrchestratorClient(),
    )


@pytest.mark.anyio
async def test_service_prepares_request_and_relay_events() -> None:
    """Submit a completed request and expose relayed orchestration events."""

    service = _service()
    started = await service.start_session(
        StartSessionRequest(requested_by="operator@example.com")
    )
    prepared = await service.add_user_message(
        started.session_id,
        UserMessageRequest(
            message=(
                "We need 10 high density battery modules for Munich by June 15. "
                "Bid deadline May 29 at 12. Ask up to 3 European suppliers and "
                "create the purchase order automatically."
            )
        ),
    )

    assert prepared.state == "ready_for_confirmation"
    assert prepared.orchestration_request is not None

    submitted = await service.confirm_session(
        started.session_id, ConfirmSessionRequest(confirmed=True)
    )
    assert submitted.state == "submitted"

    events_response = await _wait_for_events(service, started.session_id)
    assert events_response.events[0].event_type == "accepted"
    assert events_response.terminal_result is not None
    assert events_response.terminal_result.status == "completed_without_purchase_orders"


@pytest.mark.anyio
async def test_confirm_session_accepts_reviewed_request() -> None:
    """Confirmed sessions can submit a user-reviewed orchestration request."""

    service = _service()
    started = await service.start_session(
        StartSessionRequest(requested_by="operator@example.com")
    )
    prepared = await service.add_user_message(
        started.session_id,
        UserMessageRequest(
            message=(
                "We need 10 high density battery modules for Munich by June 15. "
                "Bid deadline May 29 at 12."
            )
        ),
    )

    assert prepared.orchestration_request is not None
    reviewed_request = prepared.orchestration_request.model_copy(deep=True)
    reviewed_request.parts[0].quantity = 12
    reviewed_request.parts[0].required_delivery_date = date(2026, 6, 18)

    submitted = await service.confirm_session(
        started.session_id,
        ConfirmSessionRequest(
            confirmed=True,
            orchestration_request=reviewed_request,
        ),
    )

    assert submitted.orchestration_request is not None
    assert submitted.orchestration_request.parts[0].quantity == 12
    assert submitted.orchestration_request.parts[0].required_delivery_date == date(
        2026, 6, 18
    )


@pytest.mark.anyio
async def test_sse_stream_receives_event_in_real_time() -> None:
    """SSE subscribers receive orchestration events as they are relayed."""

    service = _service()
    started = await service.start_session(
        StartSessionRequest(requested_by="operator@example.com")
    )
    await service.add_user_message(
        started.session_id,
        UserMessageRequest(
            message=(
                "We need 10 high density battery modules for Munich by June 15. "
                "Bid deadline May 29 at 12."
            )
        ),
    )

    stream = service.stream_sse(started.session_id)
    await service.confirm_session(started.session_id, ConfirmSessionRequest())
    first_message = await asyncio.wait_for(anext(stream), timeout=1)
    await stream.aclose()

    assert "event: orchestration_event" in first_message
    assert "accepted" in first_message


async def _wait_for_events(service: IntakeApplicationService, session_id: str):
    """Wait until the fake orchestration stream has been consumed."""

    for _ in range(20):
        response = await service.get_orchestration_events(session_id)
        if response.events and response.terminal_result is not None:
            return response
        await asyncio.sleep(0.01)
    raise AssertionError("Timed out waiting for relayed orchestration events.")
