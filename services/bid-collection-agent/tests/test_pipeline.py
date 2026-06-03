"""
Author: L. Saetta
Date Last Modified: 2026-06-03
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
from bid_collection_agent.supplier_discovery_provider import SupplierDiscoveryResult


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
    ) -> SupplierDiscoveryResult:
        """Return configured suppliers."""

        self.calls.append((part.part_id, part.quantity))
        return SupplierDiscoveryResult(
            suppliers=self.suppliers[: constraints.max_suppliers_per_part],
            reference_unit_price=1450,
            reference_currency="EUR",
        )


def _settings() -> Settings:
    """Build test settings."""

    root = Path(__file__).resolve().parents[3]
    return Settings(
        agent_port=8000,
        agent_api_key="secret",
        procurement_data_mcp_url="http://127.0.0.1:8011/mcp",
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

    hook = _RecordingHook()
    discovery = FakeMcpSupplierDiscoveryProvider(
        [
            IdentifiedSupplier(
                supplier_id="SUP-001",
                supplier_name="VoltEdge Components",
                api_endpoint="mock://suppliers/SUP-001/offers",
                region="EU",
                country_code="DE",
                selection_reason="Preferred supplier for the requested part.",
            ),
            IdentifiedSupplier(
                supplier_id="SUP-002",
                supplier_name="CellForge Systems",
                api_endpoint="mock://suppliers/SUP-002/offers",
                region="EU",
                country_code="IT",
                selection_reason="Supplier can provide the requested part.",
            ),
        ]
    )
    agent = BidCollectionWorkflowAgent(
        _settings(),
        supplier_discovery_provider=discovery,
        hooks=[hook],
    )

    events = [event async for event in agent.run(_request_json())]

    assert hook.after_success == [True]
    assert hook.after_agent_ids == ["bid-collection-agent"]
    assert discovery.calls == [("PART-001", 10.0)]
    final = json.loads(events[-1].final_message)
    assert final["request_id"] == "REQ-2026-0001"
    assert final["status"] == "completed"
    assert final["part_results"][0]["status"] == "offers_collected"
    assert len(final["part_results"][0]["identified_suppliers"]) == 2
    assert len(final["part_results"][0]["offers"]) == 2
    first_offer = final["part_results"][0]["offers"][0]
    assert first_offer["parts_cost"] > 0
    assert first_offer["shipping_cost"] > 0
    assert first_offer["price"] == round(
        first_offer["parts_cost"] + first_offer["shipping_cost"], 2
    )
    assert 1450 * 10 * 0.70 <= first_offer["parts_cost"] <= 1450 * 10 * 1.30
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

    hook = _RecordingHook()
    payload = json.loads(_request_json())
    payload["parts"].append(payload["parts"][0])
    agent = BidCollectionWorkflowAgent(
        _settings(),
        supplier_discovery_provider=FakeMcpSupplierDiscoveryProvider([]),
        hooks=[hook],
    )

    with pytest.raises(ValueError, match="duplicate part_id"):
        async for _event in agent.run(json.dumps(payload)):
            pass

    assert hook.after_success == [False]
    assert hook.after_error_counts == [1]


class _RecordingHook:
    """Record Locus lifecycle hook calls for assertions."""

    def __init__(self) -> None:
        """Initialize recorded hook call lists."""

        self.after_success: list[bool] = []
        self.after_agent_ids: list[str | None] = []
        self.after_error_counts: list[int] = []

    async def on_before_invocation(self, _prompt, state):
        """Return state unchanged from before-invocation."""

        return state

    async def on_after_invocation(self, state, success):
        """Record after-invocation calls."""

        self.after_success.append(success)
        self.after_agent_ids.append(state.agent_id)
        self.after_error_counts.append(len(state.errors))
