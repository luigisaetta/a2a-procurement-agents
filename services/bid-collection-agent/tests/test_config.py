"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Tests for Bid Collection Agent configuration loading.
"""

from __future__ import annotations

from bid_collection_agent import config
from bid_collection_agent.config import load_settings


def test_load_settings_reads_environment(monkeypatch) -> None:
    """Load valid settings from environment variables."""

    monkeypatch.setenv("BID_COLLECTION_AGENT_PORT", "8000")
    monkeypatch.setenv("AGENT_API_KEY", "secret")
    monkeypatch.setenv("PROCUREMENT_DATA_MCP_URL", "http://127.0.0.1:8010/mcp")
    monkeypatch.setenv("PROCUREMENT_DATA_MCP_TIMEOUT_SECONDS", "3.5")

    settings = load_settings()

    assert settings.agent_port == 8000
    assert settings.agent_api_key == "secret"
    assert settings.procurement_data_mcp_url == "http://127.0.0.1:8010/mcp"
    assert settings.mcp_timeout_seconds == 3.5
    assert settings.request_schema_file.exists()
    assert settings.response_schema_file.exists()


def test_load_settings_rejects_invalid_port(monkeypatch, tmp_path) -> None:
    """Reject invalid port values."""

    monkeypatch.setattr(config, "LOCAL_ENV_FILE", tmp_path / ".env")
    monkeypatch.setenv("BID_COLLECTION_AGENT_PORT", "invalid")
    monkeypatch.setenv("AGENT_API_KEY", "secret")
    monkeypatch.setenv("PROCUREMENT_DATA_MCP_URL", "http://127.0.0.1:8010/mcp")

    try:
        load_settings()
    except RuntimeError as exc:
        assert "BID_COLLECTION_AGENT_PORT must be an integer" in str(exc)
    else:
        raise AssertionError("Expected invalid port to raise RuntimeError.")
