"""
Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    Master-data resolver boundary for procurement intake grounding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from fastmcp import Client


@dataclass(frozen=True)
class PlantRecord:
    """Canonical plant data used by the intake layer."""

    plant_id: str
    plant_code: str
    plant_name: str
    city: str
    country_code: str
    is_active: bool


@dataclass(frozen=True)
class PartRecord:
    """Canonical part data used by the intake layer."""

    part_id: str
    part_code: str
    part_name: str
    description: str
    category: str
    unit_of_measure: str
    is_active: bool


class MasterDataResolver(Protocol):
    """Read-only resolver used to ground extracted procurement entities."""

    async def resolve_plant(self, text: str) -> list[PlantRecord]:
        """Resolve a natural-language plant reference.

        Args:
            text: User-provided plant reference.

        Returns:
            Matching active plant candidates.
        """

    async def resolve_part(self, text: str) -> list[PartRecord]:
        """Resolve a natural-language material reference.

        Args:
            text: User-provided material reference.

        Returns:
            Matching active part candidates.
        """


class StaticMasterDataResolver:
    """Small deterministic resolver used until the MCP client is wired in."""

    def __init__(self) -> None:
        """Initialize static demo records aligned with the seed dataset."""

        self._plants = [
            PlantRecord(
                plant_id="PLANT-001",
                plant_code="DE-MUN",
                plant_name="LuxEV Munich Assembly Plant",
                city="Munich",
                country_code="DE",
                is_active=True,
            ),
            PlantRecord(
                plant_id="PLANT-002",
                plant_code="IT-TOR",
                plant_name="LuxEV Turin Assembly Plant",
                city="Turin",
                country_code="IT",
                is_active=True,
            ),
        ]
        self._parts = [
            PartRecord(
                part_id="PART-001",
                part_code="EV-BAT-MOD-001",
                part_name="High Density Battery Module",
                description="Modular lithium battery pack segment",
                category="battery",
                unit_of_measure="EA",
                is_active=True,
            ),
            PartRecord(
                part_id="PART-008",
                part_code="EV-INV-800-008",
                part_name="800V Traction Inverter",
                description="High-voltage traction inverter",
                category="power electronics",
                unit_of_measure="EA",
                is_active=True,
            ),
        ]

    async def resolve_plant(self, text: str) -> list[PlantRecord]:
        """Resolve a plant reference against static records."""

        normalized = _normalize(text)
        return [
            plant
            for plant in self._plants
            if plant.is_active
            and (
                _normalize(plant.plant_code) in normalized
                or _normalize(plant.city) in normalized
                or _normalize(plant.plant_name) in normalized
            )
        ]

    async def resolve_part(self, text: str) -> list[PartRecord]:
        """Resolve a part reference against static records."""

        normalized = _normalize(text)
        return [
            part
            for part in self._parts
            if part.is_active
            and (
                _normalize(part.part_code) in normalized
                or _normalize(part.part_name) in normalized
                or _normalize(part.category) in normalized
            )
        ]


def _normalize(value: str) -> str:
    """Normalize text for simple deterministic matching."""

    return value.casefold().replace("-", " ").strip()


class McpMasterDataResolver:
    """Master-data resolver backed by the Procurement Data MCP Server."""

    def __init__(
        self,
        mcp_url: str,
        timeout_seconds: float = 10.0,
        client_factory: Any = Client,
    ) -> None:
        """Initialize the MCP-backed resolver.

        Args:
            mcp_url: Streamable HTTP endpoint of the procurement data MCP server.
            timeout_seconds: Timeout for MCP calls.
            client_factory: FastMCP client factory, injectable for tests.
        """

        self._mcp_url = mcp_url
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory
        self._parts_cache: list[PartRecord] | None = None
        self._plants_cache: list[PlantRecord] | None = None

    async def resolve_plant(self, text: str) -> list[PlantRecord]:
        """Resolve a plant reference against MCP master data."""

        normalized = _normalize(text)
        plants = await self._load_plants()
        return [
            plant
            for plant in plants
            if plant.is_active
            and (
                _normalize(plant.plant_code) in normalized
                or _normalize(plant.city) in normalized
                or _normalize(plant.plant_name) in normalized
            )
        ]

    async def resolve_part(self, text: str) -> list[PartRecord]:
        """Resolve a part reference against MCP master data."""

        normalized = _normalize(text)
        parts = await self._load_parts()
        return [
            part
            for part in parts
            if part.is_active
            and (
                _normalize(part.part_code) in normalized
                or _normalize(part.part_name) in normalized
                or _normalize(part.category) in normalized
            )
        ]

    async def _load_parts(self) -> list[PartRecord]:
        """Load active parts from MCP once per service process."""

        if self._parts_cache is None:
            payload = await self._call_tool(
                "list_parts",
                {"limit": 200, "offset": 0, "active_only": True},
            )
            self._parts_cache = [
                PartRecord(
                    part_id=item["part_id"],
                    part_code=item["part_code"],
                    part_name=item["part_name"],
                    description=item.get("description", ""),
                    category=item.get("category", ""),
                    unit_of_measure=item.get("unit_of_measure", "EA"),
                    is_active=bool(item.get("is_active", True)),
                )
                for item in payload.get("items", [])
            ]
        return self._parts_cache

    async def _load_plants(self) -> list[PlantRecord]:
        """Load active plants from MCP once per service process."""

        if self._plants_cache is None:
            payload = await self._call_tool(
                "list_plants",
                {"limit": 200, "offset": 0, "active_only": True},
            )
            self._plants_cache = [
                PlantRecord(
                    plant_id=item["plant_id"],
                    plant_code=item["plant_code"],
                    plant_name=item["plant_name"],
                    city=item.get("city", ""),
                    country_code=item.get("country_code", ""),
                    is_active=bool(item.get("is_active", True)),
                )
                for item in payload.get("items", [])
            ]
        return self._plants_cache

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call one MCP tool and return structured content."""

        async with self._client_factory(
            self._mcp_url,
            timeout=self._timeout_seconds,
        ) as client:
            result = await client.call_tool(name, arguments)
        return _extract_structured_content(result)


def _extract_structured_content(result: Any) -> dict[str, Any]:
    """Extract structured MCP tool content."""

    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    content = getattr(result, "content", [])
    if content and hasattr(content[0], "text"):
        parsed = json.loads(content[0].text)
        if isinstance(parsed, dict):
            return parsed

    raise RuntimeError("MCP master-data lookup did not return structured content.")
