# Docker Compose Deployment

This folder contains the first Docker Compose deployment for running the local A2A procurement agent network.

The current compose stack runs:

- MySQL demo data store on port `3306`
- Procurement Data MCP Server on port `8010`
- Bid Collection Agent on port `8000`
- Offer Evaluation Agent on port `8001`
- Purchase Order Agent on port `8002`
- Procurement Orchestrator on port `8003`

The agents are built as independent containers and communicate through their A2A HTTP contracts. The Bid Collection Agent reads supplier master data through the Procurement Data MCP Server. The Procurement Orchestrator calls the Bid Collection, Offer Evaluation, and Purchase Order agents through A2A.

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

Update:

- `OCI_REGION`
- `OCI_MODEL_ID`
- `OCI_COMPARTMENT_ID`
- `AGENT_API_KEY`
- `OCI_CONFIG_DIR`
- `MYSQL_ROOT_PASSWORD`
- `MYSQL_PASSWORD`
- `PROCUREMENT_DATA_MCP_PORT`
- `PROCUREMENT_DATA_MCP_URL`
- `BID_COLLECTION_AGENT_URL`
- `OFFER_EVALUATION_AGENT_URL`
- `PURCHASE_ORDER_AGENT_URL`

`OCI_CONFIG_DIR` must point to the local directory containing the OCI config and API key files. The compose stack mounts it read-only at `/root/.oci` for the Offer Evaluation Agent.

## Start

Run from this folder:

```bash
cd deployments/docker-compose
docker compose up --build
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

The MCP endpoint is available at:

```text
http://127.0.0.1:8010/mcp
```

The MCP server always uses streamable HTTP, including local development.

The MySQL service creates the `procurement_demo` schema on first startup and loads:

- `plants`
- `parts`
- `suppliers`
- `supplier_parts`

The workflow tables `procurement_requests`, `supplier_offers`, and `purchase_orders` are created empty.

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
curl -i http://127.0.0.1:8010/mcp
```

The endpoint is an MCP streamable HTTP endpoint, so a plain browser or curl request may return a protocol-level error. A reachable HTTP response confirms that the service is running.

## Stop

```bash
docker compose down
```

To reset the MySQL volume and reload seed data:

```bash
docker compose down -v
docker compose up --build
```

## Notes

The Dockerfile uses a shared runtime image pattern but copies each service folder into its own image. This keeps the deployment simple while preserving the project rule that agents do not share business runtime code.

If `locus-sdk==0.2.0b23` is not available from the package index used by Docker, replace the dependency source in `requirements.txt` or override the Dockerfile with an internal base image that already contains Locus.

MySQL initialization scripts run only when the `mysql-data` volume is empty. The seed loader uses `LOAD DATA LOCAL INFILE` against the CSV files mounted from `specs/examples/data`. Changing seed CSV files after the first startup requires recreating the volume with `docker compose down -v`.
