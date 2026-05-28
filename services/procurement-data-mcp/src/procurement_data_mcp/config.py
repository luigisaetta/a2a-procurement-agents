"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Runtime configuration for the Procurement Data MCP Server.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parents[2]
LOCAL_ENV_FILE = SERVICE_DIR / ".env"


@dataclass(frozen=True)
class Settings:
    """Validated database settings for the MCP server.

    Attributes:
        db_host: MySQL host.
        db_port: MySQL port.
        db_name: MySQL schema name.
        db_user: MySQL user.
        db_password: MySQL password.
    """

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str


def load_settings() -> Settings:
    """Load MCP server settings from environment variables.

    Returns:
        Validated settings.

    Raises:
        RuntimeError: If required settings are missing or invalid.
    """

    load_dotenv(LOCAL_ENV_FILE, override=False)

    db_user = os.environ.get("PROCUREMENT_DB_USER", "").strip()
    db_password = os.environ.get("PROCUREMENT_DB_PASSWORD", "").strip()
    if not db_user or not db_password:
        raise RuntimeError(
            "PROCUREMENT_DB_USER and PROCUREMENT_DB_PASSWORD must be set."
        )

    try:
        db_port = int(os.environ.get("PROCUREMENT_DB_PORT", "3306"))
    except ValueError as exc:
        raise RuntimeError("PROCUREMENT_DB_PORT must be an integer.") from exc

    return Settings(
        db_host=os.environ.get("PROCUREMENT_DB_HOST", "127.0.0.1").strip()
        or "127.0.0.1",
        db_port=db_port,
        db_name=os.environ.get("PROCUREMENT_DB_NAME", "procurement_demo").strip()
        or "procurement_demo",
        db_user=db_user,
        db_password=db_password,
    )
