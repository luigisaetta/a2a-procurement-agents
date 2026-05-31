# Bid Collection Agent

This service exposes the `collect_bids` A2A skill.

The agent is deterministic. It uses the Procurement Data MCP Server over streamable HTTP to identify eligible suppliers, then calls a simulated supplier offer provider behind a local provider boundary.

## Environment

Use the repository conda environment:

```bash
conda activate a2a-procurement-agents
```

Required variables:

```bash
export BID_COLLECTION_AGENT_PORT=8000
export AGENT_API_KEY=change-me
export PROCUREMENT_DATA_MCP_URL=http://127.0.0.1:8011/mcp
```

Optional Locus telemetry:

```bash
export BID_COLLECTION_AGENT_TELEMETRY_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
```

The built-in Locus `TelemetryHook` emits native Locus metrics such as `locus.invocations` and `locus.invocation.duration`.

## Run

Start MySQL and the Procurement Data MCP Server first:

```bash
cd deployments/docker-compose
docker compose up -d mysql procurement-data-mcp
```

Run the agent from the repository root:

```bash
PYTHONPATH=services/bid-collection-agent/src \
conda run -n a2a-procurement-agents \
python -m bid_collection_agent.server --host 127.0.0.1 --port 8000
```

The Agent Card is available at:

```text
http://127.0.0.1:8000/.well-known/agent-card.json
```
