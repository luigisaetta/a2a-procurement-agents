"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Tests for the Bid Collection Agent deterministic workflow.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_collection_agent.config import Settings
from bid_collection_agent.models import (
    IdentifiedSupplier,
    PartBidRequest,
    SourcingConstraints,
)
from bid_collection_agent.pipeline import BidCollectionWorkflowAgent


class FakeMcpSupplierDiscoveryProvider:  # pylint: disable=too-few-public-methods
    """Fake supplier discovery provider that mimics MCP-backed output."""

    def __init__(self, suppliers: list[IdentifiedSupplier]) -> None:
        """Initialize the fake provider."""

        self.suppliers = suppliers
        self.calls: list[tuple[str, float]] = []

    async def identify_suppliers(
        self,
        part: PartBidRequest,
        constraints: SourcingConstraints,
    ) -> list[IdentifiedSupplier]:
        """Return configured suppliers."""

        self.calls.append((part.part_id, part.quantity))
        return self.suppliers[: constraints.max_suppliers_per_part]


def _settings() -> Settings:
    """Build test settings."""

    root = Path(__file__).resolve().parents[3]
    return Settings(
        agent_port=8000,
        agent_api_key="secret",
        procurement_data_mcp_url="http://127.0.0.1:8010/mcp",
        mcp_timeout_seconds=10,
        request_schema_file=root / "specs/schemas/collect-bids-request.schema.json",
        response_schema_file=root / "specs/schemas/collect-bids-response.schema.json",
    )


def _request_json() -> str:
    """Build a valid collect bids request."""

    return json.dumps(
        {
            "request_id": "REQ-2026-0001",
            "currency": "EUR",
            "evaluation_policy_id": "standard-urgent-procurement-v1",
            "response_deadline": "2026-05-29T12:00:00Z",
            "sourcing_constraints": {
                "max_suppliers_per_part": 2,
                "allowed_regions": ["EU"],
                "preferred_supplier_ids": [],
            },
            "parts": [
                {
                    "part_id": "PART-001",
                    "plant_code": "DE-MUN",
                    "material_code": "EV-BAT-MOD-001",
                    "material_description": "Battery module",
                    "quantity": 10,
                    "unit_of_measure": "EA",
                    "required_delivery_date": "2026-06-15",
                    "supplier_search_hints": {
                        "commodity_category": "battery-system",
                        "required_certifications": [],
                    },
                }
            ],
        }
    )


@pytest.mark.anyio
async def test_pipeline_collects_bids_from_mcp_suppliers() -> None:
    """Collect supplier offers using suppliers discovered through MCP."""

    discovery = FakeMcpSupplierDiscoveryProvider(
        [
            IdentifiedSupplier(
                supplier_id="SUP-001",
                supplier_name="VoltEdge Components",
                api_endpoint="mock://suppliers/SUP-001/offers",
                region="EU",
                selection_reason="Preferred supplier for the requested part.",
            ),
            IdentifiedSupplier(
                supplier_id="SUP-002",
                supplier_name="CellForge Systems",
                api_endpoint="mock://suppliers/SUP-002/offers",
                region="EU",
                selection_reason="Supplier can provide the requested part.",
            ),
        ]
    )
    agent = BidCollectionWorkflowAgent(
        _settings(),
        supplier_discovery_provider=discovery,
    )

    events = [event async for event in agent.run(_request_json())]

    assert discovery.calls == [("PART-001", 10.0)]
    final = json.loads(events[-1].final_message)
    assert final["request_id"] == "REQ-2026-0001"
    assert final["status"] == "completed"
    assert final["part_results"][0]["status"] == "offers_collected"
    assert len(final["part_results"][0]["identified_suppliers"]) == 2
    assert len(final["part_results"][0]["offers"]) == 2
    assert final["evaluation_requests"][0]["material_code"] == "EV-BAT-MOD-001"
    assert len(final["evaluation_requests"][0]["offers"]) == 2


@pytest.mark.anyio
async def test_pipeline_returns_failed_when_mcp_finds_no_suppliers() -> None:
    """Return a valid failed response when MCP finds no eligible suppliers."""

    agent = BidCollectionWorkflowAgent(
        _settings(),
        supplier_discovery_provider=FakeMcpSupplierDiscoveryProvider([]),
    )

    events = [event async for event in agent.run(_request_json())]

    final = json.loads(events[-1].final_message)
    assert final["status"] == "failed"
    assert final["part_results"][0]["status"] == "no_offers"
    assert final["part_results"][0]["supplier_responses"][0]["supplier_id"] == (
        "NO-SUPPLIER"
    )
    assert final["evaluation_requests"] == []


@pytest.mark.anyio
async def test_pipeline_rejects_duplicate_part_ids() -> None:
    """Reject duplicate requested part IDs."""

    payload = json.loads(_request_json())
    payload["parts"].append(payload["parts"][0])
    agent = BidCollectionWorkflowAgent(
        _settings(),
        supplier_discovery_provider=FakeMcpSupplierDiscoveryProvider([]),
    )

    with pytest.raises(ValueError, match="duplicate part_id"):
        async for _event in agent.run(json.dumps(payload)):
            pass
