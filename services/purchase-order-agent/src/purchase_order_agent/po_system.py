"""
Purchase order system integration wrapper.

Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Encapsulates the future external purchase order system API.
                The initial implementation returns deterministic fake data.
"""

from __future__ import annotations

from datetime import UTC, datetime

from purchase_order_agent.models import (
    CreatePurchaseOrderRequest,
    CreatePurchaseOrderResponse,
    PurchaseOrderError,
    PurchaseOrderRegistration,
)


class PurchaseOrderSystemClient:  # pylint: disable=too-few-public-methods
    """Client wrapper for the company purchase order system."""

    def register_purchase_order(
        self,
        request: CreatePurchaseOrderRequest,
    ) -> CreatePurchaseOrderResponse:
        """Register a purchase order in the company purchase order system.

        The initial implementation is a deterministic fake call. Future
        implementations can replace this method with an API, database, ERP, or
        other enterprise integration without changing the A2A contract.

        Args:
            request: Validated purchase order registration request.

        Returns:
            Structured registration response.
        """

        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
        registered_at = timestamp.replace("+00:00", "Z")
        external_reference = f"ERP-{request.purchase_order_id}"

        return CreatePurchaseOrderResponse(
            request_id=request.request_id,
            status="registered",
            purchase_order=PurchaseOrderRegistration(
                purchase_order_id=request.purchase_order_id,
                external_reference=external_reference,
                registered_at=registered_at,
            ),
            message=(
                f"Purchase order {request.purchase_order_id} "
                "was registered successfully."
            ),
            error=PurchaseOrderError(code="", message=""),
        )
