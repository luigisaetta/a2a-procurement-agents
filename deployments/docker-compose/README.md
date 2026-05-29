# Docker Compose Deployment

This folder contains the first Docker Compose deployment for running the local A2A procurement agent network.

The current compose stack runs:

- MySQL demo data store on port `3306`
- Procurement Data MCP Server on port `8011`
- Bid Collection Agent on port `8000`
- Offer Evaluation Agent on port `8001`
- Purchase Order Agent on port `8002`
- Procurement Orchestrator on port `8003`
- Conversational Procurement Intake Layer on port `8012`
- Procurement Intake Web UI on port `3000` when the optional `ui` profile is enabled

The agents are built as independent containers and communicate through their A2A HTTP contracts. The Bid Collection Agent reads supplier master data through the Procurement Data MCP Server. The Procurement Orchestrator calls the Bid Collection, Offer Evaluation, and Purchase Order agents through A2A.

The Conversational Procurement Intake Layer is not an A2A agent. It serves the UI through HTTP, uses an LLM extractor by default, calls the Procurement Orchestrator through an A2A client, and relays orchestration progress to the UI through Server-Sent Events.

The Procurement Intake Web UI is a Next.js application. It proxies browser requests to the Conversational Procurement Intake Layer through `/api/intake` and renders workflow progress in real time.

The UI container is optional because it requires the Node base image from Docker Hub. If Docker Hub access is blocked by a corporate TLS proxy, start the backend stack with Compose and run the UI locally with npm.

## Prerequisites

- Docker with Compose support
- OCI API key configuration for the Offer Evaluation Agent
- access to the Oracle Locus SDK package used by the runtime image

The Purchase Order Agent does not call an LLM, but it keeps the same runtime environment contract for consistency with the rest of the platform.

MySQL is used as a local demo data store for the minimal procurement data model. It is initialized with the synthetic automotive seed CSV files from [../../specs/examples/data](../../specs/examples/data).

The Procurement Data MCP Server exposes read-only MCP tools backed by the MySQL demo data store.

## Environment

Create a local compose environment file:

```bash
cp deployments/docker-compose/.env.example deployments/docker-compose/.env
```

For the end-to-end demo, update:

- `OCI_REGION`
- `OCI_MODEL_ID`
- `OCI_COMPARTMENT_ID`
- `AGENT_API_KEY`
- `OCI_CONFIG_DIR`

`OCI_CONFIG_DIR` must point to the local directory containing the OCI config and API key files. The compose stack mounts it read-only at `/root/.oci` for the Offer Evaluation Agent and Conversational Procurement Intake Layer.

The remaining values in `.env.example` have local-demo defaults. Override them only when a port, database password, or internal service URL conflicts with your environment.

The end-to-end demo client needs only:

- `PROCUREMENT_ORCHESTRATOR_PORT`
- `CONVERSATIONAL_INTAKE_PORT`
- `PROCUREMENT_INTAKE_UI_PORT`
- `AGENT_API_KEY`

Both values are read from the shell environment first and then from this compose `.env` file.

## Build

Run from this folder:

```bash
cd deployments/docker-compose
docker compose build
```

To build only the orchestrator image:

```bash
docker compose build procurement-orchestrator
```

## Start

Run the backend stack:

```bash
cd deployments/docker-compose
docker compose up -d
```

To rebuild and start in one command:

```bash
docker compose up -d --build
```

To include the UI container as well:

```bash
docker compose --profile ui up -d --build
```

For the recommended local UI test when Docker Hub cannot pull `node:22-slim`, start the backend stack with Compose and run the UI from the repository root in a second shell:

```bash
cd services/procurement-intake-ui
CONVERSATIONAL_INTAKE_BASE_URL=http://127.0.0.1:8012 \
  npm run dev -- --hostname 127.0.0.1 --port 3000
```

The Agent Cards are available at:

```text
http://127.0.0.1:8001/.well-known/agent-card.json
http://127.0.0.1:8002/.well-known/agent-card.json
```

The Bid Collection Agent Card is available at:

```text
http://127.0.0.1:8000/.well-known/agent-card.json
```

