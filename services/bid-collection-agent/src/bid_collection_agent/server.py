"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    A2A server entry point for the Bid Collection Agent.
"""

from __future__ import annotations

import argparse

from locus.a2a import A2AServer, AgentProvider, AgentSkill

from bid_collection_agent.config import Settings, load_settings
from bid_collection_agent.pipeline import build_workflow_agent


def build_server(settings: Settings) -> A2AServer:
    """Build the A2A server for the Bid Collection Agent.

    Args:
        settings: Validated runtime settings.

    Returns:
        Configured Locus A2A server.
    """

    agent = build_workflow_agent(settings)
    return A2AServer(
        agent=agent,
        name="bid-collection-agent",
        description=(
            "Identifies eligible suppliers through the procurement data MCP "
            "server, requests simulated supplier offers, and returns normalized "
            "bid collection results."
        ),
        url=f"http://127.0.0.1:{settings.agent_port}",
        provider=AgentProvider(
            organization="Oracle", url="https://github.com/oracle-samples/locus"
        ),
        version="0.2.0",
        skills=[
            AgentSkill(
                id="collect_bids",
                name="Collect Bids",
                description=(
                    "Identify suppliers through MCP, collect supplier offers, "
                    "and build Offer Evaluation Agent payloads."
                ),
                tags=["procurement", "bids", "suppliers", "mcp"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=["Collect supplier bids for this JSON procurement request."],
            )
        ],
        api_key=settings.agent_api_key,
    )


def main() -> None:
    """Run the Bid Collection Agent A2A server."""

    settings = load_settings()
    parser = argparse.ArgumentParser(
        description="Run the Bid Collection Agent A2A server."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument(
        "--port",
        type=int,
        default=settings.agent_port,
        help="Port to bind. Defaults to BID_COLLECTION_AGENT_PORT.",
    )
    args = parser.parse_args()
    build_server(settings).run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
