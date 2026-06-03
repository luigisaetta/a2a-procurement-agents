"""
Author: L. Saetta
Date Last Modified: 2026-06-03
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

        if request.part.reference_currency != request.currency:
            return _failed_response(
                request,
                "REFERENCE_CURRENCY_MISMATCH",
                "Reference part price currency does not match the request currency.",
            )

        variance = _price_variance(seed)
        unit_price = round(request.part.reference_unit_price * (1 + variance), 2)
        parts_cost = round(unit_price * request.part.quantity, 2)
        shipping_cost = round(parts_cost * _shipping_rate(request), 2)
        price = round(parts_cost + shipping_cost, 2)
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
                parts_cost=parts_cost,
                shipping_cost=shipping_cost,
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


def _price_variance(seed: int) -> float:
    """Return a deterministic reference price variance between -30% and +30%."""

    return ((seed % 61) - 30) / 100


def _shipping_rate(request: SupplierBidRequest) -> float:
    """Return a deterministic shipping rate based on supplier and plant country."""

    plant_country = request.part.plant_code.split("-", maxsplit=1)[0].upper()
    supplier_country = request.supplier.country_code.upper()
    if supplier_country and supplier_country == plant_country:
        return 0.02
    if supplier_country in {"GB", "UK"} or plant_country in {"GB", "UK"}:
        return 0.08
    return 0.05


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
            parts_cost=0,
            shipping_cost=0,
            price=0,
            currency=request.currency,
            delivery_date=request.part.required_delivery_date,
            quality_score=0,
            reliability_score=0,
            valid_until=request.response_deadline.date(),
        ),
        error=SupplierBidError(code=code, message=message),
    )
