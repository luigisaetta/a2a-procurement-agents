# Changelog

All meaningful changes to this project are documented in this file.

## 2026-10-24

- Added a read-only `list_recent_purchase_orders` A2A skill to the Purchase Order Agent, with request and response JSON Schemas, and a `GET /purchase-orders?limit=N` endpoint to the Conversational Procurement Intake Layer that calls it. It returns the last N purchase orders (default 10, at most 100), newest first, with all stored fields, for a future UI table. The intake layer reads the agent URL from `PURCHASE_ORDER_AGENT_URL`, now set in Docker Compose.
- Changed the Procurement Intake Web UI workflow timeline to show seconds in step timestamps, so the duration of each phase can be read in the UI.
- Changed the Offer Evaluation Agent so that the LLM decision is final. The deterministic guardrail that re-applied the policy in code and replaced the LLM choice is removed, as required by the spec rule that selection rules live only in the Markdown policy. The technical consistency checks are unchanged. The offline accuracy test now checks that the workflow returns the LLM decision unchanged; decision accuracy is measured by the opt-in live LLM test, which accepts any of the tied offers in case `ACC-019`.
- Fixed the Procurement Orchestrator so that a failed downstream call (timeout, A2A or HTTP error, malformed response) ends only the affected part with a `part_failed` event and an error code such as `BID_COLLECTION_TIMEOUT`, instead of failing the whole orchestration. The other parts continue and the final response reports `partial` or `failed`. A Purchase Order Agent failure gives `purchase_order_failed` and is not retried.
- Fixed the Conversational Procurement Intake relay so that a submitted session always reaches a terminal outcome. A failed, canceled, or rejected orchestrator task, a JSON-RPC error in the stream, or a stream that ends without a final result now sets the session to `failed` and publishes `orchestration_failed`, also to SSE clients that connect later. Connection error details go to the log instead of the UI.
- Fixed the Conversational Procurement Intake identifiers so they are never reused after a restart. Session and request IDs were built from an in-memory counter that restarted from 1, so a new request could reuse an old `request_id` and receive an old purchase order from the Purchase Order Agent idempotency check. IDs now combine the UTC creation time and a random suffix, for example `REQ-20261024-153012-8B07D2`, and the request ID is generated once per session.
- Fixed Conversational Procurement Intake date handling, which assumed that today was always 2026-05-29. Relative dates now use the current date in the `Europe/Rome` business timezone, also in the LLM prompt. A month and day without a year means its next occurrence (counted from the bid deadline for the delivery date). Deadlines in the past, delivery dates in the past or before the deadline, and impossible dates are rejected and asked again with the reason. The README and RUNBOOK demo requests now use dates without a year, so they stay valid.
- Fixed purchase order idempotency for retried requests. The orchestrator sent `unit_price` as `price / quantity` with 6 decimals and shipping included, MySQL stored it with 2 decimals, and the Purchase Order Agent compared 4 decimals, so a plain retry returned `IDEMPOTENCY_CONFLICT`. The orchestrator now sends the material unit price without shipping, rounded half up to 2 decimals, and the Purchase Order Agent rounds and compares quantity (4 decimals) and amounts (2 decimals) at the column scale.
- Fixed pytest collection, which silently skipped about 30 tests. Every service `tests` folder was a package named `tests`, so files with the same name, such as `test_pipeline.py`, became the same module, and only the first one ran. The `__init__.py` files are removed, `pytest.ini` collects only test folders, and a root `conftest.py` stops the run if a test file is replaced by another module. The Offer Evaluation Agent tests now load the example client from its path instead of importing `test_client`, which only worked with an extra `PYTHONPATH` entry.
- Moved the orchestrator part result builders into `part_results.py`.
- Upgraded `locus-sdk` from `0.2.0b23` to `3.0.1`. The A2A server and client, `Agent`/`AgentConfig`, hook, event, and OCI model APIs used by the agents are unchanged.

## 2026-06-04

- Reworked the main README to describe the current end-to-end procurement demo, implemented components, demo flow, observability, and remaining planned capabilities.
- Clarified the `AGENTS.md` spec-first guidance with the current `specs` directory layout and repository structure.

## 2026-06-03

- Added Procurement Orchestrator business telemetry metrics for purchase order count, purchase order amount by plant, selected offer price deviation by plant, and shipping cost percentage, with Grafana dashboard panels and observability documentation.
- Fixed the Procurement Intake Web UI workflow status badge so it shows completed or failed after the terminal orchestration result arrives instead of returning to waiting.
- Added part reference unit prices to the procurement data model and changed simulated supplier offer pricing to derive parts cost from MCP-backed reference prices, deterministic price variance, and separate shipping cost.
- Fixed `run_e2e_demo_test.sh` so it handles empty argument arrays correctly under Bash with strict unset-variable checking.
- Added an opt-in Docker Compose end-to-end demo test with a dedicated `run_e2e_demo_test.sh` runner and README documentation.
- Added a root-level `check.sh` quality gate for black, pylint, pytest, and Procurement Intake Web UI TypeScript type checking, and documented it in the repository development standards.

## 2026-06-02

- Added pragmatic A2A JSON Schema discovery endpoints to all A2A agents, documented the convention, and added tests for discovery mappings and served schemas.

## 2026-06-01

- Fixed Purchase Order Agent MySQL schema handling by creating the current `purchase_orders` table shape from the start, widening persisted request and offer identifiers for generated workflow IDs, and rejecting incompatible legacy tables instead of recreating them implicitly.
- Fixed conversational intake part grounding so the UI sample request resolves the specific High Density Battery Module instead of becoming ambiguous against all active battery parts.
- Updated the agent catalog to reflect that the Agent Telemetry observability layer has an initial implementation, not only a draft specification.
- Added a dedicated 20-case Offer Evaluation Agent accuracy suite with recorded expected winners and workflow-level result comparison.
- Implemented Docker Compose MySQL persistence for the Purchase Order Agent, including lazy schema creation, idempotent registration, database-backed purchase order numbering, deployment wiring, and tests.
- Specified Docker Compose MySQL persistence, lazy schema creation, idempotency, and database-backed purchase order numbering for the Purchase Order Agent.
- Added the A2A Procurement Agents overview image to the main README.
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
