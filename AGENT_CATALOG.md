# Agent Catalog

This catalog describes the agents developed in this project.

The README keeps only a short public-facing list of agents. This document provides the deeper operational descriptions that will grow as new agents are specified, implemented, and integrated through A2A.

## Offer Evaluation Agent

Status: Draft specification

Specification: [specs/agents/offer-evaluation-agent.md](specs/agents/offer-evaluation-agent.md)

The Offer Evaluation Agent receives supplier offers for a procurement request and determines the best offer according to configurable procurement policy.

The evaluation logic is driven by Markdown policy documents. This keeps procurement rules explicit, reviewable, and versionable while allowing the implementation to focus on validation, scoring, ranking, and explainability.

### Responsibilities

The agent is responsible for:

- receiving a list of supplier offers
- validating input payloads
- loading evaluation policies
- applying scoring logic
- ranking offers
- selecting the winning supplier
- generating explainable evaluation output
- returning structured validation or processing errors

### Non Responsibilities

The agent does not:

- contact suppliers
- negotiate offers
- generate purchase orders
- persist workflow state
- manage workflow orchestration

### A2A Capability

The agent exposes the `evaluate_offers` skill through its Agent Card.

The skill evaluates supplier offers according to procurement policy and returns a structured result containing:

- the selected winning supplier
- ranked offers
- scoring details
- applied policy information
- explainable evaluation rationale

### Enterprise Notes

The agent is designed to support future enterprise capabilities, including:

- structured JSON logging
- distributed tracing
- checkpointing through Oracle Database
- authentication and authorization
- policy versioning
- human approval workflows
