# Future Extensions

This document collects possible future extensions for the A2A Procurement Agents platform.

The list is intentionally lightweight. Items here are not committed roadmap promises; they are ideas to revisit as the project evolves.

## Observability With Langfuse

Integrate Langfuse to improve observability for agent execution and LLM-driven decisions.

The baseline agent telemetry contract is now specified in [specs/observability/agent-telemetry.md](specs/observability/agent-telemetry.md). Any Langfuse integration should build on that OpenTelemetry-first contract instead of replacing it.

Potential goals:

- trace each A2A task across agent boundaries
- capture LLM prompts, completions, latency, and token usage
- correlate policy version, request payload, and selected decision
- inspect failed or invalid structured-output responses
- compare offer evaluation behavior across policy versions
- support debugging and audit review for procurement workflows

Initial integration points:

- Offer Evaluation Agent LLM invocation
- A2A task lifecycle events
- policy loading and policy version metadata
- structured-output validation failures
- technical consistency check failures

The integration should avoid storing sensitive supplier or procurement data unless an explicit redaction strategy is defined.
