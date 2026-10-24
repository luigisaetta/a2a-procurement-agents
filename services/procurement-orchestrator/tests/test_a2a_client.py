"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Tests for downstream A2A call error classification.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from locus.a2a import Artifact, Task, TaskState, TaskStatus, TextPart

from procurement_orchestrator.a2a_client import (
    BID_COLLECTION_AGENT,
    DownstreamAgentError,
    _call_agent,
)


class FakeA2AClient:  # pylint: disable=too-few-public-methods
    """Fake Locus A2A client that returns a task or raises an error."""

    def __init__(self, outcome: Task | Exception) -> None:
        """Initialize the fake with the task to return or the error to raise."""

        self.outcome = outcome

    async def send_message(self, _message: Any, *, timeout: float) -> Task:
        """Return or raise the configured outcome."""

        del timeout
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


async def _call(outcome: Task | Exception) -> dict[str, Any]:
    """Call the Bid Collection Agent through a fake A2A client."""

    return await _call_agent(
        FakeA2AClient(outcome),
        BID_COLLECTION_AGENT,
        {"request_id": "REQ-2026-0001"},
        "test-message",
        30,
    )


def _task(artifact_texts: list[str]) -> Task:
    """Build a completed A2A task with one text artifact per entry."""

    return Task(
        id="task-1",
        contextId="context-1",
        status=TaskStatus(state=TaskState.completed),
        artifacts=[
            Artifact(artifactId=f"artifact-{index}", parts=[TextPart(text=text)])
            for index, text in enumerate(artifact_texts)
        ],
    )


@pytest.mark.anyio
async def test_call_agent_returns_the_json_artifact() -> None:
    """A completed task with a JSON object artifact is returned as a dict."""

    response = await _call(_task([json.dumps({"status": "completed"})]))

    assert response == {"status": "completed"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("outcome", "expected_code"),
    [
        (httpx.ReadTimeout("read timed out"), "BID_COLLECTION_TIMEOUT"),
        (httpx.ConnectError("connection refused"), "BID_COLLECTION_FAILED"),
        (RuntimeError("A2A error -32603: internal error"), "BID_COLLECTION_FAILED"),
        (ValueError("not a valid task"), "BID_COLLECTION_INVALID_RESPONSE"),
        (_task([]), "BID_COLLECTION_INVALID_RESPONSE"),
        (_task(["not json"]), "BID_COLLECTION_INVALID_RESPONSE"),
        (_task(["[1, 2]"]), "BID_COLLECTION_INVALID_RESPONSE"),
    ],
)
async def test_call_agent_classifies_failures(
    outcome: Task | Exception, expected_code: str
) -> None:
    """Every failure is raised as DownstreamAgentError with a stable code."""

    with pytest.raises(DownstreamAgentError) as error_info:
        await _call(outcome)

    assert error_info.value.code == expected_code
    assert "connection refused" not in error_info.value.message
    assert "Bid Collection Agent" in error_info.value.message
