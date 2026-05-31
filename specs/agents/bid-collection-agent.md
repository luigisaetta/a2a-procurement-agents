# Bid Collection Agent Specification

Version: 0.2.0

Status: Draft

---

# Purpose

The Bid Collection Agent identifies eligible suppliers, requests supplier offers for one or more procurement parts, and returns a normalized list of offers that can be passed to the Offer Evaluation Agent.

The agent is deterministic and does not use an LLM.

The agent produces:

- supplier-specific bid requests
- identified supplier lists
- supplier response summaries
- normalized supplier offers
- downstream offer evaluation request payloads

---

# Responsibilities

The agent must:

- receive a procurement request containing one or more requested parts
- validate input payloads
- identify eligible suppliers for each requested part
- build supplier-specific bid requests for each part and supplier
- contact suppliers through a supplier offer provider API
- receive supplier bid responses
- normalize successful supplier offers into the Offer Evaluation Agent offer shape
- return a structured collection result
- generate downstream `EvaluateOffersRequest` payloads for parts with at least one received offer
- expose its capability through A2A v1

Supplier discovery must use the Procurement Data MCP Server over streamable HTTP. The agent must not carry its own supplier catalog.

---

# Non Responsibilities

The agent does NOT:

- evaluate or rank offers
- select a winning supplier
- perform compliance checks
- create purchase orders
- negotiate with suppliers
- persist workflow state
- orchestrate the full procurement workflow
- use an LLM for bid collection

---

# Communication Protocol

## Transport

- HTTP

## Protocol

- A2A v1
- JSON-RPC 2.0

## Content Modes

- input: `application/json`
- output: `application/json`

---

# Agent Card

## Skills

### collect_bids

Identifies suppliers, requests supplier offers for the requested procurement parts, and returns normalized offers grouped by part.

---

# Input Schema

## CollectBidsRequest

Canonical schema: [specs/schemas/collect-bids-request.schema.json](../schemas/collect-bids-request.schema.json)

```json
{
  "request_id": "REQ-2026-0001",
  "currency": "EUR",
  "evaluation_policy_id": "standard-urgent-procurement-v1",
  "response_deadline": "2026-05-29T12:00:00Z",
  "sourcing_constraints": {
    "max_suppliers_per_part": 3,
    "allowed_regions": ["EU", "UK"],
    "preferred_supplier_ids": ["SUP-001", "SUP-002"]
  },
  "parts": [
    {
      "part_id": "PART-001",
      "plant_code": "PLANT-01",
      "material_code": "MAT-12345",
      "material_description": "Industrial pump replacement kit",
      "quantity": 10,
      "unit_of_measure": "EA",
      "required_delivery_date": "2026-06-15",
      "supplier_search_hints": {
        "commodity_category": "industrial-pump-parts",
        "required_certifications": ["ISO-9001"]
      }
    }
  ]
}
```

Each part carries optional supplier search hints. The agent uses those hints and the request-level sourcing constraints to identify suppliers for each part.

---

# Output Schema

## CollectBidsResponse

Canonical schema: [specs/schemas/collect-bids-response.schema.json](../schemas/collect-bids-response.schema.json)

