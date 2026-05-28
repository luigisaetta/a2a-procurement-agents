"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Pydantic models for procurement orchestration contracts.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SupplierSearchHints(BaseModel):
    """Optional hints used during supplier discovery."""

    model_config = ConfigDict(extra="forbid")

    commodity_category: str = ""
    required_certifications: list[str] = Field(default_factory=list)


class PartOrchestrationRequest(BaseModel):
    """Requested procurement part to orchestrate."""

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


class OrchestrationTimeouts(BaseModel):
    """Timeout settings for downstream calls and total orchestration."""

    model_config = ConfigDict(extra="forbid")

    bid_collection_seconds: int = Field(ge=1)
    offer_evaluation_seconds: int = Field(ge=1)
    purchase_order_seconds: int = Field(ge=1)
    total_seconds: int = Field(ge=1)


class ProcurementOrchestrationRequest(BaseModel):
    """Input payload accepted by the Procurement Orchestrator Agent."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    evaluation_policy_id: str = Field(min_length=1)
    response_deadline: datetime
    auto_create_purchase_order: bool
    max_rebid_attempts: int = Field(default=2, ge=0, le=2)
    timeouts: OrchestrationTimeouts = Field(
        default_factory=lambda: OrchestrationTimeouts(
            bid_collection_seconds=300,
            offer_evaluation_seconds=120,
            purchase_order_seconds=120,
            total_seconds=1800,
        )
    )
    sourcing_constraints: SourcingConstraints
    parts: list[PartOrchestrationRequest] = Field(min_length=1)


class ProcurementOrchestrationEvent(BaseModel):
    """Streaming event emitted by the Procurement Orchestrator Agent."""

    model_config = ConfigDict(extra="forbid")

    orchestration_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    timestamp: datetime
    event_type: Literal[
        "accepted",
        "workflow_started",
        "bid_collection_started",
        "bid_collection_completed",
        "offer_evaluation_started",
        "offer_evaluation_completed",
        "rebid_requested",
        "purchase_order_started",
        "purchase_order_completed",
        "part_completed",
        "part_failed",
        "workflow_completed",
        "workflow_failed",
    ]
    status: Literal["accepted", "running", "retrying", "completed", "partial", "failed"]
    message: str = Field(min_length=1)
    payload: dict[str, Any]


class OrchestrationError(BaseModel):
    """Structured orchestration error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class SelectedOffer(BaseModel):
    """Selected offer summary."""

    model_config = ConfigDict(extra="forbid")

    offer_id: str
    supplier_id: str
    supplier_name: str
    price: float
    currency: str
    delivery_date: str
    quality_score: float
    reliability_score: float
    valid_until: str


class BidCollectionSummary(BaseModel):
    """Bid collection result summary."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "partial", "failed", ""]
    identified_suppliers_count: int = Field(ge=0)
    offers_count: int = Field(ge=0)


class EvaluationSummary(BaseModel):
    """Offer evaluation result summary."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["selected_offer", "no_valid_offers", ""]
    selected_offer: SelectedOffer
    explanation: str


class PurchaseOrderSummary(BaseModel):
    """Purchase order registration result summary."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["registered", "failed", "skipped", ""]
    purchase_order_id: str
    external_reference: str
    registered_at: str


class PartOrchestrationResult(BaseModel):
    """Terminal orchestration result for one requested part."""

    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    material_code: str = Field(min_length=1)
    status: Literal[
        "purchase_order_created",
        "winner_selected",
        "no_valid_offer",
        "purchase_order_failed",
        "failed",
    ]
    attempts_used: int = Field(ge=1)
    bid_collection: BidCollectionSummary
    evaluation: EvaluationSummary
    purchase_order: PurchaseOrderSummary
    error: OrchestrationError


class ProcurementOrchestrationResponse(BaseModel):
    """Final response returned by the Procurement Orchestrator Agent."""

    model_config = ConfigDict(extra="forbid")

    orchestration_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    status: Literal[
        "completed_with_purchase_orders",
        "completed_without_purchase_orders",
        "completed_without_valid_offer",
        "partial",
        "failed",
    ]
    started_at: datetime
    completed_at: datetime
    part_results: list[PartOrchestrationResult] = Field(min_length=1)
    message: str = Field(min_length=1)
    error: OrchestrationError
