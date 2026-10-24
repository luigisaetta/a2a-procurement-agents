"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Intake extraction contracts and deterministic implementation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Awaitable, Callable, Protocol, TypeVar

from conversational_procurement_intake.business_clock import Clock, business_now
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

ResolvedRecordT = TypeVar("ResolvedRecordT")

_NUMBER = r"(\d+(?:\.\d+)?)"
_UNIT = r"(?:units?|items?|pieces?|pcs|ea)"
# Words allowed between a buying verb and the quantity: "I need urgently 10".
_QUANTITY_ADVERB = (
    r"(?:urgently|immediately|asap|about|around|approximately|exactly|"
    r"only|just|another|at\s+least)"
)
QUANTITY_EVIDENCE_PATTERNS = [
    # "quantity is 10", "qty: 10"
    re.compile(rf"\b(?:quantity|qty)\s*(?:is|=|:)?\s*{_NUMBER}\b", re.IGNORECASE),
    # "we need 10", "I need urgently 10", "order 12"; not a voltage like "need 48 V"
    re.compile(
        rf"\b(?:need|require|order|buy|procure)\s+(?:{_QUANTITY_ADVERB}\s+)?"
        rf"{_NUMBER}\b(?!\s*v\b)",
        re.IGNORECASE,
    ),
    # "10 units", "10 pieces", "10 battery modules"
    re.compile(
        rf"\b{_NUMBER}\s+(?:{_UNIT}|battery\s+modules?|modules?|inverters?)\b",
        re.IGNORECASE,
    ),
    # A reply that is only a number, such as "10" or "10 units", on its own line
    re.compile(rf"^\s*{_NUMBER}\s*{_UNIT}?\s*\.?\s*$", re.IGNORECASE | re.MULTILINE),
]

MONTH_NUMBERS = {
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
        request_id: str,
    ) -> ExtractionResult:
        """Extract and validate intake state from conversation text."""


class DeterministicIntakeExtractor:  # pylint: disable=too-few-public-methods
    """Small rule-based extractor used as a local fallback."""

    def __init__(
        self,
        master_data_resolver: MasterDataResolver,
        clock: Clock = business_now,
    ) -> None:
        """Initialize the extractor.

        Args:
            master_data_resolver: Resolver used to ground parts and plants.
            clock: Source of the current time used for relative dates.
        """

        self._master_data_resolver = master_data_resolver
        self._clock = clock

    async def extract(
        self,
        text: str,
        requested_by: str,
        request_id: str,
    ) -> ExtractionResult:
        """Extract a candidate orchestration request from conversation text.

        Args:
            text: Full conversation text collected for the session.
            requested_by: User identifier associated with the session.
            request_id: Idempotency key generated for the session.

        Returns:
            Extraction result containing either missing fields or a request.
        """

        now = self._clock()
        candidate = build_deterministic_candidate(text, now.date())
        return await build_extraction_result(
            candidate,
            self._master_data_resolver,
            requested_by,
            request_id,
            now,
            text,
        )


