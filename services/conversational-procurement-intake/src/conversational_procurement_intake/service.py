"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Application service for conversational procurement intake.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from conversational_procurement_intake.extraction import IntakeExtractor
from conversational_procurement_intake.models import (
    ConfirmSessionRequest,
    IntakeSessionResponse,
    OrchestrationEventsResponse,
    ProcurementOrchestrationEvent,
    ProcurementOrchestrationResponse,
    StartSessionRequest,
    UserMessageRequest,
)
from conversational_procurement_intake.orchestrator_client import OrchestratorClient
from conversational_procurement_intake.session_store import (
    IntakeSession,
    SessionEventBroker,
    SessionStore,
)


class IntakeApplicationService:
    """Coordinates HTTP intake, validation, submission, and event relay."""

    def __init__(
        self,
        session_store: SessionStore,
        event_broker: SessionEventBroker,
        extractor: IntakeExtractor,
        orchestrator_client: OrchestratorClient,
    ) -> None:
        """Initialize the application service.

        Args:
            session_store: Session persistence boundary.
            event_broker: SSE event broker.
            extractor: Request extraction and grounding component.
            orchestrator_client: A2A client boundary for the orchestrator.
        """

        self._session_store = session_store
        self._event_broker = event_broker
        self._extractor = extractor
        self._orchestrator_client = orchestrator_client

    async def start_session(
        self, request: StartSessionRequest
    ) -> IntakeSessionResponse:
        """Create a new intake session."""

        session = await self._session_store.create(request.requested_by)
        return _to_response(session)

    async def add_user_message(
        self, session_id: str, request: UserMessageRequest
    ) -> IntakeSessionResponse:
        """Add a user message and update session extraction state."""

        session = await self._session_store.get(session_id)
        if request.requested_by:
            session.requested_by = request.requested_by
            session.known_fields["requested_by"] = request.requested_by
        session.user_messages.append(request.message)
        result = await self._extractor.extract(
            "\n".join(session.user_messages),
            session.requested_by,
            session.ordinal,
        )
        session.message = result.message
        session.missing_fields = result.missing_fields
        session.ambiguities = result.ambiguities
        session.defaults_applied = result.defaults_applied
        session.orchestration_request = result.orchestration_request
        if result.orchestration_request is None:
            session.state = "needs_clarification"
            session.confirmation_summary = None
        else:
            session.state = "ready_for_confirmation"
            session.confirmation_summary = _confirmation_summary(
                result.orchestration_request
            )
        await self._session_store.update_timestamp(session)
        return _to_response(session)

    async def confirm_session(
        self, session_id: str, request: ConfirmSessionRequest
    ) -> IntakeSessionResponse:
        """Confirm the session and start the orchestrator stream relay."""

        session = await self._session_store.get(session_id)
        if not request.confirmed:
            session.state = "cancelled"
            session.message = "The intake session was cancelled."
            await self._session_store.update_timestamp(session)
            return _to_response(session)
        if session.orchestration_request is None:
            session.state = "needs_clarification"
            session.message = "The procurement request is not ready for confirmation."
            await self._session_store.update_timestamp(session)
            return _to_response(session)
        if request.orchestration_request is not None:
            session.orchestration_request = request.orchestration_request
            session.confirmation_summary = _confirmation_summary(
                request.orchestration_request
            )
        session.state = "submitted"
        session.message = "The procurement workflow was submitted."
        session.orchestration_id = f"ORCH-{session.orchestration_request.request_id}"
        await self._session_store.update_timestamp(session)
        asyncio.create_task(self._relay_orchestration(session.session_id))
        return _to_response(session)

    async def get_session(self, session_id: str) -> IntakeSessionResponse:
        """Return current session state."""

        return _to_response(await self._session_store.get(session_id))

    async def get_orchestration_events(
        self, session_id: str, cursor: int = 0
    ) -> OrchestrationEventsResponse:
        """Return stored orchestration events after ``cursor``."""

        session = await self._session_store.get(session_id)
        events = [event for event in session.events if event.sequence > cursor]
        next_cursor = events[-1].sequence if events else cursor
        return OrchestrationEventsResponse(
            session_id=session.session_id,
            orchestration_id=session.orchestration_id,
            state=session.state,
            events=events,
            next_cursor=next_cursor,
            terminal_result=session.terminal_result,
        )

    async def stream_sse(self, session_id: str) -> AsyncIterator[str]:
        """Yield serialized SSE messages for a session."""

        session = await self._session_store.get(session_id)
        for event in session.events:
            yield _sse("orchestration_event", event.model_dump(mode="json"))
        if session.terminal_result is not None:
            yield _sse(
                "orchestration_completed",
                session.terminal_result.model_dump(mode="json"),
            )
            return

        queue = await self._event_broker.subscribe(session_id)
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield _sse("heartbeat", {"timestamp": _now_iso()})
                    continue
                yield message
                if message.startswith("event: orchestration_completed") or (
                    message.startswith("event: orchestration_failed")
                ):
                    break
        finally:
            await self._event_broker.unsubscribe(session_id, queue)

    async def _relay_orchestration(self, session_id: str) -> None:
        """Consume the A2A stream and relay each event to connected UI clients."""

        session = await self._session_store.get(session_id)
        request = session.orchestration_request
        if request is None:
            return
        try:
            async for item in self._orchestrator_client.run_workflow(request):
                if item.kind == "event" and item.event is not None:
                    await self._record_event(session, item.event)
                elif item.kind == "completed" and item.response is not None:
                    await self._record_terminal_response(session, item.response)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            await self._record_failure(session, str(exc))

    async def _record_event(
        self, session: IntakeSession, event: ProcurementOrchestrationEvent
    ) -> None:
        """Store and immediately publish one orchestration event."""

        if any(
            existing.orchestration_id == event.orchestration_id
            and existing.request_id == event.request_id
            and existing.sequence == event.sequence
            for existing in session.events
        ):
            return
        session.orchestration_id = event.orchestration_id
        session.events.append(event)
        await self._session_store.update_timestamp(session)
        await self._event_broker.publish(
            session.session_id,
            _sse("orchestration_event", event.model_dump(mode="json")),
        )

    async def _record_terminal_response(
        self, session: IntakeSession, response: ProcurementOrchestrationResponse
    ) -> None:
        """Store and publish the terminal orchestration response."""

        session.terminal_result = response
        session.orchestration_id = response.orchestration_id
        session.state = "failed" if response.status == "failed" else "submitted"
        await self._session_store.update_timestamp(session)
        await self._event_broker.publish(
            session.session_id,
            _sse("orchestration_completed", response.model_dump(mode="json")),
        )

    async def _record_failure(self, session: IntakeSession, message: str) -> None:
        """Store and publish a safe orchestration relay failure."""

        session.state = "failed"
        session.message = "The orchestration stream failed."
        await self._session_store.update_timestamp(session)
        await self._event_broker.publish(
            session.session_id,
            _sse(
                "orchestration_failed",
                {"message": "The orchestration stream failed.", "detail": message},
            ),
        )


