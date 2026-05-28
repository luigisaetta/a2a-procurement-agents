"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Manual A2A end-to-end test client for the Procurement
                Orchestrator Agent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from locus.a2a import A2AClient, Message, TextPart

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = REPOSITORY_ROOT / "deployments" / "docker-compose" / ".env"
SEPARATOR_WIDTH = 72

SAMPLE_PAYLOAD: dict[str, Any] = {
    "request_id": "REQ-DEMO-E2E-0001",
    "requested_by": "demo.operator@example.com",
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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments.
    """

    parser = argparse.ArgumentParser(
        description="Invoke the Procurement Orchestrator Agent."
    )
    parser.add_argument(
        "--url",
        default=None,
        help="A2A server base URL. Defaults to localhost and the configured port.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Environment file containing AGENT_API_KEY and orchestrator port.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Use a non-streaming A2A request and print only the final artifact.",
    )
    return parser.parse_args()


async def invoke_streaming(
    base_url: str, api_key: str, payload: dict[str, Any]
) -> None:
    """Invoke the orchestrator with A2A streaming enabled.

    Args:
        base_url: Base URL of the A2A server.
        api_key: Bearer token shared with the server.
        payload: Orchestration request payload.
    """

    client = A2AClient(url=base_url, api_key=api_key)
    message = _message(payload)
    async for event in client.send_message_streaming(message, timeout=1200):
        _print_separator(_message_type(event))
        print(json.dumps(event, indent=2, sort_keys=True))


async def invoke_non_streaming(
    base_url: str, api_key: str, payload: dict[str, Any]
) -> None:
    """Invoke the orchestrator and print the final task artifact.

    Args:
        base_url: Base URL of the A2A server.
        api_key: Bearer token shared with the server.
        payload: Orchestration request payload.

    Raises:
        RuntimeError: If the task completes without a text artifact.
    """

    client = A2AClient(url=base_url, api_key=api_key)
    task = await client.send_message(_message(payload), timeout=1200)
    if not task.artifacts:
        raise RuntimeError(
            f"A2A task completed without artifacts. State: {task.status.state}"
        )

    text = getattr(task.artifacts[-1].parts[0], "text", "")
    if not text:
        raise RuntimeError("A2A task artifact does not contain text output.")
    _print_separator("final_response")
    print(json.dumps(json.loads(text), indent=2, sort_keys=True))


def _message(payload: dict[str, Any]) -> Message:
    """Build the A2A message sent to the orchestrator."""

    return Message(
        role="user",
        parts=[TextPart(text=json.dumps(payload, indent=2))],
        messageId="sample-procurement-orchestration-request",
    )


def _print_separator(title: str) -> None:
    """Print a readable centered message separator."""

    line = "-" * SEPARATOR_WIDTH
    print()
    print(line)
    print(title.center(SEPARATOR_WIDTH))
    print(line)


def _message_type(event: dict[str, Any]) -> str:
    """Return a human-readable type for one streamed A2A event."""

    orchestration_event = _extract_orchestration_json(event)
    if orchestration_event:
        return str(orchestration_event.get("event_type", "orchestration_event"))

    if "error" in event:
        return "a2a_error"

    for key in ("kind", "type", "event", "event_type"):
        value = event.get(key)
        if value:
            return str(value)

    return "a2a_message"


def _extract_orchestration_json(event: dict[str, Any]) -> dict[str, Any]:
    """Extract the JSON orchestration event embedded in an A2A update."""

    for text in _iter_text_values(event):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "event_type" in parsed:
            return parsed
    return {}


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


async def main_async() -> None:
    """Run the manual end-to-end client."""

    args = parse_args()
    load_dotenv(args.env_file, override=False)

    port = os.environ.get("PROCUREMENT_ORCHESTRATOR_PORT", "8003")
    base_url = args.url or f"http://127.0.0.1:{port}"
    api_key = os.environ.get("AGENT_API_KEY")
    if not api_key:
        raise RuntimeError(
            "AGENT_API_KEY must be set in the environment or compose .env file."
        )

    print(f"Invoking Procurement Orchestrator at {base_url}")
    if args.no_stream:
        await invoke_non_streaming(base_url, api_key, SAMPLE_PAYLOAD)
    else:
        await invoke_streaming(base_url, api_key, SAMPLE_PAYLOAD)


def main() -> None:
    """Run the async client from a synchronous entry point."""

    asyncio.run(main_async())


if __name__ == "__main__":
    main()
