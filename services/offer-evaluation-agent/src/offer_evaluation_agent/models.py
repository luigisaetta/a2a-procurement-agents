"""
Typed request and response models for offer evaluation.

Author: L. Saetta
Date Last Modified: 2026-05-27
License: MIT
Description:    Pydantic models mirroring the canonical JSON Schemas used
                by the Offer Evaluation Agent.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SupplierOffer(BaseModel):
    """Supplier offer received in an evaluation request."""

    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(min_length=1)
    supplier_id: str = Field(min_length=1)
    supplier_name: str = Field(min_length=1)
    price: float = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    delivery_date: date
    quality_score: float = Field(ge=0, le=100)
    reliability_score: float = Field(ge=0, le=100)
    valid_until: date


class EvaluateOffersRequest(BaseModel):
    """Input payload accepted by the Offer Evaluation Agent."""

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


class SelectedOfferDecision(BaseModel):
    """Decision returned when a valid offer is selected."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["selected_offer"]
    selected_offer: SupplierOffer


class NoValidOffersDecision(BaseModel):
    """Decision returned when policy exclusions remove every offer."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["no_valid_offers"]
    reasons: list[str] = Field(min_length=1)


class EvaluateOffersResponse(BaseModel):
    """Output payload returned by the Offer Evaluation Agent."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    decision: SelectedOfferDecision | NoValidOffersDecision = Field(
        discriminator="status"
    )
    explanation: str = Field(min_length=1)
