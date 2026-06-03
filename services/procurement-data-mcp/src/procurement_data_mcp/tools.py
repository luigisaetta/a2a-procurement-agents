"""
Author: L. Saetta
Date Last Modified: 2026-06-03
License: MIT
Description:    Read-only MCP tool logic for procurement master data.
"""

from __future__ import annotations

from typing import Any, Protocol

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class ToolError(ValueError):
    """Structured tool error raised for invalid inputs or missing records."""

    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        """Initialize the tool error.

        Args:
            code: Stable error code.
            message: Human-readable error message.
            details: Optional structured error details.
        """

        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Return the error as a JSON-compatible dictionary."""

        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ProcurementDataRepositoryProtocol(Protocol):
    """Repository operations required by the MCP tool layer."""

    def list_plants(
        self, *, limit: int, offset: int, active_only: bool
    ) -> list[dict[str, Any]]:
        """List plants."""

    def get_plant(
        self, *, plant_id: str | None = None, plant_code: str | None = None
    ) -> dict[str, Any] | None:
        """Return one plant."""

    def list_parts(
        self, *, category: str | None, limit: int, offset: int, active_only: bool
    ) -> list[dict[str, Any]]:
        """List parts."""

    def get_part(
        self, *, part_id: str | None = None, part_code: str | None = None
    ) -> dict[str, Any] | None:
        """Return one part."""

    def list_suppliers(
        self, *, limit: int, offset: int, active_only: bool
    ) -> list[dict[str, Any]]:
        """List suppliers."""

    def get_supplier(self, *, supplier_id: str) -> dict[str, Any] | None:
        """Return one supplier."""

    def list_suppliers_for_part(
        self, *, part_id: str, active_only: bool
    ) -> list[dict[str, Any]]:
        """List suppliers for a part."""

    def list_parts_for_supplier(
        self, *, supplier_id: str, active_only: bool
    ) -> list[dict[str, Any]]:
        """List parts for a supplier."""


class ProcurementDataTools:
    """Read-only procurement data tool implementation."""

    def __init__(self, repository: ProcurementDataRepositoryProtocol) -> None:
        """Initialize the tool layer.

        Args:
            repository: Read-only data repository.
        """

        self._repository = repository

    def list_plants(
        self, limit: int = DEFAULT_LIMIT, offset: int = 0, active_only: bool = True
    ) -> dict[str, Any]:
        """Return plants with pagination."""

        limit, offset = _validate_pagination(limit, offset)
        items = self._repository.list_plants(
            limit=limit, offset=offset, active_only=active_only
        )
        return _paged(items, limit, offset)

    def get_plant(
        self, plant_id: str | None = None, plant_code: str | None = None
    ) -> dict[str, Any]:
        """Return one plant by ID or code."""

        _validate_exactly_one("plant_id", plant_id, "plant_code", plant_code)
        plant = self._repository.get_plant(
            plant_id=_clean(plant_id), plant_code=_clean(plant_code)
        )
        if plant is None:
            raise ToolError(
                "PLANT_NOT_FOUND",
                "No plant was found for the provided identifier.",
                {"plant_id": plant_id, "plant_code": plant_code},
            )
        return {"plant": plant}

    def list_parts(
        self,
        category: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        active_only: bool = True,
    ) -> dict[str, Any]:
        """Return parts with optional category filtering."""

        limit, offset = _validate_pagination(limit, offset)
        items = self._repository.list_parts(
            category=_clean(category),
            limit=limit,
            offset=offset,
            active_only=active_only,
        )
        return _paged(items, limit, offset)

    def get_part(
        self, part_id: str | None = None, part_code: str | None = None
    ) -> dict[str, Any]:
        """Return one part by ID or code."""

        _validate_exactly_one("part_id", part_id, "part_code", part_code)
        part = self._get_part(part_id=part_id, part_code=part_code)
        return {"part": part}

    def list_suppliers(
        self, limit: int = DEFAULT_LIMIT, offset: int = 0, active_only: bool = True
    ) -> dict[str, Any]:
        """Return suppliers with pagination."""

        limit, offset = _validate_pagination(limit, offset)
        items = self._repository.list_suppliers(
            limit=limit, offset=offset, active_only=active_only
        )
        return _paged(items, limit, offset)

    def get_supplier(self, supplier_id: str) -> dict[str, Any]:
        """Return one supplier by ID."""

        supplier_id = _require_string("supplier_id", supplier_id)
        supplier = self._repository.get_supplier(supplier_id=supplier_id)
        if supplier is None:
            raise ToolError(
                "SUPPLIER_NOT_FOUND",
                f"No supplier was found for supplier_id {supplier_id}.",
                {"supplier_id": supplier_id},
            )
        return {"supplier": supplier}

    def list_suppliers_for_part(
        self,
        part_id: str | None = None,
        part_code: str | None = None,
        active_only: bool = True,
    ) -> dict[str, Any]:
        """Return suppliers that can provide a part."""

        _validate_exactly_one("part_id", part_id, "part_code", part_code)
        part = self._get_part(part_id=part_id, part_code=part_code)
        items = self._repository.list_suppliers_for_part(
            part_id=part["part_id"], active_only=active_only
        )
        return {
            "part": _part_summary(part),
            "items": items,
            "count": len(items),
        }

    def list_parts_for_supplier(
        self, supplier_id: str, active_only: bool = True
    ) -> dict[str, Any]:
        """Return parts that a supplier can provide."""

        supplier = self.get_supplier(supplier_id)["supplier"]
        items = self._repository.list_parts_for_supplier(
            supplier_id=supplier["supplier_id"], active_only=active_only
        )
        return {
            "supplier": _supplier_summary(supplier),
            "items": items,
            "count": len(items),
        }

    # The argument list mirrors the public MCP tool contract.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def find_suppliers_for_part(
        self,
        part_id: str | None = None,
        part_code: str | None = None,
        plant_id: str | None = None,
        plant_code: str | None = None,
        quantity: float | int | None = None,
        active_only: bool = True,
    ) -> dict[str, Any]:
        """Return supplier candidates for a sourcing request."""

        _validate_exactly_one("part_id", part_id, "part_code", part_code)
        _validate_at_most_one("plant_id", plant_id, "plant_code", plant_code)
        requested_quantity = _validate_quantity(quantity)
        part = self._get_part(part_id=part_id, part_code=part_code)
        plant = None
        if _clean(plant_id) or _clean(plant_code):
            plant = self.get_plant(plant_id=plant_id, plant_code=plant_code)["plant"]

        items = self._repository.list_suppliers_for_part(
            part_id=part["part_id"], active_only=active_only
        )
        enriched = [
            {
                **item,
                "eligible_for_quantity": _eligible_for_quantity(
                    requested_quantity, item.get("min_order_quantity")
                ),
            }
            for item in items
        ]
        return {
            "part": {
                **_part_summary(part),
                "unit_of_measure": part["unit_of_measure"],
                "reference_unit_price": part["reference_unit_price"],
                "reference_currency": part["reference_currency"],
            },
            "plant": _plant_summary(plant) if plant else None,
            "requested_quantity": requested_quantity,
            "items": enriched,
            "count": len(enriched),
        }

    def _get_part(
        self, *, part_id: str | None = None, part_code: str | None = None
    ) -> dict[str, Any]:
        """Return one part or raise a structured error."""

        part = self._repository.get_part(
            part_id=_clean(part_id), part_code=_clean(part_code)
        )
        if part is None:
            raise ToolError(
                "PART_NOT_FOUND",
                "No part was found for the provided identifier.",
                {"part_id": part_id, "part_code": part_code},
            )
        return part


def _validate_pagination(limit: int, offset: int) -> tuple[int, int]:
    """Validate pagination values."""

    if not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ToolError(
            "INVALID_LIMIT",
            f"limit must be an integer between 1 and {MAX_LIMIT}.",
            {"limit": limit},
        )
    if not isinstance(offset, int) or offset < 0:
        raise ToolError(
            "INVALID_OFFSET",
            "offset must be an integer greater than or equal to 0.",
            {"offset": offset},
        )
    return limit, offset


def _validate_exactly_one(
    first_name: str, first_value: str | None, second_name: str, second_value: str | None
) -> None:
    """Validate that exactly one identifier is present."""

    present = [bool(_clean(first_value)), bool(_clean(second_value))]
    if sum(present) != 1:
        raise ToolError(
            "INVALID_IDENTIFIER_ARGUMENTS",
            f"Exactly one of {first_name} or {second_name} must be provided.",
            {first_name: first_value, second_name: second_value},
        )


def _validate_at_most_one(
    first_name: str, first_value: str | None, second_name: str, second_value: str | None
) -> None:
    """Validate that no more than one identifier is present."""

    if bool(_clean(first_value)) and bool(_clean(second_value)):
        raise ToolError(
            "INVALID_IDENTIFIER_ARGUMENTS",
            f"At most one of {first_name} or {second_name} may be provided.",
            {first_name: first_value, second_name: second_value},
        )


def _validate_quantity(quantity: float | int | None) -> float | int | None:
    """Validate optional quantity."""

    if quantity is None:
        return None
    if not isinstance(quantity, (int, float)) or quantity <= 0:
        raise ToolError(
            "INVALID_QUANTITY",
            "quantity must be a positive number when provided.",
            {"quantity": quantity},
        )
    return quantity


def _eligible_for_quantity(
    quantity: float | int | None, min_order_quantity: float | int | None
) -> bool:
    """Evaluate supplier quantity eligibility."""

    if quantity is None or min_order_quantity is None:
        return True
    return quantity >= min_order_quantity


def _require_string(name: str, value: str) -> str:
    """Validate a required string."""

    cleaned = _clean(value)
    if cleaned is None:
        raise ToolError(
            "MISSING_REQUIRED_ARGUMENT",
            f"{name} must be provided.",
            {name: value},
        )
    return cleaned


def _clean(value: str | None) -> str | None:
    """Normalize optional string input."""

    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _paged(items: list[dict[str, Any]], limit: int, offset: int) -> dict[str, Any]:
    """Build a paged response."""

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "count": len(items),
    }


def _part_summary(part: dict[str, Any]) -> dict[str, Any]:
    """Build a compact part object."""

    return {
        "part_id": part["part_id"],
        "part_code": part["part_code"],
        "part_name": part["part_name"],
        "reference_unit_price": part.get("reference_unit_price", 0),
        "reference_currency": part.get("reference_currency", ""),
    }


def _plant_summary(plant: dict[str, Any]) -> dict[str, Any]:
    """Build a compact plant object."""

    return {
        "plant_id": plant["plant_id"],
        "plant_code": plant["plant_code"],
        "plant_name": plant["plant_name"],
    }


def _supplier_summary(supplier: dict[str, Any]) -> dict[str, Any]:
    """Build a compact supplier object."""

    return {
        "supplier_id": supplier["supplier_id"],
        "supplier_name": supplier["supplier_name"],
    }