def _to_response(session: IntakeSession) -> IntakeSessionResponse:
    """Convert internal session state into an HTTP response model."""

    return IntakeSessionResponse(
        session_id=session.session_id,
        state=session.state,
        message=session.message,
        known_fields=dict(session.known_fields),
        missing_fields=list(session.missing_fields),
        ambiguities=list(session.ambiguities),
        defaults_applied=list(session.defaults_applied),
        confirmation_summary=session.confirmation_summary,
        orchestration_request=session.orchestration_request,
        orchestration_id=session.orchestration_id,
    )


def _confirmation_summary(request: object) -> dict[str, object]:
    """Build a compact confirmation summary from a request model."""

    payload = request.model_dump(mode="json")  # type: ignore[attr-defined]
    return {
        "request_id": payload["request_id"],
        "requested_by": payload["requested_by"],
        "currency": payload["currency"],
        "evaluation_policy_id": payload["evaluation_policy_id"],
        "response_deadline": payload["response_deadline"],
        "auto_create_purchase_order": payload["auto_create_purchase_order"],
        "sourcing_constraints": payload["sourcing_constraints"],
        "parts": payload["parts"],
    }


def _sse(event_name: str, payload: dict[str, object]) -> str:
    """Serialize an SSE event."""

    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


def _now_iso() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(UTC).isoformat()
