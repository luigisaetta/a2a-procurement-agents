"""
Typed request and response models for purchase order registration.

Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Pydantic models mirroring the canonical JSON Schemas used
                by the Purchase Order Agent.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Supplier(BaseModel):
    """Supplier receiving the purchase order."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: str = Field(min_length=1)
    supplier_name: str = Field(min_length=1)


class PurchaseOrderLineItem(BaseModel):
    """Single purchase order line item."""

    model_config = ConfigDict(extra="forbid")

    material_code: str = Field(min_length=1)
    material_description: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit_of_measure: str = Field(min_length=1)
    unit_price: float = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    requested_delivery_date: date
    confirmed_delivery_date: date


class SourceOffer(BaseModel):
    """Selected source offer used to create the purchase order."""

    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(min_length=1)
    price: float = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class CreatePurchaseOrderRequest(BaseModel):
    """Input payload accepted by the Purchase Order Agent."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    purchase_order_id: str = Field(min_length=1)
    plant_code: str = Field(min_length=1)
    supplier: Supplier
    line_items: list[PurchaseOrderLineItem] = Field(min_length=1)
    source_offer: SourceOffer


class PurchaseOrderRegistration(BaseModel):
    """Purchase order registration details."""

    model_config = ConfigDict(extra="forbid")

    purchase_order_id: str
    external_reference: str
    registered_at: str


class PurchaseOrderError(BaseModel):
    """Structured purchase order registration error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class CreatePurchaseOrderResponse(BaseModel):
    """Output payload returned by the Purchase Order Agent."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    status: Literal["registered", "failed"]
    purchase_order: PurchaseOrderRegistration
    message: str
    error: PurchaseOrderError
