# Procurement Orchestrator Agent Specification

Version: 0.1.0

Status: Draft

---

# Purpose

The Procurement Orchestrator Agent coordinates the end-to-end structured procurement workflow across specialized A2A agents.

The orchestrator receives a structured JSON request, immediately acknowledges that processing has started, streams workflow progress events, and eventually returns a terminal orchestration result.

The orchestrator does not interpret natural language. Natural-language intake, clarification, and conversion to structured JSON belong to a separate conversational intake layer.

The initial orchestrator coordinates:

- Bid Collection Agent
- Offer Evaluation Agent
- Purchase Order Agent

The Compliance Agent is intentionally left out of the initial workflow and will be inserted later between offer evaluation and purchase order creation.

---

# Responsibilities

The agent must:

- receive a structured procurement orchestration request
- validate the input payload
- emit an immediate accepted event to the A2A streaming client
- call the Bid Collection Agent to collect supplier offers
- call the Offer Evaluation Agent to evaluate collected offers
- call the Purchase Order Agent when a winning offer exists and automatic purchase order creation is enabled
- retry bid collection and evaluation when no valid offer is selected
- stream progress events while the workflow runs
- return one terminal orchestration response
- expose its capability through A2A v1

---

# Non Responsibilities

The agent does NOT:

- parse natural language requests
- chat with the end user
- identify suppliers directly
- contact supplier APIs directly
- evaluate or rank offers directly
- register purchase orders directly
- perform compliance checks in the initial version
- persist checkpoints in the initial version
- own supplier, plant, or part master data
- mutate the procurement data MCP store

---

# Communication Protocol

## Transport

- HTTP

## Protocol

- A2A v1
- JSON-RPC 2.0

## Content Modes

- input: `application/json`
- streaming output: `application/json`
- final output: `application/json`

The orchestrator must be implemented as an A2A agent and must use A2A clients to call downstream agents.

---

# Agent Card

## Skills

### run_procurement_workflow

Runs the end-to-end procurement workflow for one structured procurement request.

The skill accepts a `ProcurementOrchestrationRequest`, streams `ProcurementOrchestrationEvent` messages, and completes with a `ProcurementOrchestrationResponse`.

---

# Input Schema

## ProcurementOrchestrationRequest

Canonical schema: [specs/schemas/procurement-orchestration-request.schema.json](../schemas/procurement-orchestration-request.schema.json)

```json
{
  "request_id": "REQ-2026-0001",
  "requested_by": "operator@example.com",
  "currency": "EUR",
  "evaluation_policy_id": "standard-urgent-procurement-v1",
  "response_deadline": "2026-05-29T12:00:00Z",
  "auto_create_purchase_order": true,
  "max_rebid_attempts": 2,
  "timeouts": {
    "bid_collection_seconds": 300,
    "offer_evaluation_seconds": 120,
    "purchase_order_seconds": 120,
    "total_seconds": 1800
  },
  "sourcing_constraints": {
    "max_suppliers_per_part": 3,
    "allowed_regions": ["EU", "UK"],
    "preferred_supplier_ids": []
  },
  "parts": [
    {
      "part_id": "PART-001",
      "plant_code": "DE-MUN",
      "material_code": "EV-BAT-MOD-001",
      "material_description": "High Density Battery Module",
      "quantity": 10,
      "unit_of_measure": "EA",
      "required_delivery_date": "2026-06-15",
      "supplier_search_hints": {
        "commodity_category": "battery",
        "required_certifications": []
      }
    }
  ]
}
```

`request_id` is the idempotency key for the orchestration request. In the initial implementation, the agent must prevent duplicate purchase order creation within the lifetime of a running task. Durable idempotency across restarts requires persistence and is out of scope until checkpointing is introduced.

---

# Streaming Output Schema

## ProcurementOrchestrationEvent

Canonical schema: [specs/schemas/procurement-orchestration-event.schema.json](../schemas/procurement-orchestration-event.schema.json)

The first event must be emitted immediately after input validation:

```json
{
  "orchestration_id": "ORCH-REQ-2026-0001",
  "request_id": "REQ-2026-0001",
  "sequence": 1,
  "timestamp": "2026-05-28T14:00:00Z",
  "event_type": "accepted",
  "status": "accepted",
  "message": "Procurement orchestration accepted and started.",
  "payload": {
    "parts_count": 1,
    "auto_create_purchase_order": true
  }
}
```

Subsequent events report progress:

```json
{
  "orchestration_id": "ORCH-REQ-2026-0001",
  "request_id": "REQ-2026-0001",
  "sequence": 4,
  "timestamp": "2026-05-28T14:01:30Z",
  "event_type": "offer_evaluation_completed",
  "status": "running",
  "message": "Offer evaluation completed for part PART-001.",
  "payload": {
    "part_id": "PART-001",
    "attempt_number": 1,
    "decision_status": "selected_offer",
    "selected_offer_id": "OFF-REQ-2026-0001-PART-001-SUP-001"
  }
}
```

---

# Final Output Schema

## ProcurementOrchestrationResponse

