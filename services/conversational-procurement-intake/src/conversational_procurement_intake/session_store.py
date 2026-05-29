"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    In-memory session store and event broker for procurement intake.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from conversational_procurement_intake.models import (
    ClarificationAmbiguity,
    DefaultApplied,
    IntakeState,
    ProcurementOrchestrationEvent,
    ProcurementOrchestrationRequest,
    ProcurementOrchestrationResponse,
)


@dataclass
# The session intentionally owns the conversational and orchestration state.
# pylint: disable=too-many-instance-attributes
class IntakeSession:
    """Mutable state for one conversational intake session."""

    session_id: str
    requested_by: str
    ordinal: int
    state: IntakeState = "needs_clarification"
    message: str = "Session created."
    user_messages: list[str] = field(default_factory=list)
    known_fields: dict[str, object] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    ambiguities: list[ClarificationAmbiguity] = field(default_factory=list)
    defaults_applied: list[DefaultApplied] = field(default_factory=list)
    confirmation_summary: dict[str, object] | None = None
    orchestration_request: ProcurementOrchestrationRequest | None = None
    orchestration_id: str | None = None
    events: list[ProcurementOrchestrationEvent] = field(default_factory=list)
    terminal_result: ProcurementOrchestrationResponse | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SessionStore:
    """In-memory store for intake sessions."""

    def __init__(self) -> None:
        """Initialize an empty store."""

        self._sessions: dict[str, IntakeSession] = {}
        self._next_ordinal = 1
        self._lock = asyncio.Lock()

    async def create(self, requested_by: str) -> IntakeSession:
        """Create a new intake session.

        Args:
            requested_by: User identifier associated with the session.

        Returns:
            Newly created session.
        """

        async with self._lock:
            ordinal = self._next_ordinal
            self._next_ordinal += 1
            session = IntakeSession(
                session_id=f"INTAKE-2026-{ordinal:04d}",
                requested_by=requested_by,
                ordinal=ordinal,
                known_fields={"requested_by": requested_by},
            )
            self._sessions[session.session_id] = session
            return session

    async def get(self, session_id: str) -> IntakeSession:
        """Return a session by identifier.

        Args:
            session_id: Intake session identifier.

        Returns:
            Matching session.

        Raises:
            KeyError: If the session does not exist.
        """

        return self._sessions[session_id]

    async def update_timestamp(self, session: IntakeSession) -> None:
        """Mark a session as updated."""

        session.updated_at = datetime.now(UTC)


class SessionEventBroker:
    """Publish-subscribe broker for real-time session events."""

    def __init__(self) -> None:
        """Initialize an empty broker."""

        self._subscribers: dict[str, set[asyncio.Queue[str]]] = {}

    async def subscribe(self, session_id: str) -> asyncio.Queue[str]:
        """Subscribe to serialized SSE messages for a session."""

        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.setdefault(session_id, set()).add(queue)
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue[str]) -> None:
        """Remove an SSE subscription."""

        subscribers = self._subscribers.get(session_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(session_id, None)

    async def publish(self, session_id: str, message: str) -> None:
        """Publish one serialized SSE message to connected subscribers."""

        for queue in list(self._subscribers.get(session_id, set())):
            await queue.put(message)
