"""
Tests for Purchase Order Agent configuration.

Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    Verifies required environment loading and validation.
"""

from __future__ import annotations

import pytest

from purchase_order_agent import config
from purchase_order_agent.config import REQUIRED_ENV_VARS, load_settings


def test_load_settings_prefers_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Load settings from environment variables."""

    values = {
        "OCI_REGION": "us-chicago-1",
        "OCI_AUTH": "API_KEY",
        "OCI_MODEL_ID": "openai.gpt-5",
        "OCI_COMPARTMENT_ID": "ocid1.compartment.oc1..example",
        "PURCHASE_ORDER_AGENT_PORT": "8011",
        "AGENT_API_KEY": "secret",
        "PURCHASE_ORDER_STORAGE_BACKEND": "fake",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    settings = load_settings()

    assert settings.oci_region == "us-chicago-1"
    assert settings.oci_auth == "API_KEY"
    assert settings.oci_model_id == "openai.gpt-5"
    assert settings.agent_port == 8011
    assert settings.agent_api_key == "secret"
    assert settings.purchase_order_storage_backend == "fake"
    assert settings.oci_endpoint == (
        "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com/openai/v1"
    )


def test_load_settings_requires_all_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raise a clear error when required variables are missing."""

    for name in REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", config.SERVICE_DIR / "missing.env")

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        load_settings()


def test_load_settings_reads_mysql_purchase_order_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load MySQL settings for purchase order persistence."""

    values = {
        "OCI_REGION": "us-chicago-1",
        "OCI_AUTH": "API_KEY",
        "OCI_MODEL_ID": "openai.gpt-5",
        "OCI_COMPARTMENT_ID": "ocid1.compartment.oc1..example",
        "PURCHASE_ORDER_AGENT_PORT": "8011",
        "AGENT_API_KEY": "secret",
        "PURCHASE_ORDER_STORAGE_BACKEND": "mysql",
        "PROCUREMENT_DB_HOST": "mysql",
        "PROCUREMENT_DB_PORT": "3307",
        "PROCUREMENT_DB_NAME": "procurement_demo",
        "PROCUREMENT_DB_USER": "procurement_app",
        "PROCUREMENT_DB_PASSWORD": "procurement_app_password",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    settings = load_settings()

    assert settings.purchase_order_storage_backend == "mysql"
    assert settings.db_host == "mysql"
    assert settings.db_port == 3307
    assert settings.db_name == "procurement_demo"
    assert settings.db_user == "procurement_app"
    assert settings.db_password == "procurement_app_password"
