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

Telemetry must be emitted through OpenTelemetry so the platform can send metrics and traces to a standard collector, backend, or dashboard without coupling agents to a specific visualization product.

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

Telemetry standardization must therefore happen through this specification, not through a mandatory repository-local shared module.

Each agent may implement its own local telemetry adapter as long as it emits the metric names, units, and attributes defined here.

If Oracle Locus provides a stable telemetry hook package or runtime integration, agents may use that external runtime capability because Locus is already the common infrastructure layer. That usage must remain limited to protocol/runtime instrumentation and must not introduce shared procurement business logic.

## Locus Boundary Instrumentation

Telemetry must be attached at the Locus A2A task execution boundary.

The preferred integration point is a Locus lifecycle hook or middleware that observes:

- task accepted
- task completed
- task failed
- task canceled or timed out, when supported by the runtime

If the installed Locus version does not expose a native hook API for this boundary, the agent must instrument the narrowest local wrapper around its Locus task handler. The resulting behavior must be equivalent from the metric consumer's point of view.

## OpenTelemetry First

Metrics must be emitted through the OpenTelemetry metrics API and exported through OTLP.

Agents must not write metrics directly to a dashboard-specific API.

An OpenTelemetry Collector should be the default deployment boundary for routing telemetry to Prometheus, Grafana, OCI Application Performance Monitoring, or another backend.

## Low Cardinality Metrics

Metric attributes must remain low-cardinality.

Request IDs, A2A task IDs, purchase order IDs, supplier IDs, and other per-execution identifiers must not be metric attributes.

Those identifiers may be attached to spans or structured logs when tracing is enabled.

---

# Metric Contract

All metric names use the `a2a.procurement.agent` namespace.

## Invocation Counter

Name: `a2a.procurement.agent.invocations`

Type: counter

Unit: `{execution}`

Description: Counts A2A agent task executions observed at the agent boundary.

The counter must be incremented once for each accepted execution.

Invalid requests rejected before task execution may increment `a2a.procurement.agent.validation_errors`, but must not increment this metric unless the runtime has already accepted the task for execution.

## Execution Duration Histogram

Name: `a2a.procurement.agent.execution.duration`

Type: histogram

Unit: `ms`

Description: Records elapsed wall-clock execution duration for one A2A agent task execution.

The duration starts when the accepted task begins executing inside the agent and ends when the agent returns a terminal success, terminal failure, cancellation, or timeout response.

Dashboards must derive average, minimum, maximum, and percentile execution time from this histogram or from backend-specific histogram aggregations.

## Error Counter

Name: `a2a.procurement.agent.errors`

Type: counter

Unit: `{error}`

Description: Counts A2A agent task executions that terminate with an error outcome.

The counter must be incremented once per failed execution, not once per exception or retry.

## Validation Error Counter

Name: `a2a.procurement.agent.validation_errors`

Type: counter

Unit: `{error}`

Description: Counts inbound payload validation failures that prevent normal task execution.

This metric is optional for the first implementation, but recommended because it explains why rejected requests may not appear in the invocation counter.

---

# Required Metric Attributes

Every metric emitted by this specification must include:

| Attribute | Example | Description |
| --- | --- | --- |
| `service.name` | `offer-evaluation-agent` | OpenTelemetry service name for the process emitting telemetry. |
| `agent.name` | `Offer Evaluation Agent` | Human-readable agent name. |
| `agent.role` | `offer_evaluation` | Stable low-cardinality role identifier. |
| `agent.version` | `0.1.0` | Agent implementation or contract version known at runtime. |
| `a2a.skill` | `evaluate_offers` | A2A skill being executed. |
| `deployment.environment` | `local` | Runtime environment such as `local`, `demo`, `test`, or `prod`. |

Terminal metrics must also include:

| Attribute | Example | Description |
| --- | --- | --- |
| `execution.outcome` | `success` | One of `success`, `error`, `timeout`, or `canceled`. |

Error metrics must also include:

| Attribute | Example | Description |
| --- | --- | --- |
| `error.type` | `validation_error` | Stable low-cardinality error category. |

---

# Recommended Span Attributes

When tracing is enabled, each A2A task execution should create or continue a span with:

| Attribute | Example |
| --- | --- |
| `a2a.task_id` | `task-123` |
| `procurement.request_id` | `REQ-2026-0001` |
| `a2a.skill` | `run_procurement_workflow` |
| `agent.name` | `Procurement Orchestrator` |
| `agent.role` | `procurement_orchestrator` |
| `execution.outcome` | `success` |

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

Each agent must support telemetry configuration through environment variables.

Required variables:

| Variable | Default | Description |
| --- | --- | --- |
| `OTEL_SERVICE_NAME` | agent-specific service name | OpenTelemetry service name. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OTLP collector endpoint. If unset, telemetry export may be disabled locally. |
| `OTEL_METRICS_EXPORTER` | `otlp` when endpoint is set | OpenTelemetry metrics exporter selection. |
| `OTEL_TRACES_EXPORTER` | `otlp` when endpoint is set | OpenTelemetry traces exporter selection. |
| `OTEL_RESOURCE_ATTRIBUTES` | unset | Additional OpenTelemetry resource attributes. |
| `DEPLOYMENT_ENVIRONMENT` | `local` | Value used for `deployment.environment`. |

Agent-specific configuration may add an explicit telemetry enablement flag, but telemetry must be safe to disable for local development and tests.

Tests must be able to run without an external OpenTelemetry Collector.

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

Agents may define additional low-cardinality error categories in their own specifications.

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
- agent role
- A2A skill
- execution outcome

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
- unit tests verify metric emission without requiring an external collector
- Docker Compose can optionally route telemetry to an OpenTelemetry Collector
- README or quickstart documentation explains how to enable telemetry locally
- black passes for any Python implementation changes
- pylint passes for any Python implementation changes
- pytest passes
- changelog is updated
