"""
Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    Tests for deterministic conversational intake extraction.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from conversational_procurement_intake.extraction import (
    CandidateIntakeFields,
    DeterministicIntakeExtractor,
    build_extraction_result,
)
from conversational_procurement_intake.master_data import (
    McpMasterDataResolver,
    StaticMasterDataResolver,
)


@pytest.mark.anyio
async def test_extractor_requests_missing_response_deadline() -> None:
    """Ask for clarification when a mandatory deadline is missing."""

    extractor = DeterministicIntakeExtractor(StaticMasterDataResolver())

    result = await extractor.extract(
        "We need 10 high density battery modules for Munich by June 15.",
        "operator@example.com",
        1,
    )

    assert result.orchestration_request is None
    assert "response_deadline" in result.missing_fields
    assert result.message == "Which bid response deadline should I use?"


@pytest.mark.anyio
async def test_extractor_requests_all_missing_details() -> None:
    """Ask for all missing mandatory values in one clarification."""

    extractor = DeterministicIntakeExtractor(StaticMasterDataResolver())

    result = await extractor.extract(
        "We need battery modules for the Munich plant as soon as possible.",
        "operator@example.com",
        2,
    )

    assert result.orchestration_request is None
    assert result.missing_fields == [
        "parts[0].quantity",
        "parts[0].required_delivery_date",
        "response_deadline",
    ]
    assert result.message == (
        "Please provide these missing details: What quantity do you need? "
        "What required delivery date should I use? "
        "Which bid response deadline should I use?"
    )


@pytest.mark.anyio
async def test_extractor_builds_orchestration_request_with_defaults() -> None:
    """Build a valid orchestration request after all mandatory fields exist."""

    extractor = DeterministicIntakeExtractor(StaticMasterDataResolver())

    result = await extractor.extract(
        (
            "We need 10 high density battery modules for Munich by June 15. "
            "Bid deadline May 29 at 12. Ask up to 3 European suppliers and "
            "create the purchase order automatically."
        ),
        "operator@example.com",
        7,
    )

    request = result.orchestration_request
    assert request is not None
    assert request.request_id == "REQ-2026-0007"
    assert request.currency == "EUR"
    assert request.auto_create_purchase_order is True
    assert request.sourcing_constraints.allowed_regions == ["EU"]
    assert request.parts[0].part_id == "PART-001"
    assert request.parts[0].plant_code == "DE-MUN"
    assert request.parts[0].unit_of_measure == "EA"
    assert result.missing_fields == []
    assert {item.field for item in result.defaults_applied} >= {
        "currency",
        "evaluation_policy_id",
    }


@pytest.mark.anyio
async def test_extractor_does_not_use_delivery_day_as_quantity() -> None:
    """Do not infer quantity from dates in a clarification message."""

    extractor = DeterministicIntakeExtractor(StaticMasterDataResolver())

    result = await extractor.extract(
        (
            "We need battery modules for the Munich plant as soon as possible. "
            "Required delivery date is June 15. Bid deadline is today at 17:00. "
            "Ask up to 3 European suppliers and create the purchase order "
            "automatically."
        ),
        "operator@example.com",
        8,
    )

    assert result.orchestration_request is None
    assert "parts[0].quantity" in result.missing_fields
    assert result.message == "What quantity do you need?"


@pytest.mark.anyio
async def test_extractor_reads_quantity_from_units_clarification() -> None:
    """Accept quantity when the user provides it with units."""

    extractor = DeterministicIntakeExtractor(StaticMasterDataResolver())

    result = await extractor.extract(
        (
            "We need battery modules for the Munich plant as soon as possible. "
            "Quantity is 10 units. Required delivery date is June 15. "
            "Bid deadline is today at 17:00. Ask up to 3 European suppliers "
            "and create the purchase order automatically."
        ),
        "operator@example.com",
        9,
    )

    request = result.orchestration_request
    assert request is not None
    assert request.parts[0].quantity == 10


@pytest.mark.anyio
async def test_extractor_resolves_full_demo_catalog_from_mcp() -> None:
    """Resolve parts beyond the static fallback catalog through MCP data."""

    extractor = DeterministicIntakeExtractor(
        McpMasterDataResolver(
            "http://mcp.example/mcp",
            client_factory=_FakeMcpClient,
        )
    )

    result = await extractor.extract(
        (
            "I need 16 units of EV-DC-DC-009, High Voltage DC DC Converter, "
            "for the Turin plant IT-TOR. The required delivery date is "
            "2026-07-25. The bid response deadline is 2026-06-15 at 17:00 UTC. "
            "Create the final purchase order."
        ),
        "operator@example.com",
        10,
    )

    request = result.orchestration_request
    assert request is not None
    assert request.auto_create_purchase_order is True
    assert request.parts[0].part_id == "PART-009"
    assert request.parts[0].material_code == "EV-DC-DC-009"
    assert request.parts[0].plant_code == "IT-TOR"


@pytest.mark.anyio
async def test_extraction_falls_back_to_conversation_text_for_grounding() -> None:
    """Ground part and plant codes even if candidate references are empty."""

    result = await build_extraction_result(
        CandidateIntakeFields(
            quantity=16,
            required_delivery_date=date(2026, 7, 25),
            response_deadline=datetime(2026, 6, 15, 17, 0, tzinfo=UTC),
            auto_create_purchase_order=True,
        ),
        McpMasterDataResolver(
            "http://mcp.example/mcp",
            client_factory=_FakeMcpClient,
        ),
        "operator@example.com",
        11,
        "Please start a tender for EV-DC-DC-009 at IT-TOR with final PO creation.",
    )

    request = result.orchestration_request
    assert request is not None
    assert request.parts[0].part_id == "PART-009"
    assert request.parts[0].plant_code == "IT-TOR"


@pytest.mark.anyio
async def test_extraction_prefers_specific_part_name_over_category_matches() -> None:
    """Resolve the UI sample part even when several active battery parts exist."""

    result = await build_extraction_result(
        CandidateIntakeFields(
            material_reference="battery modules",
            plant_reference="Munich plant",
            quantity=10,
            required_delivery_date=date(2026, 6, 15),
            response_deadline=datetime(2026, 5, 29, 12, 0, tzinfo=UTC),
            auto_create_purchase_order=True,
            max_suppliers_per_part=3,
            allowed_regions=["Europe"],
        ),
        McpMasterDataResolver(
            "http://mcp.example/mcp",
            client_factory=_FakeBatteryCatalogMcpClient,
        ),
        "operator@example.com",
        12,
        (
            "We need 10 high density battery modules for the Munich plant by "
            "June 15. Bid deadline May 29 at 12. Ask up to 3 European suppliers "
            "and create the purchase order automatically."
        ),
    )

    request = result.orchestration_request
    assert request is not None
    assert result.ambiguities == []
    assert request.parts[0].part_id == "PART-001"
    assert request.parts[0].material_code == "EV-BAT-MOD-001"


class _FakeMcpResult:  # pylint: disable=too-few-public-methods
    """Fake FastMCP result carrying structured content."""

    def __init__(self, structured_content: dict) -> None:
        """Initialize the fake result."""

        setattr(self, "structuredContent", structured_content)


class _FakeMcpClient:
    """Fake async MCP client for resolver tests."""

    def __init__(self, mcp_url: str, timeout: float) -> None:
        """Accept the same constructor shape as FastMCP Client."""

        self.mcp_url = mcp_url
        self.timeout = timeout

    async def __aenter__(self) -> "_FakeMcpClient":
        """Enter the fake async context manager."""

        return self

    async def __aexit__(self, *_args) -> None:
        """Exit the fake async context manager."""

    async def call_tool(self, name: str, _arguments: dict) -> _FakeMcpResult:
        """Return fake master data tool responses."""

        if name == "list_parts":
            return _FakeMcpResult(
                {
                    "items": [
                        {
                            "part_id": "PART-009",
                            "part_code": "EV-DC-DC-009",
                            "part_name": "High Voltage DC DC Converter",
                            "description": "Converter for HV to low voltage systems",
                            "category": "power electronics",
                            "unit_of_measure": "EA",
                            "is_active": True,
                        }
                    ]
                }
            )
        if name == "list_plants":
            return _FakeMcpResult(
                {
                    "items": [
                        {
                            "plant_id": "PLANT-002",
                            "plant_code": "IT-TOR",
                            "plant_name": "LuxEV Turin Assembly Plant",
                            "city": "Turin",
                            "country_code": "IT",
                            "is_active": True,
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected tool call: {name}")


class _FakeBatteryCatalogMcpClient(
    _FakeMcpClient
):  # pylint: disable=too-few-public-methods
    """Fake MCP client with multiple battery category matches."""

    async def call_tool(self, name: str, _arguments: dict) -> _FakeMcpResult:
        """Return fake master data with an exact part-name match and broad matches."""

        if name == "list_parts":
            return _FakeMcpResult(
                {
                    "items": [
                        {
                            "part_id": "PART-001",
                            "part_code": "EV-BAT-MOD-001",
                            "part_name": "High Density Battery Module",
                            "description": "Modular lithium battery pack segment",
                            "category": "battery",
                            "unit_of_measure": "EA",
                            "is_active": True,
                        },
                        {
                            "part_id": "PART-002",
                            "part_code": "EV-BAT-CELL-002",
                            "part_name": "Prismatic Battery Cell",
                            "description": "High energy density prismatic cell",
                            "category": "battery",
                            "unit_of_measure": "EA",
                            "is_active": True,
                        },
                    ]
                }
            )
        if name == "list_plants":
            return _FakeMcpResult(
                {
                    "items": [
                        {
                            "plant_id": "PLANT-001",
                            "plant_code": "DE-MUN",
                            "plant_name": "LuxEV Munich Assembly Plant",
                            "city": "Munich",
                            "country_code": "DE",
                            "is_active": True,
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected tool call: {name}")
