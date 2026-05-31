# Procurement Orchestrator Agent

This service exposes the `run_procurement_workflow` A2A skill.

The orchestrator accepts only structured JSON. It streams progress events as JSON text inside A2A status updates, calls the Bid Collection Agent, Offer Evaluation Agent, and Purchase Order Agent through A2A, and returns a final orchestration response.

Checkpointing is intentionally not implemented yet. The initial implementation writes minimal structured JSON logs for orchestration steps.

## Environment

Use the repository conda environment:

```bash
conda activate a2a-procurement-agents
```

Required variables:

```bash
export PROCUREMENT_ORCHESTRATOR_PORT=8003
export AGENT_API_KEY=change-me
export BID_COLLECTION_AGENT_URL=http://127.0.0.1:8000
export OFFER_EVALUATION_AGENT_URL=http://127.0.0.1:8001
export PURCHASE_ORDER_AGENT_URL=http://127.0.0.1:8002
```

Optional Locus telemetry:

```bash
export PROCUREMENT_ORCHESTRATOR_TELEMETRY_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
```

The built-in Locus `TelemetryHook` emits native Locus metrics such as `locus.invocations` and `locus.invocation.duration`.

## Run

Start the downstream agents first, then run the orchestrator from the repository root:

```bash
PYTHONPATH=services/procurement-orchestrator/src \
conda run -n a2a-procurement-agents \
python -m procurement_orchestrator.server --host 127.0.0.1 --port 8003
```

The Agent Card is available at:

```text
http://127.0.0.1:8003/.well-known/agent-card.json
```

## Manual Client

The Docker Compose end-to-end client reads `AGENT_API_KEY` and `PROCUREMENT_ORCHESTRATOR_PORT` from the shell environment or from [../../deployments/docker-compose/.env](../../deployments/docker-compose/.env):

```bash
conda run -n a2a-procurement-agents \
  python services/procurement-orchestrator/examples/test_client.py
```

The sample request payload is embedded in [examples/test_client.py](examples/test_client.py).

## Contracts

- Request: [../../specs/schemas/procurement-orchestration-request.schema.json](../../specs/schemas/procurement-orchestration-request.schema.json)
- Streaming event: [../../specs/schemas/procurement-orchestration-event.schema.json](../../specs/schemas/procurement-orchestration-event.schema.json)
- Final response: [../../specs/schemas/procurement-orchestration-response.schema.json](../../specs/schemas/procurement-orchestration-response.schema.json)

The specification is maintained in [../../specs/agents/procurement-orchestrator.md](../../specs/agents/procurement-orchestrator.md).
