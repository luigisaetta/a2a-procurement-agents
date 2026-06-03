"""
Author: L. Saetta
Date Last Modified: 2026-06-03
License: MIT
Description:    Builds supplier bid requests and downstream offer evaluation payloads.
"""

from __future__ import annotations

from bid_collection_agent.models import (
    CollectBidsRequest,
    EvaluateOffersRequestPayload,
    IdentifiedSupplier,
    PartBidRequest,
    SupplierBidRequest,
    SupplierBidRequestPart,
    SupplierBidRequestSupplier,
    SupplierOffer,
)


class OfferListProvider:
    """Construct bid request and offer list payloads."""

    def build_bid_request(
        self,
        request: CollectBidsRequest,
        part: PartBidRequest,
        supplier: IdentifiedSupplier,
        reference_price: tuple[float, str],
    ) -> SupplierBidRequest:
        """Build one supplier-facing bid request."""

        reference_unit_price, reference_currency = reference_price
        return SupplierBidRequest(
            request_id=request.request_id,
            bid_request_id=(
                f"BIDREQ-{request.request_id}-{part.part_id}-{supplier.supplier_id}"
            ),
            supplier=SupplierBidRequestSupplier(
                supplier_id=supplier.supplier_id,
                supplier_name=supplier.supplier_name,
                api_endpoint=supplier.api_endpoint,
                country_code=supplier.country_code,
            ),
            part=SupplierBidRequestPart(
                part_id=part.part_id,
                plant_code=part.plant_code,
                material_code=part.material_code,
                material_description=part.material_description,
                quantity=part.quantity,
                unit_of_measure=part.unit_of_measure,
                reference_unit_price=reference_unit_price,
                reference_currency=reference_currency,
                required_delivery_date=part.required_delivery_date,
            ),
            currency=request.currency,
            response_deadline=request.response_deadline,
        )

    def build_evaluation_request(
        self,
        request: CollectBidsRequest,
        part: PartBidRequest,
        offers: list[SupplierOffer],
    ) -> EvaluateOffersRequestPayload:
        """Build one Offer Evaluation Agent request payload."""

        return EvaluateOffersRequestPayload(
            request_id=request.request_id,
            plant_code=part.plant_code,
            material_code=part.material_code,
            material_description=part.material_description,
            quantity=part.quantity,
            unit_of_measure=part.unit_of_measure,
            currency=request.currency,
            required_delivery_date=part.required_delivery_date,
            evaluation_policy_id=request.evaluation_policy_id,
            offers=offers,
        )
