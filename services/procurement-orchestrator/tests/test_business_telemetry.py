"""
Author: L. Saetta
Date Last Modified: 2026-06-03
License: MIT
Description:    Tests for procurement business telemetry metrics.
"""

from __future__ import annotations

from typing import Any

from procurement_orchestrator.business_telemetry import BusinessTelemetryHook


def test_business_telemetry_records_purchase_order_metrics() -> None:
    """Record purchase order count, amount, deviation, and shipping percentage."""

    meter = _FakeMeter()
    hook = BusinessTelemetryHook(meter=meter, enabled=True)

    hook.record_purchase_order_created(
        plant_code="DE-MUN",
        total_amount=1400.0,
        currency="EUR",
        price_deviation_percent=-2.5,
        shipping_percentage=7.1429,
    )

    assert meter.counters["procurement.purchase_orders"].adds == [
        (1, {"plant_code": "DE-MUN", "currency": "EUR"})
    ]
    assert meter.counters["procurement.purchase_order.amount"].adds == [
        (1400.0, {"plant_code": "DE-MUN", "currency": "EUR"})
    ]
    assert meter.histograms[
        "procurement.purchase_order.price_deviation_percent"
    ].records == [(-2.5, {"plant_code": "DE-MUN"})]
    assert meter.histograms[
        "procurement.purchase_order.shipping_percentage"
    ].records == [(7.1429, {"plant_code": "DE-MUN"})]


def test_disabled_business_telemetry_does_not_create_instruments() -> None:
    """Skip instrument creation when business telemetry is disabled."""

    meter = _FakeMeter()
    hook = BusinessTelemetryHook(meter=meter, enabled=False)

    hook.record_purchase_order_created(
        plant_code="DE-MUN",
        total_amount=1400.0,
        currency="EUR",
        price_deviation_percent=0.0,
        shipping_percentage=7.1429,
    )

    assert meter.counters == {}
    assert meter.histograms == {}


class _FakeMeter:
    """Small fake OpenTelemetry meter."""

    def __init__(self) -> None:
        """Initialize instrument registries."""

        self.counters: dict[str, _FakeCounter] = {}
        self.histograms: dict[str, _FakeHistogram] = {}

    def create_counter(self, name: str, **_kwargs: Any) -> "_FakeCounter":
        """Create and store a fake counter."""

        counter = _FakeCounter()
        self.counters[name] = counter
        return counter

    def create_histogram(self, name: str, **_kwargs: Any) -> "_FakeHistogram":
        """Create and store a fake histogram."""

        histogram = _FakeHistogram()
        self.histograms[name] = histogram
        return histogram


class _FakeCounter:
    """Record counter additions."""

    def __init__(self) -> None:
        """Initialize recorded additions."""

        self.adds: list[tuple[float, dict[str, str]]] = []

    def add(self, value: float, attributes: dict[str, str]) -> None:
        """Record one counter addition."""

        self.adds.append((value, attributes))


class _FakeHistogram:
    """Record histogram observations."""

    def __init__(self) -> None:
        """Initialize recorded observations."""

        self.records: list[tuple[float, dict[str, str]]] = []

    def record(self, value: float, attributes: dict[str, str]) -> None:
        """Record one histogram observation."""

        self.records.append((value, attributes))
