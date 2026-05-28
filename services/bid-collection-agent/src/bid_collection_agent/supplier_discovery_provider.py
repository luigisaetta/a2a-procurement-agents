"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Supplier discovery provider backed by the Procurement Data MCP Server.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from fastmcp import Client

from bid_collection_agent.models import (
    IdentifiedSupplier,
    PartBidRequest,
    SourcingConstraints,
)


class SupplierDiscoveryProvider(Protocol):  # pylint: disable=too-few-public-methods
    """Supplier discovery provider contract."""

    async def identify_suppliers(
        self,
        part: PartBidRequest,
        constraints: SourcingConstraints,
    ) -> list[IdentifiedSupplier]:
        """Identify eligible suppliers for one requested part."""


class McpSupplierDiscoveryProvider:  # pylint: disable=too-few-public-methods
    """Supplier discovery provider using streamable HTTP MCP tools."""

    def __init__(self, mcp_url: str, timeout_seconds: float = 10.0) -> None:
        """Initialize the provider.

        Args:
            mcp_url: Streamable HTTP endpoint of the procurement data MCP server.
            timeout_seconds: Timeout for MCP calls.
        """

        self._mcp_url = mcp_url
        self._timeout_seconds = timeout_seconds

    async def identify_suppliers(
        self,
        part: PartBidRequest,
        constraints: SourcingConstraints,
    ) -> list[IdentifiedSupplier]:
        """Identify eligible suppliers for one requested part."""

        async with Client(self._mcp_url, timeout=self._timeout_seconds) as client:
            result = await client.call_tool(
                "find_suppliers_for_part",
                {
                    "part_id": part.part_id,
                    "plant_code": part.plant_code,
                    "quantity": part.quantity,
                    "active_only": True,
                },
            )

        payload = _extract_structured_content(result)
        if payload.get("error"):
            error = payload["error"]
            raise RuntimeError(
                f"MCP supplier lookup failed: {error.get('code', 'UNKNOWN')}: "
                f"{error.get('message', '')}"
            )

        candidates = [
            _to_identified_supplier(item)
            for item in payload.get("items", [])
            if item.get("eligible_for_quantity", True)
        ]
        return _apply_constraints(candidates, constraints)


def _extract_structured_content(result: Any) -> dict[str, Any]:
    """Extract structured MCP tool content.

    Args:
        result: FastMCP call tool result.

    Returns:
        JSON-compatible dictionary.
    """

    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    content = getattr(result, "content", [])
    if content and hasattr(content[0], "text"):
        parsed = json.loads(content[0].text)
        if isinstance(parsed, dict):
            return parsed

    raise RuntimeError("MCP supplier lookup did not return structured content.")


def _to_identified_supplier(item: dict[str, Any]) -> IdentifiedSupplier:
    """Convert an MCP supplier candidate into the agent response shape."""

    reason = "Supplier can provide the requested part according to MCP master data."
    if item.get("is_preferred"):
        reason = "Preferred supplier for the requested part in MCP master data."

    return IdentifiedSupplier(
        supplier_id=item["supplier_id"],
        supplier_name=item["supplier_name"],
        api_endpoint=item["contact_endpoint"],
        region=_supplier_region(item),
        selection_reason=reason,
    )


def _supplier_region(item: dict[str, Any]) -> str:
    """Return the sourcing region used by bid collection constraints."""

    country_code = str(item.get("country_code", "")).upper()
    if country_code in {"GB", "UK"}:
        return "UK"
    return "EU"


def _apply_constraints(
    suppliers: list[IdentifiedSupplier],
    constraints: SourcingConstraints,
) -> list[IdentifiedSupplier]:
    """Apply request-level supplier filtering and ordering."""

    allowed_regions = set(constraints.allowed_regions)
    filtered = [
        supplier
        for supplier in suppliers
        if not allowed_regions or supplier.region in allowed_regions
    ]
    preferred = set(constraints.preferred_supplier_ids)
    filtered.sort(
        key=lambda supplier: (
            supplier.supplier_id not in preferred,
            supplier.supplier_id,
        )
    )
    return filtered[: constraints.max_suppliers_per_part]
