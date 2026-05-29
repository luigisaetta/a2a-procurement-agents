"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Intake extraction contracts and deterministic implementation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Protocol

from conversational_procurement_intake.master_data import MasterDataResolver
from conversational_procurement_intake.models import (
    ClarificationAmbiguity,
    DefaultApplied,
    PartOrchestrationRequest,
    ProcurementOrchestrationRequest,
    SourcingConstraints,
    SupplierSearchHints,
)
from pydantic import BaseModel, ConfigDict, Field

CURRENT_YEAR = 2026


@dataclass(frozen=True)
class ExtractionResult:
    """Result of interpreting one accumulated intake conversation."""

    message: str
    missing_fields: list[str]
    ambiguities: list[ClarificationAmbiguity]
    defaults_applied: list[DefaultApplied]
    orchestration_request: ProcurementOrchestrationRequest | None


class CandidateIntakeFields(BaseModel):
    """Candidate fields extracted from the user conversation."""

    model_config = ConfigDict(extra="forbid")

    material_reference: str = ""
    plant_reference: str = ""
    quantity: float | None = Field(default=None, gt=0)
    required_delivery_date: date | None = None
    response_deadline: datetime | None = None
    auto_create_purchase_order: bool = False
    max_suppliers_per_part: int | None = Field(default=None, ge=1)
    allowed_regions: list[str] = Field(default_factory=list)
    clarification_question: str = ""
    missing_fields: list[str] = Field(default_factory=list)


class IntakeExtractor(Protocol):  # pylint: disable=too-few-public-methods
    """Extractor contract used by the intake application service."""

    async def extract(
        self,
        text: str,
        requested_by: str,
        session_ordinal: int,
    ) -> ExtractionResult:
        """Extract and validate intake state from conversation text."""


class DeterministicIntakeExtractor:  # pylint: disable=too-few-public-methods
    """Small rule-based extractor used as a local fallback."""

    def __init__(self, master_data_resolver: MasterDataResolver) -> None:
        """Initialize the extractor.

        Args:
            master_data_resolver: Resolver used to ground parts and plants.
        """

        self._master_data_resolver = master_data_resolver

    async def extract(
        self,
        text: str,
        requested_by: str,
        session_ordinal: int,
    ) -> ExtractionResult:
        """Extract a candidate orchestration request from conversation text.

        Args:
            text: Full conversation text collected for the session.
            requested_by: User identifier associated with the session.
            session_ordinal: Monotonic ordinal used to generate stable request IDs.

        Returns:
            Extraction result containing either missing fields or a request.
        """

        candidate = CandidateIntakeFields(
            material_reference=text,
            plant_reference=text,
            quantity=_extract_quantity(text),
            required_delivery_date=_extract_delivery_date(text),
            response_deadline=_extract_response_deadline(text),
            auto_create_purchase_order=_extract_auto_create_purchase_order(text),
            max_suppliers_per_part=_extract_max_suppliers(text),
            allowed_regions=_extract_allowed_regions(text),
        )
        return await build_extraction_result(
            candidate,
            self._master_data_resolver,
            requested_by,
            session_ordinal,
        )


async def build_extraction_result(
    candidate: CandidateIntakeFields,
    master_data_resolver: MasterDataResolver,
    requested_by: str,
    session_ordinal: int,
) -> ExtractionResult:
    """Ground candidate fields and build an orchestration request if possible.

    Args:
        candidate: Candidate extraction output from deterministic or LLM extraction.
        master_data_resolver: Resolver used to ground plants and parts.
        requested_by: User identifier associated with the session.
        session_ordinal: Monotonic ordinal used to generate stable request IDs.

    Returns:
        Valid extraction result for the current conversation state.
    """

    defaults = _default_values(candidate)
    missing = list(candidate.missing_fields)
    ambiguities: list[ClarificationAmbiguity] = []

    if candidate.quantity is None:
        missing.append("parts[0].quantity")
    if candidate.required_delivery_date is None:
        missing.append("parts[0].required_delivery_date")
    if candidate.response_deadline is None:
        missing.append("response_deadline")

    part_candidates = await master_data_resolver.resolve_part(
        candidate.material_reference
    )
    if not part_candidates:
        missing.append("parts[0].material_code")
    elif len(part_candidates) > 1:
        ambiguities.append(
            ClarificationAmbiguity(
                field="parts[0].material_code",
                reason="Multiple active parts matched the user request.",
                candidates=[
                    {
                        "part_id": part.part_id,
                        "part_code": part.part_code,
                        "part_name": part.part_name,
                    }
                    for part in part_candidates
                ],
            )
        )

    plant_candidates = await master_data_resolver.resolve_plant(
        candidate.plant_reference
    )
    if not plant_candidates:
        missing.append("parts[0].plant_code")
    elif len(plant_candidates) > 1:
        ambiguities.append(
            ClarificationAmbiguity(
                field="parts[0].plant_code",
                reason="Multiple active plants matched the user request.",
                candidates=[
                    {
                        "plant_id": plant.plant_id,
                        "plant_code": plant.plant_code,
                        "plant_name": plant.plant_name,
                    }
                    for plant in plant_candidates
                ],
            )
        )

    missing = _deduplicate(missing)
    if missing or ambiguities:
        return ExtractionResult(
            message=(
                candidate.clarification_question
                or _clarification_message(missing, ambiguities)
            ),
            missing_fields=missing,
            ambiguities=ambiguities,
            defaults_applied=defaults,
            orchestration_request=None,
        )

    part = part_candidates[0]
    plant = plant_candidates[0]
    request = ProcurementOrchestrationRequest(
        request_id=f"REQ-2026-{session_ordinal:04d}",
        requested_by=requested_by,
        currency="EUR",
        evaluation_policy_id="standard-urgent-procurement-v1",
        response_deadline=candidate.response_deadline,
        auto_create_purchase_order=candidate.auto_create_purchase_order,
        max_rebid_attempts=2,
        sourcing_constraints=SourcingConstraints(
            max_suppliers_per_part=candidate.max_suppliers_per_part or 3,
            allowed_regions=candidate.allowed_regions,
            preferred_supplier_ids=[],
        ),
        parts=[
            PartOrchestrationRequest(
                part_id=part.part_id,
                plant_code=plant.plant_code,
                material_code=part.part_code,
                material_description=part.part_name,
                quantity=candidate.quantity,
                unit_of_measure=part.unit_of_measure,
                required_delivery_date=candidate.required_delivery_date,
                supplier_search_hints=SupplierSearchHints(
                    commodity_category=part.category,
                    required_certifications=[],
                ),
            )
        ],
    )
    return ExtractionResult(
        message="The procurement request is ready for confirmation.",
        missing_fields=[],
        ambiguities=[],
        defaults_applied=defaults,
        orchestration_request=request,
    )


