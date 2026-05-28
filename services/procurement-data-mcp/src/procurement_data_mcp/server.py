"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    FastMCP server exposing read-only procurement data tools.
"""

from __future__ import annotations

import argparse
from typing import Any

from fastmcp import FastMCP

from procurement_data_mcp.config import Settings, load_settings
from procurement_data_mcp.database import ProcurementDataRepository
from procurement_data_mcp.tools import ProcurementDataRepositoryProtocol
from procurement_data_mcp.tools import ProcurementDataTools, ToolError


def build_server(
    settings: Settings | None = None,
    repository: ProcurementDataRepositoryProtocol | None = None,
) -> FastMCP:
    """Build the FastMCP server.

    Args:
        settings: Optional settings. Loaded from environment when omitted.
        repository: Optional repository, mainly for tests.

    Returns:
        Configured FastMCP server.
    """

    resolved_repository = repository
    if resolved_repository is None:
        resolved_settings = settings or load_settings()
        resolved_repository = ProcurementDataRepository(resolved_settings)
    tools = ProcurementDataTools(resolved_repository)
    mcp = FastMCP(
        name="Procurement Data MCP Server",
        instructions=(
            "Read-only MCP server for procurement plants, parts, suppliers, "
            "and supplier-part relationships."
        ),
    )

    @mcp.tool
    def list_plants(
        limit: int = 50, offset: int = 0, active_only: bool = True
    ) -> dict[str, Any]:
        """Return plants with pagination."""

        return _call_tool(tools.list_plants, limit, offset, active_only)

    @mcp.tool
    def get_plant(
        plant_id: str | None = None, plant_code: str | None = None
    ) -> dict[str, Any]:
        """Return one plant by plant_id or plant_code."""

        return _call_tool(tools.get_plant, plant_id, plant_code)

    @mcp.tool
    def list_parts(
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> dict[str, Any]:
        """Return parts with optional category filtering."""

        return _call_tool(tools.list_parts, category, limit, offset, active_only)

    @mcp.tool
    def get_part(
        part_id: str | None = None, part_code: str | None = None
    ) -> dict[str, Any]:
        """Return one part by part_id or part_code."""

        return _call_tool(tools.get_part, part_id, part_code)

    @mcp.tool
    def list_suppliers(
        limit: int = 50, offset: int = 0, active_only: bool = True
    ) -> dict[str, Any]:
        """Return suppliers with pagination."""

        return _call_tool(tools.list_suppliers, limit, offset, active_only)

    @mcp.tool
    def get_supplier(supplier_id: str) -> dict[str, Any]:
        """Return one supplier by supplier_id."""

        return _call_tool(tools.get_supplier, supplier_id)

    @mcp.tool
    def list_suppliers_for_part(
        part_id: str | None = None,
        part_code: str | None = None,
        active_only: bool = True,
    ) -> dict[str, Any]:
        """Return suppliers that can provide a part."""

        return _call_tool(
            tools.list_suppliers_for_part, part_id, part_code, active_only
        )

    @mcp.tool
    def list_parts_for_supplier(
        supplier_id: str, active_only: bool = True
    ) -> dict[str, Any]:
        """Return parts that a supplier can provide."""

        return _call_tool(tools.list_parts_for_supplier, supplier_id, active_only)

    @mcp.tool
    # The argument list mirrors the public MCP tool contract.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def find_suppliers_for_part(
        part_id: str | None = None,
        part_code: str | None = None,
        plant_id: str | None = None,
        plant_code: str | None = None,
        quantity: float | None = None,
        active_only: bool = True,
    ) -> dict[str, Any]:
        """Return supplier candidates for a sourcing request."""

        return _call_tool(
            tools.find_suppliers_for_part,
            part_id,
            part_code,
            plant_id,
            plant_code,
            quantity,
            active_only,
        )

    return mcp


def _call_tool(function: Any, *args: Any) -> dict[str, Any]:
    """Call a tool and convert structured errors to JSON-compatible output."""

    try:
        return function(*args)
    except ToolError as exc:
        return {"error": exc.to_dict()}


def main() -> None:
    """Run the MCP server over streamable HTTP."""

    parser = argparse.ArgumentParser(description="Run the Procurement Data MCP Server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8010, help="HTTP port to bind.")
    parser.add_argument("--path", default="/mcp", help="HTTP MCP endpoint path.")
    args = parser.parse_args()

    server = build_server()
    server.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        path=args.path,
    )


if __name__ == "__main__":
    main()
