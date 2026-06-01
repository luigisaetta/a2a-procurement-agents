# Agent Telemetry Specification

Version: 0.1.0

Status: Draft

---

# Purpose

This specification defines the first observability layer for A2A Procurement Agents.

The goal is to make it simple to collect and later visualize operational metrics for each A2A agent:

- how many times each agent has been invoked
- average, minimum, and maximum execution time per agent
- number of errors per agent

Telemetry must be emitted through the built-in Oracle Locus telemetry hook so the platform uses the runtime's native instrumentation wherever possible.

Locus emits OpenTelemetry-compatible telemetry. Deployment can route that telemetry to a standard collector, backend, or dashboard without coupling agents to a specific visualization product.

---

# Scope

This specification applies to A2A agent task executions.

Initial in-scope components:

- Procurement Orchestrator Agent
- Bid Collection Agent
- Offer Evaluation Agent
- Purchase Order Agent

Out of scope for the initial version:

- browser UI telemetry
- Conversational Procurement Intake Layer HTTP request metrics
- Procurement Data MCP Server metrics
- supplier API metrics beyond the Bid Collection Agent execution boundary
- LLM token usage and prompt tracing
- long-term audit storage

Those components may adopt compatible OpenTelemetry conventions later, but their contracts must be specified separately.

---

# Design Principles

## No Shared Agent Runtime Code

The project rule remains unchanged: independently deployable agents must not depend on internal implementation details or shared business runtime code from other agents.

Telemetry standardization must therefore happen through this specification and Locus runtime hooks, not through a mandatory repository-local shared module.

Each agent may implement the small local lifecycle bridge needed to let its workflow participate in Locus hook execution. That bridge must not contain shared procurement business logic.

The baseline telemetry provider is `locus.hooks.builtin.telemetry.TelemetryHook` or the corresponding Locus factory helper.

Using this Locus runtime capability is allowed because Locus is already the common infrastructure layer. That usage must remain limited to protocol/runtime instrumentation and must not introduce shared procurement business logic.

## Locus Boundary Instrumentation

Telemetry must be attached at the Locus A2A task execution boundary.

The preferred integration point is a Locus lifecycle hook or middleware that observes:

- task accepted
- task completed
- task failed
- task canceled or timed out, when supported by the runtime

If the installed Locus version does not expose a native hook API for this boundary, the agent must instrument the narrowest local wrapper around its Locus task handler. The resulting behavior must be equivalent from the metric consumer's point of view.

## OpenTelemetry First

Metrics must be emitted by Locus telemetry instrumentation and exported through the configured OpenTelemetry pipeline.

Agents must not write metrics directly to a dashboard-specific API.

An OpenTelemetry Collector should be the default deployment boundary for routing telemetry to Prometheus, Grafana, OCI Application Performance Monitoring, or another backend.

## Low Cardinality Metrics

Metric attributes must remain low-cardinality.

Request IDs, A2A task IDs, purchase order IDs, supplier IDs, and other per-execution identifiers must not be metric attributes.

Those identifiers may be attached to spans or structured logs when tracing is enabled.

---

# Metric Contract

The baseline metric names are the native names emitted by the Locus `TelemetryHook`.

Procurement dashboards must derive their agent-level views from these native Locus metrics and their service-level attributes.

The project does not define custom `a2a.procurement.*` metrics in the initial implementation.

## Invocation Counter

Name: `locus.invocations`

Type: counter

Unit: `{execution}`

Description: Counts A2A agent task executions observed at the agent boundary.

The counter must be incremented once for each accepted execution.

Invalid requests that reach the workflow lifecycle should appear as failed Locus invocations. Requests rejected by the HTTP or JSON-RPC transport before workflow execution may only appear in transport-level logs or telemetry.

## Execution Duration Histogram

Name: `locus.invocation.duration`

Type: histogram

Unit: `ms`

Description: Records elapsed wall-clock execution duration for one A2A agent task execution.

The duration starts when the accepted task begins executing inside the agent and ends when the agent returns a terminal success, terminal failure, cancellation, or timeout response.

Dashboards must derive average, minimum, maximum, and percentile execution time from this histogram or from backend-specific histogram aggregations.

## Error Counter

Name: derived from `locus.invocation.duration` where `success` is `False`, or from error spans when tracing is enabled.

Type: derived view

Unit: `{error}`

Description: Counts A2A agent task executions that terminate with an error outcome.

The dashboard or backend query must count failed invocation records once per execution, not once per exception or retry.

## Validation Error Counter

Name: derived from failed `locus.invocation.duration` records or error spans with a validation error category.

Type: derived view

Unit: `{error}`

Description: Counts inbound payload validation failures that prevent normal task execution.

This derived view is optional for the first implementation, but recommended because it explains why rejected requests may appear as failed executions.

---

# Required Metric Attributes

Every telemetry-enabled agent must set a distinct Locus/OpenTelemetry service name.

| Attribute | Example | Description |
| --- | --- | --- |
| `service.name` | `offer-evaluation-agent` | OpenTelemetry service name for the process emitting telemetry. |

Locus built-in invocation metrics also include runtime-defined attributes such as:

| Attribute | Example | Description |
| --- | --- | --- |
| `agent_id` | `offer-evaluation-agent` | Agent identifier attached to the Locus `AgentState`. |
| `success` | `True` | Whether the Locus invocation completed without an exception. |

---

# Recommended Span Attributes

