#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./stop_demo.sh [options]

Stop the local A2A Procurement Agents demo.

Options:
  --volumes       Also remove Docker Compose volumes.
  --docker-context CTX
                  Use a specific Docker context.
  -h, --help      Show this help message.

Examples:
  ./stop_demo.sh
  ./stop_demo.sh --volumes
EOF
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deployments/docker-compose/docker-compose.yml"

REMOVE_VOLUMES=false
DOCKER_CONTEXT_NAME="${DEMO_DOCKER_CONTEXT:-${DOCKER_CONTEXT:-}}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --volumes)
      REMOVE_VOLUMES=true
      ;;
    --docker-context)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --docker-context." >&2
        exit 2
      fi
      DOCKER_CONTEXT_NAME="$2"
      shift
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

COMPOSE_ARGS=(-f "${COMPOSE_FILE}" --profile ui --profile observability)
DOWN_ARGS=(down)
DOCKER_CMD=(docker)

if [ -n "${DOCKER_CONTEXT_NAME}" ]; then
  DOCKER_CMD+=(--context "${DOCKER_CONTEXT_NAME}")
fi

if [ "${REMOVE_VOLUMES}" = true ]; then
  DOWN_ARGS+=(-v)
fi

echo "Stopping A2A Procurement Agents demo..."
"${DOCKER_CMD[@]}" compose "${COMPOSE_ARGS[@]}" "${DOWN_ARGS[@]}"
echo "Demo stack stopped."
