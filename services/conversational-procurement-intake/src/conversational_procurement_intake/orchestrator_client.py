"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Procurement Orchestrator client boundary used by the intake
                layer.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from locus.a2a import A2AClient, Message, TextPart

from conversational_procurement_intake.models import (
    ProcurementOrchestrationEvent,
    ProcurementOrchestrationRequest,
    ProcurementOrchestrationResponse,
)

StreamItemKind = Literal["event", "completed"]


@dataclass(frozen=True)
class OrchestrationStreamItem:
    """One normalized item consumed from the orchestrator stream."""

    kind: StreamItemKind
    event: ProcurementOrchestrationEvent | None = None
    response: ProcurementOrchestrationResponse | None = None


class OrchestratorClient(Protocol):  # pylint: disable=too-few-public-methods
    """Client contract for submitting requests to the orchestrator."""

    async def run_workflow(
        self, request: ProcurementOrchestrationRequest
    ) -> AsyncIterator[OrchestrationStreamItem]:
        """Submit one orchestration request and stream progress updates."""


class A2AOrchestratorClient:  # pylint: disable=too-few-public-methods
    """A2A client wrapper for the Procurement Orchestrator."""

    def __init__(self, orchestrator_url: str, api_key: str) -> None:
        """Initialize the A2A client.

        Args:
            orchestrator_url: Procurement Orchestrator A2A base URL.
            api_key: Bearer token used by the A2A server.
        """

        self._client = A2AClient(url=orchestrator_url, api_key=api_key)

    async def run_workflow(
        self, request: ProcurementOrchestrationRequest
    ) -> AsyncIterator[OrchestrationStreamItem]:
        """Submit the request and yield normalized orchestration updates."""

        message = Message(
            role="user",
            parts=[TextPart(text=request.model_dump_json())],
            messageId=f"intake-{request.request_id}",
        )
        async for raw_event in self._client.send_message_streaming(
            message, timeout=1200
        ):
            parsed = _extract_json_object(raw_event)
            if not parsed:
                continue
            if "event_type" in parsed and "sequence" in parsed:
                yield OrchestrationStreamItem(
                    kind="event",
                    event=ProcurementOrchestrationEvent.model_validate(parsed),
                )
            elif "part_results" in parsed and "completed_at" in parsed:
                yield OrchestrationStreamItem(
                    kind="completed",
                    response=ProcurementOrchestrationResponse.model_validate(parsed),
                )


def _extract_json_object(value: Any) -> dict[str, Any]:
    """Extract the first JSON object embedded in a streamed A2A event."""

    if isinstance(value, dict):
        if "event_type" in value or "part_results" in value:
            return value
        for text in _iter_text_values(value):
            parsed = _parse_json_object(text)
            if parsed:
                return parsed
    return {}


def _parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from text if possible."""

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _iter_text_values(value: Any) -> list[str]:
    """Return all nested string values stored under keys named ``text``."""

    if isinstance(value, dict):
        items: list[str] = []
        for key, nested in value.items():
            if key == "text" and isinstance(nested, str):
                items.append(nested)
            else:
                items.extend(_iter_text_values(nested))
        return items
    if isinstance(value, list):
        items = []
        for nested in value:
            items.extend(_iter_text_values(nested))
        return items
    return []
