# End-to-End Demo Checklist

This checklist verifies the local A2A Procurement Agents demo from environment setup through workflow execution, UI inspection, and observability validation.

The full demo path is:

```text
Procurement Intake UI
  -> Conversational Procurement Intake Layer
  -> Procurement Orchestrator
  -> Bid Collection Agent
  -> Offer Evaluation Agent
  -> Purchase Order Agent
  -> OpenTelemetry Collector
  -> Prometheus
  -> Grafana
```

## Prerequisites

- Docker with Compose support is running.
- The `a2a-procurement-agents` conda environment exists.
- OCI credentials are available for the LLM-backed services.
- The repository root is the current working directory.

## Environment Checklist

Create the local Docker Compose environment file if it does not exist:

```bash
cp deployments/docker-compose/.env.example deployments/docker-compose/.env
```

Edit `deployments/docker-compose/.env` and confirm these values:

- `OCI_REGION`
- `OCI_AUTH`
- `OCI_MODEL_ID`
- `OCI_COMPARTMENT_ID`
- `OCI_PROFILE`
- `OCI_CONFIG_DIR`
- `AGENT_API_KEY`

For observability, the `start_demo.sh --observability` helper enables these values for the current run:

```env
PROCUREMENT_ORCHESTRATOR_TELEMETRY_ENABLED=true
BID_COLLECTION_AGENT_TELEMETRY_ENABLED=true
OFFER_EVALUATION_AGENT_TELEMETRY_ENABLED=true
PURCHASE_ORDER_AGENT_TELEMETRY_ENABLED=true
```

The default OTLP endpoint should remain:

```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

The default metric export interval is tuned for demos:

```env
OTEL_METRIC_EXPORT_INTERVAL=5000
```

## Start Checklist

Start the complete demo with UI and observability:

```bash
./start_demo.sh --ui --observability
```

If Docker Desktop uses a non-default context:

```bash
./start_demo.sh --docker-context desktop-linux --ui --observability
```

Use this lighter variant when the UI container is not needed:

```bash
./start_demo.sh --observability
```

If images are already built and only a restart is needed:

```bash
./start_demo.sh --ui --observability --no-build
```

Confirm containers are running:

```bash
docker compose \
  -f deployments/docker-compose/docker-compose.yml \
  --profile ui \
  --profile observability \
  ps
```

## Health Checks

Check the A2A Agent Cards:

```bash
curl -H "Authorization: Bearer $AGENT_API_KEY" \
  http://127.0.0.1:8000/.well-known/agent-card.json

curl -H "Authorization: Bearer $AGENT_API_KEY" \
  http://127.0.0.1:8001/.well-known/agent-card.json

curl -H "Authorization: Bearer $AGENT_API_KEY" \
  http://127.0.0.1:8002/.well-known/agent-card.json

curl -H "Authorization: Bearer $AGENT_API_KEY" \
  http://127.0.0.1:8003/.well-known/agent-card.json
```

Check the MCP endpoint is reachable:

```bash
curl -i http://127.0.0.1:8011/mcp
```

The MCP endpoint may return a protocol-level response to plain curl. Any reachable HTTP response is enough for this check.

Check the observability services:

```bash
curl http://127.0.0.1:9464/metrics
curl http://127.0.0.1:9090/-/ready
curl http://127.0.0.1:3001/api/health
```

Open Prometheus targets:

```text
http://127.0.0.1:9090/targets
```

The `otel-collector` target should be `UP`.

## Invoke The Workflow

Run the manual A2A client from the repository root:

```bash
conda run -n a2a-procurement-agents \
  python services/procurement-orchestrator/examples/test_client.py
```

For a final-result-only run:

```bash
conda run -n a2a-procurement-agents \
  python services/procurement-orchestrator/examples/test_client.py --no-stream
