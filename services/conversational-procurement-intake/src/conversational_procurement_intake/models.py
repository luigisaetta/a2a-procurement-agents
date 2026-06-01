"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Pydantic models for the conversational procurement intake layer.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

IntakeState = Literal[
    "needs_clarification",
    "ready_for_confirmation",
    "ready_for_orchestration",
    "submitted",
    "cancelled",
    "failed",
]


class SupplierSearchHints(BaseModel):
    """Optional hints used during supplier discovery."""

    model_config = ConfigDict(extra="forbid")

    commodity_category: str = ""
    required_certifications: list[str] = Field(default_factory=list)


class PartOrchestrationRequest(BaseModel):
    """Requested procurement part sent to the Procurement Orchestrator."""

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


class ProcurementOrchestrationRequest(BaseModel):
    """Structured request accepted by the Procurement Orchestrator."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    evaluation_policy_id: str = Field(min_length=1)
    response_deadline: datetime
    auto_create_purchase_order: bool
    max_rebid_attempts: int = Field(default=2, ge=0, le=2)
    sourcing_constraints: SourcingConstraints
    parts: list[PartOrchestrationRequest] = Field(min_length=1)


class ProcurementOrchestrationEvent(BaseModel):
    """Normalized orchestration progress event relayed to the UI."""

    model_config = ConfigDict(extra="allow")

    orchestration_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    timestamp: datetime
    event_type: str = Field(min_length=1)
    status: str = Field(min_length=1)
    message: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class ProcurementOrchestrationResponse(BaseModel):
    """Terminal orchestration response relayed to the UI."""

    model_config = ConfigDict(extra="allow")

    orchestration_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    part_results: list[dict[str, Any]]
    message: str = Field(min_length=1)
    error: dict[str, Any] = Field(default_factory=dict)


class DefaultApplied(BaseModel):
    """Default value applied during intake."""

    field: str
    value: Any
    reason: str


class ClarificationAmbiguity(BaseModel):
    """Ambiguous field that requires user choice."""

    field: str
    reason: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class StartSessionRequest(BaseModel):
    """HTTP request used to start an intake session."""

    model_config = ConfigDict(extra="forbid")

    requested_by: str = Field(min_length=1)


class UserMessageRequest(BaseModel):
    """HTTP request containing one natural-language user message."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    requested_by: str | None = None


class ConfirmSessionRequest(BaseModel):
    """HTTP request used to confirm the structured orchestration payload."""

    model_config = ConfigDict(extra="forbid")

    confirmed: bool = True
    orchestration_request: ProcurementOrchestrationRequest | None = None


class IntakeSessionResponse(BaseModel):
    """HTTP response returned for intake session operations."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    state: IntakeState
    message: str
    known_fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    ambiguities: list[ClarificationAmbiguity] = Field(default_factory=list)
    defaults_applied: list[DefaultApplied] = Field(default_factory=list)
    confirmation_summary: dict[str, Any] | None = None
    orchestration_request: ProcurementOrchestrationRequest | None = None
    orchestration_id: str | None = None


class OrchestrationEventsResponse(BaseModel):
    """Polling response containing orchestration events after a cursor."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    orchestration_id: str | None
    state: IntakeState
    events: list[ProcurementOrchestrationEvent]
    next_cursor: int
    terminal_result: ProcurementOrchestrationResponse | None = None
