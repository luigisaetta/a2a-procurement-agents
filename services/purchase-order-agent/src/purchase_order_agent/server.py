"""
A2A server entry point for the Purchase Order Agent.

Author: L. Saetta
Date Last Modified: 2026-05-31
License: MIT
Description:    Builds the deterministic purchase order workflow and exposes
                it through a Locus A2AServer.
"""

from __future__ import annotations

import argparse
import os

from locus.a2a import A2AServer, AgentProvider, AgentSkill
from locus.hooks.builtin.telemetry import create_telemetry_hook

from purchase_order_agent.config import Settings, load_settings
from purchase_order_agent.pipeline import build_workflow_agent

TELEMETRY_ENABLED_ENV = "PURCHASE_ORDER_AGENT_TELEMETRY_ENABLED"

# Telemetry enablement intentionally mirrors other independent agents without
# introducing shared runtime code between services.
# pylint: disable=duplicate-code


def build_server(settings: Settings) -> A2AServer:
    """Build the A2A server for the Purchase Order Agent.

    Args:
        settings: Validated runtime settings.

    Returns:
        Configured Locus A2A server.
    """

    telemetry_hook = create_telemetry_hook(
        enabled=_telemetry_enabled(),
        service_name="purchase-order-agent",
    )
    agent = build_workflow_agent(settings, hooks=[telemetry_hook])
    return A2AServer(
        agent=agent,
        name="purchase-order-agent",
        description=(
            "Registers purchase orders in the company purchase order system "
            "through an isolated integration wrapper."
        ),
        url=f"http://127.0.0.1:{settings.agent_port}",
        provider=AgentProvider(
            organization="Oracle", url="https://github.com/oracle-samples/locus"
        ),
        version="0.1.0",
        skills=[
            AgentSkill(
                id="create_purchase_order",
                name="Create Purchase Order",
                description=(
                    "Register a purchase order and return a structured technical "
                    "confirmation for the orchestrator."
                ),
                tags=["procurement", "purchase-order", "erp", "registration"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[
                    "Register this JSON purchase order request in the PO system."
                ],
            )
        ],
        api_key=settings.agent_api_key,
    )


def _telemetry_enabled() -> bool:
    """Return whether Locus telemetry hooks should be enabled."""

    value = os.environ.get(TELEMETRY_ENABLED_ENV, "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def main() -> None:
    """Run the Purchase Order Agent A2A server."""

    settings = load_settings()
    parser = argparse.ArgumentParser(
        description="Run the Purchase Order Agent A2A server."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument(
        "--port",
        type=int,
        default=settings.agent_port,
        help="Port to bind. Defaults to PURCHASE_ORDER_AGENT_PORT.",
    )
    args = parser.parse_args()
    build_server(settings).run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