def _default_values(candidate: CandidateIntakeFields) -> list[DefaultApplied]:
    """Return the defaults applied to a candidate request."""

    defaults = [
        DefaultApplied(
            field="currency",
            value="EUR",
            reason="Configured default for European procurement.",
        ),
        DefaultApplied(
            field="evaluation_policy_id",
            value="standard-urgent-procurement-v1",
            reason="Default urgent procurement policy.",
        ),
    ]
    if candidate.max_suppliers_per_part is None:
        defaults.append(
            DefaultApplied(
                field="sourcing_constraints.max_suppliers_per_part",
                value=3,
                reason="Default maximum suppliers per part.",
            )
        )
    if not candidate.allowed_regions:
        defaults.append(
            DefaultApplied(
                field="sourcing_constraints.allowed_regions",
                value=[],
                reason="No region restriction was specified.",
            )
        )
    return defaults


def _extract_quantity(text: str) -> float | None:
    """Extract a positive numeric quantity from text."""

    match = re.search(r"\b(\d+(?:\.\d+)?)\b", text)
    if not match:
        return None
    value = float(match.group(1))
    return value if value > 0 else None


def _extract_delivery_date(text: str) -> date | None:
    """Extract the required delivery date from text."""

    match = re.search(r"\bby\s+([A-Za-z]+)\s+(\d{1,2})\b", text, re.IGNORECASE)
    if not match:
        match = re.search(
            r"\bdelivery\s+(?:by|date)\s+([A-Za-z]+)\s+(\d{1,2})\b",
            text,
            re.IGNORECASE,
        )
    if not match:
        return None
    return _month_day_to_date(match.group(1), int(match.group(2)))


def _extract_response_deadline(text: str) -> datetime | None:
    """Extract a bid response deadline from text."""

    match = re.search(
        r"\b(?:bid|response)\s+deadline\s+([A-Za-z]+)\s+(\d{1,2})"
        r"(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    deadline_date = _month_day_to_date(match.group(1), int(match.group(2)))
    hour = int(match.group(3) or "17")
    minute = int(match.group(4) or "0")
    return datetime.combine(deadline_date, time(hour, minute), tzinfo=UTC)


def _extract_auto_create_purchase_order(text: str) -> bool:
    """Return whether the user explicitly asked for automatic PO creation."""

    normalized = text.casefold()
    return "create" in normalized and (
        "purchase order" in normalized or "po" in normalized
    )


def _extract_max_suppliers(text: str) -> int | None:
    """Extract a maximum supplier count when the user provides one."""

    match = re.search(r"\b(?:up to|ask)\s+(\d+)\s+(?:european\s+)?suppliers", text)
    if not match:
        return None
    return max(1, int(match.group(1)))


def _extract_allowed_regions(text: str) -> list[str]:
    """Extract simple region constraints from text."""

    normalized = text.casefold()
    if "european" in normalized or "eu suppliers" in normalized:
        return ["EU"]
    return []


def _month_day_to_date(month_name: str, day: int) -> date:
    """Convert a month name and day into a date in the current demo year."""

    month_names = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    month = month_names[month_name.casefold()]
    return date(CURRENT_YEAR, month, day)


def _clarification_message(  # pylint: disable=too-many-return-statements
    missing: list[str], ambiguities: list[ClarificationAmbiguity]
) -> str:
    """Build a concise clarification message."""

    if ambiguities:
        return ambiguities[0].reason
    if "response_deadline" in missing:
        return "Which bid response deadline should I use?"
    if "parts[0].required_delivery_date" in missing:
        return "What required delivery date should I use?"
    if "parts[0].quantity" in missing:
        return "What quantity do you need?"
    if "parts[0].material_code" in missing:
        return "Which material or part do you need?"
    if "parts[0].plant_code" in missing:
        return "Which destination plant should receive the material?"
    return "Please provide the missing procurement details."


def _deduplicate(values: list[str]) -> list[str]:
    """Return values without duplicates while preserving order."""

    deduplicated: list[str] = []
    for value in values:
        if value not in deduplicated:
            deduplicated.append(value)
    return deduplicated
