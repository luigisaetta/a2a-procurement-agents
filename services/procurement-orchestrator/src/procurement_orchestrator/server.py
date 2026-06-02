"""
Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    A2A server entry point for the Procurement Orchestrator Agent.
"""

from __future__ import annotations

import argparse
import json
import logging
import os

from locus.a2a import A2AServer, AgentProvider, AgentSkill
from locus.hooks.builtin.telemetry import create_telemetry_hook

from procurement_orchestrator.config import Settings, load_settings
from procurement_orchestrator.logging_utils import configure_logging
from procurement_orchestrator.pipeline import build_workflow_agent

TELEMETRY_ENABLED_ENV = "PROCUREMENT_ORCHESTRATOR_TELEMETRY_ENABLED"

# Telemetry enablement intentionally mirrors other independent agents without
# introducing shared runtime code between services.
# pylint: disable=duplicate-code,import-outside-toplevel,too-many-locals


def build_server(settings: Settings) -> A2AServer:
    """Build the A2A server for the Procurement Orchestrator Agent.

    Args:
        settings: Validated runtime settings.

    Returns:
        Configured Locus A2A server.
    """

    telemetry_enabled = _telemetry_enabled()
    if telemetry_enabled:
        _configure_open_telemetry("procurement-orchestrator")

    telemetry_hook = create_telemetry_hook(
        enabled=telemetry_enabled,
        service_name="procurement-orchestrator",
    )
    agent = build_workflow_agent(settings, hooks=[telemetry_hook])
    server = A2AServer(
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
    _add_schema_routes(server, settings)
    return server


def _add_schema_routes(server: A2AServer, settings: Settings) -> None:
    """Add pragmatic JSON Schema discovery routes to the A2A FastAPI app."""

    schema_files = {
        "procurement-orchestration-request.schema.json": settings.request_schema_file,
        "procurement-orchestration-event.schema.json": settings.event_schema_file,
        "procurement-orchestration-response.schema.json": settings.response_schema_file,
    }

    @server.app.get("/.well-known/a2a-schemas")
    async def schema_discovery() -> dict:
        return {
            "agent": "procurement-orchestrator",
            "protocol_version": "1.0",
            "skills": {
                "run_procurement_workflow": {
                    "input_schema": (
                        "/schemas/procurement-orchestration-request.schema.json"
                    ),
                    "event_schema": (
                        "/schemas/procurement-orchestration-event.schema.json"
                    ),
                    "output_schema": (
                        "/schemas/procurement-orchestration-response.schema.json"
                    ),
                }
            },
        }

    @server.app.get("/schemas/{schema_name}")
    async def get_schema(schema_name: str) -> dict:
        if schema_name not in schema_files:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Schema not found.")
        schema_file = schema_files[schema_name]
        return json.loads(schema_file.read_text(encoding="utf-8"))


def _telemetry_enabled() -> bool:
    """Return whether Locus telemetry hooks should be enabled."""

    value = os.environ.get(TELEMETRY_ENABLED_ENV, "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _configure_open_telemetry(service_name: str) -> None:
    """Configure OpenTelemetry OTLP exporters for Locus telemetry."""

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logging.getLogger(__name__).warning(
            "OpenTelemetry exporter unavailable: %s", exc
        )
        return

    resource = Resource.create(
        {"service.name": os.environ.get("OTEL_SERVICE_NAME", service_name)}
    )
    insecure = not endpoint.startswith("https://")
    export_interval = int(os.environ.get("OTEL_METRIC_EXPORT_INTERVAL", "5000"))

    metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=insecure)
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=export_interval,
    )
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[metric_reader])
    )

    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=insecure))
    )
    trace.set_tracer_provider(trace_provider)


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
