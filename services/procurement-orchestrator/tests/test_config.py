"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Tests for Procurement Orchestrator configuration loading.
"""

from __future__ import annotations

import pytest

from procurement_orchestrator import config
from procurement_orchestrator.config import load_settings


def test_load_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Load valid settings from environment variables."""

    monkeypatch.setenv("PROCUREMENT_ORCHESTRATOR_PORT", "8003")
    monkeypatch.setenv("AGENT_API_KEY", "secret")
    monkeypatch.setenv("BID_COLLECTION_AGENT_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("OFFER_EVALUATION_AGENT_URL", "http://127.0.0.1:8001")
    monkeypatch.setenv("PURCHASE_ORDER_AGENT_URL", "http://127.0.0.1:8002")

    settings = load_settings()

    assert settings.agent_port == 8003
    assert settings.agent_api_key == "secret"
    assert settings.bid_collection_agent_url == "http://127.0.0.1:8000"
    assert settings.offer_evaluation_agent_url == "http://127.0.0.1:8001"
    assert settings.purchase_order_agent_url == "http://127.0.0.1:8002"
    assert settings.request_schema_file.exists()
    assert settings.event_schema_file.exists()
    assert settings.response_schema_file.exists()


def test_load_settings_rejects_invalid_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Reject invalid port values."""

    monkeypatch.setattr(config, "LOCAL_ENV_FILE", tmp_path / ".env")
    monkeypatch.setenv("PROCUREMENT_ORCHESTRATOR_PORT", "invalid")
    monkeypatch.setenv("AGENT_API_KEY", "secret")
    monkeypatch.setenv("BID_COLLECTION_AGENT_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("OFFER_EVALUATION_AGENT_URL", "http://127.0.0.1:8001")
    monkeypatch.setenv("PURCHASE_ORDER_AGENT_URL", "http://127.0.0.1:8002")

    with pytest.raises(RuntimeError, match="PROCUREMENT_ORCHESTRATOR_PORT"):
        load_settings()
