"""
Runtime configuration for the Offer Evaluation Agent.

Author: L. Saetta
Date Last Modified: 2026-05-27
License: MIT
Description:    Loads required environment variables from the process
                environment first, then from the local .env file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
LOCAL_ENV_FILE = SERVICE_DIR / ".env"
DEFAULT_POLICY_FILE = SERVICE_DIR / "policies" / "standard-urgent-procurement-v1.md"
REQUEST_SCHEMA_FILE = (
    REPOSITORY_ROOT / "specs" / "schemas" / "evaluate-offers-request.schema.json"
)
RESPONSE_SCHEMA_FILE = (
    REPOSITORY_ROOT / "specs" / "schemas" / "evaluate-offers-response.schema.json"
)

REQUIRED_ENV_VARS = (
    "OCI_REGION",
    "OCI_AUTH",
    "OCI_MODEL_ID",
    "OCI_COMPARTMENT_ID",
    "OFFER_EVALUATION_AGENT_PORT",
    "AGENT_API_KEY",
)


@dataclass(frozen=True)
# pylint: disable=too-many-instance-attributes
class Settings:
    """Validated runtime settings for the offer evaluation service.

    Attributes:
        oci_region: OCI region hosting Generative AI inference.
        oci_auth: Authentication mode requested by the service.
        oci_model_id: OCI Generative AI model identifier.
        oci_compartment_id: OCI compartment OCID used for model calls.
        agent_port: Local TCP port used by the A2A server.
        agent_api_key: Bearer token shared by A2A clients and the server.
        oci_profile: OCI config profile used for API key authentication.
        oci_endpoint: OCI OpenAI-compatible chat completions endpoint.
        policy_file: Local Markdown policy file.
        request_schema_file: Canonical request JSON Schema file.
        response_schema_file: Canonical response JSON Schema file.
    """

    oci_region: str
    oci_auth: str
    oci_model_id: str
    oci_compartment_id: str
    agent_port: int
    agent_api_key: str
    oci_profile: str
    oci_endpoint: str
    policy_file: Path
    request_schema_file: Path
    response_schema_file: Path


def load_settings() -> Settings:
    """Load and validate service settings.

    Existing process environment values take precedence. If any required
    variable is missing, the function loads ``services/offer-evaluation-agent/.env``
    without overriding existing values, then validates the final environment.

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
        agent_port = int(os.environ["OFFER_EVALUATION_AGENT_PORT"])
    except ValueError as exc:
        raise RuntimeError("OFFER_EVALUATION_AGENT_PORT must be an integer.") from exc

    if agent_port <= 0 or agent_port > 65535:
        raise RuntimeError("OFFER_EVALUATION_AGENT_PORT must be between 1 and 65535.")

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
        policy_file=DEFAULT_POLICY_FILE,
        request_schema_file=REQUEST_SCHEMA_FILE,
        response_schema_file=RESPONSE_SCHEMA_FILE,
    )
