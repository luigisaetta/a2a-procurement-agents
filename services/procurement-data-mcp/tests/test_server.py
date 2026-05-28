"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Tests for the Procurement Data MCP FastMCP server wrapper.
"""

# pylint: disable=unused-argument

from __future__ import annotations

import sys

import pytest

from procurement_data_mcp import server as server_module
from procurement_data_mcp.server import build_server
from procurement_data_mcp.tools import ProcurementDataRepositoryProtocol


class FakeRepository:
    """Small fake repository for server registration tests."""

    def list_plants(self, *, limit: int, offset: int, active_only: bool):
        """List plants."""

        return []

    def get_plant(self, *, plant_id=None, plant_code=None):
        """Return one plant."""

        return None

    def list_parts(self, *, category, limit: int, offset: int, active_only: bool):
        """List parts."""

        return []

    def get_part(self, *, part_id=None, part_code=None):
        """Return one part."""

        return None

    def list_suppliers(self, *, limit: int, offset: int, active_only: bool):
        """List suppliers."""

        return []

    def get_supplier(self, *, supplier_id: str):
        """Return one supplier."""

        return None

    def list_suppliers_for_part(self, *, part_id: str, active_only: bool):
        """List suppliers for a part."""

        return []

    def list_parts_for_supplier(self, *, supplier_id: str, active_only: bool):
        """List parts for a supplier."""

        return []


@pytest.mark.anyio
async def test_build_server_registers_expected_tools() -> None:
    """Register every MCP tool defined by the specification."""

    server = build_server(repository=FakeRepository())  # type: ignore[arg-type]
    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert {
        "list_plants",
        "get_plant",
        "list_parts",
        "get_part",
        "list_suppliers",
        "get_supplier",
        "list_suppliers_for_part",
        "list_parts_for_supplier",
        "find_suppliers_for_part",
    } <= names


def _requires_protocol(_: ProcurementDataRepositoryProtocol) -> None:
    """Type-check helper for the fake repository."""


def test_main_runs_streamable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the CLI entrypoint with streamable HTTP only."""

    captured: dict[str, object] = {}

    class FakeServer:
        """Fake FastMCP server that records run arguments."""

        # FastMCP only needs the run method for this entrypoint test.
        # pylint: disable=too-few-public-methods

        def run(self, **kwargs: object) -> None:
            """Record run arguments."""

            captured.update(kwargs)

    def build_fake_server() -> FakeServer:
        """Build the fake FastMCP server."""

        return FakeServer()

    monkeypatch.setattr(server_module, "build_server", build_fake_server)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "procurement-data-mcp",
            "--host",
            "0.0.0.0",
            "--port",
            "9010",
            "--path",
            "/mcp",
        ],
    )

    server_module.main()

    assert captured == {
        "transport": "streamable-http",
        "host": "0.0.0.0",
        "port": 9010,
        "path": "/mcp",
    }
