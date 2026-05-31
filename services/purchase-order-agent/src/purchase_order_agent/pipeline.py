"""
Deterministic workflow for purchase order registration.

Author: L. Saetta
Date Last Modified: 2026-05-31
License: MIT
Description:    Implements validation, fake purchase order system invocation,
                and output serialization for the Purchase Order Agent.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from locus.agent.hook_orchestrator import HookOrchestrator
from locus.core.events import LocusEvent, TerminateEvent, ThinkEvent
from locus.core.state import AgentState

from purchase_order_agent.config import Settings
from purchase_order_agent.models import CreatePurchaseOrderRequest
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
        """Run the purchase order registration workflow.

        Args:
            prompt: JSON text containing a ``CreatePurchaseOrderRequest``.

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
        """Run the deterministic purchase order workflow body."""

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
    return PurchaseOrderWorkflowAgent(settings, hooks=hooks)


def _ensure_file_exists(path: Path) -> None:
    """Ensure a required local file exists.

    Args:
        path: File path to verify.

    Raises:
        FileNotFoundError: If the path does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(path)
