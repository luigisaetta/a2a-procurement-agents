"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Runtime configuration for the Bid Collection Agent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
LOCAL_ENV_FILE = SERVICE_DIR / ".env"
REQUEST_SCHEMA_FILE = (
    REPOSITORY_ROOT / "specs" / "schemas" / "collect-bids-request.schema.json"
)
RESPONSE_SCHEMA_FILE = (
    REPOSITORY_ROOT / "specs" / "schemas" / "collect-bids-response.schema.json"
)

REQUIRED_ENV_VARS = (
    "BID_COLLECTION_AGENT_PORT",
    "AGENT_API_KEY",
    "PROCUREMENT_DATA_MCP_URL",
)


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings for the bid collection service.

    Attributes:
        agent_port: Local TCP port used by the A2A server.
        agent_api_key: Bearer token shared by A2A clients and the server.
        procurement_data_mcp_url: Streamable HTTP MCP endpoint URL.
        mcp_timeout_seconds: Timeout for MCP tool calls.
        request_schema_file: Canonical request JSON Schema file.
        response_schema_file: Canonical response JSON Schema file.
    """

    agent_port: int
    agent_api_key: str
    procurement_data_mcp_url: str
    mcp_timeout_seconds: float
    request_schema_file: Path
    response_schema_file: Path


def load_settings() -> Settings:
    """Load and validate service settings.

    Returns:
        Validated service settings.

    Raises:
        RuntimeError: If a required variable is missing or invalid.
    """

    if any(not os.environ.get(name) for name in REQUIRED_ENV_VARS):
        load_dotenv(LOCAL_ENV_FILE, override=False)

    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing required environment variables: {joined}. "
            f"Set them in the environment or in {LOCAL_ENV_FILE}."
        )

    try:
        agent_port = int(os.environ["BID_COLLECTION_AGENT_PORT"])
    except ValueError as exc:
        raise RuntimeError("BID_COLLECTION_AGENT_PORT must be an integer.") from exc

    if agent_port <= 0 or agent_port > 65535:
        raise RuntimeError("BID_COLLECTION_AGENT_PORT must be between 1 and 65535.")

    try:
        timeout = float(os.environ.get("PROCUREMENT_DATA_MCP_TIMEOUT_SECONDS", "10"))
    except ValueError as exc:
        raise RuntimeError(
            "PROCUREMENT_DATA_MCP_TIMEOUT_SECONDS must be a number."
        ) from exc

    if timeout <= 0:
        raise RuntimeError("PROCUREMENT_DATA_MCP_TIMEOUT_SECONDS must be positive.")

    return Settings(
        agent_port=agent_port,
        agent_api_key=os.environ["AGENT_API_KEY"].strip(),
        procurement_data_mcp_url=os.environ["PROCUREMENT_DATA_MCP_URL"].strip(),
        mcp_timeout_seconds=timeout,
        request_schema_file=REQUEST_SCHEMA_FILE,
        response_schema_file=RESPONSE_SCHEMA_FILE,
    )
