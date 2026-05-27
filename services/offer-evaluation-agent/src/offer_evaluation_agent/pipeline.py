"""
Deterministic workflow for LLM-driven offer evaluation.

Author: L. Saetta
Date Last Modified: 2026-05-27
License: MIT
Description:    Implements the fixed sequence of validation, policy loading,
                LLM invocation, output validation, and consistency checks.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from locus.agent import Agent, AgentConfig
from locus.core.events import LocusEvent, TerminateEvent, ThinkEvent

from offer_evaluation_agent.config import Settings
from offer_evaluation_agent.model_factory import build_model
from offer_evaluation_agent.models import (
    EvaluateOffersRequest,
    EvaluateOffersResponse,
    SupplierOffer,
)

SYSTEM_PROMPT = """You are the Offer Evaluation Agent.

You must evaluate procurement offers using only the provided Markdown policy.
Do not apply hidden procurement rules.
Return only a JSON object matching the provided EvaluateOffersResponse schema.
Do not wrap the JSON in Markdown fences.
"""


class OfferEvaluationWorkflowAgent:
    """Locus-compatible agent wrapper with deterministic pre/post steps."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the workflow agent.

        Args:
            settings: Validated runtime settings.
        """

        self._settings = settings
        self._decision_agent = Agent(
            config=AgentConfig(
                model=build_model(settings),
                system_prompt=SYSTEM_PROMPT,
                max_iterations=1,
                output_schema=EvaluateOffersResponse,
                output_schema_strict=True,
                output_schema_retries=2,
            )
        )

    async def run(self, prompt: str) -> AsyncIterator[LocusEvent]:
        """Run the deterministic offer evaluation workflow.

        Args:
            prompt: JSON text containing an ``EvaluateOffersRequest``.

        Yields:
            Locus events consumed by ``A2AServer``.
        """

        yield ThinkEvent(iteration=1, reasoning="Validating EvaluateOffersRequest.")
        request = EvaluateOffersRequest.model_validate_json(prompt)

        yield ThinkEvent(iteration=2, reasoning="Loading local evaluation policy.")
        policy_text = self._settings.policy_file.read_text(encoding="utf-8")

        yield ThinkEvent(iteration=3, reasoning="Loading canonical output schema.")
        response_schema = self._settings.response_schema_file.read_text(
            encoding="utf-8"
        )

        yield ThinkEvent(iteration=4, reasoning="Invoking Locus LLM policy evaluator.")
        llm_prompt = self._build_llm_prompt(request, policy_text, response_schema)
        result = await asyncio.to_thread(self._decision_agent.run_sync, llm_prompt)
        response = self._parse_response(result.parsed, result.message)

        yield ThinkEvent(iteration=5, reasoning="Running technical consistency checks.")
        self.validate_consistency(request, response)

        yield TerminateEvent(
            reason="complete",
            iterations_used=5,
            final_confidence=1.0,
            total_tool_calls=0,
            final_message=response.model_dump_json(),
        )

    def _build_llm_prompt(
        self,
        request: EvaluateOffersRequest,
        policy_text: str,
        response_schema: str,
    ) -> str:
        """Build the prompt for the LLM decision step.

        Args:
            request: Validated request payload.
            policy_text: Local Markdown policy contents.
            response_schema: Canonical response JSON Schema text.

        Returns:
            Prompt passed to the Locus LLM agent.
        """

        request_json = request.model_dump_json(indent=2)
        return (
            "Evaluate this procurement request.\n\n"
            "Markdown policy:\n"
            f"{policy_text}\n\n"
            "Canonical output JSON Schema:\n"
            f"{response_schema}\n\n"
            "Request JSON:\n"
            f"{request_json}\n\n"
            "Return only the EvaluateOffersResponse JSON object."
        )

    def _parse_response(
        self,
        parsed: object,
        raw_message: str,
    ) -> EvaluateOffersResponse:
        """Parse the LLM result into the response contract.

        Args:
            parsed: Structured output parsed by Locus, when available.
            raw_message: Raw model message fallback.

        Returns:
            Validated response model.
        """

        if isinstance(parsed, EvaluateOffersResponse):
            return parsed
        return EvaluateOffersResponse.model_validate_json(
            _extract_json_object(raw_message)
        )

    def validate_consistency(
        self,
        request: EvaluateOffersRequest,
        response: EvaluateOffersResponse,
    ) -> None:
        """Validate response consistency that JSON Schema cannot express.

        Args:
            request: Original request payload.
            response: LLM-generated response payload.

        Raises:
            ValueError: If the response contradicts the request.
        """

        if response.request_id != request.request_id:
            raise ValueError("Response request_id does not match input request_id.")

        decision = response.decision
        if decision.status == "no_valid_offers":
            if decision.selected_offer.offer_id:
                raise ValueError(
                    "No-valid-offers decision must not include selected_offer."
                )
            if not decision.reasons:
                raise ValueError(
                    "No-valid-offers decision must include at least one reason."
                )
            return

        if not decision.selected_offer.offer_id:
            raise ValueError("Selected-offer decision must include selected_offer.")
        if decision.reasons:
            raise ValueError("Selected-offer decision must not include reasons.")

        selected_offer = SupplierOffer.model_validate(
            decision.selected_offer.model_dump(mode="json")
        )

        offers_by_id = {offer.offer_id: offer for offer in request.offers}
        source_offer = offers_by_id.get(selected_offer.offer_id)
        if source_offer is None:
            raise ValueError("Selected offer_id is not present in the input request.")

        source = source_offer.model_dump(mode="json")
        selected = selected_offer.model_dump(mode="json")
        if selected != source:
            raise ValueError("Selected offer details do not match the input offer.")


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


def build_workflow_agent(settings: Settings) -> OfferEvaluationWorkflowAgent:
    """Build the Locus-compatible deterministic workflow agent.

    Args:
        settings: Validated runtime settings.

    Returns:
        Configured offer evaluation workflow agent.
    """

    _ensure_file_exists(settings.policy_file)
    _ensure_file_exists(settings.response_schema_file)
    return OfferEvaluationWorkflowAgent(settings)


def _ensure_file_exists(path: Path) -> None:
    """Ensure a required local file exists.

    Args:
        path: File path to verify.

    Raises:
        FileNotFoundError: If the path does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(path)
