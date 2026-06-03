# Docker Compose End-to-End Demo Test

This directory contains the opt-in end-to-end test for the local Docker Compose demo.

The test verifies the core A2A workflow:

- Docker Compose services are reachable.
- The Procurement Orchestrator Agent Card is served.
- A structured procurement request is submitted through A2A streaming.
- Orchestration events are emitted.
- Bid collection completes.
- Offer evaluation selects a winning offer.
- Purchase order creation completes.
- The final orchestration response reports created purchase orders for all requested parts.

## Why This Test Is Opt-In

The test depends on Docker Compose, local ports, the `a2a-procurement-agents` conda environment, and valid demo configuration in `deployments/docker-compose/.env`.

It is intentionally excluded from the default `pytest` run and from `./check.sh`.

## Prerequisites

From the repository root, create the Docker Compose environment file if needed:

```bash
cp deployments/docker-compose/.env.example deployments/docker-compose/.env
```

Edit `deployments/docker-compose/.env` and confirm these values are valid:

- `OCI_REGION`
- `OCI_AUTH`
- `OCI_MODEL_ID`
- `OCI_COMPARTMENT_ID`
- `OCI_PROFILE`
- `OCI_CONFIG_DIR`
- `AGENT_API_KEY`

Docker must be running and reachable by the current shell.

## Run

Run the complete managed test:

```bash
./run_e2e_demo_test.sh
```

Run without rebuilding images:

```bash
./run_e2e_demo_test.sh --no-build
```

Use a non-default Docker context:

```bash
./run_e2e_demo_test.sh --docker-context desktop-linux
```

Leave the stack running after the test:

```bash
./run_e2e_demo_test.sh --keep-running
```

Include optional demo profiles:

```bash
./run_e2e_demo_test.sh --ui --observability
```

## Run Against An Already Running Stack

If the Docker Compose stack is already running, execute only the pytest test:

```bash
conda run -n a2a-procurement-agents pytest -m e2e tests/e2e
```

## Scope

This test validates the core backend workflow. It does not inspect the browser UI and does not assert Grafana dashboard contents.

UI and observability checks remain documented in `docs/e2e-demo.md` and `RUNBOOK.md`.
