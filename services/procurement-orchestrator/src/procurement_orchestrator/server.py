"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    A2A server entry point for the Procurement Orchestrator Agent.
"""

from __future__ import annotations

import argparse

from locus.a2a import A2AServer, AgentProvider, AgentSkill

from procurement_orchestrator.config import Settings, load_settings
from procurement_orchestrator.logging_utils import configure_logging
from procurement_orchestrator.pipeline import build_workflow_agent


def build_server(settings: Settings) -> A2AServer:
    """Build the A2A server for the Procurement Orchestrator Agent.

    Args:
        settings: Validated runtime settings.

    Returns:
        Configured Locus A2A server.
    """

    agent = build_workflow_agent(settings)
    return A2AServer(
        agent=agent,
        name="procurement-orchestrator",
        description=(
            "Coordinates bid collection, offer evaluation, and purchase order "
            "registration across specialized A2A agents."
        ),
        url=f"http://127.0.0.1:{settings.agent_port}",
        provider=AgentProvider(
            organization="Oracle", url="https://github.com/oracle-samples/locus"
        ),
        version="0.1.0",
        skills=[
            AgentSkill(
                id="run_procurement_workflow",
                name="Run Procurement Workflow",
                description=(
                    "Run the structured procurement workflow and stream progress "
                    "events until a terminal orchestration result is available."
                ),
                tags=["procurement", "orchestration", "workflow", "streaming"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=["Run this structured procurement orchestration request."],
            )
        ],
        api_key=settings.agent_api_key,
    )


def main() -> None:
    """Run the Procurement Orchestrator Agent A2A server."""

    configure_logging()
    settings = load_settings()
    parser = argparse.ArgumentParser(
        description="Run the Procurement Orchestrator Agent A2A server."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument(
        "--port",
        type=int,
        default=settings.agent_port,
        help="Port to bind. Defaults to PROCUREMENT_ORCHESTRATOR_PORT.",
    )
    args = parser.parse_args()
    build_server(settings).run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