```

Expected result:

- streaming orchestration events are printed
- bid collection completes
- offer evaluation selects a winning offer
- purchase order registration returns a confirmation
- the final orchestration artifact is returned

## UI Checklist

Open the Procurement Intake UI:

```text
http://127.0.0.1:3000
```

Run a conversational procurement request. Confirm that:

- the UI creates a session
- missing information is clarified when needed
- the structured request can be confirmed
- orchestration progress appears in the timeline
- the final result appears without exposing raw stack traces or protocol internals

## Grafana Checklist

Open Grafana:

```text
http://127.0.0.1:3001
```

Default local credentials:

```text
admin / admin
```

Open the provisioned dashboard:

```text
A2A Procurement / A2A Procurement Agent Telemetry
```

After at least one workflow invocation, confirm:

- the Prometheus datasource is available
- the Collector scrape health panel is healthy
- invocation metrics appear for the agents that executed
- error rate remains empty or zero for successful runs
- average invocation duration updates after workflow traffic

## Port Map

| Port | Service | URL |
| --- | --- | --- |
| `3000` | Procurement Intake UI | `http://127.0.0.1:3000` |
| `3001` | Grafana | `http://127.0.0.1:3001` |
| `3306` | MySQL | `127.0.0.1:3306` |
| `4317` | OpenTelemetry Collector OTLP gRPC | `http://127.0.0.1:4317` |
| `4318` | OpenTelemetry Collector OTLP HTTP | `http://127.0.0.1:4318` |
| `8000` | Bid Collection Agent | `http://127.0.0.1:8000` |
| `8001` | Offer Evaluation Agent | `http://127.0.0.1:8001` |
| `8002` | Purchase Order Agent | `http://127.0.0.1:8002` |
| `8003` | Procurement Orchestrator | `http://127.0.0.1:8003` |
| `8011` | Procurement Data MCP Server | `http://127.0.0.1:8011/mcp` |
| `8012` | Conversational Procurement Intake | `http://127.0.0.1:8012` |
| `9090` | Prometheus | `http://127.0.0.1:9090` |
| `9464` | Collector Prometheus exporter | `http://127.0.0.1:9464/metrics` |

## Logs

Follow the main workflow logs:

```bash
docker compose \
  -f deployments/docker-compose/docker-compose.yml \
  --profile ui \
  --profile observability \
  logs -f \
  procurement-intake-ui \
  conversational-procurement-intake \
  procurement-orchestrator \
  bid-collection-agent \
  offer-evaluation-agent \
  purchase-order-agent
```

Follow observability logs:

```bash
docker compose \
  -f deployments/docker-compose/docker-compose.yml \
  --profile observability \
  logs -f otel-collector prometheus grafana
```

## Troubleshooting

If a port is already in use, override the matching value in `deployments/docker-compose/.env`.

If the UI container cannot pull the Node base image, start the backend and observability stack with:

```bash
./start_demo.sh --observability
```

Then run the UI locally:

```bash
cd services/procurement-intake-ui
CONVERSATIONAL_INTAKE_BASE_URL=http://127.0.0.1:8012 \
  npm run dev -- --hostname 127.0.0.1 --port 3000
```

If Agent Card requests return unauthorized, confirm `AGENT_API_KEY` is exported in the shell or read it from `deployments/docker-compose/.env`.

If Prometheus has no `locus_*` metrics:

- confirm the workflow has been invoked at least once
- confirm `./start_demo.sh --observability` was used
- restart agents after changing telemetry-related environment variables
- check `http://127.0.0.1:9464/metrics`

If Grafana has no dashboard data:

- check `http://127.0.0.1:9090/targets`
- confirm `otel-collector` is `UP`
- wait at least one Prometheus scrape interval
- generate another workflow invocation

If the LLM-backed services fail, confirm OCI settings and mounted credentials:

- `OCI_REGION`
- `OCI_AUTH`
- `OCI_MODEL_ID`
- `OCI_COMPARTMENT_ID`
- `OCI_CONFIG_DIR`

## Stop And Reset

Stop the demo:

```bash
./stop_demo.sh
```

Stop and remove Docker Compose volumes:

```bash
./stop_demo.sh --volumes
```
