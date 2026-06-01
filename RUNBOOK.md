# A2A Procurement Demo Runbook

This runbook is the fast presenter path for running the local A2A Procurement Agents demo with UI and observability.

Use it when you need to start cleanly, run a few successful procurement workflows, show the UI and Grafana, and recover quickly from common demo issues.

## 1. Preflight

Run from the repository root.

Confirm Docker is reachable:

```bash
docker info
```

Confirm the local environment file exists:

```bash
test -f deployments/docker-compose/.env
```

If it does not exist:

```bash
cp deployments/docker-compose/.env.example deployments/docker-compose/.env
```

Before a live demo, confirm `deployments/docker-compose/.env` has valid values for:

- `OCI_REGION`
- `OCI_AUTH`
- `OCI_MODEL_ID`
- `OCI_COMPARTMENT_ID`
- `OCI_PROFILE`
- `OCI_CONFIG_DIR`
- `AGENT_API_KEY`

## 2. Start

Start the full demo:

```bash
./start_demo.sh --ui --observability
```

If Docker uses a non-default context:

```bash
./start_demo.sh --docker-context desktop-linux --ui --observability
```

For a quick restart without rebuilding images:

```bash
./start_demo.sh --ui --observability --no-build
```

Expected startup endpoints:

| Surface | URL |
| --- | --- |
| Procurement Intake UI | `http://127.0.0.1:3000` |
| Grafana | `http://127.0.0.1:3001` |
| Prometheus | `http://127.0.0.1:9090` |
| Collector metrics | `http://127.0.0.1:9464/metrics` |
| Conversational Intake | `http://127.0.0.1:8012` |
| Procurement Orchestrator | `http://127.0.0.1:8003` |

## 3. Health Checks

Check containers:

```bash
docker compose \
  -f deployments/docker-compose/docker-compose.yml \
  --profile ui \
  --profile observability \
  ps
```

Check Grafana:

```bash
curl http://127.0.0.1:3001/api/health
```

Check Prometheus:

```bash
curl http://127.0.0.1:9090/-/ready
```

Check Collector metrics:

```bash
curl http://127.0.0.1:9464/metrics
```

Open Prometheus targets and confirm `otel-collector` is `UP`:

```text
http://127.0.0.1:9090/targets
```

Confirm telemetry is enabled on the orchestrator after startup:

```bash
docker exec a2a-procurement-agents-procurement-orchestrator-1 env | \
  grep PROCUREMENT_ORCHESTRATOR_TELEMETRY_ENABLED
```

Expected:

```text
PROCUREMENT_ORCHESTRATOR_TELEMETRY_ENABLED=true
```

## 4. Demo Flow

Open the UI:

```text
http://127.0.0.1:3000
```

Use one request at a time. Confirm the structured request in the UI when prompted.

### Request 1

```text
Start an urgent tender for 16 units of EV-DC-DC-009, High Voltage DC DC Converter, for the Turin plant IT-TOR. Required delivery date is 2026-07-25. Bid response deadline is 2026-06-15 at 17:00 UTC. Ask up to 3 European suppliers and create the final purchase order automatically.
```

Expected highlights:

- part resolves to `EV-DC-DC-009`
- plant resolves to `IT-TOR`
- supplier bids are collected
- a winning offer is selected
- a final purchase order is created

### Request 2

```text
Start an urgent tender for 8 units of EV-BRAKE-CAL-018, Lightweight Brake Caliper, for the Barcelona plant ES-BCN. Required delivery date is 2026-08-12. Bid response deadline is 2026-06-19 at 15:30 UTC. Ask up to 3 European suppliers and create the final purchase order automatically.
```

Expected highlights:

- part resolves to `EV-BRAKE-CAL-018`
- plant resolves to `ES-BCN`
- workflow completes with one purchase order

### Request 3

```text
Start an urgent tender for 6 units of Low Temperature Radiator for the Graz plant AT-GRA. Required delivery date is 2026-08-28. Bid response deadline is 2026-06-21 at 16:00 UTC. Ask up to 3 European suppliers and create the final purchase order automatically.
```

Expected highlights:

- part resolves by name, without a part code
- plant resolves to `AT-GRA`
- workflow completes with one purchase order

## 5. What To Show In The UI

For each request, show:

- the conversational request
- any clarification behavior, if triggered
- the structured procurement request before confirmation
- the live timeline events
- bid collection completion
- offer evaluation completion
- purchase order completion
- final workflow result

The strongest demo moment is the transition from natural language to a confirmed structured workflow, followed by real-time orchestration events.

## 6. What To Show In Grafana

Open Grafana:

```text
http://127.0.0.1:3001
```

Default local credentials:

```text
admin / admin
```

Open:

```text
A2A Procurement / A2A Procurement Agent Telemetry
```

Show these panels in order:

- `Agent Invocations`
- `Average Invocation Duration (5m)`
- `Completed Workflows`
- `Purchase Orders Created`
- `Agent Error Rate`

Expected successful-demo behavior:

- all four A2A agents receive invocations
- completed workflows and purchase orders move together
- average invocation duration updates after traffic
- error rate remains empty or zero

Important demo note: agent telemetry counters are in process memory. If agent containers restart, live counters restart from the current process lifetime.

## 7. Fast Troubleshooting

If the UI keeps asking which material or part is needed:

```bash
docker compose \
  -f deployments/docker-compose/docker-compose.yml \
  logs procurement-data-mcp conversational-procurement-intake --tail=120
```

Check that the conversational intake container has the MCP URL:

```bash
docker exec a2a-procurement-agents-conversational-procurement-intake-1 env | \
  grep PROCUREMENT_DATA_MCP_URL
```

Expected:

```text
PROCUREMENT_DATA_MCP_URL=http://procurement-data-mcp:8011/mcp
```

If Grafana counters do not move after a successful workflow, check telemetry flags:

```bash
docker exec a2a-procurement-agents-procurement-orchestrator-1 env | \
  grep TELEMETRY_ENABLED
```

If telemetry is `false`, restart with:

```bash
./start_demo.sh --ui --observability --no-build
```

If Grafana shows old values, hard refresh the browser. The business counter panels use instant Prometheus queries and should reflect the current live counter values.

If Prometheus has no metrics:

```bash
curl http://127.0.0.1:9464/metrics
docker compose \
  -f deployments/docker-compose/docker-compose.yml \
  --profile observability \
  logs otel-collector --tail=120
```

If the LLM-backed intake or offer evaluation fails, check OCI settings and mounted credentials:

```bash
docker compose \
  -f deployments/docker-compose/docker-compose.yml \
  logs conversational-procurement-intake offer-evaluation-agent --tail=120
```

## 8. Logs During The Demo

Follow workflow logs:

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

## 9. Stop

Stop the demo:

```bash
./stop_demo.sh
```

Stop and remove Docker volumes for a clean data reset:

```bash
./stop_demo.sh --volumes
```

After a volume reset, the next startup recreates MySQL seed data from the repository seed files.

## 10. Presenter Checklist

Before starting:

- Docker is running.
- `.env` exists and OCI values are valid.
- `./start_demo.sh --ui --observability` completes successfully.
- UI opens at `http://127.0.0.1:3000`.
- Grafana opens at `http://127.0.0.1:3001`.
- Prometheus target `otel-collector` is `UP`.

During the demo:

- Run one prepared request.
- Confirm the structured request.
- Narrate the event timeline as each agent completes.
- Open Grafana and show agent invocations plus business counters.
- Use the error panel only as the final diagnostic view.

After the demo:

- Stop the stack with `./stop_demo.sh`.
- Use `./stop_demo.sh --volumes` only when you want a fully clean local reset.
