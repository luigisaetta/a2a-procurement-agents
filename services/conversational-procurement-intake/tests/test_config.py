"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Tests for conversational intake service configuration.
"""

from __future__ import annotations

import pytest

from conversational_procurement_intake.config import load_settings


def test_load_settings_defaults_to_llm_and_requires_oci(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default to LLM extraction and require OCI variables."""

    for name in (
        "CONVERSATIONAL_INTAKE_PORT",
        "CONVERSATIONAL_INTAKE_EXTRACTOR_MODE",
        "OCI_REGION",
        "OCI_AUTH",
        "OCI_MODEL_ID",
        "OCI_COMPARTMENT_ID",
        "PROCUREMENT_DATA_MCP_URL",
        "PROCUREMENT_DATA_MCP_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="Missing required LLM extraction"):
        load_settings()


def test_load_settings_accepts_explicit_deterministic_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allow deterministic extraction only when explicitly requested."""

    monkeypatch.setenv("CONVERSATIONAL_INTAKE_EXTRACTOR_MODE", "deterministic")
    monkeypatch.delenv("OCI_REGION", raising=False)
    monkeypatch.delenv("OCI_AUTH", raising=False)
    monkeypatch.delenv("OCI_MODEL_ID", raising=False)
    monkeypatch.delenv("OCI_COMPARTMENT_ID", raising=False)
    monkeypatch.delenv("PROCUREMENT_DATA_MCP_URL", raising=False)
    monkeypatch.delenv("PROCUREMENT_DATA_MCP_TIMEOUT_SECONDS", raising=False)

    settings = load_settings()

    assert settings.service_port == 8012
    assert settings.extractor_mode == "deterministic"
    assert settings.procurement_data_mcp_url == ""
    assert settings.procurement_data_mcp_timeout_seconds == 10


def test_load_settings_validates_llm_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Require OCI settings when LLM extraction is enabled."""

    monkeypatch.setenv("CONVERSATIONAL_INTAKE_EXTRACTOR_MODE", "llm")
    monkeypatch.delenv("OCI_REGION", raising=False)
    monkeypatch.delenv("OCI_AUTH", raising=False)
    monkeypatch.delenv("OCI_MODEL_ID", raising=False)
    monkeypatch.delenv("OCI_COMPARTMENT_ID", raising=False)

    with pytest.raises(RuntimeError, match="Missing required LLM extraction"):
        load_settings()


def test_load_settings_accepts_llm_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load OCI settings for LLM extraction."""

    monkeypatch.setenv("CONVERSATIONAL_INTAKE_EXTRACTOR_MODE", "llm")
    monkeypatch.setenv("OCI_REGION", "us-chicago-1")
    monkeypatch.setenv("OCI_AUTH", "API_KEY")
    monkeypatch.setenv("OCI_MODEL_ID", "openai.gpt-5")
    monkeypatch.setenv("OCI_COMPARTMENT_ID", "ocid1.compartment.oc1..example")

    settings = load_settings()

    assert settings.extractor_mode == "llm"
    assert settings.oci_endpoint == (
        "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com/openai/v1"
    )


def test_load_settings_reads_procurement_data_mcp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load Procurement Data MCP resolver settings."""

    monkeypatch.setenv("CONVERSATIONAL_INTAKE_EXTRACTOR_MODE", "deterministic")
    monkeypatch.setenv("PROCUREMENT_DATA_MCP_URL", "http://127.0.0.1:8011/mcp")
    monkeypatch.setenv("PROCUREMENT_DATA_MCP_TIMEOUT_SECONDS", "2.5")

    settings = load_settings()

    assert settings.procurement_data_mcp_url == "http://127.0.0.1:8011/mcp"
    assert settings.procurement_data_mcp_timeout_seconds == 2.5
