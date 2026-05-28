"""
Deterministic workflow for purchase order registration.

Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Implements validation, fake purchase order system invocation,
                and output serialization for the Purchase Order Agent.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from locus.core.events import LocusEvent, TerminateEvent, ThinkEvent

from purchase_order_agent.config import Settings
from purchase_order_agent.models import CreatePurchaseOrderRequest
from purchase_order_agent.po_system import PurchaseOrderSystemClient


class PurchaseOrderWorkflowAgent:  # pylint: disable=too-few-public-methods
    """Locus-compatible deterministic purchase order workflow agent."""

    def __init__(
        self,
        settings: Settings,
        po_system_client: PurchaseOrderSystemClient | None = None,
    ) -> None:
        """Initialize the workflow agent.

        Args:
            settings: Validated runtime settings.
            po_system_client: Optional purchase order system wrapper.
        """

        self._settings = settings
        self._po_system_client = po_system_client or PurchaseOrderSystemClient()

    async def run(self, prompt: str) -> AsyncIterator[LocusEvent]:
        """Run the purchase order registration workflow.

        Args:
            prompt: JSON text containing a ``CreatePurchaseOrderRequest``.

        Yields:
            Locus events consumed by ``A2AServer``.
        """

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


def build_workflow_agent(settings: Settings) -> PurchaseOrderWorkflowAgent:
    """Build the Locus-compatible deterministic workflow agent.

    Args:
        settings: Validated runtime settings.

    Returns:
        Configured purchase order workflow agent.
    """

    _ensure_file_exists(settings.request_schema_file)
    _ensure_file_exists(settings.response_schema_file)
    return PurchaseOrderWorkflowAgent(settings)


def _ensure_file_exists(path: Path) -> None:
    """Ensure a required local file exists.

    Args:
        path: File path to verify.

    Raises:
        FileNotFoundError: If the path does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(path)
