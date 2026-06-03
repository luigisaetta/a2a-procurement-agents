#!/usr/bin/env bash
set -euo pipefail

CONDA_ENV="${CONDA_ENV:-a2a-procurement-agents}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="${ROOT_DIR}/services/procurement-intake-ui"

PYTHON_SRC_DIRS=(
  "services/bid-collection-agent/src"
  "services/conversational-procurement-intake/src"
  "services/offer-evaluation-agent/src"
  "services/procurement-data-mcp/src"
  "services/procurement-orchestrator/src"
  "services/purchase-order-agent/src"
)

PYTHON_PACKAGES=(
  "services/bid-collection-agent/src/bid_collection_agent"
  "services/conversational-procurement-intake/src/conversational_procurement_intake"
  "services/offer-evaluation-agent/src/offer_evaluation_agent"
  "services/procurement-data-mcp/src/procurement_data_mcp"
  "services/procurement-orchestrator/src/procurement_orchestrator"
  "services/purchase-order-agent/src/purchase_order_agent"
)

PYTHON_CHECK_PATHS=(
  "${PYTHON_PACKAGES[@]}"
  "tests"
  "services/bid-collection-agent/tests"
  "services/conversational-procurement-intake/tests"
  "services/offer-evaluation-agent/tests"
  "services/procurement-data-mcp/tests"
  "services/procurement-orchestrator/tests"
  "services/purchase-order-agent/tests"
)

build_pythonpath() {
  local pythonpath=""
  local src_dir

  for src_dir in "${PYTHON_SRC_DIRS[@]}"; do
    if [[ -z "${pythonpath}" ]]; then
      pythonpath="${ROOT_DIR}/${src_dir}"
    else
      pythonpath="${pythonpath}:${ROOT_DIR}/${src_dir}"
    fi
  done

  printf '%s' "${pythonpath}"
}

run_step() {
  local label="$1"
  shift

  printf '\n==> %s\n' "${label}"
  "$@"
}

run_python_tool() {
  local pythonpath

  pythonpath="$(build_pythonpath)"
  PYTHONPATH="${pythonpath}${PYTHONPATH:+:${PYTHONPATH}}" \
    conda run -n "${CONDA_ENV}" "$@"
}

require_ui_dependencies() {
  if [[ ! -d "${UI_DIR}/node_modules" ]]; then
    printf '\nMissing UI dependencies in %s/node_modules.\n' "${UI_DIR}" >&2
    printf 'Run: cd services/procurement-intake-ui && npm ci\n' >&2
    return 1
  fi
}

cd "${ROOT_DIR}"

run_step "Black format check" \
  run_python_tool black --check "${PYTHON_CHECK_PATHS[@]}"

run_step "Pylint" \
  run_python_tool pylint --persistent=n --disable=duplicate-code "${PYTHON_PACKAGES[@]}"

run_step "Pytest" \
  run_python_tool pytest

run_step "Procurement Intake UI dependencies" \
  require_ui_dependencies

run_step "Procurement Intake UI typecheck" \
  npm --prefix "${UI_DIR}" run typecheck

printf '\nAll checks passed.\n'
