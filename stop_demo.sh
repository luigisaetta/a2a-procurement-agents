#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./stop_demo.sh [options]

Stop the local A2A Procurement Agents demo.

Options:
  --volumes       Also remove Docker Compose volumes.
  -h, --help      Show this help message.

Examples:
  ./stop_demo.sh
  ./stop_demo.sh --volumes
EOF
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deployments/docker-compose/docker-compose.yml"

REMOVE_VOLUMES=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --volumes)
      REMOVE_VOLUMES=true
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

if [ "${REMOVE_VOLUMES}" = true ]; then
  DOWN_ARGS+=(-v)
fi

echo "Stopping A2A Procurement Agents demo..."
docker compose "${COMPOSE_ARGS[@]}" "${DOWN_ARGS[@]}"
echo "Demo stack stopped."
