"""
Author: L. Saetta
Date Last Modified: 2026-06-03
License: MIT
Description:    Business telemetry hook for procurement orchestration metrics.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)

# OpenTelemetry is imported lazily so local non-telemetry runs can work even
# when exporter dependencies are not installed.
# pylint: disable=import-outside-toplevel


class BusinessTelemetryHook:
    """Emit procurement business metrics through OpenTelemetry instruments."""

    def __init__(self, meter: Any, enabled: bool) -> None:
        """Initialize business metric instruments.

        Args:
            meter: OpenTelemetry-compatible meter.
            enabled: Whether metric recording should be active.
        """

        self._enabled = enabled
        self._purchase_orders = None
        self._purchase_order_amount = None
        self._price_deviation_percent = None
        self._shipping_percentage = None
        if not enabled:
            return

        self._purchase_orders = meter.create_counter(
            "procurement.purchase_orders",
            unit="{purchase_order}",
            description="Purchase orders created by the procurement workflow.",
        )
        self._purchase_order_amount = meter.create_counter(
            "procurement.purchase_order.amount",
            unit="{currency}",
            description="Total value of purchase orders created by the workflow.",
        )
        self._price_deviation_percent = meter.create_histogram(
            "procurement.purchase_order.price_deviation_percent",
            unit="%",
            description=(
                "Selected offer parts-cost deviation from the average offered "
                "parts cost for the same plant and part."
            ),
        )
        self._shipping_percentage = meter.create_histogram(
            "procurement.purchase_order.shipping_percentage",
            unit="%",
            description="Selected offer shipping cost as a percentage of total cost.",
        )

    async def on_before_invocation(self, _prompt: str, state: Any) -> Any:
        """Return lifecycle state unchanged before invocation."""

        return state

    async def on_after_invocation(self, _state: Any, _success: bool) -> None:
        """Keep lifecycle compatibility with Locus hooks."""

    # The explicit keyword-only fields make the metric contract clear at call sites.
    # pylint: disable=too-many-arguments
    def record_purchase_order_created(
        self,
        *,
        plant_code: str,
        total_amount: float,
        currency: str,
        price_deviation_percent: float | None,
        shipping_percentage: float | None,
    ) -> None:
        """Record business metrics for one created purchase order.

        Args:
            plant_code: Destination plant code for low-cardinality grouping.
            total_amount: Total purchase order amount.
            currency: ISO 4217 purchase order currency.
            price_deviation_percent: Selected parts-cost deviation from peer offers.
            shipping_percentage: Shipping cost percentage of total offer cost.
        """

        if not self._enabled:
            return

        attributes = {"plant_code": plant_code, "currency": currency}
        plant_attributes = {"plant_code": plant_code}
        self._purchase_orders.add(1, attributes)
        self._purchase_order_amount.add(total_amount, attributes)

        if price_deviation_percent is not None:
            self._price_deviation_percent.record(
                price_deviation_percent, plant_attributes
            )
        if shipping_percentage is not None:
            self._shipping_percentage.record(shipping_percentage, plant_attributes)


def create_business_telemetry_hook(
    *, enabled: bool, service_name: str
) -> BusinessTelemetryHook:
    """Create the business telemetry hook.

    Args:
        enabled: Whether metric recording should be active.
        service_name: Meter name used for OpenTelemetry instrumentation scope.

    Returns:
        Configured business telemetry hook. If OpenTelemetry is unavailable, the
        returned hook is disabled.
    """

    if not enabled:
        return BusinessTelemetryHook(meter=None, enabled=False)

    try:
        from opentelemetry import metrics
    except ImportError as exc:
        LOGGER.warning("OpenTelemetry metrics unavailable: %s", exc)
        return BusinessTelemetryHook(meter=None, enabled=False)

    return BusinessTelemetryHook(
        meter=metrics.get_meter(service_name),
        enabled=True,
    )
