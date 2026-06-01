# Changelog

All meaningful changes to this project are documented in this file.

## 2026-06-01

- Added inline review editing in the Procurement Intake Web UI for bid deadline, part delivery dates, and quantities, and allowed the intake confirmation API to submit the reviewed orchestration request.
- Added a root-level presenter runbook for the full UI and observability demo, including startup, health checks, sample requests, Grafana review, troubleshooting, and shutdown.
- Connected the Conversational Procurement Intake Layer to the Procurement Data MCP Server for plant and part grounding, keeping the static resolver as a local fallback and using the full conversation text when LLM candidate references are incomplete.
- Moved the Grafana agent error panel to the bottom of the dashboard so operational and business counters stay first.
- Changed the Grafana business counter panels to instant Prometheus queries so restart-era historical samples do not mask the current live counters.
- Bounded the Grafana purchase order business counter by successful orchestrations so technical PO-agent invocations cannot exceed completed workflow counts.
- Replaced the Grafana collector health panel with business-facing completed workflow and purchase order counters.
- Changed the Grafana invocation duration panel to show a five-minute rolling average instead of a cumulative average.
- Simplified Grafana dashboard legends to avoid repeated agent names.
- Configured telemetry-enabled A2A agent servers to initialize OpenTelemetry SDK OTLP metric and trace exporters before creating Locus telemetry hooks.
- Added Docker daemon preflight checks and Docker context selection support to the demo helper scripts.
- Added an end-to-end demo checklist covering environment setup, startup, health checks, workflow invocation, UI verification, Grafana validation, logs, and troubleshooting.
- Added root-level `start_demo.sh` and `stop_demo.sh` helpers for the Docker Compose demo, including automatic A2A agent telemetry enablement when `--observability` is used.
- Added an OpenTelemetry observability badge to the main README.
- Extended the Docker Compose `observability` profile with Prometheus and Grafana, including provisioned Prometheus scraping, Grafana datasource configuration, and a starter A2A agent telemetry dashboard.
- Added dedicated Docker Compose observability documentation covering telemetry enablement, port mapping, startup, verification, Grafana access, and troubleshooting.
- Added an optional Docker Compose OpenTelemetry Collector profile with OTLP gRPC/HTTP receivers, debug export, and a Prometheus metrics endpoint for Locus-native agent telemetry.
- Wired Docker Compose telemetry environment variables for the Procurement Orchestrator, Bid Collection Agent, Offer Evaluation Agent, and Purchase Order Agent while keeping telemetry disabled by default.
- Updated the Agent Telemetry specification with the local Docker Compose collector deployment boundary.

## 2026-05-31

- Extended Locus lifecycle telemetry hook integration to the Procurement Orchestrator, Bid Collection Agent, and Offer Evaluation Agent, keeping telemetry opt-in per service and adding hook lifecycle tests.
- Updated observability documentation to use native Locus telemetry metrics as the initial baseline instead of custom `a2a.procurement.*` metric names.
- Added OpenTelemetry SDK and OTLP exporter dependencies to the Docker Compose runtime requirements for telemetry-enabled deployments.
- Added a Purchase Order Agent telemetry pilot that wraps the deterministic workflow with Locus lifecycle hooks and wires the server to the built-in Locus telemetry hook behind an opt-in environment flag.
- Added the draft Agent Telemetry observability specification for OpenTelemetry-based A2A agent invocation counts, execution duration histograms, error counts, required metric attributes, Locus hook placement, and dashboard requirements.
- Updated the A2A agent specifications to require Agent Telemetry metrics at the Locus task execution boundary without introducing shared agent business runtime code.

## 2026-05-29

- Updated the agent catalog and conversational intake specification to reflect the implemented Procurement Intake Web UI and multi-field clarification behavior.
- Hardened LLM-backed intake extraction so the LLM remains responsible for conversational extraction while deterministic code only validates evidence, grounds entities, and applies guardrails.
- Normalized conversational sourcing region aliases such as `Europe` and `European` to canonical region codes before sending requests to the orchestrator.
- Tightened deterministic intake quantity extraction so dates, times, and supplier counts are not mistaken for requested material quantity during clarification flows.
- Updated intake clarification behavior to ask for all currently missing mandatory details in one response instead of asking for only the first missing field.
- Added deterministic policy guardrails to the Offer Evaluation Agent so LLM decisions cannot incorrectly return no valid offers or select a non-optimal offer when eligible offers exist.
- Implemented the initial Next.js Procurement Intake Web UI with chat, structured request review, confirmation, SSE progress timeline, intake proxy routes, Dockerfile, and Docker Compose deployment.
- Added the draft Procurement Intake Web UI specification for a Next.js interface that converses with the intake layer, confirms requests, and displays real-time workflow progress through SSE.
- Added the Conversational Procurement Intake Layer to the Docker Compose deployment with LLM extraction enabled by default and A2A connectivity to the Procurement Orchestrator.
- Changed the Conversational Procurement Intake Layer default extractor mode to LLM, keeping deterministic extraction as an explicit local fallback.
- Added LLM-backed structured extraction for the Conversational Procurement Intake Layer, with deterministic grounding and tests using an injectable fake LLM client.
- Implemented the initial Conversational Procurement Intake HTTP service with in-memory sessions, deterministic demo extraction, static master-data grounding, confirmation handling, A2A orchestrator client boundary, SSE event relay, polling fallback, README, and tests.
- Added the draft Conversational Procurement Intake Layer specification for natural-language procurement intake, MCP-backed entity grounding, clarification, confirmation, and orchestration request generation.
- Clarified that the Conversational Procurement Intake Layer serves the UI through an HTTP JSON API and submits confirmed workflows to the Procurement Orchestrator through an A2A client.
- Specified orchestration event relay from the Procurement Orchestrator A2A stream to UI-facing HTTP updates, with Server-Sent Events preferred and polling required as a fallback.
- Clarified that orchestration events must be forwarded to connected UI clients in real time over SSE as they are received, not cached and emitted only after workflow completion.

