"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    A2A downstream client wrappers for the Procurement Orchestrator.
                Every downstream call failure is reported as a
                DownstreamAgentError with a stable error code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from locus.a2a import A2AClient, DataPart, Message, Task
from pydantic import BaseModel


@dataclass(frozen=True)
class DownstreamAgent:
    """Identity of a downstream agent, used in error codes and messages.

    Attributes:
        name: Human-readable agent name used in user-facing messages.
        error_code_prefix: Prefix of the error codes reported for this agent.
    """

    name: str
    error_code_prefix: str


BID_COLLECTION_AGENT = DownstreamAgent("Bid Collection Agent", "BID_COLLECTION")
OFFER_EVALUATION_AGENT = DownstreamAgent("Offer Evaluation Agent", "OFFER_EVALUATION")
PURCHASE_ORDER_AGENT = DownstreamAgent("Purchase Order Agent", "PURCHASE_ORDER")


class DownstreamAgentError(Exception):
    """A downstream agent call did not return a usable response.

    The message is safe to show to end users: it names the agent and the
    kind of failure, but never internal URLs or exception details. The
    technical cause is kept as ``__cause__`` so it can be logged.

    Attributes:
        code: Machine-readable error code, for example ``BID_COLLECTION_TIMEOUT``.
        message: User-safe description of the failure.
    """

    def __init__(self, code: str, message: str) -> None:
        """Initialize the error.

        Args:
            code: Machine-readable error code.
            message: User-safe description of the failure.
        """

        super().__init__(message)
        self.code = code
        self.message = message

    @classmethod
    def timeout(
        cls, agent: DownstreamAgent, timeout_seconds: float
    ) -> DownstreamAgentError:
        """Build the error for a call that did not answer in time."""

        return cls(
            f"{agent.error_code_prefix}_TIMEOUT",
            f"The {agent.name} did not answer within {timeout_seconds:g} seconds.",
        )

    @classmethod
    def failed(cls, agent: DownstreamAgent) -> DownstreamAgentError:
        """Build the error for a call that failed or returned an A2A error."""

        return cls(
            f"{agent.error_code_prefix}_FAILED",
            f"The {agent.name} call failed.",
        )

    @classmethod
    def invalid_response(cls, agent: DownstreamAgent) -> DownstreamAgentError:
        """Build the error for a response that does not match the contract."""

        return cls(
            f"{agent.error_code_prefix}_INVALID_RESPONSE",
            f"The {agent.name} returned a response that does not match its contract.",
        )


class ProcurementAgentClient(Protocol):
    """Client contract used by the orchestration pipeline.

    Every method returns the downstream JSON response as a dictionary and
    raises ``DownstreamAgentError`` when the call fails.
    """

    async def collect_bids(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Bid Collection Agent."""

    async def evaluate_offers(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Offer Evaluation Agent."""

    async def create_purchase_order(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Purchase Order Agent."""


class A2AProcurementAgentClient:
    """A2A client wrapper for downstream procurement agents."""

    def __init__(
        self,
        bid_collection_url: str,
        offer_evaluation_url: str,
        purchase_order_url: str,
        api_key: str,
    ) -> None:
        """Initialize the downstream A2A clients.

        Args:
            bid_collection_url: Base URL of the Bid Collection Agent.
            offer_evaluation_url: Base URL of the Offer Evaluation Agent.
            purchase_order_url: Base URL of the Purchase Order Agent.
            api_key: Bearer token for downstream A2A calls.
        """

        self._bid_collection = A2AClient(url=bid_collection_url, api_key=api_key)
        self._offer_evaluation = A2AClient(url=offer_evaluation_url, api_key=api_key)
        self._purchase_order = A2AClient(url=purchase_order_url, api_key=api_key)

    async def collect_bids(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Bid Collection Agent."""

        return await _call_agent(
            self._bid_collection,
            BID_COLLECTION_AGENT,
            payload,
            "orchestrator-collect-bids",
            timeout,
        )

    async def evaluate_offers(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Offer Evaluation Agent."""

        return await _call_agent(
            self._offer_evaluation,
            OFFER_EVALUATION_AGENT,
            payload,
            "orchestrator-evaluate-offers",
            timeout,
        )

    async def create_purchase_order(
        self, payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Call the Purchase Order Agent."""

        return await _call_agent(
            self._purchase_order,
            PURCHASE_ORDER_AGENT,
            payload,
            "orchestrator-create-purchase-order",
            timeout,
        )


# The arguments describe one call explicitly; grouping them would hide that.
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
async def _call_agent(
    client: A2AClient,
    agent: DownstreamAgent,
    payload: dict[str, Any],
    message_id: str,
    timeout: float,
) -> dict[str, Any]:
    """Call one downstream A2A agent and parse its JSON artifact.

    Args:
        client: A2A client bound to the downstream agent.
        agent: Identity of the downstream agent, used in errors.
        payload: JSON request sent as an A2A data part.
        message_id: A2A message identifier.
        timeout: HTTP timeout in seconds.

    Returns:
        The JSON object returned by the downstream agent.

    Raises:
        DownstreamAgentError: If the call times out, fails, or returns a
            response that is not a JSON object.
    """

    message = Message(role="user", parts=[DataPart(data=payload)], messageId=message_id)
    try:
        task = await client.send_message(message, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise DownstreamAgentError.timeout(agent, timeout) from exc
    except (httpx.HTTPError, RuntimeError) as exc:
        # Locus raises RuntimeError when the agent answers with a JSON-RPC error.
        raise DownstreamAgentError.failed(agent) from exc
    except ValueError as exc:
        # The HTTP body is not JSON, or it is not a valid A2A task.
        raise DownstreamAgentError.invalid_response(agent) from exc

    return _read_json_artifact(task, agent)


def _read_json_artifact(task: Task, agent: DownstreamAgent) -> dict[str, Any]:
    """Return the JSON object stored in the last artifact of an A2A task.

    Raises:
        DownstreamAgentError: If the artifact is missing or is not a JSON object.
    """

    if not task.artifacts or not task.artifacts[-1].parts:
        raise DownstreamAgentError.invalid_response(agent)

    text = getattr(task.artifacts[-1].parts[0], "text", "")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DownstreamAgentError.invalid_response(agent) from exc

    if not isinstance(parsed, dict):
        raise DownstreamAgentError.invalid_response(agent)
    return parsed


def model_to_payload(model: BaseModel) -> dict[str, Any]:
    """Convert a Pydantic model into a JSON-compatible dictionary."""

    return model.model_dump(mode="json")
