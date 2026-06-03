#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./run_e2e_demo_test.sh [options]

Start the Docker Compose demo stack and run the opt-in end-to-end test.

Options:
  --ui                  Include the Procurement Intake Web UI profile.
  --observability       Include the observability profile.
  --docker-context CTX  Use a specific Docker context.
  --no-build            Start the stack without rebuilding images.
  --keep-running        Leave the Docker Compose stack running after the test.
  -h, --help            Show this help message.

Examples:
  ./run_e2e_demo_test.sh
  ./run_e2e_demo_test.sh --no-build
  ./run_e2e_demo_test.sh --ui --observability --keep-running
EOF
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_ENV="${CONDA_ENV:-a2a-procurement-agents}"

START_ARGS=()
STOP_ARGS=()
KEEP_RUNNING=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --ui|--observability|--no-build)
      START_ARGS+=("$1")
      ;;
    --docker-context)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --docker-context." >&2
        exit 2
      fi
      START_ARGS+=("$1" "$2")
      STOP_ARGS+=("$1" "$2")
      shift
      ;;
    --keep-running)
      KEEP_RUNNING=true
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

cleanup() {
  if [ "${KEEP_RUNNING}" = false ]; then
    "${REPO_ROOT}/stop_demo.sh" "${STOP_ARGS[@]}"
  fi
}

trap cleanup EXIT

cd "${REPO_ROOT}"

"${REPO_ROOT}/start_demo.sh" "${START_ARGS[@]}"

conda run -n "${CONDA_ENV}" pytest -m e2e tests/e2e
