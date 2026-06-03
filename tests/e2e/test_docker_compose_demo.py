"""
Author: L. Saetta
Date Last Modified: 2026-06-03
License: MIT
Description:    Opt-in Docker Compose end-to-end test for the A2A
                procurement demo workflow.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest
from locus.a2a import A2AClient, Message, TextPart

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPOSITORY_ROOT / "deployments" / "docker-compose" / ".env"
AGENT_CARD_PATH = "/.well-known/agent-card.json"
REQUIRED_EVENTS = {
    "accepted",
    "workflow_started",
    "bid_collection_completed",
    "offer_evaluation_completed",
    "purchase_order_completed",
    "workflow_completed",
}


@pytest.mark.e2e
def test_docker_compose_procurement_workflow() -> None:
    """Run the Docker Compose A2A workflow and verify the terminal result."""

    _load_env_file(ENV_FILE)
    api_key = _required_env("AGENT_API_KEY")
    base_url = _orchestrator_base_url()
    _wait_for_agent_card(base_url, api_key)

    payload = _sample_payload()
    events, final_response = asyncio.run(
        _invoke_orchestrator_stream(base_url, api_key, payload)
    )

    event_types = {event["event_type"] for event in events}
    assert REQUIRED_EVENTS.issubset(event_types)
    assert final_response["request_id"] == payload["request_id"]
    assert final_response["status"] == "completed_with_purchase_orders"
    assert len(final_response["part_results"]) == len(payload["parts"])

    for part_result in final_response["part_results"]:
        assert part_result["status"] == "purchase_order_created"
        assert part_result["bid_collection"]["offers_count"] >= 1
        assert part_result["evaluation"]["status"] == "selected_offer"
        assert part_result["evaluation"]["selected_offer"]["offer_id"]
        assert part_result["purchase_order"]["status"] == "registered"
        assert part_result["purchase_order"]["purchase_order_id"]


async def _invoke_orchestrator_stream(
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Submit the workflow request and collect streamed JSON payloads."""

    client = A2AClient(url=base_url, api_key=api_key)
    message = Message(
        role="user",
        parts=[TextPart(text=json.dumps(payload))],
        messageId=f"e2e-{payload['request_id']}",
    )
    events: list[dict[str, Any]] = []
    final_response: dict[str, Any] | None = None

    async for stream_event in client.send_message_streaming(message, timeout=1200):
        for parsed in _iter_json_text_payloads(stream_event):
            if "event_type" in parsed:
                events.append(parsed)
            elif "part_results" in parsed and "completed_at" in parsed:
                final_response = parsed

    if final_response is None:
        raise AssertionError("The A2A stream did not return a final response artifact.")
    return events, final_response


def _wait_for_agent_card(base_url: str, api_key: str) -> None:
    """Wait until the orchestrator Agent Card is reachable."""

    deadline = time.monotonic() + int(
        os.environ.get("E2E_READY_TIMEOUT_SECONDS", "180")
    )
    url = f"{base_url}{AGENT_CARD_PATH}"
    last_error: str | None = None

    while time.monotonic() < deadline:
        try:
            request = Request(url, headers={"Authorization": f"Bearer {api_key}"})
            with urlopen(request, timeout=5) as response:  # nosec B310
                if response.status == 200:
                    return
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(3)

    raise AssertionError(f"Orchestrator Agent Card was not reachable: {last_error}")


def _sample_payload() -> dict[str, Any]:
    """Build a unique deterministic payload for the Docker Compose demo."""

    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return {
        "request_id": f"REQ-E2E-{suffix}",
        "requested_by": "e2e.operator@example.com",
        "currency": "EUR",
        "evaluation_policy_id": "standard-urgent-procurement-v1",
        "response_deadline": "2026-06-15T17:00:00Z",
        "auto_create_purchase_order": True,
        "max_rebid_attempts": 2,
        "timeouts": {
            "bid_collection_seconds": 300,
            "offer_evaluation_seconds": 180,
            "purchase_order_seconds": 120,
            "total_seconds": 900,
        },
        "sourcing_constraints": {
            "max_suppliers_per_part": 3,
            "allowed_regions": ["EU", "UK"],
            "preferred_supplier_ids": ["SUP-001", "SUP-002", "SUP-007"],
        },
        "parts": [
            {
                "part_id": "PART-001",
                "plant_code": "DE-MUN",
                "material_code": "EV-BAT-MOD-001",
                "material_description": "High Density Battery Module",
                "quantity": 12,
                "unit_of_measure": "EA",
                "required_delivery_date": "2026-07-15",
                "supplier_search_hints": {
                    "commodity_category": "battery",
                    "required_certifications": ["ISO-9001"],
                },
            },
            {
                "part_id": "PART-008",
                "plant_code": "IT-TOR",
                "material_code": "EV-INV-800-008",
                "material_description": "800V Traction Inverter",
                "quantity": 6,
                "unit_of_measure": "EA",
                "required_delivery_date": "2026-07-20",
                "supplier_search_hints": {
                    "commodity_category": "power electronics",
                    "required_certifications": ["ISO-9001"],
                },
            },
        ],
    }


def _iter_json_text_payloads(value: Any) -> list[dict[str, Any]]:
    """Return JSON objects found in text fields inside an A2A stream event."""

    payloads: list[dict[str, Any]] = []
    for text in _iter_text_values(value):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            payloads.append(parsed)
    return payloads


def _iter_text_values(value: Any) -> list[str]:
    """Return all string values stored under keys named ``text``."""

    if isinstance(value, dict):
        items: list[str] = []
        for key, nested in value.items():
            if key == "text" and isinstance(nested, str):
                items.append(nested)
            else:
                items.extend(_iter_text_values(nested))
        return items
    if isinstance(value, list):
        items = []
        for nested in value:
            items.extend(_iter_text_values(nested))
        return items
    return []


def _orchestrator_base_url() -> str:
    """Return the localhost URL for the Docker Compose orchestrator."""

    port = os.environ.get("PROCUREMENT_ORCHESTRATOR_PORT", "8003")
    return os.environ.get("E2E_ORCHESTRATOR_URL", f"http://127.0.0.1:{port}")


def _required_env(name: str) -> str:
    """Return one required environment variable."""

    value = os.environ.get(name, "").strip()
    if not value:
        raise AssertionError(f"{name} must be set in the environment or in {ENV_FILE}.")
    return value


def _load_env_file(env_file: Path) -> None:
    """Load simple KEY=VALUE entries from the Docker Compose environment file."""

    if not env_file.exists():
        raise AssertionError(
            f"Missing {env_file}. Create it from deployments/docker-compose/.env.example."
        )

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))
