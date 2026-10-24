"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Read-only A2A client for the Purchase Order Agent, used to
                show the most recent purchase orders in the UI.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Protocol

import httpx
from locus.a2a import A2AClient, DataPart, Message

from conversational_procurement_intake.models import RecentPurchaseOrdersResponse

LOGGER = logging.getLogger(__name__)

LIST_RECENT_PURCHASE_ORDERS = "list_recent_purchase_orders"


class PurchaseOrderReadError(RuntimeError):
    """Recent purchase orders could not be read.

    The message is safe to show to end users; the technical cause is logged.
    """


class PurchaseOrderReader(Protocol):  # pylint: disable=too-few-public-methods
    """Contract for reading recent purchase orders."""

    async def list_recent_purchase_orders(
        self, limit: int
    ) -> RecentPurchaseOrdersResponse:
        """Return the most recent purchase orders, newest first."""


class A2APurchaseOrderReader:  # pylint: disable=too-few-public-methods
    """Reads recent purchase orders through the Purchase Order Agent A2A skill."""

    def __init__(
        self, purchase_order_url: str, api_key: str, timeout_seconds: float = 30
    ) -> None:
        """Initialize the A2A client.

        Args:
            purchase_order_url: Purchase Order Agent A2A base URL.
            api_key: Bearer token used by the A2A server.
            timeout_seconds: HTTP timeout for one read.
        """

        self._client = A2AClient(url=purchase_order_url, api_key=api_key)
        self._timeout_seconds = timeout_seconds

    async def list_recent_purchase_orders(
        self, limit: int
    ) -> RecentPurchaseOrdersResponse:
        """Return the most recent purchase orders, newest first.

        Args:
            limit: Maximum number of purchase orders, between 1 and 100.

        Returns:
            The Purchase Order Agent response.

        Raises:
            PurchaseOrderReadError: If the agent cannot be reached, returns an
                invalid response, or reports that storage could not be read.
        """

        message = Message(
            role="user",
            parts=[
                DataPart(
                    data={"operation": LIST_RECENT_PURCHASE_ORDERS, "limit": limit}
                )
            ],
            messageId=f"intake-list-purchase-orders-{uuid.uuid4().hex}",
        )
        try:
            task = await self._client.send_message(
                message, timeout=self._timeout_seconds
            )
            artifact_text = task.artifacts[-1].parts[0].text
            response = RecentPurchaseOrdersResponse.model_validate(
                json.loads(artifact_text)
            )
        # Locus raises RuntimeError for A2A errors. IndexError and
        # AttributeError mean a missing text artifact; ValueError covers
        # invalid JSON and pydantic validation errors.
        except (
            httpx.HTTPError,
            RuntimeError,
            IndexError,
            AttributeError,
            ValueError,
        ) as exc:
            LOGGER.exception("Reading recent purchase orders through A2A failed.")
            raise PurchaseOrderReadError(
                "The Purchase Order Agent could not be reached."
            ) from exc

        if response.status == "failed":
            LOGGER.warning(
                "The Purchase Order Agent could not read purchase orders: %s",
                response.error.code,
            )
            raise PurchaseOrderReadError("Purchase orders could not be read.")
        return response
