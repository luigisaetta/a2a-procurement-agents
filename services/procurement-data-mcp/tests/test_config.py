"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Tests for Procurement Data MCP configuration loading.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from procurement_data_mcp import config
from procurement_data_mcp.config import load_settings


def test_load_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Load database settings from environment variables."""

    monkeypatch.setenv("PROCUREMENT_DB_HOST", "mysql")
    monkeypatch.setenv("PROCUREMENT_DB_PORT", "3307")
    monkeypatch.setenv("PROCUREMENT_DB_NAME", "procurement_demo")
    monkeypatch.setenv("PROCUREMENT_DB_USER", "procurement_app")
    monkeypatch.setenv("PROCUREMENT_DB_PASSWORD", "secret")

    settings = load_settings()

    assert settings.db_host == "mysql"
    assert settings.db_port == 3307
    assert settings.db_name == "procurement_demo"
    assert settings.db_user == "procurement_app"
    assert settings.db_password == "secret"


def test_load_settings_requires_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Require database credentials."""

    monkeypatch.delenv("PROCUREMENT_DB_USER", raising=False)
    monkeypatch.delenv("PROCUREMENT_DB_PASSWORD", raising=False)
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", tmp_path / "missing.env")

    with pytest.raises(RuntimeError, match="PROCUREMENT_DB_USER"):
        load_settings()
