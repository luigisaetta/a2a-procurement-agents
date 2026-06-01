"""
Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    Pydantic models for downstream agent payloads used by orchestration.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SupplierOffer(BaseModel):
    """Normalized supplier offer."""

    model_config = ConfigDict(extra="forbid")

    offer_id: str
    supplier_id: str
    supplier_name: str
    price: float = Field(ge=0)
    currency: str
    delivery_date: date
    quality_score: float
    reliability_score: float
    valid_until: date


class CollectBidsRequest(BaseModel):
    """Bid Collection Agent request payload."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    currency: str
    evaluation_policy_id: str
    response_deadline: datetime
    sourcing_constraints: dict
    parts: list[dict]


class PartBidResult(BaseModel):
    """Bid Collection Agent part result."""

    model_config = ConfigDict(extra="allow")

    part_id: str
    material_code: str
    status: Literal["offers_collected", "partial", "no_offers"]
    identified_suppliers: list[dict]
    offers: list[SupplierOffer]
    supplier_responses: list[dict]


class EvaluateOffersRequest(BaseModel):
    """Offer Evaluation Agent request payload."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    plant_code: str
    material_code: str
    material_description: str
    quantity: float
    unit_of_measure: str
    currency: str
    required_delivery_date: date
    evaluation_policy_id: str
    offers: list[SupplierOffer]


class CollectBidsResponse(BaseModel):
    """Bid Collection Agent response payload."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: Literal["completed", "partial", "failed"]
    part_results: list[PartBidResult]
    evaluation_requests: list[EvaluateOffersRequest]
    message: str


class EvaluationDecision(BaseModel):
    """Offer Evaluation Agent decision."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["selected_offer", "no_valid_offers"]
    selected_offer: dict
    reasons: list[str]


class EvaluateOffersResponse(BaseModel):
    """Offer Evaluation Agent response payload."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    decision: EvaluationDecision
    explanation: str


class CreatePurchaseOrderRequest(BaseModel):
    """Purchase Order Agent request payload."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    purchase_order_id: str | None = None
    plant_code: str
    supplier: dict
    line_items: list[dict]
    source_offer: dict


class CreatePurchaseOrderResponse(BaseModel):
    """Purchase Order Agent response payload."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: Literal["registered", "failed"]
    purchase_order: dict
    message: str
    error: dict
