# Agent Catalog

This catalog describes the agents planned and developed in this project.

The README keeps only a short public-facing list of agents. This document provides the deeper operational descriptions that will grow as new agents are specified, implemented, and integrated through A2A.

## Draft Agent Network

| Agent | Status | Service Folder | Purpose |
| --- | --- | --- | --- |
| Procurement Orchestrator | Draft specification | `services/procurement-orchestrator` | Coordinates the end-to-end procurement workflow across specialized A2A agents. |
| Bid Collection Agent | Initial A2A server implementation | `services/bid-collection-agent` | Identifies suppliers through MCP, requests offers, collects bids, and prepares them for evaluation. |
| Offer Evaluation Agent | Initial A2A server implementation | `services/offer-evaluation-agent` | Evaluates supplier offers, applies procurement policy, selects the winning offer, and returns an explanation. |
| Compliance Agent | Planned | `services/compliance-agent` | Checks procurement decisions and supplier data against compliance rules. |
| Purchase Order Agent | Initial A2A server implementation | `services/purchase-order-agent` | Registers purchase orders in the company purchase order system and returns a technical confirmation. |

---

## Procurement Orchestrator

Status: Draft specification

The Procurement Orchestrator coordinates the overall procurement flow. It is responsible for invoking specialized agents through A2A, passing task context between them, and collecting their results into a coherent workflow.

The orchestrator should not own supplier discovery, bid evaluation, compliance, or purchase order business logic. Those responsibilities remain with specialized agents.

Specification: [specs/agents/procurement-orchestrator.md](specs/agents/procurement-orchestrator.md)

The initial orchestrator contract is JSON-only. Natural-language intake is handled by a separate conversational layer that converts operator requests into a structured `ProcurementOrchestrationRequest`.

The orchestrator streams progress events, retries bid collection when no valid offer is selected, and optionally creates purchase orders after a winning offer is selected.

## Bid Collection Agent

Status: Initial A2A server implementation

The Bid Collection Agent identifies eligible suppliers, sends bid requests, receives supplier offers, and normalizes those offers into the format required by the Offer Evaluation Agent.

Specification: [specs/agents/bid-collection-agent.md](specs/agents/bid-collection-agent.md)

Server entry point: [services/bid-collection-agent/src/bid_collection_agent/server.py](services/bid-collection-agent/src/bid_collection_agent/server.py)

Each requested part carries sourcing hints rather than a preselected supplier list. The agent uses the Procurement Data MCP Server for supplier discovery and keeps supplier offer calls behind a provider abstraction so simulated supplier APIs can later be replaced by real integrations without changing the external A2A contract.

### Responsibilities

The agent is responsible for:

- receiving requested procurement parts and sourcing constraints
- identifying eligible suppliers for each requested part through MCP
- building supplier-specific bid requests
- contacting supplier APIs through a provider boundary
- collecting successful offers
- recording declined or failed supplier responses
- generating downstream offer evaluation request payloads

### Non Responsibilities

The agent does not:

- evaluate offers
- select the winning supplier offer
- create purchase orders
- orchestrate the full procurement workflow

### A2A Capability

The agent will expose the `collect_bids` skill through its Agent Card.

The skill returns identified suppliers, normalized offers grouped by part, and `EvaluateOffersRequest` payloads ready for the Offer Evaluation Agent.

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

Status: Initial A2A server implementation

Specification: [specs/agents/purchase-order-agent.md](specs/agents/purchase-order-agent.md)

Server entry point: [services/purchase-order-agent/src/purchase_order_agent/server.py](services/purchase-order-agent/src/purchase_order_agent/server.py)

Quickstart: [services/purchase-order-agent/QUICKSTART.md](services/purchase-order-agent/QUICKSTART.md)

The Purchase Order Agent registers purchase orders in the company purchase order system after an approved supplier decision.

The initial design is deterministic and does not use an LLM.

The current implementation exposes an A2A server with the `create_purchase_order` skill. It validates JSON input, calls a local fake purchase order system wrapper, and returns a structured JSON confirmation.

The enterprise system integration is isolated behind a local wrapper module so the A2A contract can remain stable while the backend integration evolves.
