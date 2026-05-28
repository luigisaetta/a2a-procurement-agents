"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    A2A downstream client wrappers for the Procurement Orchestrator.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from locus.a2a import A2AClient, DataPart, Message
from pydantic import BaseModel


class ProcurementAgentClient(Protocol):
    """Client contract used by the orchestration pipeline."""

    async def collect_bids(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Bid Collection Agent."""

    async def evaluate_offers(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Offer Evaluation Agent."""

    async def create_purchase_order(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Purchase Order Agent."""


class A2AProcurementAgentClient:
    """A2A client wrapper for downstream procurement agents."""

    def __init__(
        self,
        bid_collection_url: str,
        offer_evaluation_url: str,
        purchase_order_url: str,
        api_key: str,
    ) -> None:
        """Initialize the downstream A2A clients.

        Args:
            bid_collection_url: Base URL of the Bid Collection Agent.
            offer_evaluation_url: Base URL of the Offer Evaluation Agent.
            purchase_order_url: Base URL of the Purchase Order Agent.
            api_key: Bearer token for downstream A2A calls.
        """

        self._bid_collection = A2AClient(url=bid_collection_url, api_key=api_key)
        self._offer_evaluation = A2AClient(url=offer_evaluation_url, api_key=api_key)
        self._purchase_order = A2AClient(url=purchase_order_url, api_key=api_key)

    async def collect_bids(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Bid Collection Agent."""

        return await _call_agent(
            self._bid_collection,
            payload,
            "orchestrator-collect-bids",
            timeout,
        )

    async def evaluate_offers(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Offer Evaluation Agent."""

        return await _call_agent(
            self._offer_evaluation,
            payload,
            "orchestrator-evaluate-offers",
            timeout,
        )

    async def create_purchase_order(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Purchase Order Agent."""

        return await _call_agent(
            self._purchase_order,
            payload,
            "orchestrator-create-purchase-order",
            timeout,
        )


async def _call_agent(
    client: A2AClient,
    payload: dict[str, Any],
    message_id: str,
    timeout: float,
) -> dict[str, Any]:
    """Call one downstream A2A agent and parse its JSON artifact."""

    task = await client.send_message(
        Message(
            role="user",
            parts=[DataPart(data=payload)],
            messageId=message_id,
        ),
        timeout=timeout,
    )
    if not task.artifacts:
        raise RuntimeError("Downstream A2A task completed without artifacts.")
    text = getattr(task.artifacts[-1].parts[0], "text", "")
    if not text:
        raise RuntimeError("Downstream A2A task artifact does not contain text.")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("Downstream A2A task artifact is not a JSON object.")
    return parsed


def model_to_payload(model: BaseModel) -> dict[str, Any]:
    """Convert a Pydantic model into a JSON-compatible dictionary."""

    return model.model_dump(mode="json")
