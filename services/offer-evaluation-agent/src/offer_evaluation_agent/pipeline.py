"""
Deterministic workflow for LLM-driven offer evaluation.

Author: L. Saetta
Date Last Modified: 2026-05-31
License: MIT
Description:    Implements the fixed sequence of validation, policy loading,
                LLM invocation, output validation, and consistency checks.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from locus.agent import Agent, AgentConfig
from locus.agent.hook_orchestrator import HookOrchestrator
from locus.core.events import LocusEvent, TerminateEvent, ThinkEvent
from locus.core.state import AgentState

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

# The lifecycle wrapper intentionally mirrors the other independent agents
# without introducing shared runtime code between services.
# pylint: disable=duplicate-code


class OfferEvaluationWorkflowAgent:
    """Locus-compatible agent wrapper with deterministic pre/post steps."""

    def __init__(self, settings: Settings, hooks: list[Any] | None = None) -> None:
        """Initialize the workflow agent.

        Args:
            settings: Validated runtime settings.
            hooks: Optional Locus lifecycle hooks.
        """

        self._settings = settings
        self._hooks = hooks or []
        self._hook_orchestrator = HookOrchestrator(self._hooks)
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

        state = await self._hook_orchestrator.run_before_invocation(
            prompt,
            AgentState(agent_id="offer-evaluation-agent", max_iterations=5),
        )
        success = False
        try:
            async for event in self._run_workflow(prompt):
                if isinstance(event, TerminateEvent):
                    state = state.model_copy(
                        update={
                            "iteration": event.iterations_used,
                            "confidence": event.final_confidence,
                            "updated_at": datetime.now(UTC),
                        }
                    )
                yield event
            success = True
        except Exception as exc:
            state = state.with_error(type(exc).__name__)
            raise
        finally:
            state = state.model_copy(update={"updated_at": datetime.now(UTC)})
            await self._hook_orchestrator.run_after_invocation(state, success)

    async def _run_workflow(self, prompt: str) -> AsyncIterator[LocusEvent]:
        """Run the deterministic offer evaluation workflow body."""

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
        response = enforce_policy_consistency(request, response)

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


def enforce_policy_consistency(
    request: EvaluateOffersRequest,
    response: EvaluateOffersResponse,
) -> EvaluateOffersResponse:
    """Enforce deterministic policy guardrails on top of the LLM decision.

    Args:
        request: Original evaluation request.
        response: LLM-generated evaluation response.

    Returns:
        A response consistent with the urgent procurement policy.
    """

    expected_offer = _select_best_eligible_offer(request)
    if expected_offer is None:
        return _no_valid_offers_response(request, response)

    selected_offer_id = response.decision.selected_offer.offer_id
    if (
        response.decision.status == "selected_offer"
        and selected_offer_id == expected_offer.offer_id
    ):
        return response

    return EvaluateOffersResponse(
        request_id=request.request_id,
        decision={
            "status": "selected_offer",
            "selected_offer": expected_offer.model_dump(mode="json"),
            "reasons": [],
        },
        explanation=(
            f"{expected_offer.supplier_name} was selected because it is the "
            "lowest-cost eligible offer in the requested currency and meets "
            "the required delivery date."
        ),
    )


def _select_best_eligible_offer(
    request: EvaluateOffersRequest,
) -> SupplierOffer | None:
    """Select the best eligible offer according to the local policy."""

    eligible = [
        offer
        for offer in request.offers
        if offer.currency == request.currency
        and offer.delivery_date <= request.required_delivery_date
    ]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda offer: (
            offer.price,
            -offer.reliability_score,
            offer.delivery_date,
            offer.offer_id,
        ),
    )[0]


def _no_valid_offers_response(
    request: EvaluateOffersRequest,
    response: EvaluateOffersResponse,
) -> EvaluateOffersResponse:
    """Return a consistent no-valid-offers response."""

    if response.decision.status == "no_valid_offers" and response.decision.reasons:
        return response

    return EvaluateOffersResponse(
        request_id=request.request_id,
        decision={
            "status": "no_valid_offers",
            "selected_offer": {
                "offer_id": "",
                "supplier_id": "",
                "supplier_name": "",
                "price": 0,
                "currency": "",
                "delivery_date": "",
                "quality_score": 0,
                "reliability_score": 0,
                "valid_until": "",
            },
            "reasons": [
                "Every offer was excluded because it used a different currency "
                "or missed the required delivery date."
            ],
        },
        explanation=(
            "No supplier offer was selected because every offer was excluded "
            "by the policy."
        ),
    )


def build_workflow_agent(
    settings: Settings,
    hooks: list[Any] | None = None,
) -> OfferEvaluationWorkflowAgent:
    """Build the Locus-compatible deterministic workflow agent.

    Args:
        settings: Validated runtime settings.
        hooks: Optional Locus lifecycle hooks.

    Returns:
        Configured offer evaluation workflow agent.
    """

    _ensure_file_exists(settings.policy_file)
    _ensure_file_exists(settings.response_schema_file)
    return OfferEvaluationWorkflowAgent(settings, hooks=hooks)


def _ensure_file_exists(path: Path) -> None:
    """Ensure a required local file exists.

    Args:
        path: File path to verify.

    Raises:
        FileNotFoundError: If the path does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(path)