```json
{
  "request_id": "REQ-2026-0001",
  "status": "completed",
  "part_results": [
    {
      "part_id": "PART-001",
      "material_code": "MAT-12345",
      "status": "offers_collected",
      "identified_suppliers": [
        {
          "supplier_id": "SUP-001",
          "supplier_name": "Northern Industrial Supply",
          "api_endpoint": "mock://suppliers/SUP-001/offers",
          "region": "EU",
          "selection_reason": "Supplier supports the requested commodity category in an allowed region."
        }
      ],
      "offers": [
        {
          "offer_id": "OFF-001",
          "supplier_id": "SUP-001",
          "supplier_name": "Northern Industrial Supply",
          "price": 12000.0,
          "currency": "EUR",
          "delivery_date": "2026-06-10",
          "quality_score": 92,
          "reliability_score": 88,
          "valid_until": "2026-06-01"
        }
      ],
      "supplier_responses": [
        {
          "supplier_id": "SUP-001",
          "supplier_name": "Northern Industrial Supply",
          "bid_request_id": "BIDREQ-REQ-2026-0001-PART-001-SUP-001",
          "status": "offer_received",
          "error": {
            "code": "",
            "message": ""
          }
        }
      ]
    }
  ],
  "evaluation_requests": [
    {
      "request_id": "REQ-2026-0001",
      "plant_code": "PLANT-01",
      "material_code": "MAT-12345",
      "material_description": "Industrial pump replacement kit",
      "quantity": 10,
      "unit_of_measure": "EA",
      "currency": "EUR",
      "required_delivery_date": "2026-06-15",
      "evaluation_policy_id": "standard-urgent-procurement-v1",
      "offers": [
        {
          "offer_id": "OFF-001",
          "supplier_id": "SUP-001",
          "supplier_name": "Northern Industrial Supply",
          "price": 12000.0,
          "currency": "EUR",
          "delivery_date": "2026-06-10",
          "quality_score": 92,
          "reliability_score": 88,
          "valid_until": "2026-06-01"
        }
      ]
    }
  ],
  "message": "Collected 1 supplier offer across 1 requested part."
}
```

The `evaluation_requests` array contains payloads compatible with the Offer Evaluation Agent `evaluate_offers` skill.

If no offers are collected for a part, that part remains in `part_results` with status `no_offers` and is omitted from `evaluation_requests`.

---

# Supplier-Facing Provider Schemas

The Bid Collection Agent uses local provider abstractions to isolate supplier identification, supplier communication, and offer-list construction behavior.

These provider contracts are internal to the Bid Collection Agent implementation, but they are specified here because future real supplier integrations must preserve the agent's external A2A contract.

## SupplierBidRequest

Canonical schema: [specs/schemas/supplier-bid-request.schema.json](../schemas/supplier-bid-request.schema.json)

This schema represents the request sent to a supplier API for one part.

## SupplierBidResponse

Canonical schema: [specs/schemas/supplier-bid-response.schema.json](../schemas/supplier-bid-response.schema.json)

This schema represents the response received from a supplier API for one part.

---

# Provider Boundary

The implementation must isolate supplier identification, supplier interaction, and offer-list construction behind local provider modules.

Initial modules:

- `services/bid-collection-agent/src/bid_collection_agent/supplier_discovery_provider.py`
- `services/bid-collection-agent/src/bid_collection_agent/offer_list_provider.py`
- `services/bid-collection-agent/src/bid_collection_agent/supplier_offer_provider.py`

## Supplier Discovery Provider

The supplier discovery provider is responsible for:

- identifying eligible suppliers for each requested part
- applying request-level sourcing constraints
- applying part-level supplier search hints
- returning supplier API endpoints used by the supplier offer provider
- returning a concise selection reason for each identified supplier

Initial behavior:

- call the Procurement Data MCP Server `find_suppliers_for_part` tool over streamable HTTP
- filter MCP supplier candidates using request-level sourcing constraints
- keep MCP communication localized to the supplier discovery provider
- stable supplier selection suitable for tests and audit traces

Future behavior:

- replace the MCP-backed supplier discovery provider only if supplier master data moves to a different enterprise source
- keep supplier identification changes localized to the provider module

## Offer List Provider

The offer list provider is responsible for:

- building one `SupplierBidRequest` for each part and supplier pair
- assigning deterministic `bid_request_id` values
- preserving request, part, supplier, deadline, and currency context
- normalizing successful supplier responses into offer objects compatible with `EvaluateOffersRequest.offers[]`
- building downstream `EvaluateOffersRequest` payloads from collected offers

Initial behavior:

- deterministic local construction
- no external network call
- stable IDs suitable for tests and audit traces
- deterministic offer-list construction from supplier responses

Future behavior:

- enrich bid requests with additional procurement context
- support richer supplier-specific normalization rules
- support additional downstream payload shapes if future evaluation agents require them

