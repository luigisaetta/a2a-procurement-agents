"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    LLM-backed conversational intake extraction.
"""

# pylint: disable=duplicate-code

from __future__ import annotations

import asyncio
import json
from typing import Protocol

from locus.agent import Agent, AgentConfig

from conversational_procurement_intake.extraction import (
    CandidateIntakeFields,
    ExtractionResult,
    build_extraction_result,
    enforce_candidate_evidence,
)
from conversational_procurement_intake.master_data import MasterDataResolver

SYSTEM_PROMPT = """You are the Conversational Procurement Intake Layer.

Extract only candidate procurement intake fields from the user's conversation.
Do not invent plant codes, part codes, supplier IDs, or any other canonical ID.
Use natural-language references for plants and materials exactly enough for a
separate master-data lookup step to resolve them.

If the user has not provided a mandatory business value, leave that field null
or empty and include the canonical missing field name.

Do not infer quantity from delivery dates, bid deadlines, times, supplier
counts, voltages, model numbers, or part codes. Extract quantity only when the
conversation explicitly states the requested material quantity.

Mandatory business values are:
- material_reference
- plant_reference
- quantity
- required_delivery_date
- response_deadline

Return only a JSON object matching CandidateIntakeFields.
Do not wrap the JSON in Markdown fences.
"""


class IntakeLLMClient(Protocol):  # pylint: disable=too-few-public-methods
    """LLM client contract for structured intake extraction."""

    async def extract_candidate(self, text: str) -> CandidateIntakeFields:
        """Extract candidate fields from conversation text."""


class LocusIntakeLLMClient:  # pylint: disable=too-few-public-methods
    """Locus-backed LLM client for structured intake extraction."""

    def __init__(self, model: object) -> None:
        """Initialize the Locus agent.

        Args:
            model: Locus-compatible model instance.
        """

        self._agent = Agent(
            config=AgentConfig(
                model=model,
                system_prompt=SYSTEM_PROMPT,
                max_iterations=1,
                output_schema=CandidateIntakeFields,
                output_schema_strict=True,
                output_schema_retries=2,
            )
        )

    async def extract_candidate(self, text: str) -> CandidateIntakeFields:
        """Extract candidate intake fields with the configured LLM."""

        result = await asyncio.to_thread(self._agent.run_sync, _build_prompt(text))
        if isinstance(result.parsed, CandidateIntakeFields):
            return result.parsed
        return CandidateIntakeFields.model_validate_json(
            _extract_json_object(result.message)
        )


class LLMIntakeExtractor:  # pylint: disable=too-few-public-methods
    """Extractor that uses an LLM for candidate fields and deterministic grounding."""

    def __init__(
        self,
        llm_client: IntakeLLMClient,
        master_data_resolver: MasterDataResolver,
    ) -> None:
        """Initialize the extractor.

        Args:
            llm_client: Structured LLM extraction client.
            master_data_resolver: Resolver used for deterministic grounding.
        """

        self._llm_client = llm_client
        self._master_data_resolver = master_data_resolver

    async def extract(
        self,
        text: str,
        requested_by: str,
        session_ordinal: int,
    ) -> ExtractionResult:
        """Extract and validate intake state from conversation text."""

        candidate = await self._llm_client.extract_candidate(text)
        candidate = enforce_candidate_evidence(candidate, text)
        return await build_extraction_result(
            candidate,
            self._master_data_resolver,
            requested_by,
            session_ordinal,
        )


def _build_prompt(text: str) -> str:
    """Build the prompt sent to the LLM extractor."""

    schema = CandidateIntakeFields.model_json_schema()
    return (
        "Extract candidate procurement intake fields from this conversation.\n\n"
        "Current date: 2026-05-29.\n"
        "Timezone for relative business interpretation: Europe/Rome.\n"
        "Use ISO 8601 date values for dates and timestamps.\n\n"
        "Canonical missing field names:\n"
        "- parts[0].material_code\n"
        "- parts[0].plant_code\n"
        "- parts[0].quantity\n"
        "- parts[0].required_delivery_date\n"
        "- response_deadline\n\n"
        "CandidateIntakeFields JSON Schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        "Conversation:\n"
        f"{text}\n\n"
        "Return only the CandidateIntakeFields JSON object."
    )


def _extract_json_object(raw_message: str) -> str:
    """Extract a JSON object from a raw LLM response.

    Args:
        raw_message: Raw model output.

    Returns:
        JSON object text.

    Raises:
        ValueError: If no valid JSON object can be extracted.
    """

    stripped = raw_message.strip()
    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response does not contain a JSON object.")

    candidate = stripped[start : end + 1]
    json.loads(candidate)
    return candidate
