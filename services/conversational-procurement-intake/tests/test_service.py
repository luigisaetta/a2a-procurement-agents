"""
Author: L. Saetta
Date Last Modified: 2026-10-24
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
    OrchestratorClient,
    OrchestratorStreamError,
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


def _service(
    orchestrator_client: OrchestratorClient | None = None,
) -> IntakeApplicationService:
    """Build a test application service."""

    return IntakeApplicationService(
        session_store=SessionStore(),
        event_broker=SessionEventBroker(),
        extractor=DeterministicIntakeExtractor(StaticMasterDataResolver()),
        orchestrator_client=orchestrator_client or FakeOrchestratorClient(),
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


@pytest.mark.anyio
async def test_request_id_is_stable_in_a_session_and_new_per_session() -> None:
    """Each session keeps one request_id, and no two sessions share it."""

    service = _service()
    message = UserMessageRequest(
        message=(
            "We need 10 high density battery modules for Munich by June 15. "
            "Bid deadline May 29 at 12."
        )
    )

    first = await service.start_session(
        StartSessionRequest(requested_by="a@example.com")
    )
    first_draft = await service.add_user_message(first.session_id, message)
    first_revised = await service.add_user_message(
        first.session_id, UserMessageRequest(message="Please ask up to 2 suppliers.")
    )
    second = await service.start_session(
        StartSessionRequest(requested_by="b@example.com")
    )
    second_draft = await service.add_user_message(second.session_id, message)

    assert first_draft.orchestration_request is not None
    assert first_revised.orchestration_request is not None
    assert second_draft.orchestration_request is not None
    first_request_id = first_draft.orchestration_request.request_id
    assert first_request_id.startswith("REQ-")
    assert first_revised.orchestration_request.request_id == first_request_id
    assert second_draft.orchestration_request.request_id != first_request_id


class FailingOrchestratorClient:  # pylint: disable=too-few-public-methods
    """Fake orchestrator client that streams one event and then stops early."""

    def __init__(self, error: Exception | None) -> None:
        """Initialize the fake.

        Args:
            error: Error raised after the first event, or ``None`` to end the
                stream without a terminal result.
        """

        self.error = error

    async def run_workflow(
        self, request: ProcurementOrchestrationRequest
    ) -> AsyncIterator[OrchestrationStreamItem]:
        """Yield one event, then raise or end without a terminal result."""

        yield await anext(FakeOrchestratorClient().run_workflow(request))
        if self.error is not None:
            raise self.error


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "expected_detail"),
    [
        (None, "The orchestrator stream ended without a final result."),
        (
            OrchestratorStreamError(
                "The orchestrator task ended in the 'failed' state."
            ),
            "The orchestrator task ended in the 'failed' state.",
        ),
        (
            ConnectionError("cannot reach http://procurement-orchestrator:8003"),
            "The Procurement Orchestrator could not be reached.",
        ),
    ],
)
async def test_relay_records_failure_when_stream_stops_early(
    error: Exception | None, expected_detail: str
) -> None:
    """A stream that stops without a terminal result fails the session."""

    service = _service(FailingOrchestratorClient(error))
    session_id = await _submit_ready_session(service)

    events_response = await _wait_for_state(service, session_id, "failed")
    session = await service.get_session(session_id)

    assert events_response.terminal_result is None
    assert events_response.events[0].event_type == "accepted"
    assert session.message == "The orchestration stream failed."

    stream = service.stream_sse(session_id)
    messages = [message async for message in stream]
    assert messages[-1].startswith("event: orchestration_failed")
    assert expected_detail in messages[-1]
    assert "procurement-orchestrator:8003" not in messages[-1]


async def _submit_ready_session(service: IntakeApplicationService) -> str:
    """Prepare a complete request, confirm it, and return the session ID."""

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
    await service.confirm_session(started.session_id, ConfirmSessionRequest())
    return started.session_id


async def _wait_for_state(
    service: IntakeApplicationService, session_id: str, state: str
):
    """Wait until the relayed session reaches ``state``."""

    for _ in range(20):
        response = await service.get_orchestration_events(session_id)
        if response.state == state:
            return response
        await asyncio.sleep(0.01)
    raise AssertionError(f"Timed out waiting for session state {state!r}.")


async def _wait_for_events(service: IntakeApplicationService, session_id: str):
    """Wait until the fake orchestration stream has been consumed."""

    for _ in range(20):
        response = await service.get_orchestration_events(session_id)
        if response.events and response.terminal_result is not None:
            return response
        await asyncio.sleep(0.01)
    raise AssertionError("Timed out waiting for relayed orchestration events.")
