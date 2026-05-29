"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    FastAPI entry point for the conversational procurement intake
                HTTP service.
"""

from __future__ import annotations

import argparse

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from conversational_procurement_intake.config import Settings, load_settings
from conversational_procurement_intake.extraction import DeterministicIntakeExtractor
from conversational_procurement_intake.llm_extraction import (
    LLMIntakeExtractor,
    LocusIntakeLLMClient,
)
from conversational_procurement_intake.master_data import StaticMasterDataResolver
from conversational_procurement_intake.model_factory import build_model
from conversational_procurement_intake.models import (
    ConfirmSessionRequest,
    IntakeSessionResponse,
    OrchestrationEventsResponse,
    StartSessionRequest,
    UserMessageRequest,
)
from conversational_procurement_intake.orchestrator_client import A2AOrchestratorClient
from conversational_procurement_intake.service import IntakeApplicationService
from conversational_procurement_intake.session_store import (
    SessionEventBroker,
    SessionStore,
)


def build_app(service: IntakeApplicationService | None = None) -> FastAPI:
    """Build the FastAPI application.

    Args:
        service: Optional application service, primarily used by tests.

    Returns:
        Configured FastAPI app.
    """

    app = FastAPI(
        title="Conversational Procurement Intake Layer",
        version="0.1.0",
        description=(
            "HTTP application layer for natural-language procurement intake, "
            "confirmation, orchestrator submission, and SSE event relay."
        ),
    )
    app.state.service = service or _build_default_service(load_settings())

    @app.post("/sessions", response_model=IntakeSessionResponse)
    async def start_session(request: StartSessionRequest) -> IntakeSessionResponse:
        """Create a new intake session."""

        return await app.state.service.start_session(request)

    @app.post("/sessions/{session_id}/messages", response_model=IntakeSessionResponse)
    async def add_message(
        session_id: str, request: UserMessageRequest
    ) -> IntakeSessionResponse:
        """Add one natural-language message to an intake session."""

        try:
            return await app.state.service.add_user_message(session_id, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/sessions/{session_id}/confirm", response_model=IntakeSessionResponse)
    async def confirm_session(
        session_id: str, request: ConfirmSessionRequest
    ) -> IntakeSessionResponse:
        """Confirm and submit a completed intake session."""

        try:
            return await app.state.service.confirm_session(session_id, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get("/sessions/{session_id}", response_model=IntakeSessionResponse)
    async def get_session(session_id: str) -> IntakeSessionResponse:
        """Return current intake session state."""

        try:
            return await app.state.service.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get(
        "/sessions/{session_id}/orchestration-events",
        response_model=OrchestrationEventsResponse,
    )
    async def get_orchestration_events(
        session_id: str, cursor: int = 0
    ) -> OrchestrationEventsResponse:
        """Return stored orchestration events after a cursor."""

        try:
            return await app.state.service.get_orchestration_events(session_id, cursor)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get("/sessions/{session_id}/events")
    async def stream_events(session_id: str) -> StreamingResponse:
        """Stream orchestration events to the UI through SSE."""

        try:
            await app.state.service.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        return StreamingResponse(
            app.state.service.stream_sse(session_id),
            media_type="text/event-stream",
        )

    return app


def _build_default_service(settings: Settings) -> IntakeApplicationService:
    """Build the default application service graph."""

    master_data_resolver = StaticMasterDataResolver()
    if settings.extractor_mode == "llm":
        extractor = LLMIntakeExtractor(
            LocusIntakeLLMClient(build_model(settings)),
            master_data_resolver,
        )
    else:
        extractor = DeterministicIntakeExtractor(master_data_resolver)
    return IntakeApplicationService(
        session_store=SessionStore(),
        event_broker=SessionEventBroker(),
        extractor=extractor,
        orchestrator_client=A2AOrchestratorClient(
            settings.orchestrator_url, settings.agent_api_key
        ),
    )


def main() -> None:
    """Run the conversational procurement intake HTTP service."""

    settings = load_settings()
    parser = argparse.ArgumentParser(
        description="Run the Conversational Procurement Intake HTTP service."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument(
        "--port",
        type=int,
        default=settings.service_port,
        help="Port to bind. Defaults to CONVERSATIONAL_INTAKE_PORT.",
    )
    args = parser.parse_args()
    uvicorn.run(build_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
