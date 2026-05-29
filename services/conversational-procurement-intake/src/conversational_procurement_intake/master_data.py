"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Master-data resolver boundary for procurement intake grounding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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