The Procurement Orchestrator Agent Card is available at:

```text
http://127.0.0.1:8003/.well-known/agent-card.json
```

All A2A routes require bearer authentication with `AGENT_API_KEY`.

The Conversational Procurement Intake Layer HTTP API is available at:

```text
http://127.0.0.1:8012
```

It is an application service, so it does not expose an Agent Card.

The Procurement Intake Web UI is available at this URL when either the `ui` Compose profile or the local Next.js dev server is running:

```text
http://127.0.0.1:3000
```

The MCP endpoint is available at:

```text
http://127.0.0.1:8011/mcp
```

The MCP server always uses streamable HTTP, including local development.

The MySQL service creates the `procurement_demo` schema on first startup and loads:

- `plants`
- `parts`
- `suppliers`
- `supplier_parts`

The workflow tables `procurement_requests`, `supplier_offers`, and `purchase_orders` are created empty.

## End-to-End Client

After the stack is running, invoke the Procurement Orchestrator from the repository root:

```bash
conda run -n a2a-procurement-agents \
  python services/procurement-orchestrator/examples/test_client.py
```

The client sends an embedded sample payload to the orchestrator and prints the A2A streaming events. Edit `SAMPLE_PAYLOAD` in [../../services/procurement-orchestrator/examples/test_client.py](../../services/procurement-orchestrator/examples/test_client.py) to change the test request.

The full conversational end-to-end path starts from the Conversational Procurement Intake Layer:

```text
UI/client -> Conversational Intake HTTP API -> LLM extraction -> A2A Orchestrator client -> Procurement Orchestrator -> downstream agents
```

From the browser, use the Procurement Intake Web UI:

```text
http://127.0.0.1:3000
```

The initial service exposes:

- `POST /sessions`
- `POST /sessions/{session_id}/messages`
- `POST /sessions/{session_id}/confirm`
- `GET /sessions/{session_id}/events` for SSE
- `GET /sessions/{session_id}/orchestration-events` for polling fallback

To print only the final task artifact:

```bash
conda run -n a2a-procurement-agents \
  python services/procurement-orchestrator/examples/test_client.py --no-stream
```

## Verify

In another shell:

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

Verify the demo data store:

```bash
docker compose exec mysql sh -c '
  mysql -u root -p"$MYSQL_ROOT_PASSWORD" procurement_demo \
    -e "SELECT COUNT(*) AS plants FROM plants;
        SELECT COUNT(*) AS parts FROM parts;
        SELECT COUNT(*) AS suppliers FROM suppliers;
        SELECT COUNT(*) AS supplier_parts FROM supplier_parts;"
'
```

Verify the MCP service is listening:

```bash
curl -i http://127.0.0.1:8011/mcp
```

The endpoint is an MCP streamable HTTP endpoint, so a plain browser or curl request may return a protocol-level error. A reachable HTTP response confirms that the service is running.

## Stop

```bash
cd deployments/docker-compose
docker compose down
```

To reset the MySQL volume and reload seed data:

```bash
docker compose down -v
docker compose up --build
```

## Logs

Show all logs:

```bash
cd deployments/docker-compose
docker compose logs -f
```

Follow only the orchestrator logs:

```bash
docker compose logs -f procurement-orchestrator
```

Follow the main end-to-end path:

```bash
docker compose logs -f \
  procurement-intake-ui \
  conversational-procurement-intake \
  procurement-orchestrator \
  bid-collection-agent \
  offer-evaluation-agent \
  purchase-order-agent
```

## Notes

The Dockerfile uses a shared runtime image pattern but copies each service folder into its own image. This keeps the deployment simple while preserving the project rule that agents do not share business runtime code.

If `locus-sdk==0.2.0b23` is not available from the package index used by Docker, replace the dependency source in `requirements.txt` or override the Dockerfile with an internal base image that already contains Locus.

MySQL initialization scripts run only when the `mysql-data` volume is empty. The seed loader uses `LOAD DATA LOCAL INFILE` against the CSV files mounted from `specs/examples/data`. Changing seed CSV files after the first startup requires recreating the volume with `docker compose down -v`.
