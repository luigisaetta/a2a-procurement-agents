"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Simulated supplier offer provider for bid collection.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Protocol

from bid_collection_agent.models import (
    SupplierBidError,
    SupplierBidRequest,
    SupplierBidResponse,
    SupplierBidResponseOffer,
)


class SupplierOfferProvider(Protocol):  # pylint: disable=too-few-public-methods
    """Supplier offer provider contract."""

    def request_offer(self, request: SupplierBidRequest) -> SupplierBidResponse:
        """Request an offer from one supplier."""


class SimulatedSupplierOfferProvider:  # pylint: disable=too-few-public-methods
    """Deterministic supplier offer provider using mock supplier endpoints."""

    def request_offer(self, request: SupplierBidRequest) -> SupplierBidResponse:
        """Request an offer from one supplier."""

        if not request.supplier.api_endpoint.startswith("mock://"):
            return _failed_response(
                request,
                "UNSUPPORTED_SUPPLIER_ENDPOINT",
                "Only mock:// supplier endpoints are supported by the simulator.",
            )

        seed = _stable_seed(request.bid_request_id)
        if seed % 17 == 0:
            return _declined_response(request)

        unit_price = 80 + (seed % 220)
        price = round(unit_price * request.part.quantity, 2)
        delivery_date = request.part.required_delivery_date - timedelta(days=seed % 5)
        valid_until = request.response_deadline.date() + timedelta(days=7)

        return SupplierBidResponse(
            request_id=request.request_id,
            bid_request_id=request.bid_request_id,
            supplier_id=request.supplier.supplier_id,
            status="offer_received",
            offer=SupplierBidResponseOffer(
                offer_id=f"OFF-{request.bid_request_id.removeprefix('BIDREQ-')}",
                supplier_id=request.supplier.supplier_id,
                supplier_name=request.supplier.supplier_name,
                part_id=request.part.part_id,
                material_code=request.part.material_code,
                price=price,
                currency=request.currency,
                delivery_date=delivery_date,
                quality_score=80 + (seed % 16),
                reliability_score=78 + (seed % 20),
                valid_until=valid_until,
            ),
            error=SupplierBidError(code="", message=""),
        )


def _stable_seed(value: str) -> int:
    """Return a deterministic integer seed."""

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _declined_response(request: SupplierBidRequest) -> SupplierBidResponse:
    """Build a deterministic declined response."""

    return _empty_response(
        request,
        "declined",
        "SUPPLIER_DECLINED",
        "The supplier declined to bid for the requested part.",
    )


def _failed_response(
    request: SupplierBidRequest,
    code: str,
    message: str,
) -> SupplierBidResponse:
    """Build a deterministic failed response."""

    return _empty_response(request, "failed", code, message)


def _empty_response(
    request: SupplierBidRequest,
    status: str,
    code: str,
    message: str,
) -> SupplierBidResponse:
    """Build a supplier response without a usable offer."""

    return SupplierBidResponse(
        request_id=request.request_id,
        bid_request_id=request.bid_request_id,
        supplier_id=request.supplier.supplier_id,
        status=status,
        offer=SupplierBidResponseOffer(
            offer_id="",
            supplier_id=request.supplier.supplier_id,
            supplier_name=request.supplier.supplier_name,
            part_id=request.part.part_id,
            material_code=request.part.material_code,
            price=0,
            currency=request.currency,
            delivery_date=request.part.required_delivery_date,
            quality_score=0,
            reliability_score=0,
            valid_until=request.response_deadline.date(),
        ),
        error=SupplierBidError(code=code, message=message),
    )
