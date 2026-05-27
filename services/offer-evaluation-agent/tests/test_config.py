"""
Tests for Offer Evaluation Agent configuration.

Author: L. Saetta
Date Last Modified: 2026-05-27
License: MIT
Description:    Verifies required environment loading and validation.
"""

from __future__ import annotations

import pytest

from offer_evaluation_agent.config import REQUIRED_ENV_VARS, load_settings


def test_load_settings_prefers_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Load settings from environment variables."""

    values = {
        "OCI_REGION": "us-chicago-1",
        "OCI_AUTH": "API_KEY",
        "OCI_MODEL_ID": "openai.gpt-5",
        "OCI_COMPARTMENT_ID": "ocid1.compartment.oc1..example",
        "OFFER_EVALUATION_AGENT_PORT": "8010",
        "AGENT_API_KEY": "secret",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    settings = load_settings()

    assert settings.oci_region == "us-chicago-1"
    assert settings.oci_auth == "API_KEY"
    assert settings.oci_model_id == "openai.gpt-5"
    assert settings.agent_port == 8010
    assert settings.agent_api_key == "secret"
    assert settings.oci_endpoint == (
        "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com/openai/v1"
    )


def test_load_settings_requires_all_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raise a clear error when required variables are missing."""

    for name in REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        load_settings()
