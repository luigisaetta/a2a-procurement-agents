"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    Runtime configuration for the conversational procurement
                intake HTTP service.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parents[2]
LOCAL_ENV_FILE = SERVICE_DIR / ".env"


@dataclass(frozen=True)
# The settings object groups runtime HTTP, A2A, and optional LLM configuration.
# pylint: disable=too-many-instance-attributes
class Settings:
    """Validated runtime settings for the intake service.

    Attributes:
        service_port: Local TCP port used by the HTTP API.
        orchestrator_url: Base URL of the Procurement Orchestrator A2A server.
        agent_api_key: Bearer token used for A2A calls.
        extractor_mode: Extractor implementation to use.
        oci_region: OCI region hosting Generative AI inference.
        oci_auth: Authentication mode requested by the service.
        oci_model_id: OCI Generative AI model identifier.
        oci_compartment_id: OCI compartment OCID used for model calls.
        oci_profile: OCI config profile used for API key authentication.
        oci_endpoint: OCI OpenAI-compatible chat completions endpoint.
    """

    service_port: int
    orchestrator_url: str
    agent_api_key: str
    extractor_mode: str
    oci_region: str
    oci_auth: str
    oci_model_id: str
    oci_compartment_id: str
    oci_profile: str
    oci_endpoint: str


def load_settings() -> Settings:
    """Load runtime settings from the environment or local ``.env`` file.

    Returns:
        Validated service settings.

    Raises:
        RuntimeError: If a configured value is invalid.
    """

    load_dotenv(LOCAL_ENV_FILE, override=False)

    try:
        service_port = int(os.environ.get("CONVERSATIONAL_INTAKE_PORT", "8012").strip())
    except ValueError as exc:
        raise RuntimeError("CONVERSATIONAL_INTAKE_PORT must be an integer.") from exc

    if service_port <= 0 or service_port > 65535:
        raise RuntimeError("CONVERSATIONAL_INTAKE_PORT must be between 1 and 65535.")

    extractor_mode = os.environ.get(
        "CONVERSATIONAL_INTAKE_EXTRACTOR_MODE", "llm"
    ).strip()
    if extractor_mode not in {"deterministic", "llm"}:
        raise RuntimeError(
            "CONVERSATIONAL_INTAKE_EXTRACTOR_MODE must be deterministic or llm."
        )

    oci_region = os.environ.get("OCI_REGION", "").strip()
    oci_auth = os.environ.get("OCI_AUTH", "").strip().upper()
    oci_model_id = os.environ.get("OCI_MODEL_ID", "").strip()
    oci_compartment_id = os.environ.get("OCI_COMPARTMENT_ID", "").strip()
    if extractor_mode == "llm":
        missing = [
            name
            for name, value in {
                "OCI_REGION": oci_region,
                "OCI_AUTH": oci_auth,
                "OCI_MODEL_ID": oci_model_id,
                "OCI_COMPARTMENT_ID": oci_compartment_id,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"Missing required LLM extraction environment variables: {joined}."
            )
        if oci_auth != "API_KEY":
            raise RuntimeError("OCI_AUTH must be API_KEY for LLM extraction.")

    oci_endpoint = (
        f"https://inference.generativeai.{oci_region}.oci.oraclecloud.com/openai/v1"
        if oci_region
        else ""
    )

    return Settings(
        service_port=service_port,
        orchestrator_url=os.environ.get(
            "PROCUREMENT_ORCHESTRATOR_URL", "http://127.0.0.1:8003"
        ).strip(),
        agent_api_key=os.environ.get("AGENT_API_KEY", "").strip(),
        extractor_mode=extractor_mode,
        oci_region=oci_region,
        oci_auth=oci_auth,
        oci_model_id=oci_model_id,
        oci_compartment_id=oci_compartment_id,
        oci_profile=os.environ.get("OCI_PROFILE", "DEFAULT").strip() or "DEFAULT",
        oci_endpoint=oci_endpoint,
    )
