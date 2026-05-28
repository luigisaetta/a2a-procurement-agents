"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Tests for MCP supplier discovery mapping and filtering.
"""

from __future__ import annotations

from bid_collection_agent.models import IdentifiedSupplier, SourcingConstraints
from bid_collection_agent.supplier_discovery_provider import _apply_constraints


def test_apply_constraints_prefers_requested_suppliers_and_limits_results() -> None:
    """Prefer requested suppliers and enforce the configured limit."""

    suppliers = [
        IdentifiedSupplier(
            supplier_id="SUP-003",
            supplier_name="Supplier 3",
            api_endpoint="mock://suppliers/SUP-003/offers",
            region="EU",
            selection_reason="Candidate.",
        ),
        IdentifiedSupplier(
            supplier_id="SUP-001",
            supplier_name="Supplier 1",
            api_endpoint="mock://suppliers/SUP-001/offers",
            region="EU",
            selection_reason="Candidate.",
        ),
        IdentifiedSupplier(
            supplier_id="SUP-002",
            supplier_name="Supplier 2",
            api_endpoint="mock://suppliers/SUP-002/offers",
            region="EU",
            selection_reason="Candidate.",
        ),
    ]

    result = _apply_constraints(
        suppliers,
        SourcingConstraints(
            max_suppliers_per_part=2,
            allowed_regions=["EU"],
            preferred_supplier_ids=["SUP-002"],
        ),
    )

    assert [supplier.supplier_id for supplier in result] == ["SUP-002", "SUP-001"]
