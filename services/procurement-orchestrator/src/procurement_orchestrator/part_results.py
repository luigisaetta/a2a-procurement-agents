"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Builders for the terminal result of one orchestrated part.
                Each function maps one way a part can end (purchase order
                created, winner selected, no valid offer, downstream
                failure) to a PartOrchestrationResult.
"""

from __future__ import annotations

from typing import Any, Literal

from procurement_orchestrator.a2a_client import DownstreamAgentError
from procurement_orchestrator.agent_payloads import (
    CollectBidsResponse,
    CreatePurchaseOrderResponse,
    EvaluateOffersResponse,
)
from procurement_orchestrator.models import (
    BidCollectionSummary,
    EvaluationSummary,
    OrchestrationError,
    PartOrchestrationRequest,
    PartOrchestrationResult,
    PurchaseOrderSummary,
    SelectedOffer,
)

EMPTY_ERROR = OrchestrationError(code="", message="")
EMPTY_SELECTED_OFFER = SelectedOffer(
    offer_id="",
    supplier_id="",
    supplier_name="",
    parts_cost=0,
    shipping_cost=0,
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


def find_part_bid_result(
    response: CollectBidsResponse,
    part_id: str,
) -> Any | None:
    """Return the bid collection result for a part."""

    for part_result in response.part_results:
        if part_result.part_id == part_id:
            return part_result
    return None


def bid_summary(
    response: CollectBidsResponse | None, part_id: str
) -> BidCollectionSummary:
    """Build bid collection summary for a part."""

    if response is None:
        return BidCollectionSummary(
            status="",
            identified_suppliers_count=0,
            offers_count=0,
        )
    part_result = find_part_bid_result(response, part_id)
    if part_result is None:
        return BidCollectionSummary(
            status=response.status, identified_suppliers_count=0, offers_count=0
        )
    return BidCollectionSummary(
        status=response.status,
        identified_suppliers_count=len(part_result.identified_suppliers),
        offers_count=len(part_result.offers),
    )


def evaluation_summary(evaluation: EvaluateOffersResponse | None) -> EvaluationSummary:
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
            parts_cost=float(selected.get("parts_cost", 0)),
            shipping_cost=float(selected.get("shipping_cost", 0)),
            price=float(selected.get("price", 0)),
            currency=str(selected.get("currency", "")),
            delivery_date=str(selected.get("delivery_date", "")),
            quality_score=float(selected.get("quality_score", 0)),
            reliability_score=float(selected.get("reliability_score", 0)),
            valid_until=str(selected.get("valid_until", "")),
        ),
        explanation=evaluation.explanation,
    )


def no_valid_offer_result(
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
        bid_collection=bid_summary(bid_response, part.part_id),
        evaluation=evaluation_summary(evaluation),
        purchase_order=PurchaseOrderSummary(
            status="skipped",
            purchase_order_id="",
            external_reference="",
            registered_at="",
        ),
        error=EMPTY_ERROR,
    )


# Keyword-only arguments keep each piece of part state explicit at call sites.
# pylint: disable-next=too-many-arguments
def downstream_failure_result(
    *,
    part: PartOrchestrationRequest,
    status: Literal["failed", "purchase_order_failed"],
    attempts_used: int,
    bid_response: CollectBidsResponse | None,
    evaluation: EvaluateOffersResponse | None,
    error: DownstreamAgentError,
) -> PartOrchestrationResult:
    """Build the part result for a downstream call that failed.

    Args:
        part: Requested part.
        status: ``failed`` when bid collection or offer evaluation failed,
            ``purchase_order_failed`` when purchase order creation failed.
        attempts_used: Bid collection attempts started for the part.
        bid_response: Last bid collection response, if any.
        evaluation: Last offer evaluation response, if any.
        error: The downstream call failure.

    Returns:
        Terminal part result that keeps the summaries collected so far.
    """

    purchase_order_status = "failed" if status == "purchase_order_failed" else "skipped"
    return PartOrchestrationResult(
        part_id=part.part_id,
        material_code=part.material_code,
        status=status,
        attempts_used=max(attempts_used, 1),
        bid_collection=bid_summary(bid_response, part.part_id),
        evaluation=evaluation_summary(evaluation),
        purchase_order=PurchaseOrderSummary(
            status=purchase_order_status,
            purchase_order_id="",
            external_reference="",
            registered_at="",
        ),
        error=OrchestrationError(code=error.code, message=error.message),
    )


def winner_selected_result(
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
        bid_collection=bid_summary(bid_response, part.part_id),
        evaluation=evaluation_summary(evaluation),
        purchase_order=PurchaseOrderSummary(
            status="skipped",
            purchase_order_id="",
            external_reference="",
            registered_at="",
        ),
        error=EMPTY_ERROR,
    )


def purchase_order_result(
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
        bid_collection=bid_summary(bid_response, part.part_id),
        evaluation=evaluation_summary(evaluation),
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