Canonical schema: [specs/schemas/procurement-orchestration-response.schema.json](../schemas/procurement-orchestration-response.schema.json)

```json
{
  "orchestration_id": "ORCH-REQ-2026-0001",
  "request_id": "REQ-2026-0001",
  "status": "completed_with_purchase_orders",
  "started_at": "2026-05-28T14:00:00Z",
  "completed_at": "2026-05-28T14:03:00Z",
  "part_results": [
    {
      "part_id": "PART-001",
      "material_code": "EV-BAT-MOD-001",
      "status": "purchase_order_created",
      "attempts_used": 1,
      "bid_collection": {
        "status": "completed",
        "identified_suppliers_count": 3,
        "offers_count": 3
      },
      "evaluation": {
        "status": "selected_offer",
        "selected_offer": {
          "offer_id": "OFF-REQ-2026-0001-PART-001-SUP-001",
          "supplier_id": "SUP-001",
          "supplier_name": "VoltEdge Components",
          "price": 2200.0,
          "currency": "EUR",
          "delivery_date": "2026-06-12",
          "quality_score": 94,
          "reliability_score": 92,
          "valid_until": "2026-06-05"
        },
        "explanation": "The selected offer is the lowest eligible offer that meets the required delivery date."
      },
      "purchase_order": {
        "status": "registered",
        "purchase_order_id": "PO-REQ-2026-0001-PART-001",
        "external_reference": "ERP-PO-884421",
        "registered_at": "2026-05-28T14:02:50Z"
      },
      "error": {
        "code": "",
        "message": ""
      }
    }
  ],
  "message": "Procurement workflow completed with 1 purchase order.",
  "error": {
    "code": "",
    "message": ""
  }
}
```

---

# Workflow

For each requested part, the orchestrator must run the following workflow:

1. Build a `CollectBidsRequest` from the orchestration request.
2. Call the Bid Collection Agent `collect_bids` skill.
3. Extract one `EvaluateOffersRequest` for the part from the bid collection response.
4. Call the Offer Evaluation Agent `evaluate_offers` skill.
5. If the evaluation returns `selected_offer`, continue to purchase order handling.
6. If the evaluation returns `no_valid_offers`, retry bid collection and evaluation while retry attempts remain.
7. If no valid offer exists after all attempts, mark the part as `no_valid_offer`.
8. If `auto_create_purchase_order` is `true`, build a `CreatePurchaseOrderRequest` and call the Purchase Order Agent `create_purchase_order` skill.
9. If `auto_create_purchase_order` is `false`, stop the part workflow at `winner_selected`.

The orchestrator must emit streaming events before and after each downstream agent call.

---

# Retry Policy

The initial retry policy applies only when the Offer Evaluation Agent returns `no_valid_offers`.

Default retry behavior:

- initial bid collection and evaluation attempt: attempt `1`
- maximum additional retry attempts: `2`
- default total attempts per part: `3`
- retry scope: per part
- retry payload: same part and sourcing constraints as the original request

The orchestrator must emit a `rebid_requested` event before every retry.

The orchestrator must not retry purchase order registration in the initial version. A failed purchase order registration leaves the part in `purchase_order_failed`.

---

# Multi-Part Semantics

Multi-part requests are handled independently per part.

Rules:

- retries are tracked per part
- one winning offer may be selected per part
- one purchase order may be created per part in the initial implementation
- a failure for one part must not stop other parts unless the total orchestration timeout is exceeded
- final orchestration status is `partial` when at least one part succeeds and at least one part fails or has no valid offer

The initial version does not optimize across parts and does not consolidate multiple winning part decisions into a single purchase order.

---

# Purchase Order Creation

When `auto_create_purchase_order` is `true` and a selected offer exists, the orchestrator must build a `CreatePurchaseOrderRequest`.

Mapping rules:

- `request_id` comes from the orchestration request
- `purchase_order_id` may be omitted so the Purchase Order Agent can allocate the official purchase order number
- `plant_code` comes from the requested part
- `supplier` comes from the selected offer
- `line_items[0].material_code` comes from the requested part
- `line_items[0].quantity` comes from the requested part
- `line_items[0].unit_price` is `selected_offer.price / quantity`
- `line_items[0].currency` comes from the selected offer
- `line_items[0].requested_delivery_date` comes from the requested part
- `line_items[0].confirmed_delivery_date` comes from the selected offer delivery date
- `source_offer` comes from the selected offer

When `auto_create_purchase_order` is `false`, purchase order creation is skipped and the part status is `winner_selected`.

---

# Downstream Agent Contracts

The orchestrator must call downstream agents through A2A only.

## Bid Collection Agent

Skill:

- `collect_bids`

Input:

- `CollectBidsRequest`

Output:

- `CollectBidsResponse`

## Offer Evaluation Agent

Skill:

- `evaluate_offers`

Input:

- `EvaluateOffersRequest`

Output:

- `EvaluateOffersResponse`

## Purchase Order Agent

Skill:

- `create_purchase_order`

Input:

- `CreatePurchaseOrderRequest`

