"""
Deterministic workflow for purchase order registration and reads.

Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Implements validation, purchase order system invocation, and
                output serialization for the Purchase Order Agent skills:
                create_purchase_order and list_recent_purchase_orders.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from locus.agent.hook_orchestrator import HookOrchestrator
from locus.core.events import LocusEvent, TerminateEvent, ThinkEvent
from locus.core.state import AgentState

from purchase_order_agent.config import Settings
from purchase_order_agent.models import (
    LIST_RECENT_PURCHASE_ORDERS,
    CreatePurchaseOrderRequest,
    ListRecentPurchaseOrdersRequest,
)
from purchase_order_agent.po_system import PurchaseOrderSystemClient

# The lifecycle wrapper intentionally mirrors the other independent agents
# without introducing shared runtime code between services.
# pylint: disable=duplicate-code


class PurchaseOrderWorkflowAgent:  # pylint: disable=too-few-public-methods
    """Locus-compatible deterministic purchase order workflow agent."""

    def __init__(
        self,
        settings: Settings,
        po_system_client: PurchaseOrderSystemClient | None = None,
        hooks: list[Any] | None = None,
    ) -> None:
        """Initialize the workflow agent.

        Args:
            settings: Validated runtime settings.
            po_system_client: Optional purchase order system wrapper.
            hooks: Optional Locus lifecycle hooks.
        """

        self._settings = settings
        self._po_system_client = po_system_client or PurchaseOrderSystemClient()
        self._hooks = hooks or []
        self._hook_orchestrator = HookOrchestrator(self._hooks)

    async def run(self, prompt: str) -> AsyncIterator[LocusEvent]:
        """Run the purchase order workflow selected by the payload.

        Args:
            prompt: JSON text containing a ``CreatePurchaseOrderRequest`` or a
                ``ListRecentPurchaseOrdersRequest``.

        Yields:
            Locus events consumed by ``A2AServer``.
        """

        state = await self._hook_orchestrator.run_before_invocation(
            prompt,
            AgentState(agent_id="purchase-order-agent", max_iterations=3),
        )
        success = False
        try:
            async for event in self._run_workflow(prompt):
                if isinstance(event, TerminateEvent):
                    state = state.model_copy(
                        update={
                            "iteration": event.iterations_used,
                            "confidence": event.final_confidence,
                            "updated_at": datetime.now(UTC),
                        }
                    )
                yield event
            success = True
        except Exception as exc:
            state = state.with_error(type(exc).__name__)
            raise
        finally:
            state = state.model_copy(update={"updated_at": datetime.now(UTC)})
            await self._hook_orchestrator.run_after_invocation(state, success)

    async def _run_workflow(self, prompt: str) -> AsyncIterator[LocusEvent]:
        """Run the operation selected by the request payload.

        The A2A server passes only the JSON payload to the agent, so the
        ``operation`` field selects the skill: a read when it is
        ``list_recent_purchase_orders``, a registration otherwise.
        """

        if _requested_operation(prompt) == LIST_RECENT_PURCHASE_ORDERS:
            events = self._list_recent_purchase_orders(prompt)
        else:
            events = self._register_purchase_order(prompt)
        async for event in events:
            yield event

    async def _register_purchase_order(self, prompt: str) -> AsyncIterator[LocusEvent]:
        """Validate and register one purchase order."""

        yield ThinkEvent(
            iteration=1,
            reasoning="Validating CreatePurchaseOrderRequest.",
        )
        request = CreatePurchaseOrderRequest.model_validate_json(prompt)

        yield ThinkEvent(
            iteration=2,
            reasoning="Calling purchase order system wrapper.",
        )
        response = self._po_system_client.register_purchase_order(request)

        yield ThinkEvent(
            iteration=3,
            reasoning="Returning CreatePurchaseOrderResponse.",
        )
        yield TerminateEvent(
            reason="complete",
            iterations_used=3,
            final_confidence=1.0,
            total_tool_calls=0,
            final_message=response.model_dump_json(),
        )

    async def _list_recent_purchase_orders(
        self, prompt: str
    ) -> AsyncIterator[LocusEvent]:
        """Return the most recent purchase orders, newest first."""

        yield ThinkEvent(
            iteration=1,
            reasoning="Validating ListRecentPurchaseOrdersRequest.",
        )
        request = ListRecentPurchaseOrdersRequest.model_validate_json(prompt)

        yield ThinkEvent(
            iteration=2,
            reasoning="Reading recent purchase orders.",
        )
        response = self._po_system_client.list_recent_purchase_orders(request.limit)

        yield TerminateEvent(
            reason="complete",
            iterations_used=2,
            final_confidence=1.0,
            total_tool_calls=0,
            final_message=response.model_dump_json(),
        )


def _requested_operation(prompt: str) -> str | None:
    """Return the ``operation`` field of a JSON payload, if there is one."""

    try:
        payload = json.loads(prompt)
    except json.JSONDecodeError:
        # Invalid JSON is reported by the registration request validation.
        return None
    return payload.get("operation") if isinstance(payload, dict) else None


def build_workflow_agent(
    settings: Settings,
    hooks: list[Any] | None = None,
) -> PurchaseOrderWorkflowAgent:
    """Build the Locus-compatible deterministic workflow agent.

    Args:
        settings: Validated runtime settings.
        hooks: Optional Locus lifecycle hooks.

    Returns:
        Configured purchase order workflow agent.
    """

    _ensure_file_exists(settings.request_schema_file)
    _ensure_file_exists(settings.response_schema_file)
    return PurchaseOrderWorkflowAgent(
        settings,
        po_system_client=PurchaseOrderSystemClient.from_settings(settings),
        hooks=hooks,
    )


def _ensure_file_exists(path: Path) -> None:
    """Ensure a required local file exists.

    Args:
        path: File path to verify.

    Raises:
        FileNotFoundError: If the path does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(path)