## 2026-05-28

- Changed the default Procurement Data MCP HTTP port from `8010` to `8011` across Docker Compose, examples, documentation, and bid collection tests.
- Added a manual Procurement Orchestrator end-to-end Python client for the Docker Compose deployment and documented build, start, stop, log, and client commands.
- Implemented the initial Procurement Orchestrator Agent with A2A downstream calls, streaming JSON progress events, retry handling, purchase order creation, Docker Compose deployment, tests, and minimal structured logging.
- Added the draft Procurement Orchestrator Agent specification and canonical orchestration request, streaming event, and final response schemas.
- Implemented the initial Bid Collection Agent with MCP-backed supplier discovery, simulated supplier offer collection, A2A server wiring, Docker Compose deployment, and tests.
- Standardized the Procurement Data MCP Server on streamable HTTP for both Docker Compose and local development.
- Added the Procurement Data MCP Server to the Docker Compose deployment using streamable HTTP and the MySQL demo data store.
- Implemented the initial read-only Procurement Data MCP Server with FastMCP, MySQL-backed lookup tools, unit tests, and local startup documentation.
- Updated local development instructions to use the `a2a-procurement-agents` conda environment and configured pytest to collect both agent test suites together.
- Added the draft Procurement Data MCP Server specification for read-only access to plants, parts, suppliers, and supplier-part relationships.
- Added MySQL to the Docker Compose deployment with schema initialization and synthetic procurement seed data loading.
- Added synthetic CSV seed data for plants, electric vehicle parts, suppliers, and supplier-part assignments.
- Simplified the persistent procurement data model around the initial automotive scenario and the seven core entities needed for the first workflow.
- Added the initial persistent procurement data model specification.
- Added the draft Bid Collection Agent specification and canonical bid collection and supplier bid schemas, consolidating supplier identification, bid request, and offer collection into one agent.
- Added an initial Docker Compose deployment for running the Offer Evaluation and Purchase Order A2A agents together.
- Added a sample purchase order JSON payload and manual A2A test client for the Purchase Order Agent.
- Updated the Purchase Order Agent quickstart with sample invocation instructions.
- Added the initial Purchase Order Agent A2A server implementation with deterministic input validation and fake purchase order system registration.
- Added the Purchase Order Agent local environment files, quickstart, and unit tests.
- Updated the agent catalog and README to include Purchase Order Agent implementation and startup references.
- Added the initial Purchase Order Agent specification and JSON Schemas.
- Added a root-level future extensions document with Langfuse observability as the first candidate extension.
- Declared JSON input and output modes for the Offer Evaluation Agent A2A skill while keeping text/plain compatibility.

## 2026-05-27

- Reworked the Offer Evaluation Agent response model to avoid JSON Schema composition keywords unsupported by OCI structured output.
- Added a manual A2A test client and synthetic offer evaluation sample payload.
- Updated the Offer Evaluation Agent specification status to initial implementation.
- Moved Offer Evaluation Agent startup instructions from the main README to a dedicated quickstart.
- Added the first Offer Evaluation Agent A2A server implementation using Locus.
- Added local environment loading and required OCI/A2A runtime configuration.
- Documented the `locus` conda environment and server startup flow.
- Updated the agent catalog to reflect the initial Offer Evaluation Agent implementation.
- Specified that offer evaluation policies are interpreted by an LLM at runtime and policy changes must not require code changes.
- Added the first draft full agent network to the README and agent catalog.
- Clarified that the Offer Evaluation Agent applies policy selection logic rather than generic scoring logic.
- Clarified the urgent procurement policy cost priority and tie-breaker behavior.
- Added the initial local Markdown policy for urgent procurement offer evaluation.
- Updated the Offer Evaluation Agent response schema to support no-valid-offers decisions.
- Aligned the Offer Evaluation Agent specification with the simplified decision and explanation response model.
- Added the initial JSON Schema for the Offer Evaluation Agent response payload.
- Added the initial JSON Schema for the Offer Evaluation Agent request payload.
- Moved detailed agent descriptions from README and AGENTS.md into a root-level agent catalog.
- Added code design guidance requiring simple, readable, modular implementations and discouraging over-engineering.
- Added README badges for Black, Python 3.11+, Pylint, Pytest, and A2A v1.
- Replaced the initial README placeholder with a project overview covering purpose, A2A communication, Oracle Locus, the initial agent roadmap, and development standards.
