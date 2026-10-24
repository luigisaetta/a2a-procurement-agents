"""
Typed request and response models for purchase order registration and reads.

Author: L. Saetta
Date Last Modified: 2026-10-24
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
    purchase_order_id: str | None = Field(default=None, min_length=1)
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


LIST_RECENT_PURCHASE_ORDERS = "list_recent_purchase_orders"


class ListRecentPurchaseOrdersRequest(BaseModel):
    """Read-only request for the most recently registered purchase orders."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["list_recent_purchase_orders"]
    limit: int = Field(default=10, ge=1, le=100)


class PurchaseOrderRecord(BaseModel):
    """One persisted purchase order with all stored fields."""

    model_config = ConfigDict(extra="forbid")

    purchase_order_id: str
    request_id: str
    offer_id: str
    supplier_id: str
    supplier_name: str
    plant_code: str
    material_code: str
    material_description: str
    quantity: float
    unit_of_measure: str
    unit_price: float
    total_amount: float
    currency: str
    requested_delivery_date: date
    confirmed_delivery_date: date
    status: Literal["registered", "failed", "cancelled"]
    external_reference: str
    registered_at: str
    created_at: str
    updated_at: str


class ListRecentPurchaseOrdersResponse(BaseModel):
    """Most recent purchase orders, newest first."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed"]
    limit: int = Field(ge=1, le=100)
    purchase_orders: list[PurchaseOrderRecord]
    message: str
    error: PurchaseOrderError
