"""
Author: L. Saetta
Date Last Modified: 2026-05-31
License: MIT
Description:    Deterministic procurement orchestration workflow.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from locus.agent.hook_orchestrator import HookOrchestrator
from locus.core.events import LocusEvent, TerminateEvent, ThinkEvent
from locus.core.state import AgentState

from procurement_orchestrator.a2a_client import (
    A2AProcurementAgentClient,
    ProcurementAgentClient,
    model_to_payload,
)
from procurement_orchestrator.agent_payloads import (
    CollectBidsRequest,
    CollectBidsResponse,
    CreatePurchaseOrderRequest,
    CreatePurchaseOrderResponse,
    EvaluateOffersRequest,
    EvaluateOffersResponse,
)
from procurement_orchestrator.config import Settings
from procurement_orchestrator.logging_utils import LOGGER_NAME, log_step
from procurement_orchestrator.models import (
    BidCollectionSummary,
    EvaluationSummary,
    OrchestrationError,
    PartOrchestrationRequest,
    PartOrchestrationResult,
    ProcurementOrchestrationEvent,
    ProcurementOrchestrationRequest,
    ProcurementOrchestrationResponse,
    PurchaseOrderSummary,
    SelectedOffer,
)

EMPTY_ERROR = OrchestrationError(code="", message="")
EMPTY_SELECTED_OFFER = SelectedOffer(
    offer_id="",
    supplier_id="",
    supplier_name="",
    price=0,
    currency="",
    delivery_date="",
    quality_score=0,
    reliability_score=0,
    valid_until="",
)
EMPTY_EVALUATION = EvaluationSummary(
    status="",
    selected_offer=EMPTY_SELECTED_OFFER,
    explanation="",
)
EMPTY_PURCHASE_ORDER = PurchaseOrderSummary(
    status="",
    purchase_order_id="",
    external_reference="",
    registered_at="",
)

# The lifecycle wrapper intentionally mirrors the other independent agents
# without introducing shared runtime code between services.
# pylint: disable=duplicate-code


class ProcurementOrchestratorWorkflowAgent:  # pylint: disable=too-few-public-methods
    """Locus-compatible procurement orchestration workflow agent."""

    def __init__(
        self,
        settings: Settings,
        agent_client: ProcurementAgentClient | None = None,
        logger: logging.Logger | None = None,
        hooks: list[Any] | None = None,
    ) -> None:
        """Initialize the workflow agent.

        Args:
            settings: Validated runtime settings.
            agent_client: Optional downstream A2A client wrapper.
            logger: Optional logger for structured step logs.
            hooks: Optional Locus lifecycle hooks.
        """

        self._settings = settings
        self._agent_client = agent_client or A2AProcurementAgentClient(
            bid_collection_url=settings.bid_collection_agent_url,
            offer_evaluation_url=settings.offer_evaluation_agent_url,
            purchase_order_url=settings.purchase_order_agent_url,
            api_key=settings.agent_api_key,
        )
        self._logger = logger or logging.getLogger(LOGGER_NAME)
        self._hooks = hooks or []
        self._hook_orchestrator = HookOrchestrator(self._hooks)

    async def run(self, prompt: str) -> AsyncIterator[LocusEvent]:
        """Run the procurement orchestration workflow.

        Args:
            prompt: JSON text containing a ``ProcurementOrchestrationRequest``.

        Yields:
            Locus events consumed by ``A2AServer``.
        """

        state = await self._hook_orchestrator.run_before_invocation(
            prompt,
            AgentState(agent_id="procurement-orchestrator", max_iterations=1),
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
        """Run the deterministic procurement orchestration workflow body."""

        request = ProcurementOrchestrationRequest.model_validate_json(prompt)
        _validate_unique_part_ids(request)
        orchestration_id = f"ORCH-{request.request_id}"
        sequence = 1
        started_at = _now()

        event = _event(
            request,
            orchestration_id,
            sequence,
            "accepted",
            "accepted",
            "Procurement orchestration accepted and started.",
            {
                "parts_count": len(request.parts),
                "auto_create_purchase_order": request.auto_create_purchase_order,
            },
        )
        self._log_event(event)
        yield _think(event)
        sequence += 1

        event = _event(
            request,
            orchestration_id,
            sequence,
            "workflow_started",
            "running",
            "Procurement orchestration workflow started.",
            {"requested_by": request.requested_by},
        )
        self._log_event(event)
        yield _think(event)
        sequence += 1

        part_results: list[PartOrchestrationResult] = []
        for part in request.parts:
            async for step_event, result in self._run_part(
                request,
                orchestration_id,
                part,
                sequence,
            ):
                if result is None:
                    self._log_event(step_event)
                    yield _think(step_event)
                    sequence = step_event.sequence + 1
                else:
                    part_results.append(result)

        response = _build_final_response(
            request=request,
            orchestration_id=orchestration_id,
            started_at=started_at,
            part_results=part_results,
        )
        event_type = (
            "workflow_failed" if response.status == "failed" else "workflow_completed"
        )
        event_status = "failed" if response.status == "failed" else "completed"
        event = _event(
            request,
            orchestration_id,
            sequence,
            event_type,
            event_status,
            response.message,
            {"status": response.status},
        )
        self._log_event(event)
        yield _think(event)

        yield TerminateEvent(
            reason="complete",
            iterations_used=sequence,
            final_confidence=1.0,
            total_tool_calls=0,
            final_message=response.model_dump_json(),
        )

    # The local variables track the state of a long-running part workflow.
    # pylint: disable=too-many-locals
    async def _run_part(
        self,
        request: ProcurementOrchestrationRequest,
        orchestration_id: str,
        part: PartOrchestrationRequest,
        sequence: int,
    ) -> AsyncIterator[
        tuple[ProcurementOrchestrationEvent, PartOrchestrationResult | None]
    ]:
        """Run the orchestration workflow for one part."""

        attempts_used = 0
        last_bid_response: CollectBidsResponse | None = None
        last_evaluation: EvaluateOffersResponse | None = None
        max_attempts = request.max_rebid_attempts + 1

        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            if attempt > 1:
                yield (
                    _event(
                        request,
                        orchestration_id,
                        sequence,
                        "rebid_requested",
                        "retrying",
                        f"Requesting new supplier offers for part {part.part_id}.",
                        {"part_id": part.part_id, "attempt_number": attempt},
                    ),
                    None,
                )
                sequence += 1

            yield (
                _event(
                    request,
                    orchestration_id,
                    sequence,
                    "bid_collection_started",
                    "running",
                    f"Bid collection started for part {part.part_id}.",
                    {"part_id": part.part_id, "attempt_number": attempt},
                ),
                None,
            )
            sequence += 1
            bid_response = await self._collect_bids(request, part)
            last_bid_response = bid_response
            part_bid = _find_part_bid_result(bid_response, part.part_id)
            yield (
                _event(
                    request,
                    orchestration_id,
                    sequence,
                    "bid_collection_completed",
                    "running",
                    f"Bid collection completed for part {part.part_id}.",
                    {
                        "part_id": part.part_id,
                        "attempt_number": attempt,
                        "status": bid_response.status,
                        "offers_count": len(part_bid.offers) if part_bid else 0,
                    },
                ),
                None,
            )
            sequence += 1

            evaluation_request = _find_evaluation_request(bid_response, part.part_id)
            if evaluation_request is None:
                continue

            yield (
                _event(
                    request,
                    orchestration_id,
                    sequence,
                    "offer_evaluation_started",
                    "running",
                    f"Offer evaluation started for part {part.part_id}.",
                    {"part_id": part.part_id, "attempt_number": attempt},
                ),
                None,
            )
            sequence += 1
            evaluation = await self._evaluate_offers(request, evaluation_request)
            last_evaluation = evaluation
            yield (
                _event(
                    request,
                    orchestration_id,
                    sequence,
                    "offer_evaluation_completed",
                    "running",
                    f"Offer evaluation completed for part {part.part_id}.",
                    {
                        "part_id": part.part_id,
                        "attempt_number": attempt,
                        "decision_status": evaluation.decision.status,
                        "selected_offer_id": evaluation.decision.selected_offer.get(
                            "offer_id", ""
                        ),
                    },
                ),
                None,
            )
            sequence += 1
            if evaluation.decision.status == "selected_offer":
                result, emitted = await self._handle_selected_offer(
                    request,
                    orchestration_id,
                    part,
                    attempts_used,
                    last_bid_response,
                    evaluation,
                    sequence,
                )
                for event in emitted:
                    yield event, None
                yield emitted[-1], result
                return

        result = _no_valid_offer_result(
            part,
            attempts_used,
            last_bid_response,
            last_evaluation,
        )
        yield (
            _event(
                request,
                orchestration_id,
                sequence,
                "part_failed",
                "failed",
                f"No valid offer found for part {part.part_id}.",
                {"part_id": part.part_id, "attempts_used": attempts_used},
            ),
            None,
        )
        yield (
            _event(
                request,
                orchestration_id,
                sequence + 1,
                "part_failed",
                "failed",
                f"Part {part.part_id} completed without a valid offer.",
                {"part_id": part.part_id},
            ),
            result,
        )

    async def _collect_bids(
        self,
        request: ProcurementOrchestrationRequest,
        part: PartOrchestrationRequest,
    ) -> CollectBidsResponse:
        """Call the Bid Collection Agent for one part."""

        payload = CollectBidsRequest(
            request_id=request.request_id,
            currency=request.currency,
            evaluation_policy_id=request.evaluation_policy_id,
            response_deadline=request.response_deadline,
            sourcing_constraints=request.sourcing_constraints.model_dump(mode="json"),
            parts=[part.model_dump(mode="json", exclude_none=True)],
        )
        response = await self._agent_client.collect_bids(
            model_to_payload(payload),
            float(request.timeouts.bid_collection_seconds),
        )
        return CollectBidsResponse.model_validate(response)

    async def _evaluate_offers(
        self,
        request: ProcurementOrchestrationRequest,
        payload: EvaluateOffersRequest,
    ) -> EvaluateOffersResponse:
        """Call the Offer Evaluation Agent."""

        response = await self._agent_client.evaluate_offers(
            model_to_payload(payload),
            float(request.timeouts.offer_evaluation_seconds),
        )
        return EvaluateOffersResponse.model_validate(response)

    # The signature keeps the orchestration context explicit at the call site.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    async def _handle_selected_offer(
        self,
        request: ProcurementOrchestrationRequest,
        orchestration_id: str,
        part: PartOrchestrationRequest,
        attempts_used: int,
        bid_response: CollectBidsResponse,
        evaluation: EvaluateOffersResponse,
        sequence: int,
    ) -> tuple[PartOrchestrationResult, list[ProcurementOrchestrationEvent]]:
        """Handle selected offer and optional purchase order creation."""

        events: list[ProcurementOrchestrationEvent] = []
        if not request.auto_create_purchase_order:
            result = _winner_selected_result(
                part, attempts_used, bid_response, evaluation
            )
            events.append(
                _event(
                    request,
                    orchestration_id,
                    sequence,
                    "part_completed",
                    "completed",
                    f"Winning offer selected for part {part.part_id}.",
                    {"part_id": part.part_id, "purchase_order_skipped": True},
                )
            )
            return result, events

        events.append(
            _event(
                request,
                orchestration_id,
                sequence,
                "purchase_order_started",
                "running",
                f"Purchase order creation started for part {part.part_id}.",
                {"part_id": part.part_id},
            )
        )
        po_request = _build_purchase_order_request(request, part, evaluation)
        po_response = CreatePurchaseOrderResponse.model_validate(
            await self._agent_client.create_purchase_order(
                model_to_payload(po_request),
                float(request.timeouts.purchase_order_seconds),
            )
        )
        events.append(
            _event(
                request,
                orchestration_id,
                sequence + 1,
                "purchase_order_completed",
                "running",
                f"Purchase order creation completed for part {part.part_id}.",
                {
                    "part_id": part.part_id,
                    "purchase_order_status": po_response.status,
                    "purchase_order_id": po_response.purchase_order.get(
                        "purchase_order_id", ""
                    ),
                },
            )
        )
        result = _purchase_order_result(
            part,
            attempts_used,
            bid_response,
            evaluation,
            po_response,
        )
        final_type = (
            "part_completed"
            if result.status == "purchase_order_created"
            else "part_failed"
        )
        final_status = (
            "completed" if result.status == "purchase_order_created" else "failed"
        )
        events.append(
            _event(
                request,
                orchestration_id,
                sequence + 2,
                final_type,
                final_status,
                f"Part {part.part_id} finished with status {result.status}.",
                {"part_id": part.part_id, "status": result.status},
            )
        )
        return result, events

    def _log_event(self, event: ProcurementOrchestrationEvent) -> None:
        """Log one orchestration event."""

        log_step(
            self._logger,
            orchestration_id=event.orchestration_id,
            request_id=event.request_id,
            event_type=event.event_type,
            message=event.message,
            sequence=event.sequence,
            status=event.status,
            event_payload=event.payload,
        )


def build_workflow_agent(
    settings: Settings,
    hooks: list[Any] | None = None,
) -> ProcurementOrchestratorWorkflowAgent:
    """Build the Locus-compatible deterministic workflow agent."""

    _ensure_file_exists(settings.request_schema_file)
    _ensure_file_exists(settings.event_schema_file)
    _ensure_file_exists(settings.response_schema_file)
    return ProcurementOrchestratorWorkflowAgent(settings, hooks=hooks)


# The event factory mirrors the canonical event schema.
# pylint: disable=too-many-arguments,too-many-positional-arguments
def _event(
    request: ProcurementOrchestrationRequest,
    orchestration_id: str,
    sequence: int,
    event_type: str,
    status: str,
    message: str,
    payload: dict[str, Any],
) -> ProcurementOrchestrationEvent:
    """Build one streaming orchestration event."""

    return ProcurementOrchestrationEvent(
        orchestration_id=orchestration_id,
        request_id=request.request_id,
        sequence=sequence,
        timestamp=_now(),
        event_type=event_type,
        status=status,
        message=message,
        payload=payload,
    )


def _think(event: ProcurementOrchestrationEvent) -> ThinkEvent:
    """Convert an orchestration event into a Locus streaming event."""

    return ThinkEvent(iteration=event.sequence, reasoning=event.model_dump_json())


def _now() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(UTC).replace(microsecond=0)


def _validate_unique_part_ids(request: ProcurementOrchestrationRequest) -> None:
    """Validate duplicate part IDs."""

    part_ids = [part.part_id for part in request.parts]
    if len(part_ids) != len(set(part_ids)):
        raise ValueError(
            "ProcurementOrchestrationRequest contains duplicate part_id values."
        )


def _find_part_bid_result(
    response: CollectBidsResponse,
    part_id: str,
) -> Any | None:
    """Return the bid collection result for a part."""

    for part_result in response.part_results:
        if part_result.part_id == part_id:
            return part_result
    return None


def _find_evaluation_request(
    response: CollectBidsResponse,
    part_id: str,
) -> EvaluateOffersRequest | None:
    """Return the evaluation request for a part."""

    for evaluation_request in response.evaluation_requests:
        for offer in evaluation_request.offers:
            part_result = _find_part_bid_result(response, part_id)
            if part_result and offer.offer_id in {
                item.offer_id for item in part_result.offers
            }:
                return evaluation_request
    return None


def _bid_summary(
    response: CollectBidsResponse | None, part_id: str
) -> BidCollectionSummary:
    """Build bid collection summary for a part."""

    if response is None:
        return BidCollectionSummary(
            status="",
            identified_suppliers_count=0,
            offers_count=0,
        )
    part_result = _find_part_bid_result(response, part_id)
    if part_result is None:
        return BidCollectionSummary(
            status=response.status, identified_suppliers_count=0, offers_count=0
        )
    return BidCollectionSummary(
        status=response.status,
        identified_suppliers_count=len(part_result.identified_suppliers),
        offers_count=len(part_result.offers),
    )


def _evaluation_summary(evaluation: EvaluateOffersResponse | None) -> EvaluationSummary:
    """Build evaluation summary."""

    if evaluation is None:
        return EMPTY_EVALUATION.model_copy(deep=True)
    selected = evaluation.decision.selected_offer
    return EvaluationSummary(
        status=evaluation.decision.status,
        selected_offer=SelectedOffer(
            offer_id=str(selected.get("offer_id", "")),
            supplier_id=str(selected.get("supplier_id", "")),
            supplier_name=str(selected.get("supplier_name", "")),
            price=float(selected.get("price", 0)),
            currency=str(selected.get("currency", "")),
            delivery_date=str(selected.get("delivery_date", "")),
            quality_score=float(selected.get("quality_score", 0)),
            reliability_score=float(selected.get("reliability_score", 0)),
            valid_until=str(selected.get("valid_until", "")),
        ),
        explanation=evaluation.explanation,
    )


def _no_valid_offer_result(
    part: PartOrchestrationRequest,
    attempts_used: int,
    bid_response: CollectBidsResponse | None,
    evaluation: EvaluateOffersResponse | None,
) -> PartOrchestrationResult:
    """Build a no-valid-offer part result."""

    return PartOrchestrationResult(
        part_id=part.part_id,
        material_code=part.material_code,
        status="no_valid_offer",
        attempts_used=max(attempts_used, 1),
        bid_collection=_bid_summary(bid_response, part.part_id),
        evaluation=_evaluation_summary(evaluation),
        purchase_order=PurchaseOrderSummary(
            status="skipped",
            purchase_order_id="",
            external_reference="",
            registered_at="",
        ),
        error=EMPTY_ERROR,
    )


def _winner_selected_result(
    part: PartOrchestrationRequest,
    attempts_used: int,
    bid_response: CollectBidsResponse,
    evaluation: EvaluateOffersResponse,
) -> PartOrchestrationResult:
    """Build a winner-selected part result without purchase order creation."""

    return PartOrchestrationResult(
        part_id=part.part_id,
        material_code=part.material_code,
        status="winner_selected",
        attempts_used=attempts_used,
        bid_collection=_bid_summary(bid_response, part.part_id),
        evaluation=_evaluation_summary(evaluation),
        purchase_order=PurchaseOrderSummary(
            status="skipped",
            purchase_order_id="",
            external_reference="",
            registered_at="",
        ),
        error=EMPTY_ERROR,
    )


def _build_purchase_order_request(
    request: ProcurementOrchestrationRequest,
    part: PartOrchestrationRequest,
    evaluation: EvaluateOffersResponse,
) -> CreatePurchaseOrderRequest:
    """Build a Purchase Order Agent request from the selected offer."""

    selected = evaluation.decision.selected_offer
    price = float(selected["price"])
    unit_price = round(price / part.quantity, 6)
    purchase_order_id = f"PO-{request.request_id}-{part.part_id}"
    return CreatePurchaseOrderRequest(
        request_id=request.request_id,
        purchase_order_id=purchase_order_id,
        plant_code=part.plant_code,
        supplier={
            "supplier_id": selected["supplier_id"],
            "supplier_name": selected["supplier_name"],
        },
        line_items=[
            {
                "material_code": part.material_code,
                "material_description": part.material_description,
                "quantity": part.quantity,
                "unit_of_measure": part.unit_of_measure,
                "unit_price": unit_price,
                "currency": selected["currency"],
                "requested_delivery_date": part.required_delivery_date.isoformat(),
                "confirmed_delivery_date": selected["delivery_date"],
            }
        ],
        source_offer={
            "offer_id": selected["offer_id"],
            "price": price,
            "currency": selected["currency"],
        },
    )


def _purchase_order_result(
    part: PartOrchestrationRequest,
    attempts_used: int,
    bid_response: CollectBidsResponse,
    evaluation: EvaluateOffersResponse,
    po_response: CreatePurchaseOrderResponse,
) -> PartOrchestrationResult:
    """Build a purchase-order terminal part result."""

    if po_response.status == "registered":
        status = "purchase_order_created"
        error = EMPTY_ERROR
    else:
        status = "purchase_order_failed"
        error = OrchestrationError(
            code=str(po_response.error.get("code", "PURCHASE_ORDER_FAILED")),
            message=str(po_response.error.get("message", "Purchase order failed.")),
        )
    return PartOrchestrationResult(
        part_id=part.part_id,
        material_code=part.material_code,
        status=status,
        attempts_used=attempts_used,
        bid_collection=_bid_summary(bid_response, part.part_id),
        evaluation=_evaluation_summary(evaluation),
        purchase_order=PurchaseOrderSummary(
            status=po_response.status,
            purchase_order_id=str(
                po_response.purchase_order.get("purchase_order_id", "")
            ),
            external_reference=str(
                po_response.purchase_order.get("external_reference", "")
            ),
            registered_at=str(po_response.purchase_order.get("registered_at", "")),
        ),
        error=error,
    )


def _build_final_response(
    request: ProcurementOrchestrationRequest,
    orchestration_id: str,
    started_at: datetime,
    part_results: list[PartOrchestrationResult],
) -> ProcurementOrchestrationResponse:
    """Build the final orchestration response."""

    statuses = {result.status for result in part_results}
    if not part_results:
        status = "failed"
        message = "Procurement workflow failed before any part completed."
        error = OrchestrationError(code="NO_PART_RESULTS", message=message)
    elif statuses == {"purchase_order_created"}:
        status = "completed_with_purchase_orders"
        message = f"Procurement workflow completed with {len(part_results)} purchase order(s)."
        error = EMPTY_ERROR
    elif statuses == {"winner_selected"}:
        status = "completed_without_purchase_orders"
        message = (
            "Procurement workflow completed with winning offers and no purchase orders."
        )
        error = EMPTY_ERROR
    elif statuses == {"no_valid_offer"}:
        status = "completed_without_valid_offer"
        message = "Procurement workflow completed without valid supplier offers."
        error = EMPTY_ERROR
    elif all(
        item in {"failed", "purchase_order_failed", "no_valid_offer"}
        for item in statuses
    ):
        status = "failed"
        message = "Procurement workflow failed for every requested part."
        error = OrchestrationError(code="ALL_PARTS_FAILED", message=message)
    else:
        status = "partial"
        message = "Procurement workflow completed with partial results."
        error = EMPTY_ERROR

    return ProcurementOrchestrationResponse(
        orchestration_id=orchestration_id,
        request_id=request.request_id,
        status=status,
        started_at=started_at,
        completed_at=_now(),
        part_results=part_results,
        message=message,
        error=error,
    )


def _ensure_file_exists(path: Path) -> None:
    """Ensure a required local file exists."""

    if not path.exists():
        raise FileNotFoundError(path)
