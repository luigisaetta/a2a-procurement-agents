# Agent Catalog

This catalog describes the agents planned and developed in this project.

The README keeps only a short public-facing list of agents. This document provides the deeper operational descriptions that will grow as new agents are specified, implemented, and integrated through A2A.

## Draft Agent Network

| Agent | Status | Service Folder | Purpose |
| --- | --- | --- | --- |
| Procurement Orchestrator | Planned | `services/procurement-orchestrator` | Coordinates the end-to-end procurement workflow across specialized A2A agents. |
| Supplier Discovery Agent | Planned | `services/supplier-discovery-agent` | Identifies candidate suppliers for a procurement request. |
| Bid Invitation Agent | Planned | `services/bid-invitation-agent` | Sends bid invitations to selected suppliers. |
| Bid Collection Agent | Planned | `services/bid-collection-agent` | Collects supplier bids and prepares them for evaluation. |
| Offer Evaluation Agent | Initial A2A server implementation | `services/offer-evaluation-agent` | Evaluates supplier offers, applies procurement policy, selects the winning offer, and returns an explanation. |
| Compliance Agent | Planned | `services/compliance-agent` | Checks procurement decisions and supplier data against compliance rules. |
| Purchase Order Agent | Draft specification | `services/purchase-order-agent` | Registers purchase orders in the company purchase order system and returns a technical confirmation. |

---

## Procurement Orchestrator

Status: Planned

The Procurement Orchestrator coordinates the overall procurement flow. It is responsible for invoking specialized agents through A2A, passing task context between them, and collecting their results into a coherent workflow.

The orchestrator should not own supplier discovery, bid evaluation, compliance, or purchase order business logic. Those responsibilities remain with specialized agents.

## Supplier Discovery Agent

Status: Planned

The Supplier Discovery Agent identifies candidate suppliers for a procurement request.

Future specifications will define the input criteria, supplier data sources, and output contract for discovered supplier candidates.

## Bid Invitation Agent

Status: Planned

The Bid Invitation Agent sends bid invitations to selected suppliers.

Future specifications will define invitation payloads, supplier contact requirements, response deadlines, and delivery tracking.

## Bid Collection Agent

Status: Planned

The Bid Collection Agent collects supplier bids and normalizes them into the offer format required by the Offer Evaluation Agent.

Future specifications will define bid ingestion, validation, deadline handling, and handoff to offer evaluation.

## Offer Evaluation Agent

Status: Initial A2A server implementation

Specification: [specs/agents/offer-evaluation-agent.md](specs/agents/offer-evaluation-agent.md)

Default policy: [services/offer-evaluation-agent/policies/standard-urgent-procurement-v1.md](services/offer-evaluation-agent/policies/standard-urgent-procurement-v1.md)

Server entry point: [services/offer-evaluation-agent/src/offer_evaluation_agent/server.py](services/offer-evaluation-agent/src/offer_evaluation_agent/server.py)

The Offer Evaluation Agent receives supplier offers for a procurement request and determines the best offer according to configurable procurement policy.

The current policy is deterministic and intentionally simple:

- exclude offers with a currency different from the request currency
- exclude offers with delivery dates later than the requested delivery date
- select the lowest-cost eligible offer
- use supplier reliability and earlier delivery date as tie-breakers
- return either a selected offer decision or a no-valid-offers decision

### Responsibilities

The agent is responsible for:

- receiving a list of supplier offers
- validating input payloads
- loading local evaluation policies
- applying policy selection logic
- selecting the winning supplier offer when one is eligible
- returning a no-valid-offers decision when every offer is excluded
- generating a concise explanation of the decision
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

- `request_id`
- `decision`
- `explanation`

## Compliance Agent

Status: Planned

The Compliance Agent checks procurement decisions, supplier information, and purchasing context against compliance requirements.

Future specifications will define compliance checks, approval outcomes, exception handling, and audit evidence.

## Purchase Order Agent

Status: Draft specification

Specification: [specs/agents/purchase-order-agent.md](specs/agents/purchase-order-agent.md)

The Purchase Order Agent registers purchase orders in the company purchase order system after an approved supplier decision.

The initial design is deterministic and does not use an LLM.

Future implementation will isolate the enterprise system integration behind a local wrapper module so the A2A contract can remain stable while the backend integration evolves.
