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

    settings = load_settings()

    assert settings.service_port == 8012
    assert settings.extractor_mode == "deterministic"


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
