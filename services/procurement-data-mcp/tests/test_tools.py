"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Unit tests for the Procurement Data MCP tool layer.
"""

# pylint: disable=unused-argument

from __future__ import annotations

import pytest

from procurement_data_mcp.tools import ProcurementDataTools, ToolError


class FakeRepository:
    """In-memory repository used by tool tests."""

    plants = [
        {
            "plant_id": "PLANT-001",
            "plant_code": "DE-MUN",
            "plant_name": "LuxEV Munich Assembly Plant",
            "country_code": "DE",
            "country_name": "Germany",
            "city": "Munich",
            "address": "Leopoldstrasse 240 Munich",
            "is_active": True,
        }
    ]
    parts = [
        {
            "part_id": "PART-001",
            "part_code": "EV-BAT-MOD-001",
            "part_name": "High Density Battery Module",
            "description": "Modular lithium battery pack segment",
            "category": "battery",
            "unit_of_measure": "EA",
            "is_active": True,
        }
    ]
    suppliers = [
        {
            "supplier_id": "SUP-001",
            "supplier_name": "VoltEdge Components",
            "country_code": "DE",
            "country_name": "Germany",
            "contact_endpoint": "mock://suppliers/SUP-001/offers",
            "currency": "EUR",
            "quality_score": 94,
            "reliability_score": 92,
            "is_active": True,
        }
    ]
    supplier_rows = [
        {
            "supplier_part_id": "SP-001",
            "supplier_id": "SUP-001",
            "supplier_name": "VoltEdge Components",
            "contact_endpoint": "mock://suppliers/SUP-001/offers",
            "currency": "EUR",
            "quality_score": 94,
            "reliability_score": 92,
            "lead_time_days": 14,
            "min_order_quantity": 10,
            "is_preferred": True,
        }
    ]
    part_rows = [
        {
            "supplier_part_id": "SP-001",
            "part_id": "PART-001",
            "part_code": "EV-BAT-MOD-001",
            "part_name": "High Density Battery Module",
            "category": "battery",
            "unit_of_measure": "EA",
            "lead_time_days": 14,
            "min_order_quantity": 10,
            "is_preferred": True,
        }
    ]

    def list_plants(self, *, limit: int, offset: int, active_only: bool):
        """List plants."""

        return self.plants[offset : offset + limit]

    def get_plant(self, *, plant_id=None, plant_code=None):
        """Return a plant."""

        for plant in self.plants:
            if plant_id == plant["plant_id"] or plant_code == plant["plant_code"]:
                return plant
        return None

    def list_parts(self, *, category, limit: int, offset: int, active_only: bool):
        """List parts."""

        rows = [
            part
            for part in self.parts
            if category is None or part["category"] == category
        ]
        return rows[offset : offset + limit]

    def get_part(self, *, part_id=None, part_code=None):
        """Return a part."""

        for part in self.parts:
            if part_id == part["part_id"] or part_code == part["part_code"]:
                return part
        return None

    def list_suppliers(self, *, limit: int, offset: int, active_only: bool):
        """List suppliers."""

        return self.suppliers[offset : offset + limit]

    def get_supplier(self, *, supplier_id: str):
        """Return a supplier."""

        for supplier in self.suppliers:
            if supplier_id == supplier["supplier_id"]:
                return supplier
        return None

    def list_suppliers_for_part(self, *, part_id: str, active_only: bool):
        """List suppliers for a part."""

        return self.supplier_rows if part_id == "PART-001" else []

    def list_parts_for_supplier(self, *, supplier_id: str, active_only: bool):
        """List parts for a supplier."""

        return self.part_rows if supplier_id == "SUP-001" else []


@pytest.fixture(name="tools")
def tools_fixture() -> ProcurementDataTools:
    """Build tool layer with fake repository."""

    return ProcurementDataTools(FakeRepository())


def test_list_plants_returns_paged_response(tools: ProcurementDataTools) -> None:
    """Return paged plant data."""

    result = tools.list_plants()

    assert result["count"] == 1
    assert result["items"][0]["plant_code"] == "DE-MUN"


def test_get_part_requires_exactly_one_identifier(
    tools: ProcurementDataTools,
) -> None:
    """Reject ambiguous part identifiers."""

    with pytest.raises(ToolError) as exc_info:
        tools.get_part(part_id="PART-001", part_code="EV-BAT-MOD-001")

    assert exc_info.value.code == "INVALID_IDENTIFIER_ARGUMENTS"


def test_get_supplier_returns_structured_not_found(
    tools: ProcurementDataTools,
) -> None:
    """Return a structured error for an unknown supplier."""

    with pytest.raises(ToolError) as exc_info:
        tools.get_supplier("SUP-UNKNOWN")

    assert exc_info.value.to_dict()["code"] == "SUPPLIER_NOT_FOUND"


def test_find_suppliers_for_part_enriches_quantity_eligibility(
    tools: ProcurementDataTools,
) -> None:
    """Return supplier candidates enriched with eligibility."""

    result = tools.find_suppliers_for_part(
        part_code="EV-BAT-MOD-001", plant_code="DE-MUN", quantity=8
    )

    assert result["part"]["part_id"] == "PART-001"
    assert result["plant"]["plant_id"] == "PLANT-001"
    assert result["items"][0]["eligible_for_quantity"] is False


def test_invalid_limit_is_rejected(tools: ProcurementDataTools) -> None:
    """Reject invalid pagination arguments."""

    with pytest.raises(ToolError) as exc_info:
        tools.list_parts(limit=201)

    assert exc_info.value.code == "INVALID_LIMIT"
