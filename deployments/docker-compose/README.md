# Docker Compose Deployment

This folder contains the first Docker Compose deployment for running the local A2A procurement agent network.

The current compose stack runs:

- Offer Evaluation Agent on port `8001`
- Purchase Order Agent on port `8002`

Both services are built as independent containers and communicate through their A2A HTTP contracts.

## Prerequisites

- Docker with Compose support
- OCI API key configuration for the Offer Evaluation Agent
- access to the Oracle Locus SDK package used by the runtime image

The Purchase Order Agent does not call an LLM, but it keeps the same runtime environment contract for consistency with the rest of the platform.

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

All A2A routes require bearer authentication with `AGENT_API_KEY`.

## Verify

In another shell:

```bash
curl -H "Authorization: Bearer $AGENT_API_KEY" \
  http://127.0.0.1:8001/.well-known/agent-card.json

curl -H "Authorization: Bearer $AGENT_API_KEY" \
  http://127.0.0.1:8002/.well-known/agent-card.json
```

## Stop

```bash
docker compose down
```

## Notes

The Dockerfile uses a shared runtime image pattern but copies each service folder into its own image. This keeps the deployment simple while preserving the project rule that agents do not share business runtime code.

If `locus-sdk==0.2.0b22` is not available from the package index used by Docker, replace the dependency source in `requirements.txt` or override the Dockerfile with an internal base image that already contains Locus.
