# Purchase Order Agent Quickstart

This guide starts the Purchase Order Agent as a local Locus A2A server.

## Prerequisites

Use the `locus` conda environment:

```bash
conda activate locus
```

The environment must include Locus and the development tools used by this repository.

## Environment

Create a local environment file from the example:

```bash
cp services/purchase-order-agent/.env.example services/purchase-order-agent/.env
```

Set these values in `services/purchase-order-agent/.env` or export them in the shell before starting the server:

```bash
OCI_REGION=us-chicago-1
OCI_AUTH=API_KEY
OCI_MODEL_ID=openai.gpt-5
OCI_COMPARTMENT_ID=ocid1.compartment.oc1..example
PURCHASE_ORDER_AGENT_PORT=8002
AGENT_API_KEY=change-me
```

Environment variables already present in the shell take precedence. Missing values are loaded from the local `.env` file.

The initial Purchase Order Agent does not call an LLM, but it keeps the same OCI runtime variables used by the other agents for operational consistency.

## Start The Server

Run the A2A server from the repository root:

```bash
PYTHONPATH=services/purchase-order-agent/src \
python -m purchase_order_agent.server
```

The server publishes its Agent Card at:

```text
http://127.0.0.1:8002/.well-known/agent-card.json
```

All A2A routes require bearer authentication with `AGENT_API_KEY`.

## Verify

Check the Agent Card:

```bash
curl -H "Authorization: Bearer $AGENT_API_KEY" \
  http://127.0.0.1:8002/.well-known/agent-card.json
```

## Payload Contract

The agent accepts `application/json` input matching:

```text
specs/schemas/create-purchase-order-request.schema.json
```

It returns `application/json` output matching:

```text
specs/schemas/create-purchase-order-response.schema.json
```

The current purchase order system call is a deterministic fake wrapper implemented in:

```text
services/purchase-order-agent/src/purchase_order_agent/po_system.py
```
