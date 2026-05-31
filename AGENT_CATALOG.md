# Agent Catalog

This catalog describes the agents and adjacent system components planned and developed in this project.

The README keeps only a short public-facing list. This document provides the deeper operational descriptions that will grow as new agents and system components are specified, implemented, and integrated.

## Draft System Components

| Component | Type | Status | Service Folder | Purpose |
| --- | --- | --- | --- | --- |
| Procurement Intake Web UI | Next.js web application | Initial implementation | `services/procurement-intake-ui` | Lets users converse with the intake layer, review structured procurement requests, launch workflows, and monitor progress in real time. |
| Agent Telemetry Layer | Cross-cutting observability contract | Draft specification | N/A | Defines OpenTelemetry metrics and Locus task-boundary instrumentation rules for A2A agent invocations, execution duration, and errors. |
| Conversational Procurement Intake Layer | HTTP application layer | Initial HTTP implementation | `services/conversational-procurement-intake` | Serves the UI over HTTP, converts natural-language requests into validated orchestration JSON, uses read-only MCP lookup for grounding, and calls the Procurement Orchestrator through an A2A client. |
| Procurement Orchestrator | A2A agent | Initial A2A server implementation | `services/procurement-orchestrator` | Coordinates the end-to-end procurement workflow across specialized A2A agents. |
| Bid Collection Agent | A2A agent | Initial A2A server implementation | `services/bid-collection-agent` | Identifies suppliers through MCP, requests offers, collects bids, and prepares them for evaluation. |
| Offer Evaluation Agent | A2A agent | Initial A2A server implementation | `services/offer-evaluation-agent` | Evaluates supplier offers, applies procurement policy, selects the winning offer, and returns an explanation. |
| Compliance Agent | A2A agent | Planned | `services/compliance-agent` | Checks procurement decisions and supplier data against compliance rules. |
| Purchase Order Agent | A2A agent | Initial A2A server implementation | `services/purchase-order-agent` | Registers purchase orders in the company purchase order system and returns a technical confirmation. |

---

## Procurement Intake Web UI

Status: Initial implementation

Type: Next.js web application, not an A2A agent

Specification: [specs/ui/procurement-intake-web-ui.md](specs/ui/procurement-intake-web-ui.md)

The Procurement Intake Web UI is the browser-based entry point for procurement operators.

It lets users describe procurement needs in natural language, clarify missing information, review the structured request prepared by the Conversational Procurement Intake Layer, explicitly confirm workflow launch, and monitor orchestration progress in real time.

The UI communicates only with the Conversational Procurement Intake Layer. It must not call the Procurement Orchestrator, downstream agents, or MCP server directly.

The primary live update path is Server-Sent Events relayed by the intake layer. The UI must translate low-level orchestration events into business-friendly progress messages and avoid showing unnecessary technical protocol details in the main workflow.

### Responsibilities

The UI is responsible for:

- natural-language conversation with the operator
- displaying clarification prompts
- displaying structured procurement request summaries
- requiring explicit confirmation before workflow launch
- opening and consuming SSE progress streams
- showing real-time business-friendly workflow status
- showing terminal procurement results
- providing polling fallback for missed events or SSE reconnects

### Non Responsibilities

The UI does not:

- interpret procurement requests with an LLM
- resolve master data
- generate orchestration JSON
- call A2A agents directly
- call MCP tools directly
- expose raw protocol details in the primary user experience

---

## Agent Telemetry Layer

Status: Draft specification

Type: Cross-cutting observability contract, not an A2A agent

Specification: [specs/observability/agent-telemetry.md](specs/observability/agent-telemetry.md)

The Agent Telemetry Layer defines the shared operational contract for collecting A2A agent metrics with OpenTelemetry.

It standardizes metric names, units, low-cardinality attributes, error categories, and the preferred Locus task-boundary hook placement without introducing shared business runtime code between agents.

Initial metrics cover invocation count, execution duration, and error count for the Procurement Orchestrator, Bid Collection Agent, Offer Evaluation Agent, and Purchase Order Agent.

---

## Conversational Procurement Intake Layer

Status: Initial HTTP implementation

Type: HTTP application layer, not an A2A agent

Specification: [specs/layers/conversational-procurement-intake.md](specs/layers/conversational-procurement-intake.md)

Service folder: [services/conversational-procurement-intake](services/conversational-procurement-intake)

The Conversational Procurement Intake Layer provides the natural-language entry point for end users.

It interprets user requests, checks whether they are clear and complete, asks for missing or ambiguous information, and produces the structured `ProcurementOrchestrationRequest` JSON payload accepted by the Procurement Orchestrator.

The layer may use the read-only Procurement Data MCP Server to resolve and validate plant, part, supplier, and supplier-part references. LLM output is treated as candidate extraction only; canonical procurement identifiers must come from validated user input or MCP lookup results.

The initial implementation must not expose an Agent Card and must not be treated as a peer A2A agent. It is an HTTP application/service layer that communicates with the UI through a JSON API, prepares structured requests, and submits confirmed requests to the Procurement Orchestrator through an A2A client.

After submission, the layer consumes the orchestrator A2A event stream, stores normalized progress events in the intake session state, and relays each event to the UI immediately through Server-Sent Events. Polling remains a required fallback for reconnect and recovery, not the primary live update path.

The implementation includes an LLM-backed structured extractor, a deterministic fallback for local testing, and a static master-data resolver for the demo scenario. The static resolver is the replaceable boundary for the planned read-only Procurement Data MCP client.

The layer must ask for explicit user confirmation before submitting a completed request to the Procurement Orchestrator.

### Responsibilities

The layer is responsible for:

- natural-language procurement intake
- HTTP API communication with the UI
- conversation state during request clarification
- extraction of candidate procurement fields
- MCP-backed entity grounding and validation
- clarification questions for missing, ambiguous, or conflicting information
- documented default application
- final JSON Schema validation
- A2A client submission to the Procurement Orchestrator after user confirmation
- orchestration event relay from the A2A stream to UI-facing HTTP updates

### Non Responsibilities

The layer does not:

- collect supplier bids
- evaluate supplier offers
- select suppliers
- create purchase orders directly
- mutate procurement master data
- bypass the Procurement Orchestrator

---

## Procurement Orchestrator

Status: Initial A2A server implementation

The Procurement Orchestrator coordinates the overall procurement flow. It is responsible for invoking specialized agents through A2A, passing task context between them, and collecting their results into a coherent workflow.

The orchestrator should not own supplier discovery, bid evaluation, compliance, or purchase order business logic. Those responsibilities remain with specialized agents.

Specification: [specs/agents/procurement-orchestrator.md](specs/agents/procurement-orchestrator.md)

Server entry point: [services/procurement-orchestrator/src/procurement_orchestrator/server.py](services/procurement-orchestrator/src/procurement_orchestrator/server.py)

The initial orchestrator contract is JSON-only. Natural-language intake is handled by a separate conversational layer that converts operator requests into a structured `ProcurementOrchestrationRequest`.

The orchestrator streams progress events, writes minimal structured logs, retries bid collection when no valid offer is selected, and optionally creates purchase orders after a winning offer is selected.

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
