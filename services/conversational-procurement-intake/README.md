# Conversational Procurement Intake Layer

HTTP application layer for natural-language procurement intake.

The service is not an A2A agent. It exposes a JSON HTTP API to the UI, prepares a validated `ProcurementOrchestrationRequest`, submits confirmed requests to the Procurement Orchestrator through an A2A client, and relays orchestration progress to the UI through Server-Sent Events.

## Status

Initial implementation.

The first implementation provides:

- in-memory intake sessions
- LLM-backed structured extraction when enabled
- deterministic extraction fallback for local tests and demos
- static master-data grounding aligned with the seed dataset
- request confirmation before orchestration submission
- A2A orchestrator client boundary
- real-time SSE event relay
- polling fallback for orchestration events

The static resolver is intentionally small. It is the grounding boundary that will be replaced by the read-only Procurement Data MCP client.

## Local Run

Use the repository conda environment:

```bash
PYTHONPATH=services/conversational-procurement-intake/src \
  conda run -n a2a-procurement-agents \
  python -m conversational_procurement_intake.server
```

Optional environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `CONVERSATIONAL_INTAKE_PORT` | `8012` | HTTP API port. |
| `CONVERSATIONAL_INTAKE_EXTRACTOR_MODE` | `llm` | Use `deterministic` only for local tests and demos. |
| `PROCUREMENT_ORCHESTRATOR_URL` | `http://127.0.0.1:8003` | Procurement Orchestrator A2A base URL. |
| `AGENT_API_KEY` | empty | Bearer token used for A2A calls. |
| `OCI_REGION` | none | Required by the default LLM extractor. |
| `OCI_AUTH` | none | Must be `API_KEY` for LLM extraction. |
| `OCI_MODEL_ID` | none | OCI Generative AI model identifier. |
| `OCI_COMPARTMENT_ID` | none | OCI compartment OCID for model calls. |
| `OCI_PROFILE` | `DEFAULT` | OCI config profile for API key authentication. |

Example:

```bash
PYTHONPATH=services/conversational-procurement-intake/src \
  conda run -n a2a-procurement-agents \
  python -m conversational_procurement_intake.server
```

## API

Initial endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/sessions` | Start an intake session. |
| `POST` | `/sessions/{session_id}/messages` | Add a natural-language user message. |
| `POST` | `/sessions/{session_id}/confirm` | Confirm and submit the structured request. |
| `GET` | `/sessions/{session_id}` | Return current session state. |
| `GET` | `/sessions/{session_id}/events` | Stream orchestration progress through SSE. |
| `GET` | `/sessions/{session_id}/orchestration-events` | Poll stored orchestration events. |

## Development Notes

The service stores sessions in memory in the first implementation. If the process stops during an active orchestration, durable recovery is not provided yet.

SSE is the primary live update path. Polling exists for reconnect and fallback behavior.