Output:

- `CreatePurchaseOrderResponse`

---

# Status Semantics

## Final Orchestration Status

- `completed_with_purchase_orders`: every part has a selected offer and a registered purchase order
- `completed_without_purchase_orders`: every part has a selected offer and purchase order creation was intentionally skipped
- `completed_without_valid_offer`: no part produced a valid offer after all retry attempts
- `partial`: at least one part succeeded and at least one part failed, had no valid offer, or failed purchase order registration
- `failed`: no part completed successfully because of technical failures

## Part Status

- `purchase_order_created`: selected offer exists and purchase order registration succeeded
- `winner_selected`: selected offer exists and purchase order creation was skipped
- `no_valid_offer`: no valid offer exists after all retry attempts
- `purchase_order_failed`: selected offer exists but purchase order registration failed
- `failed`: technical failure prevented the part workflow from completing

---

# Validation Rules

The orchestrator must validate:

- mandatory fields
- at least one requested part
- positive quantities
- ISO 4217 currency format
- ISO 8601 response deadline format
- ISO 8601 required delivery date format
- duplicate `part_id` values
- `max_rebid_attempts` between `0` and `2`
- timeout values are positive
- `request_id` is present and stable

Invalid input payloads must fail before downstream agent calls.

---

# Error Handling

The orchestrator must represent errors in streaming events and in the final response.

The orchestrator must handle:

- invalid input payload
- Bid Collection Agent timeout
- Bid Collection Agent failure
- malformed Bid Collection Agent response
- Offer Evaluation Agent timeout
- Offer Evaluation Agent failure
- malformed Offer Evaluation Agent response
- Purchase Order Agent timeout
- Purchase Order Agent failure
- malformed Purchase Order Agent response
- total orchestration timeout

When a supplier-level failure is already represented by the Bid Collection Agent inside `supplier_responses[]`, the orchestrator must not treat it as a workflow-level failure unless the part receives no offers after all attempts.

---

# Idempotency

`request_id` is the idempotency key.

Initial behavior:

- the orchestrator must not create two purchase orders for the same `request_id` and `part_id` within one running orchestration task
- deterministic `purchase_order_id` generation must use `request_id` and `part_id`

Future behavior:

- durable idempotency across process restarts will require persistence and checkpointing

---

# Timeout Policy

The orchestrator must support timeout settings for:

- bid collection
- offer evaluation
- purchase order creation
- total orchestration runtime

If `timeouts` is omitted, the implementation must use documented runtime defaults. Demo clients should send explicit timeout values to keep behavior predictable.

---

# Compliance Placeholder

The initial workflow does not call a Compliance Agent.

Future workflow position:

```text
Bid Collection -> Offer Evaluation -> Compliance Check -> Purchase Order
```

When the Compliance Agent is introduced, the orchestrator spec must be updated with:

- compliance request and response schemas
- compliance streaming events
- decision handling for approval, rejection, and manual review
- purchase order gating rules

---

# Persistence And Checkpointing

The initial implementation does not persist checkpoint state.

The orchestrator may keep in-memory task state while a task is running, but it must not claim resumability across process restarts.

Checkpointing, durable audit records, and resumable workflows will be specified later.

---

# Operational Requirements

## Logging

Structured JSON logs.

## Tracing

The orchestrator must follow the shared Agent Telemetry Specification:

[specs/observability/agent-telemetry.md](../observability/agent-telemetry.md)

It must participate in Locus lifecycle hooks so the built-in Locus `TelemetryHook` can emit native Locus telemetry for:

- `run_procurement_workflow` invocation count
- workflow execution duration
- workflow error count

When telemetry is enabled and a purchase order is successfully registered, the
orchestrator should also emit low-cardinality business metrics through a local
business telemetry hook for:

- purchase order count
- purchase order amount by plant and currency
- selected offer parts-cost deviation from the average offered parts cost by plant
- selected offer shipping cost percentage by plant

The Locus lifecycle hook bridge must be attached at the A2A workflow execution boundary or the narrowest equivalent local task-handler wrapper.

The orchestrator should propagate OpenTelemetry trace context to downstream A2A calls when supported by Locus and the HTTP transport.

The orchestrator should create child spans or equivalent trace events for:

- bid collection
- offer evaluation
- purchase order creation
- total orchestration runtime

Metrics must not use `request_id`, A2A task ID, supplier ID, purchase order ID, or other per-execution identifiers as attributes.

## Security

Initial behavior:

- A2A bearer authentication for inbound requests
- A2A bearer authentication for downstream agent calls

Future behavior:

- service-to-service mTLS
- role-based authorization
- audit-oriented identity propagation

---

# Definition of Done

Implementation is complete only if:

- this specification is implemented
- canonical schemas are validated in tests
- A2A streaming emits the accepted event immediately after validation
- downstream agent calls use A2A clients
- retry policy is covered by unit tests
- multi-part partial success behavior is covered by unit tests
- purchase order skip and purchase order creation paths are covered by unit tests
- black passes
- pylint passes
- pytest passes
- changelog is updated