# Each argument is a distinct input of the extraction step.
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
async def build_extraction_result(
    candidate: CandidateIntakeFields,
    master_data_resolver: MasterDataResolver,
    requested_by: str,
    request_id: str,
    now: datetime,
    conversation_text: str = "",
) -> ExtractionResult:
    """Ground candidate fields and build an orchestration request if possible.

    Args:
        candidate: Candidate extraction output from deterministic or LLM extraction.
        master_data_resolver: Resolver used to ground plants and parts.
        requested_by: User identifier associated with the session.
        request_id: Idempotency key generated for the session.
        now: Current time, used to reject dates in the past.
        conversation_text: Full conversation text used as grounding fallback.

    Returns:
        Valid extraction result for the current conversation state.
    """

    candidate, date_problems = _reject_invalid_dates(candidate, now)
    defaults = _default_values(candidate)
    missing = list(candidate.missing_fields)
    ambiguities: list[ClarificationAmbiguity] = []

    if candidate.quantity is None:
        missing.append("parts[0].quantity")
    if candidate.required_delivery_date is None:
        missing.append("parts[0].required_delivery_date")
    if candidate.response_deadline is None:
        missing.append("response_deadline")

    part_candidates = await _resolve_with_fallback(
        master_data_resolver.resolve_part,
        candidate.material_reference,
        conversation_text,
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

    plant_candidates = await _resolve_with_fallback(
        master_data_resolver.resolve_plant,
        candidate.plant_reference,
        conversation_text,
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

    missing = _normalize_missing_fields(
        missing, candidate, part_candidates, plant_candidates
    )
    if missing or ambiguities:
        if date_problems:
            # Say why the dates were rejected, then ask for what is missing.
            message = " ".join(
                [*date_problems, _clarification_message(missing, ambiguities)]
            )
        else:
            message = _clarification_message_for_candidate(
                candidate, missing, ambiguities
            )
        return ExtractionResult(
            message=message,
            missing_fields=missing,
            ambiguities=ambiguities,
            defaults_applied=defaults,
            orchestration_request=None,
        )

    part = part_candidates[0]
    plant = plant_candidates[0]
    request = ProcurementOrchestrationRequest(
        request_id=request_id,
        requested_by=requested_by,
        currency="EUR",
        evaluation_policy_id="standard-urgent-procurement-v1",
        response_deadline=candidate.response_deadline,
        auto_create_purchase_order=candidate.auto_create_purchase_order,
        max_rebid_attempts=2,
        sourcing_constraints=SourcingConstraints(
            max_suppliers_per_part=candidate.max_suppliers_per_part or 3,
            allowed_regions=_normalize_allowed_regions(candidate.allowed_regions),
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


def build_deterministic_candidate(text: str, today: date) -> CandidateIntakeFields:
    """Build candidate fields from simple deterministic text rules.

    Args:
        text: Full conversation text collected for the session.
        today: Current business date, used for "today" and dates without a year.

    Returns:
        Candidate fields extracted without an LLM.
    """

    response_deadline = _extract_response_deadline(text, today)
    # Delivery follows the bidding, so a delivery date without a year is the
    # next occurrence on or after the deadline, not only after today.
    delivery_reference = response_deadline.date() if response_deadline else today
    return CandidateIntakeFields(
        material_reference=text,
        plant_reference=text,
        quantity=_extract_quantity(text),
        required_delivery_date=_extract_delivery_date(text, delivery_reference),
        response_deadline=response_deadline,
        auto_create_purchase_order=_extract_auto_create_purchase_order(text),
        max_suppliers_per_part=_extract_max_suppliers(text),
        allowed_regions=_extract_allowed_regions(text),
    )


def enforce_candidate_evidence(
    candidate: CandidateIntakeFields, text: str
) -> CandidateIntakeFields:
    """Validate that sensitive LLM-extracted values are text-supported.

    Args:
        candidate: Candidate fields produced by the LLM.
        text: Full conversation text collected for the session.

    Returns:
        Candidate fields with unsupported sensitive values removed.
    """

    missing_fields = list(candidate.missing_fields)
    quantity = candidate.quantity
    clarification_question = candidate.clarification_question
    if quantity is not None and not _has_quantity_evidence(text, quantity):
        quantity = None
        missing_fields.append("parts[0].quantity")
        clarification_question = ""

    return candidate.model_copy(
        update={
            "quantity": quantity,
            "clarification_question": clarification_question,
            "missing_fields": _deduplicate(missing_fields),
        }
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


async def _resolve_with_fallback(
    resolver: Callable[[str], Awaitable[list[ResolvedRecordT]]],
    primary_reference: str,
    conversation_text: str,
) -> list[ResolvedRecordT]:
    """Resolve a reference, falling back to the complete conversation text."""

    candidates = await resolver(primary_reference)
    fallback = conversation_text.strip()
    if len(candidates) == 1 or not fallback or fallback == primary_reference.strip():
        return candidates

    fallback_candidates = await resolver(fallback)
    if len(fallback_candidates) == 1:
        return fallback_candidates
    if not candidates:
        return fallback_candidates
    return candidates


def _extract_quantity(text: str) -> float | None:
    """Extract a positive numeric quantity from text."""

    matches = _quantity_evidence_matches(text)
    if not matches:
        return None
    value = float(matches[0])
    return value if value > 0 else None


def _has_quantity_evidence(text: str, quantity: float) -> bool:
    """Return whether text contains explicit evidence for a quantity value."""

    return any(float(value) == quantity for value in _quantity_evidence_matches(text))


def _quantity_evidence_matches(text: str) -> list[str]:
    """Return the numbers that the text states as a quantity.

    Each pattern is one form listed in the "Quantity Evidence" section of the
    intake specification. Numbers in other positions, such as "Invite 10
    suppliers" or "15 of November", are deliberately not matched.
    """

    matches: list[str] = []
    for pattern in QUANTITY_EVIDENCE_PATTERNS:
        matches.extend(pattern.findall(text))
    return matches


def _extract_delivery_date(text: str, earliest: date) -> date | None:
    """Extract the required delivery date from text.

    Args:
        text: Full conversation text.
        earliest: Date from which a month and day without a year is resolved.
    """

    iso_match = re.search(
        r"\b(?:required\s+)?delivery\s+(?:by|date)\s+(?:is\s+)?"
        r"(\d{4}-\d{2}-\d{2})\b",
        text,
        re.IGNORECASE,
    )
    if iso_match:
        return _parse_iso_date(iso_match.group(1))

    match = re.search(r"\bby\s+([A-Za-z]+)\s+(\d{1,2})\b", text, re.IGNORECASE)
    if not match:
        match = re.search(
            r"\b(?:required\s+)?delivery\s+(?:by|date)\s+(?:is\s+)?"
            r"([A-Za-z]+)\s+(\d{1,2})\b",
            text,
            re.IGNORECASE,
        )
    if not match:
        return None
    return _next_month_day(match.group(1), int(match.group(2)), earliest)


def _extract_response_deadline(text: str, today: date) -> datetime | None:
    """Extract a bid response deadline from text.

    The deadline time defaults to 17:00 and is interpreted as UTC.
    """

    iso_match = re.search(
        r"\b(?:bid|response)\s+deadline\s+(?:is\s+)?(\d{4}-\d{2}-\d{2})"
        r"(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?)?",
        text,
        re.IGNORECASE,
    )
    if iso_match:
        deadline_date = _parse_iso_date(iso_match.group(1))
        return _deadline_at(deadline_date, iso_match.group(2), iso_match.group(3))

    today_match = re.search(
        r"\b(?:bid|response)\s+deadline\s+(?:is\s+)?today"
        r"(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?)?",
        text,
        re.IGNORECASE,
    )
    if today_match:
        return _deadline_at(today, today_match.group(1), today_match.group(2))

    match = re.search(
        r"\b(?:bid|response)\s+deadline\s+(?:is\s+)?([A-Za-z]+)\s+(\d{1,2})"
        r"(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    deadline_date = _next_month_day(match.group(1), int(match.group(2)), today)
    return _deadline_at(deadline_date, match.group(3), match.group(4))


def _deadline_at(
    deadline_date: date | None, hour_text: str | None, minute_text: str | None
) -> datetime | None:
    """Combine a deadline date with an optional time, as UTC.

    Returns:
        The deadline timestamp, or ``None`` when the date or time is invalid.
    """

    if deadline_date is None:
        return None
    try:
        deadline_time = time(int(hour_text or "17"), int(minute_text or "0"))
    except ValueError:
        return None
    return datetime.combine(deadline_date, deadline_time, tzinfo=UTC)


def _parse_iso_date(value: str) -> date | None:
    """Parse an ISO 8601 date, returning ``None`` for impossible dates."""

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


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


def _normalize_allowed_regions(values: list[str]) -> list[str]:
    """Normalize natural-language region names to sourcing region codes."""

    aliases = {
        "eu": "EU",
        "europe": "EU",
        "european": "EU",
        "european union": "EU",
        "uk": "UK",
        "gb": "UK",
        "great britain": "UK",
        "united kingdom": "UK",
    }
    regions: list[str] = []
    for value in values:
        normalized = aliases.get(value.casefold().strip(), value.upper().strip())
        if normalized and normalized not in regions:
            regions.append(normalized)
    return regions


def _next_month_day(month_name: str, day: int, earliest: date) -> date | None:
    """Return the next occurrence of a month and day on or after ``earliest``.

    A date without a year, such as "June 15", means the coming June 15: the
    year of ``earliest`` if that day has not passed yet, otherwise next year.

    Returns:
        The resolved date, or ``None`` for an unknown month or impossible day.
    """

    month = MONTH_NUMBERS.get(month_name.casefold())
    if month is None:
        return None
    for year in (earliest.year, earliest.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            # The day does not exist in this year, such as June 31 or a
            # February 29 outside a leap year.
            continue
        if candidate >= earliest:
            return candidate
    return None


def _reject_invalid_dates(
    candidate: CandidateIntakeFields, now: datetime
) -> tuple[CandidateIntakeFields, list[str]]:
    """Remove dates that are in the past or in the wrong order.

    A removed date becomes a missing field, so the user is asked for it
    again. Each problem is described in a user-facing sentence.

    Args:
        candidate: Candidate fields from deterministic or LLM extraction.
        now: Current time.

    Returns:
        The candidate without the rejected dates, and the problem sentences.
    """

    deadline = candidate.response_deadline
    delivery_date = candidate.required_delivery_date
    problems: list[str] = []

    if deadline is not None and _as_utc(deadline) <= now:
        problems.append(
            f"The bid response deadline {_format_deadline(deadline)} is in the past."
        )
        deadline = None

    if delivery_date is not None and delivery_date < now.date():
        problems.append(f"The required delivery date {delivery_date} is in the past.")
        delivery_date = None
    elif (
        delivery_date is not None
        and deadline is not None
        and delivery_date < _as_utc(deadline).date()
    ):
        problems.append(
            f"The required delivery date {delivery_date} is before the bid "
            f"response deadline {_format_deadline(deadline)}."
        )
        delivery_date = None

    valid_candidate = candidate.model_copy(
        update={"response_deadline": deadline, "required_delivery_date": delivery_date}
    )
    return valid_candidate, problems


def _as_utc(value: datetime) -> datetime:
    """Return a timestamp in UTC, treating a timestamp without timezone as UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_deadline(value: datetime) -> str:
    """Format a deadline for user-facing messages."""

    return f"{_as_utc(value):%Y-%m-%d %H:%M} UTC"


def _clarification_message_for_candidate(
    candidate: CandidateIntakeFields,
    missing: list[str],
    ambiguities: list[ClarificationAmbiguity],
) -> str:
    """Build a clarification message, preserving useful single LLM questions."""

    if candidate.clarification_question and len(missing) <= 1:
        return candidate.clarification_question
    return _clarification_message(missing, ambiguities)


def _clarification_message(
    missing: list[str], ambiguities: list[ClarificationAmbiguity]
) -> str:
    """Build a concise clarification message."""

    if ambiguities:
        return ambiguities[0].reason
    if len(missing) > 1:
        questions = [_missing_field_question(field) for field in missing]
        return "Please provide these missing details: " + " ".join(questions)
    if missing:
        return _missing_field_question(missing[0])
    return "Please provide the missing procurement details."


def _missing_field_question(field: str) -> str:
    """Return the user-facing question for one missing field."""

    if field == "response_deadline":
        return "Which bid response deadline should I use?"
    if field == "parts[0].required_delivery_date":
        return "What required delivery date should I use?"
    if field == "parts[0].quantity":
        return "What quantity do you need?"
    if field == "parts[0].material_code":
        return "Which material or part do you need?"
    if field == "parts[0].plant_code":
        return "Which destination plant should receive the material?"
    return "Please provide the missing procurement details."


def _deduplicate(values: list[str]) -> list[str]:
    """Return values without duplicates while preserving order."""

    deduplicated: list[str] = []
    for value in values:
        if value not in deduplicated:
            deduplicated.append(value)
    return deduplicated


def _normalize_missing_fields(
    missing: list[str],
    candidate: CandidateIntakeFields,
    part_candidates: list[object],
    plant_candidates: list[object],
) -> list[str]:
    """Remove stale LLM missing markers for fields that validated successfully."""

    resolved_fields = set()
    if candidate.quantity is not None:
        resolved_fields.add("parts[0].quantity")
    if candidate.required_delivery_date is not None:
        resolved_fields.add("parts[0].required_delivery_date")
    if candidate.response_deadline is not None:
        resolved_fields.add("response_deadline")
    if len(part_candidates) == 1:
        resolved_fields.add("parts[0].material_code")
    if len(plant_candidates) == 1:
        resolved_fields.add("parts[0].plant_code")

    return _deduplicate([field for field in missing if field not in resolved_fields])
