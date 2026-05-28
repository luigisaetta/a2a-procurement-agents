"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Runtime configuration for the Procurement Orchestrator Agent.
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
    REPOSITORY_ROOT
    / "specs"
    / "schemas"
    / "procurement-orchestration-request.schema.json"
)
EVENT_SCHEMA_FILE = (
    REPOSITORY_ROOT
    / "specs"
    / "schemas"
    / "procurement-orchestration-event.schema.json"
)
RESPONSE_SCHEMA_FILE = (
    REPOSITORY_ROOT
    / "specs"
    / "schemas"
    / "procurement-orchestration-response.schema.json"
)

REQUIRED_ENV_VARS = (
    "PROCUREMENT_ORCHESTRATOR_PORT",
    "AGENT_API_KEY",
    "BID_COLLECTION_AGENT_URL",
    "OFFER_EVALUATION_AGENT_URL",
    "PURCHASE_ORDER_AGENT_URL",
)


@dataclass(frozen=True)
# The orchestrator needs URLs for three downstream agents plus schema paths.
# pylint: disable=too-many-instance-attributes
class Settings:
    """Validated runtime settings for the procurement orchestrator.

    Attributes:
        agent_port: Local TCP port used by the A2A server.
        agent_api_key: Bearer token shared by A2A clients and servers.
        bid_collection_agent_url: Base URL of the Bid Collection Agent.
        offer_evaluation_agent_url: Base URL of the Offer Evaluation Agent.
        purchase_order_agent_url: Base URL of the Purchase Order Agent.
        request_schema_file: Canonical request JSON Schema file.
        event_schema_file: Canonical streaming event JSON Schema file.
        response_schema_file: Canonical final response JSON Schema file.
    """

    agent_port: int
    agent_api_key: str
    bid_collection_agent_url: str
    offer_evaluation_agent_url: str
    purchase_order_agent_url: str
    request_schema_file: Path
    event_schema_file: Path
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
        agent_port = int(os.environ["PROCUREMENT_ORCHESTRATOR_PORT"])
    except ValueError as exc:
        raise RuntimeError("PROCUREMENT_ORCHESTRATOR_PORT must be an integer.") from exc

    if agent_port <= 0 or agent_port > 65535:
        raise RuntimeError("PROCUREMENT_ORCHESTRATOR_PORT must be between 1 and 65535.")

    return Settings(
        agent_port=agent_port,
        agent_api_key=os.environ["AGENT_API_KEY"].strip(),
        bid_collection_agent_url=os.environ["BID_COLLECTION_AGENT_URL"].strip(),
        offer_evaluation_agent_url=os.environ["OFFER_EVALUATION_AGENT_URL"].strip(),
        purchase_order_agent_url=os.environ["PURCHASE_ORDER_AGENT_URL"].strip(),
        request_schema_file=REQUEST_SCHEMA_FILE,
        event_schema_file=EVENT_SCHEMA_FILE,
        response_schema_file=RESPONSE_SCHEMA_FILE,
    )
