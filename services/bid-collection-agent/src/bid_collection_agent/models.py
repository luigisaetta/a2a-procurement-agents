"""
Author: L. Saetta
Date Last Modified: 2026-06-03
License: MIT
Description:    Pydantic models for the Bid Collection Agent contracts.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SupplierSearchHints(BaseModel):
    """Optional hints used during supplier discovery."""

    model_config = ConfigDict(extra="forbid")

    commodity_category: str = ""
    required_certifications: list[str] = Field(default_factory=list)


class PartBidRequest(BaseModel):
    """Requested procurement part to source."""

    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    plant_code: str = Field(min_length=1)
    material_code: str = Field(min_length=1)
    material_description: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit_of_measure: str = Field(min_length=1)
    required_delivery_date: date
    supplier_search_hints: SupplierSearchHints | None = None


class SourcingConstraints(BaseModel):
    """Request-level sourcing constraints."""

    model_config = ConfigDict(extra="forbid")

    max_suppliers_per_part: int = Field(ge=1)
    allowed_regions: list[str]
    preferred_supplier_ids: list[str] = Field(default_factory=list)


class CollectBidsRequest(BaseModel):
    """Input payload accepted by the Bid Collection Agent."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    evaluation_policy_id: str = Field(min_length=1)
    response_deadline: datetime
    sourcing_constraints: SourcingConstraints
    parts: list[PartBidRequest] = Field(min_length=1)


class IdentifiedSupplier(BaseModel):
    """Supplier selected for bid collection."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: str = Field(min_length=1)
    supplier_name: str = Field(min_length=1)
    api_endpoint: str = Field(min_length=1)
    region: str = ""
    country_code: str = ""
    selection_reason: str = ""


class SupplierBidRequestSupplier(BaseModel):
    """Supplier payload sent to the supplier offer provider."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: str = Field(min_length=1)
    supplier_name: str = Field(min_length=1)
    api_endpoint: str = Field(min_length=1)
    country_code: str = ""


class SupplierBidRequestPart(BaseModel):
    """Requested part payload sent to the supplier offer provider."""

    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    plant_code: str = Field(min_length=1)
    material_code: str = Field(min_length=1)
    material_description: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit_of_measure: str = Field(min_length=1)
    reference_unit_price: float = Field(gt=0)
    reference_currency: str = Field(pattern=r"^[A-Z]{3}$")
    required_delivery_date: date


class SupplierBidRequest(BaseModel):
    """Supplier-facing bid request for one part and one supplier."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    bid_request_id: str = Field(min_length=1)
    supplier: SupplierBidRequestSupplier
    part: SupplierBidRequestPart
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    response_deadline: datetime


class SupplierOffer(BaseModel):
    """Normalized supplier offer."""

    model_config = ConfigDict(extra="forbid")

    offer_id: str
    supplier_id: str
    supplier_name: str
    parts_cost: float = Field(default=0, ge=0)
    shipping_cost: float = Field(default=0, ge=0)
    price: float = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    delivery_date: date
    quality_score: float = Field(ge=0, le=100)
    reliability_score: float = Field(ge=0, le=100)
    valid_until: date


class SupplierBidResponseOffer(SupplierOffer):
    """Supplier offer returned by the supplier-facing provider."""

    part_id: str
    material_code: str


class SupplierBidError(BaseModel):
    """Supplier bid error details."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class SupplierBidResponse(BaseModel):
    """Supplier-facing bid response."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    bid_request_id: str = Field(min_length=1)
    supplier_id: str = Field(min_length=1)
    status: Literal["offer_received", "declined", "failed"]
    offer: SupplierBidResponseOffer
    error: SupplierBidError


class SupplierResponseSummary(BaseModel):
    """Technical response summary for one contacted supplier."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: str = Field(min_length=1)
    supplier_name: str = Field(min_length=1)
    bid_request_id: str = Field(min_length=1)
    status: Literal["offer_received", "declined", "failed"]
    error: SupplierBidError


class EvaluateOffersRequestPayload(BaseModel):
    """Payload compatible with the Offer Evaluation Agent."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    plant_code: str = Field(min_length=1)
    material_code: str = Field(min_length=1)
    material_description: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit_of_measure: str = Field(min_length=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    required_delivery_date: date
    evaluation_policy_id: str = Field(min_length=1)
    offers: list[SupplierOffer] = Field(min_length=1)


class PartBidResult(BaseModel):
    """Bid collection result for one requested part."""

    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    material_code: str = Field(min_length=1)
    status: Literal["offers_collected", "partial", "no_offers"]
    identified_suppliers: list[IdentifiedSupplier]
    offers: list[SupplierOffer]
    supplier_responses: list[SupplierResponseSummary] = Field(min_length=1)


class CollectBidsResponse(BaseModel):
    """Output payload returned by the Bid Collection Agent."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    status: Literal["completed", "partial", "failed"]
    part_results: list[PartBidResult] = Field(min_length=1)
    evaluation_requests: list[EvaluateOffersRequestPayload]
    message: str = Field(min_length=1)
