"""
Manual A2A test client for the Purchase Order Agent.

Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Sends a synthetic English purchase order registration request
                to the local Purchase Order Agent A2A server.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from locus.a2a import A2AClient, DataPart, Message

SERVICE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = SERVICE_DIR / ".env"
DEFAULT_INPUT_FILE = Path(__file__).with_name(
    "sample-create-purchase-order-request.json"
)


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON payload file.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.
    """

    return json.loads(path.read_text(encoding="utf-8"))


async def invoke_agent(base_url: str, api_key: str, payload: dict[str, Any]) -> str:
    """Invoke the local A2A agent with the sample payload.

    Args:
        base_url: Base URL of the A2A server.
        api_key: Bearer token shared with the server.
        payload: Purchase order registration request payload.

    Returns:
        Text artifact returned by the agent.
    """

    client = A2AClient(url=base_url, api_key=api_key)
    task = await client.send_message(
        Message(
            role="user",
            parts=[DataPart(data=payload)],
            messageId="sample-create-purchase-order-request",
        )
    )

    if not task.artifacts:
        raise RuntimeError(
            f"A2A task completed without artifacts. State: {task.status.state}"
        )

    text = getattr(task.artifacts[-1].parts[0], "text", "")
    if not text:
        raise RuntimeError("A2A task artifact does not contain text output.")
    return text


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments.
    """

    parser = argparse.ArgumentParser(description="Invoke the Purchase Order Agent.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help="JSON input payload file.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="A2A server base URL. Defaults to localhost and the configured port.",
    )
    return parser.parse_args()


async def main_async() -> None:
    """Run the test client."""

    load_dotenv(DEFAULT_ENV_FILE, override=False)
    args = parse_args()

    port = os.environ.get("PURCHASE_ORDER_AGENT_PORT", "8002")
    base_url = args.url or f"http://127.0.0.1:{port}"
    api_key = os.environ.get("AGENT_API_KEY")
    if not api_key:
        raise RuntimeError(
            "AGENT_API_KEY must be set in the environment or local .env file."
        )

    payload = load_json(args.input)
    response_text = await invoke_agent(base_url, api_key, payload)
    print(response_text)


def main() -> None:
    """Run the async client from a synchronous entry point."""

    asyncio.run(main_async())


if __name__ == "__main__":
    main()
