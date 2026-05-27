# Offer Evaluation Agent Quickstart

This guide starts the Offer Evaluation Agent as a local Locus A2A server.

## Prerequisites

Use the `locus` conda environment:

```bash
conda activate locus
```

The environment must include Locus and the development tools used by this repository.

## Environment

Create a local environment file from the example:

```bash
cp services/offer-evaluation-agent/.env.example services/offer-evaluation-agent/.env
```

Set these values in `services/offer-evaluation-agent/.env` or export them in the shell before starting the server:

```bash
OCI_REGION=us-chicago-1
OCI_AUTH=API_KEY
OCI_MODEL_ID=openai.gpt-5
OCI_COMPARTMENT_ID=ocid1.compartment.oc1..example
OFFER_EVALUATION_AGENT_PORT=8001
AGENT_API_KEY=change-me
```

Environment variables already present in the shell take precedence. Missing values are loaded from the local `.env` file.

`OCI_AUTH=API_KEY` uses the OCI config profile named by `OCI_PROFILE`, or `DEFAULT` when `OCI_PROFILE` is not set.

## Start The Server

Run the A2A server from the repository root:

```bash
PYTHONPATH=services/offer-evaluation-agent/src \
python -m offer_evaluation_agent.server
```

The server publishes its Agent Card at:

```text
http://127.0.0.1:8001/.well-known/agent-card.json
```

All A2A routes require bearer authentication with `AGENT_API_KEY`.

## Verify

Check the Agent Card:

```bash
curl -H "Authorization: Bearer $AGENT_API_KEY" \
  http://127.0.0.1:8001/.well-known/agent-card.json
```