When tracing is enabled, each A2A task execution should create or continue a span with:

| Attribute | Example |
| --- | --- |
| `a2a.task_id` | `task-123` |
| `procurement.request_id` | `REQ-2026-0001` |
| `agent_id` | `procurement-orchestrator` |
| `service.name` | `procurement-orchestrator` |

The Procurement Orchestrator should propagate trace context to downstream A2A calls when the transport and Locus runtime support it.

Trace identifiers may be used to correlate logs, spans, and metrics exemplars. They must not be required in metric attributes.

---

# Agent Role Registry

Initial role identifiers:

| Agent | `service.name` | `agent.role` | A2A Skill |
| --- | --- | --- | --- |
| Procurement Orchestrator | `procurement-orchestrator` | `procurement_orchestrator` | `run_procurement_workflow` |
| Bid Collection Agent | `bid-collection-agent` | `bid_collection` | `collect_bids` |
| Offer Evaluation Agent | `offer-evaluation-agent` | `offer_evaluation` | `evaluate_offers` |
| Purchase Order Agent | `purchase-order-agent` | `purchase_order` | `create_purchase_order` |

New A2A agents must extend this registry before implementation.

---

# Configuration

Each agent must support telemetry enablement through a service-specific environment variable.

Initial enablement variables:

| Agent | Variable |
| --- | --- |
| Procurement Orchestrator | `PROCUREMENT_ORCHESTRATOR_TELEMETRY_ENABLED` |
| Bid Collection Agent | `BID_COLLECTION_AGENT_TELEMETRY_ENABLED` |
| Offer Evaluation Agent | `OFFER_EVALUATION_AGENT_TELEMETRY_ENABLED` |
| Purchase Order Agent | `PURCHASE_ORDER_AGENT_TELEMETRY_ENABLED` |

Required variables:

| Variable | Default | Description |
| --- | --- | --- |
| `OTEL_SERVICE_NAME` | agent-specific service name | Optional OpenTelemetry service name override. The service code sets a stable default when creating the Locus telemetry hook. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OTLP collector endpoint. If unset, telemetry export may be disabled locally. |
| `OTEL_METRICS_EXPORTER` | `otlp` when endpoint is set | OpenTelemetry metrics exporter selection. |
| `OTEL_TRACES_EXPORTER` | `otlp` when endpoint is set | OpenTelemetry traces exporter selection. |
| `OTEL_RESOURCE_ATTRIBUTES` | unset | Additional OpenTelemetry resource attributes. |
| `DEPLOYMENT_ENVIRONMENT` | `local` | Value used for `deployment.environment`. |

Runtime images that export telemetry through OTLP must include the OpenTelemetry SDK and OTLP exporter packages.

Telemetry must be disabled by default for local development and tests.

Tests must be able to run without an external OpenTelemetry Collector.

## Local Docker Compose Collector

The Docker Compose deployment provides an optional `observability` profile that runs a local OpenTelemetry Collector, Prometheus, and Grafana.

The collector accepts OTLP traffic on:

- gRPC port `4317`
- HTTP port `4318`

The collector exposes a Prometheus metrics endpoint on port `9464`.

Prometheus scrapes that collector endpoint and is exposed locally on port `9090`.

Grafana is exposed locally on port `3001` with a preconfigured Prometheus datasource and starter agent telemetry dashboard.

This collector is a deployment boundary only. Agents remain coupled to Locus and OpenTelemetry contracts, not to a specific dashboard or backend.

---

# Error Categories

Initial `error.type` values:

| Error Type | Meaning |
| --- | --- |
| `validation_error` | Input payload or schema validation failed. |
| `downstream_agent_error` | A downstream A2A agent call failed. |
| `supplier_provider_error` | Supplier discovery or supplier offer provider failed. |
| `llm_error` | LLM invocation or structured output generation failed. |
| `policy_error` | Policy loading or policy interpretation failed. |
| `purchase_order_system_error` | Purchase order backend registration failed. |
| `timeout` | Execution exceeded a configured timeout. |
| `internal_error` | Unexpected internal failure. |

The initial Locus-native telemetry implementation does not require custom `error.type` metric attributes. These categories are reserved for future custom spans, log correlation, or derived views if a backend supports them.

---

# Dashboard Requirements

The first dashboard view should provide:

- invocation count by agent
- error count by agent
- error rate by agent
- average execution time by agent
- minimum execution time by agent
- maximum execution time by agent

The dashboard should support filtering by:

- environment
- `service.name`
- `agent_id`
- `success`

Dashboard implementation is not part of this specification.

---

# Security And Privacy

Telemetry must not include sensitive procurement payloads, supplier commercial terms, full user prompts, or raw purchase order contents as metric attributes.

Metric attributes must stay operational and low-cardinality.

If traces or logs capture payload fragments for debugging, a redaction strategy must be specified before enabling that behavior outside local development.

---

# Definition of Done

The observability layer is complete only if:

- this specification is implemented by all in-scope A2A agents
- each in-scope agent records invocation count, execution duration, and error count
- telemetry can be disabled for tests and local development
- unit tests verify Locus lifecycle hook execution without requiring an external collector
- Docker Compose can optionally route telemetry to an OpenTelemetry Collector in a later deployment step
- README or quickstart documentation explains how to enable telemetry locally
- black passes for any Python implementation changes
- pylint passes for any Python implementation changes
- pytest passes
- changelog is updated
