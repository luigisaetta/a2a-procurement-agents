"""
Author: L. Saetta
Date Last Modified: 2026-05-31
License: MIT
Description:    Deterministic bid collection workflow using MCP supplier discovery.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from locus.agent.hook_orchestrator import HookOrchestrator
from locus.core.events import LocusEvent, TerminateEvent, ThinkEvent
from locus.core.state import AgentState

from bid_collection_agent.config import Settings
from bid_collection_agent.models import (
    CollectBidsRequest,
    CollectBidsResponse,
    EvaluateOffersRequestPayload,
    PartBidRequest,
    PartBidResult,
    SupplierOffer,
    SupplierResponseSummary,
)
from bid_collection_agent.offer_list_provider import OfferListProvider
from bid_collection_agent.supplier_discovery_provider import (
    McpSupplierDiscoveryProvider,
    SupplierDiscoveryProvider,
)
from bid_collection_agent.supplier_offer_provider import (
    SimulatedSupplierOfferProvider,
    SupplierOfferProvider,
)

# The lifecycle wrapper intentionally mirrors the other independent agents
# without introducing shared runtime code between services.
# pylint: disable=duplicate-code


class BidCollectionWorkflowAgent:  # pylint: disable=too-few-public-methods
    """Locus-compatible deterministic bid collection workflow agent."""

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        settings: Settings,
        supplier_discovery_provider: SupplierDiscoveryProvider | None = None,
        supplier_offer_provider: SupplierOfferProvider | None = None,
        offer_list_provider: OfferListProvider | None = None,
        hooks: list[Any] | None = None,
    ) -> None:
        """Initialize the workflow agent.

        Args:
            settings: Validated runtime settings.
            supplier_discovery_provider: Optional supplier discovery provider.
            supplier_offer_provider: Optional supplier offer provider.
            offer_list_provider: Optional offer list provider.
            hooks: Optional Locus lifecycle hooks.
        """

        self._settings = settings
        self._supplier_discovery_provider = (
            supplier_discovery_provider
            or McpSupplierDiscoveryProvider(
                settings.procurement_data_mcp_url,
                settings.mcp_timeout_seconds,
            )
        )
        self._supplier_offer_provider = (
            supplier_offer_provider or SimulatedSupplierOfferProvider()
        )
        self._offer_list_provider = offer_list_provider or OfferListProvider()
        self._hooks = hooks or []
        self._hook_orchestrator = HookOrchestrator(self._hooks)

    async def run(self, prompt: str) -> AsyncIterator[LocusEvent]:
        """Run the bid collection workflow.

        Args:
            prompt: JSON text containing a ``CollectBidsRequest``.

        Yields:
            Locus events consumed by ``A2AServer``.
        """

        state = await self._hook_orchestrator.run_before_invocation(
            prompt,
            AgentState(agent_id="bid-collection-agent", max_iterations=1),
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
        """Run the deterministic bid collection workflow body."""

        yield ThinkEvent(iteration=1, reasoning="Validating CollectBidsRequest.")
        request = CollectBidsRequest.model_validate_json(prompt)
        _validate_unique_part_ids(request)

        part_results: list[PartBidResult] = []
        evaluation_requests: list[EvaluateOffersRequestPayload] = []
        supplier_failures = 0

        for index, part in enumerate(request.parts, start=1):
            yield ThinkEvent(
                iteration=index + 1,
                reasoning=f"Collecting supplier bids for part {part.part_id}.",
            )
            part_result, evaluation_request = await self._collect_part_bids(
                request,
                part,
            )
            supplier_failures += sum(
                response.status == "failed"
                for response in part_result.supplier_responses
            )
            part_results.append(part_result)
            if evaluation_request is not None:
                evaluation_requests.append(evaluation_request)

        response = _build_response(
            request=request,
            part_results=part_results,
            evaluation_requests=evaluation_requests,
            supplier_failures=supplier_failures,
        )

        yield TerminateEvent(
            reason="complete",
            iterations_used=len(request.parts) + 1,
            final_confidence=1.0,
            total_tool_calls=len(part_results),
            final_message=response.model_dump_json(),
        )

    async def _collect_part_bids(
        self,
        request: CollectBidsRequest,
        part: PartBidRequest,
    ) -> tuple[PartBidResult, EvaluateOffersRequestPayload | None]:
        """Collect bids for one requested part."""

        suppliers = await self._supplier_discovery_provider.identify_suppliers(
            part,
            request.sourcing_constraints,
        )
        _validate_unique_supplier_ids(part, suppliers)

        offers: list[SupplierOffer] = []
        responses: list[SupplierResponseSummary] = []
        for supplier in suppliers:
            bid_request = self._offer_list_provider.build_bid_request(
                request,
                part,
                supplier,
            )
            supplier_response = self._supplier_offer_provider.request_offer(bid_request)
            _validate_supplier_response(
                part, bid_request.bid_request_id, supplier_response
            )
            responses.append(
                SupplierResponseSummary(
                    supplier_id=supplier.supplier_id,
                    supplier_name=supplier.supplier_name,
                    bid_request_id=bid_request.bid_request_id,
                    status=supplier_response.status,
                    error=supplier_response.error,
                )
            )
            if supplier_response.status == "offer_received":
                offers.append(
                    SupplierOffer.model_validate(
                        supplier_response.offer.model_dump(
                            exclude={"part_id", "material_code"}
                        )
                    )
                )

        if not responses:
            responses.append(
                SupplierResponseSummary(
                    supplier_id="NO-SUPPLIER",
                    supplier_name="No supplier identified",
                    bid_request_id=f"BIDREQ-{request.request_id}-{part.part_id}-NONE",
                    status="failed",
                    error={
                        "code": "NO_SUPPLIERS_IDENTIFIED",
                        "message": "No eligible suppliers were returned by MCP.",
                    },
                )
            )

        part_status = _part_status(offers, responses)
        result = PartBidResult(
            part_id=part.part_id,
            material_code=part.material_code,
            status=part_status,
            identified_suppliers=suppliers,
            offers=offers,
            supplier_responses=responses,
        )
        evaluation_request = (
            self._offer_list_provider.build_evaluation_request(
                request,
                part,
                offers,
            )
            if offers
            else None
        )
        return result, evaluation_request


def build_workflow_agent(
    settings: Settings,
    hooks: list[Any] | None = None,
) -> BidCollectionWorkflowAgent:
    """Build the Locus-compatible deterministic workflow agent.

    Args:
        settings: Validated runtime settings.
        hooks: Optional Locus lifecycle hooks.

    Returns:
        Configured bid collection workflow agent.
    """

    _ensure_file_exists(settings.request_schema_file)
    _ensure_file_exists(settings.response_schema_file)
    return BidCollectionWorkflowAgent(settings, hooks=hooks)


def _validate_unique_part_ids(request: CollectBidsRequest) -> None:
    """Validate duplicate part IDs."""

    part_ids = [part.part_id for part in request.parts]
    if len(part_ids) != len(set(part_ids)):
        raise ValueError("CollectBidsRequest contains duplicate part_id values.")


def _validate_unique_supplier_ids(
    part: PartBidRequest,
    suppliers: list,
) -> None:
    """Validate duplicate supplier IDs for one part."""

    supplier_ids = [supplier.supplier_id for supplier in suppliers]
    if len(supplier_ids) != len(set(supplier_ids)):
        raise ValueError(
            f"Supplier discovery returned duplicate suppliers for part {part.part_id}."
        )


def _validate_supplier_response(
    part: PartBidRequest,
    bid_request_id: str,
    supplier_response: object,
) -> None:
    """Validate supplier response consistency with the original request."""

    if supplier_response.bid_request_id != bid_request_id:
        raise ValueError("Supplier response bid_request_id does not match request.")
    if supplier_response.status == "offer_received":
        if supplier_response.offer.part_id != part.part_id:
            raise ValueError("Supplier offer part_id does not match request.")
        if supplier_response.offer.material_code != part.material_code:
            raise ValueError("Supplier offer material_code does not match request.")


def _part_status(
    offers: list[SupplierOffer],
    responses: list[SupplierResponseSummary],
) -> str:
    """Return the part-level status."""

    if not offers:
        return "no_offers"
    if len(offers) == len(responses):
        return "offers_collected"
    return "partial"


def _build_response(
    request: CollectBidsRequest,
    part_results: list[PartBidResult],
    evaluation_requests: list[EvaluateOffersRequestPayload],
    supplier_failures: int,
) -> CollectBidsResponse:
    """Build the final collection response."""

    offers_count = sum(len(result.offers) for result in part_results)
    if offers_count == 0:
        status = "failed"
    elif supplier_failures or len(evaluation_requests) != len(part_results):
        status = "partial"
    else:
        status = "completed"

    return CollectBidsResponse(
        request_id=request.request_id,
        status=status,
        part_results=part_results,
        evaluation_requests=evaluation_requests,
        message=(
            f"Collected {offers_count} supplier offer"
            f"{'' if offers_count == 1 else 's'} across "
            f"{len(part_results)} requested part"
            f"{'' if len(part_results) == 1 else 's'}."
        ),
    )


def _ensure_file_exists(path: Path) -> None:
    """Ensure a required local file exists."""

    if not path.exists():
        raise FileNotFoundError(path)