## Supplier Offer Provider

The supplier offer provider is responsible for:

- sending each `SupplierBidRequest` to the configured supplier API endpoint
- receiving a `SupplierBidResponse`
- converting supplier-specific responses into the canonical supplier bid response shape
- returning declined or failed responses without raising workflow-level failures

Initial behavior:

- deterministic simulated supplier APIs
- `mock://` supplier endpoints
- synthetic prices, delivery dates, scores, and validity dates
- controlled declined and failed responses for tests

Future behavior:

- replace simulated suppliers with real HTTP APIs, ERP integrations, supplier portals, or marketplace APIs
- keep supplier communication changes localized to the provider module
- preserve `CollectBidsRequest` and `CollectBidsResponse` unless the A2A contract intentionally evolves

---

# Collection Semantics

For each requested part, the agent must:

1. identify eligible suppliers through the supplier discovery provider
2. build one supplier bid request per identified supplier
3. request an offer through the supplier offer provider
4. collect successful offers
5. record declined or failed supplier responses
6. build one downstream evaluation request when at least one offer is collected

The agent must not fail the entire collection workflow because one supplier declines or fails.

The overall response status is:

- `completed` when all parts receive at least one offer and every supplier call returns successfully or declines normally
- `partial` when at least one part receives offers but at least one part receives no offers or at least one supplier call fails
- `failed` when no offers are collected for any requested part

Part-level status is:

- `offers_collected` when every contacted supplier for the part returns an offer
- `partial` when at least one supplier returns an offer and at least one supplier declines or fails
- `no_offers` when no supplier returns an offer for the part

---

# Compatibility With Offer Evaluation

The normalized offer object in `CollectBidsResponse.part_results[].offers[]` must match the offer object expected by `EvaluateOffersRequest.offers[]`.

The agent must generate `evaluation_requests[]` entries with:

- the original procurement `request_id`
- the part's plant, material, quantity, unit, and delivery date
- the request currency
- the request evaluation policy ID
- the collected offers for that part

For multi-part procurement requests, the initial contract creates one offer evaluation request per part.

Cross-part optimization is out of scope for this agent.

---

# Validation Rules

The agent must validate:

- mandatory fields
- at least one requested part
- positive quantities
- ISO 4217 currency format
- ISO 8601 delivery date format
- ISO 8601 response deadline format
- duplicate `part_id` values
- duplicate discovered supplier IDs within the same part
- supplier response consistency with the original bid request
- supplier offer consistency with the requested part and supplier

Invalid input payloads must generate structured validation errors.

---

# Error Handling

Supplier-level failures must be represented inside `supplier_responses[]`.

The agent must return structured errors for:

- invalid input payload
- malformed supplier bid response
- unsupported supplier endpoint scheme
- supplier timeout
- supplier API failure
- internal processing failure

The agent should return a valid `CollectBidsResponse` whenever supplier-level failures can be represented without losing the whole workflow result.

---

# Operational Requirements

## Logging

Structured JSON logs.

## Tracing

The agent must follow the shared Agent Telemetry Specification:

[specs/observability/agent-telemetry.md](../observability/agent-telemetry.md)

It must emit OpenTelemetry metrics for:

- `collect_bids` invocation count
- bid collection execution duration
- bid collection error count

The telemetry hook must be attached at the Locus A2A task execution boundary or the narrowest equivalent local task-handler wrapper.

Bid request IDs should be stable and included in logs to support traceability across supplier calls.

Bid request IDs, supplier IDs, and supplier response IDs must not be used as metric attributes.

## Persistence

The initial implementation does not persist data.

Future implementations may persist bid requests, supplier responses, and audit events.

## Security

Future support for:

- supplier API authentication
- JWT authentication
- mTLS
- outbound request signing
- role-based authorization

---

# Definition of Done

Implementation is complete only if:

- spec implemented
- unit tests added
- black passes
- pylint passes
- pytest passes
- changelog updated
