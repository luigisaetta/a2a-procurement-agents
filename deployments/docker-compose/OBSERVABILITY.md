# Observability Profile

This document explains how to run the local observability stack for the A2A Procurement Agents Docker Compose deployment.

The `observability` profile starts:

- OpenTelemetry Collector
- Prometheus
- Grafana

The telemetry path is:

```text
A2A agents -> Locus TelemetryHook -> OTLP -> OpenTelemetry Collector -> Prometheus -> Grafana
```

Telemetry is disabled by default. Enable it explicitly only for the agents you want to observe.

## Services

| Service | Purpose | Default URL |
| --- | --- | --- |
| OpenTelemetry Collector OTLP gRPC | Receives telemetry from agents | `http://127.0.0.1:4317` |
| OpenTelemetry Collector OTLP HTTP | Receives telemetry from agents | `http://127.0.0.1:4318` |
| OpenTelemetry Collector Prometheus exporter | Exposes collected metrics for scraping | `http://127.0.0.1:9464/metrics` |
| Prometheus | Scrapes Collector metrics | `http://127.0.0.1:9090` |
| Grafana | Displays dashboards | `http://127.0.0.1:3001` |

Grafana credentials default to:

```text
admin / admin
```

Override them through `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD`.

## Configuration

Copy the example environment file if needed:

```bash
cp deployments/docker-compose/.env.example deployments/docker-compose/.env
```

Enable telemetry for the four A2A agents:

```env
PROCUREMENT_ORCHESTRATOR_TELEMETRY_ENABLED=true
BID_COLLECTION_AGENT_TELEMETRY_ENABLED=true
OFFER_EVALUATION_AGENT_TELEMETRY_ENABLED=true
PURCHASE_ORDER_AGENT_TELEMETRY_ENABLED=true
```

The default in-container OTLP endpoint is:

```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

The default OpenTelemetry resource attributes are:

```env
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=local
```

## Start

Run from the Docker Compose folder:

```bash
cd deployments/docker-compose
docker compose --profile observability up -d --build
```

To include the web UI as well:

```bash
docker compose --profile observability --profile ui up -d --build
```

## Generate Metrics

From the repository root, invoke the workflow after the stack is running:

```bash
conda run -n a2a-procurement-agents \
  python services/procurement-orchestrator/examples/test_client.py
```

The Locus telemetry hook emits native Locus metrics such as:

- `locus.invocations`
- `locus.invocation.duration`

When exported to Prometheus, metric names are normalized. For example, dotted names commonly appear with underscores, such as `locus_invocations_total`.

## Verify

Check the Collector Prometheus endpoint:

```bash
curl http://127.0.0.1:9464/metrics
```

Check Prometheus targets:

```text
http://127.0.0.1:9090/targets
```

The `otel-collector` target should be `UP`.

Open Grafana:

```text
http://127.0.0.1:3001
```

The Prometheus datasource is provisioned automatically. The dashboard is available under:

```text
A2A Procurement / A2A Procurement Agent Telemetry
```

## Troubleshooting

If Grafana is empty, first generate at least one workflow invocation and wait for the Prometheus scrape interval.

If Prometheus has no `locus_*` metrics, verify that the agent telemetry flags are set to `true` and that the agents were restarted after changing `.env`.

If the Collector has metrics but Prometheus does not, open `http://127.0.0.1:9090/targets` and confirm that the `otel-collector` scrape target is `UP`.

If port `3001` conflicts with another local service, set:

```env
GRAFANA_PORT=3002
```

If port `9090` conflicts, set:

```env
PROMETHEUS_PORT=9091
```

## Stop

Stop the stack:

```bash
docker compose --profile observability down
```

To remove Prometheus and Grafana local volumes:

```bash
docker compose --profile observability down -v
```
