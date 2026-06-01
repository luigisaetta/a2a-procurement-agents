"""
Runtime configuration for the Purchase Order Agent.

Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    Loads required environment variables from the process
                environment first, then from the local .env file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# The service config intentionally mirrors the other independent A2A agents.
# pylint: disable=duplicate-code

SERVICE_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
LOCAL_ENV_FILE = SERVICE_DIR / ".env"
REQUEST_SCHEMA_FILE = (
    REPOSITORY_ROOT / "specs" / "schemas" / "create-purchase-order-request.schema.json"
)
RESPONSE_SCHEMA_FILE = (
    REPOSITORY_ROOT / "specs" / "schemas" / "create-purchase-order-response.schema.json"
)

REQUIRED_ENV_VARS = (
    "OCI_REGION",
    "OCI_AUTH",
    "OCI_MODEL_ID",
    "OCI_COMPARTMENT_ID",
    "PURCHASE_ORDER_AGENT_PORT",
    "AGENT_API_KEY",
)


@dataclass(frozen=True)
# pylint: disable=too-many-instance-attributes
class Settings:
    """Validated runtime settings for the purchase order service.

    Attributes:
        oci_region: OCI region retained for runtime consistency.
        oci_auth: Authentication mode requested by the service.
        oci_model_id: OCI Generative AI model identifier retained for consistency.
        oci_compartment_id: OCI compartment OCID retained for consistency.
        agent_port: Local TCP port used by the A2A server.
        agent_api_key: Bearer token shared by A2A clients and the server.
        oci_profile: OCI config profile used for API key authentication.
        oci_endpoint: OCI OpenAI-compatible endpoint derived from the region.
        request_schema_file: Canonical request JSON Schema file.
        response_schema_file: Canonical response JSON Schema file.
        purchase_order_storage_backend: Backend used by the PO system wrapper.
        db_host: Optional MySQL host for persisted purchase orders.
        db_port: Optional MySQL port for persisted purchase orders.
        db_name: Optional MySQL schema for persisted purchase orders.
        db_user: Optional MySQL user for persisted purchase orders.
        db_password: Optional MySQL password for persisted purchase orders.
    """

    oci_region: str
    oci_auth: str
    oci_model_id: str
    oci_compartment_id: str
    agent_port: int
    agent_api_key: str
    oci_profile: str
    oci_endpoint: str
    request_schema_file: Path
    response_schema_file: Path
    purchase_order_storage_backend: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str


def load_settings() -> Settings:
    """Load and validate service settings.

    Existing process environment values take precedence. If any required
    variable is missing, the function loads
    ``services/purchase-order-agent/.env`` without overriding existing values,
    then validates the final environment.

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

    oci_auth = os.environ["OCI_AUTH"].strip().upper()
    if oci_auth != "API_KEY":
        raise RuntimeError("OCI_AUTH must be API_KEY for the initial implementation.")

    try:
        agent_port = int(os.environ["PURCHASE_ORDER_AGENT_PORT"])
    except ValueError as exc:
        raise RuntimeError("PURCHASE_ORDER_AGENT_PORT must be an integer.") from exc

    if agent_port <= 0 or agent_port > 65535:
        raise RuntimeError("PURCHASE_ORDER_AGENT_PORT must be between 1 and 65535.")

    storage_backend = os.environ.get("PURCHASE_ORDER_STORAGE_BACKEND", "fake").strip()
    storage_backend = storage_backend.lower() or "fake"
    if storage_backend not in {"fake", "mysql"}:
        raise RuntimeError("PURCHASE_ORDER_STORAGE_BACKEND must be fake or mysql.")

    try:
        db_port = int(os.environ.get("PROCUREMENT_DB_PORT", "3306"))
    except ValueError as exc:
        raise RuntimeError("PROCUREMENT_DB_PORT must be an integer.") from exc

    db_user = os.environ.get("PROCUREMENT_DB_USER", "").strip()
    db_password = os.environ.get("PROCUREMENT_DB_PASSWORD", "").strip()
    if storage_backend == "mysql" and (not db_user or not db_password):
        raise RuntimeError(
            "PROCUREMENT_DB_USER and PROCUREMENT_DB_PASSWORD must be set "
            "when PURCHASE_ORDER_STORAGE_BACKEND=mysql."
        )

    region = os.environ["OCI_REGION"].strip()
    endpoint = f"https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1"

    return Settings(
        oci_region=region,
        oci_auth=oci_auth,
        oci_model_id=os.environ["OCI_MODEL_ID"].strip(),
        oci_compartment_id=os.environ["OCI_COMPARTMENT_ID"].strip(),
        agent_port=agent_port,
        agent_api_key=os.environ["AGENT_API_KEY"].strip(),
        oci_profile=os.environ.get("OCI_PROFILE", "DEFAULT").strip() or "DEFAULT",
        oci_endpoint=endpoint,
        request_schema_file=REQUEST_SCHEMA_FILE,
        response_schema_file=RESPONSE_SCHEMA_FILE,
        purchase_order_storage_backend=storage_backend,
        db_host=os.environ.get("PROCUREMENT_DB_HOST", "127.0.0.1").strip()
        or "127.0.0.1",
        db_port=db_port,
        db_name=os.environ.get("PROCUREMENT_DB_NAME", "procurement_demo").strip()
        or "procurement_demo",
        db_user=db_user,
        db_password=db_password,
    )
