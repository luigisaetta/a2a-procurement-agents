#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./start_demo.sh [options]

Start the local A2A Procurement Agents demo with Docker Compose.

Options:
  --ui                 Include the Procurement Intake Web UI profile.
  --observability      Include OpenTelemetry Collector, Prometheus, and Grafana.
                       Also enables telemetry for all A2A agents.
  --no-build           Start without rebuilding images.
  -h, --help           Show this help message.

Examples:
  ./start_demo.sh
  ./start_demo.sh --ui
  ./start_demo.sh --observability
  ./start_demo.sh --ui --observability
EOF
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deployments/docker-compose/docker-compose.yml"
ENV_FILE="${REPO_ROOT}/deployments/docker-compose/.env"

INCLUDE_UI=false
INCLUDE_OBSERVABILITY=false
BUILD_FLAG="--build"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --ui)
      INCLUDE_UI=true
      ;;
    --observability)
      INCLUDE_OBSERVABILITY=true
      ;;
    --no-build)
      BUILD_FLAG=""
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [ ! -f "${ENV_FILE}" ]; then
  echo "Missing ${ENV_FILE}."
  echo "Create it with:"
  echo "  cp deployments/docker-compose/.env.example deployments/docker-compose/.env"
  exit 1
fi

set -a
# shellcheck source=/dev/null
. "${ENV_FILE}"
set +a

COMPOSE_ARGS=(-f "${COMPOSE_FILE}")

if [ "${INCLUDE_UI}" = true ]; then
  COMPOSE_ARGS+=(--profile ui)
fi

if [ "${INCLUDE_OBSERVABILITY}" = true ]; then
  COMPOSE_ARGS+=(--profile observability)
  export PROCUREMENT_ORCHESTRATOR_TELEMETRY_ENABLED=true
  export BID_COLLECTION_AGENT_TELEMETRY_ENABLED=true
  export OFFER_EVALUATION_AGENT_TELEMETRY_ENABLED=true
  export PURCHASE_ORDER_AGENT_TELEMETRY_ENABLED=true
  export OTEL_EXPORTER_OTLP_ENDPOINT="${OTEL_EXPORTER_OTLP_ENDPOINT:-http://otel-collector:4317}"
  export OTEL_METRICS_EXPORTER="${OTEL_METRICS_EXPORTER:-otlp}"
  export OTEL_TRACES_EXPORTER="${OTEL_TRACES_EXPORTER:-otlp}"
  export OTEL_RESOURCE_ATTRIBUTES="${OTEL_RESOURCE_ATTRIBUTES:-deployment.environment=local}"
fi

echo "Starting A2A Procurement Agents demo..."
if [ "${INCLUDE_OBSERVABILITY}" = true ]; then
  echo "Observability enabled: agent telemetry flags are set to true for this run."
fi

if [ -n "${BUILD_FLAG}" ]; then
  docker compose "${COMPOSE_ARGS[@]}" up -d "${BUILD_FLAG}"
else
  docker compose "${COMPOSE_ARGS[@]}" up -d
fi

echo
echo "Demo stack started."
echo "Core endpoints:"
echo "  Procurement Orchestrator: http://127.0.0.1:${PROCUREMENT_ORCHESTRATOR_PORT:-8003}"
echo "  Conversational Intake:    http://127.0.0.1:${CONVERSATIONAL_INTAKE_PORT:-8012}"

if [ "${INCLUDE_UI}" = true ]; then
  echo "  Procurement Intake UI:    http://127.0.0.1:${PROCUREMENT_INTAKE_UI_PORT:-3000}"
fi

if [ "${INCLUDE_OBSERVABILITY}" = true ]; then
  echo "Observability endpoints:"
  echo "  Collector metrics:        http://127.0.0.1:${OTEL_PROMETHEUS_PORT:-9464}/metrics"
  echo "  Prometheus:               http://127.0.0.1:${PROMETHEUS_PORT:-9090}"
  echo "  Grafana:                  http://127.0.0.1:${GRAFANA_PORT:-3001}"
fi
