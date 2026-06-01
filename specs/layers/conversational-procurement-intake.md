# Conversational Procurement Intake Layer Specification

Version: 0.1.0

Status: Draft

---

# Purpose

The Conversational Procurement Intake Layer provides the natural-language entry point for end users who want to start an end-to-end procurement workflow.

The layer interprets user requests, checks whether they are clear and complete, resolves procurement master-data references through the read-only Procurement Data MCP Server, asks clarification questions when needed, and produces the structured `ProcurementOrchestrationRequest` JSON payload accepted by the Procurement Orchestrator.

The Procurement Orchestrator remains JSON-only. Natural-language understanding, clarification, entity grounding, and final request assembly belong to this separate intake layer.

---

# Responsibilities

The layer must:

- accept procurement requests expressed in natural language
- expose an HTTP API for the user interface
- maintain the conversation state needed to complete one procurement intake session
- extract candidate procurement intent and entities from user messages
- detect missing mandatory information
- detect ambiguous, conflicting, or underspecified information
- use the read-only Procurement Data MCP Server to resolve and validate plants, parts, suppliers, and supplier-part eligibility when needed
- ask concise clarification questions until the request is clear, unambiguous, and complete
- apply documented defaults only when allowed by this specification
- produce a JSON payload that conforms to `ProcurementOrchestrationRequest`
- validate the final payload against the canonical JSON Schema before submission
- provide an auditable explanation of extracted values, defaults, clarifications, and MCP lookups
- submit the validated payload to the Procurement Orchestrator through an A2A client after user confirmation

---

# Non Responsibilities

The layer does NOT:

- collect supplier bids
- evaluate offers
- select winning suppliers
- create purchase orders directly
- mutate procurement master data
- write to the Procurement Data MCP store
- bypass the Procurement Orchestrator
- override procurement evaluation policy logic
- invent plant, part, supplier, or policy identifiers that cannot be validated or explicitly configured

---

# Runtime Role

The layer uses an LLM for language understanding, clarification generation, and structured extraction.

The LLM output must be treated as a candidate result. Deterministic validation and MCP grounding remain mandatory before the request is considered ready for orchestration.

The initial implementation must be delivered as an application layer or service, not as an A2A agent.

The layer must not publish an Agent Card in the initial implementation. If a future requirement exposes this capability to other agents, that change must be specified separately.

---

# Communication Boundaries

The layer has three different communication boundaries:

| Boundary | Direction | Protocol | Purpose |
| --- | --- | --- | --- |
| User Interface | inbound and outbound | HTTP JSON API plus optional Server-Sent Events | Receive user messages and return clarification, confirmation, submission, and orchestration status updates. |
| Procurement Data MCP Server | outbound | MCP streamable HTTP | Resolve and validate procurement master-data references through read-only tools. |
| Procurement Orchestrator | outbound | A2A v1 over HTTP streaming | Submit a validated `ProcurementOrchestrationRequest` and consume orchestration events and final result. |

The layer is not itself an A2A server in the initial implementation. It is an HTTP application service that also acts as an A2A client when calling the Procurement Orchestrator.

---

# UI HTTP API

The user interface communicates with this layer through HTTP.

The initial API should be JSON-based and session-oriented. Exact endpoint names may evolve during implementation, but the API must support these operations:

| Operation | Purpose |
| --- | --- |
| Start intake session | Create a new conversational procurement intake session. |
| Submit user message | Add a natural-language user message and receive the next layer response. |
| Confirm structured request | Explicitly confirm the final structured request before orchestration submission. |
| Cancel intake session | Cancel an in-progress intake session. |
| Get session status | Retrieve current session state, known fields, missing fields, and latest response. |
| Get orchestration status | Retrieve orchestration events and final result after submission. |

The HTTP API must never require the UI to construct a `ProcurementOrchestrationRequest` directly from scratch. The UI sends natural-language messages, user confirmations, session commands, and may send a reviewed version of the layer-generated candidate payload when the operator edits explicitly reviewable fields before confirmation. The layer owns extraction, grounding, validation, and final orchestration payload assembly.

Suggested request shape for a user message:

```json
{
  "session_id": "INTAKE-2026-0001",
  "message": "We need 10 high density battery modules for Munich by June 15.",
  "requested_by": "operator@example.com"
}
```

Suggested response shape:

```json
{
  "session_id": "INTAKE-2026-0001",
  "state": "needs_clarification",
  "message": "Please provide these missing details: What quantity do you need? What required delivery date should I use? Which bid response deadline should I use?",
  "missing_fields": [
    "parts[0].quantity",
    "parts[0].required_delivery_date",
    "response_deadline"
  ],
  "ambiguities": [],
  "confirmation_summary": null,
  "orchestration_request": null,
  "orchestration_id": null
}
```

When the state is `ready_for_confirmation`, the response should include a confirmation summary and the candidate orchestration payload for review.

The confirmation request may include a reviewed `orchestration_request` derived from the candidate payload. The layer must validate this reviewed payload before submission and must submit the reviewed payload rather than the original candidate when validation succeeds.

The HTTP API must support returning orchestration progress after submission. The preferred first implementation is Server-Sent Events for real-time live updates, with polling as a fallback for clients or deployments that cannot keep streaming HTTP connections open.

---

# Procurement Orchestrator A2A Client

After explicit user confirmation, the layer must call the Procurement Orchestrator using an A2A client over HTTP.

The layer must call the orchestrator skill that accepts `ProcurementOrchestrationRequest` and returns orchestration progress events and a terminal `ProcurementOrchestrationResponse`.

Before calling the orchestrator, the layer must:

- validate the final payload against the canonical orchestration request JSON Schema
- ensure the user confirmed the exact payload or a summary that faithfully represents it
- generate or preserve the `request_id` idempotency key
- record the final payload and confirmation metadata for audit

After calling the orchestrator, the layer must:

- retain the returned orchestration identifier when available
- expose orchestration progress to the UI through the HTTP API
- expose the terminal orchestration result to the UI
- surface submission or protocol failures as user-facing HTTP responses with safe error messages

The layer must not call Bid Collection, Offer Evaluation, or Purchase Order agents directly. All workflow execution must go through the Procurement Orchestrator.

---

# Orchestration Event Relay

The Procurement Orchestrator emits a stream of `ProcurementOrchestrationEvent` messages followed by a terminal `ProcurementOrchestrationResponse`.

The Conversational Procurement Intake Layer is responsible for relaying those updates to the UI. The UI must not connect directly to the Procurement Orchestrator in the initial architecture.

The relay flow is:

1. The UI confirms the structured procurement request through the intake HTTP API.
2. The intake layer validates the final payload and starts the orchestrator task through an A2A client.
3. The intake layer consumes the orchestrator A2A event stream.
4. Each orchestration event is stored in the intake session state with its `sequence`, timestamp, event type, status, message, and payload.
5. Each orchestration event is forwarded immediately to connected UI clients through the intake layer's SSE update channel.
6. The terminal orchestration response is stored and exposed as the final session result.

The layer should expose two UI-facing mechanisms:

| Mechanism | Requirement | Purpose |
| --- | --- | --- |
| Server-Sent Events endpoint | Preferred | Push each orchestration update to the UI over HTTP as soon as the layer receives it from the A2A stream. |
| Polling status endpoint | Required fallback | Let the UI fetch missed events, reconnect after network failures, or operate without streaming support. |

SSE delivery is a real-time relay requirement. The layer must not wait until the orchestration finishes before sending accumulated events to the UI. Caching or persistence is allowed only to support reconnect, polling, auditability, and final status retrieval; it must not replace immediate per-event forwarding while an SSE client is connected.

When an SSE client is connected, the layer should flush each SSE message promptly after serializing the corresponding orchestration event. Heartbeats should be emitted during long gaps so intermediaries and browsers keep the connection open.

Suggested SSE event names:

| SSE event | Payload |
| --- | --- |
| `orchestration_event` | One normalized `ProcurementOrchestrationEvent`. |
| `orchestration_completed` | Terminal `ProcurementOrchestrationResponse`. |
| `orchestration_failed` | Safe error payload when the A2A call, stream, or orchestration fails. |
| `heartbeat` | Lightweight keepalive event for long-running workflows. |

The polling endpoint should support a cursor based on the orchestrator event `sequence` value or an intake-local monotonically increasing event offset.

Example polling response:

```json
{
  "session_id": "INTAKE-2026-0001",
  "orchestration_id": "ORCH-REQ-2026-0001",
  "state": "submitted",
  "events": [
    {
      "sequence": 1,
      "timestamp": "2026-05-29T10:00:00Z",
      "event_type": "accepted",
      "status": "accepted",
      "message": "Procurement orchestration accepted and started.",
      "payload": {
        "parts_count": 1,
        "auto_create_purchase_order": true
      }
    }
  ],
  "next_cursor": 1,
  "terminal_result": null
}
```

The relay must preserve the original orchestrator event ordering. If duplicate events are received after a reconnect or retry, the layer should de-duplicate them using `orchestration_id`, `request_id`, and `sequence`.

If the UI disconnects, the orchestrator task must continue. The intake layer should keep consuming the A2A stream and store events so the UI can reconnect and recover missed updates through the polling endpoint or by reopening the SSE stream with a cursor.

If the intake layer process stops during an active orchestration in the first implementation, durable recovery is not required unless persistence has been added. The limitation must be documented operationally.

---

# Input Conversation

The user may provide all details in one message or through multiple turns.

Example initial request:

```text
We urgently need 10 high density battery modules for the Munich plant by June 15.
Ask up to three European suppliers and create the purchase order automatically if a valid offer is selected.
```

The layer must preserve the original user text for audit purposes.

---

# Required Target Payload

The final output must conform to the canonical schema:

[specs/schemas/procurement-orchestration-request.schema.json](../schemas/procurement-orchestration-request.schema.json)

At minimum, the intake session must resolve:

| Target field | Source |
| --- | --- |
| `request_id` | Generated by the intake layer unless provided by the caller. |
| `requested_by` | Authenticated user context or explicit user identifier. |
| `currency` | User input, configured default, or validated supplier/business context. |
| `evaluation_policy_id` | User input or configured default. |
| `response_deadline` | User input or clarified deadline for bid responses. |
| `auto_create_purchase_order` | User input or configured default. |
| `sourcing_constraints.max_suppliers_per_part` | User input or configured default. |
| `sourcing_constraints.allowed_regions` | User input or configured default. |
| `parts[].part_id` | Resolved through Procurement Data MCP. |
| `parts[].plant_code` | Resolved through Procurement Data MCP. |
| `parts[].material_code` | Resolved through Procurement Data MCP part code. |
| `parts[].material_description` | Resolved through Procurement Data MCP part name or description. |
| `parts[].quantity` | User input. |
| `parts[].unit_of_measure` | User input or resolved through Procurement Data MCP part data. |
| `parts[].required_delivery_date` | User input or clarified required delivery date. |

---

# Defaults

Defaults must be explicit and auditable.

Initial defaults:

| Field | Default | Rule |
| --- | --- | --- |
| `request_id` | Generated value such as `REQ-YYYY-NNNN`. | May be generated automatically. |
| `currency` | `EUR` | May be applied when the user does not specify currency and the business context is European procurement. |
| `evaluation_policy_id` | `standard-urgent-procurement-v1` | May be applied for urgent procurement requests. |
| `auto_create_purchase_order` | `false` | Must remain false unless the user explicitly requests automatic PO creation or confirms it. |
| `max_rebid_attempts` | `2` | May use the orchestrator default. |
| `timeouts` | Omitted | The orchestrator may apply runtime defaults when configured to do so. |
| `sourcing_constraints.max_suppliers_per_part` | `3` | May be applied when the user does not specify supplier count. |
| `sourcing_constraints.allowed_regions` | `[]` | Empty array means no region restriction. |
| `supplier_search_hints.required_certifications` | `[]` | May be applied when no certifications are specified. |

The layer must report which defaults were applied before final confirmation.

---

# MCP Grounding Requirements

The layer may call only read-only Procurement Data MCP tools.

Allowed lookup purposes:

- resolve plant names, cities, countries, or colloquial references to `plant_code`
- resolve material names, part names, categories, or part codes to canonical part data
- validate that a requested part exists and is active
- validate that a destination plant exists and is active
- validate preferred supplier identifiers when the user names preferred suppliers
- check supplier availability for a part and quantity using `find_suppliers_for_part`
- derive `unit_of_measure`, `material_description`, and commodity search hints from canonical part data

The layer must not treat LLM guesses as canonical identifiers. A plant, part, or supplier identifier is canonical only when it comes from user-provided exact IDs that validate successfully or from MCP lookup results.

When an MCP lookup returns no matches, the layer must ask the user for a corrected value or a more specific description.

When an MCP lookup returns multiple plausible matches, the layer must ask the user to choose among the candidates unless there is a deterministic exact match.

---

# Clarification Policy

The layer must ask for clarification when:

- any required target field is missing and has no allowed default
- a relative date cannot be converted safely to an absolute date
- a plant reference cannot be resolved to one active plant
- a material reference cannot be resolved to one active part
- the requested quantity is missing, zero, negative, or incompatible with the resolved part
- the unit of measure conflicts with the resolved part unit of measure
- the required delivery date is missing or earlier than the current date
- the response deadline is missing and no configured default exists
- the user requests automatic purchase order creation ambiguously
- the user includes contradictory constraints
- a preferred supplier is unknown, inactive, or not eligible for the requested part

Clarification questions should be concise and should include candidate options when MCP lookup returns plausible matches.

When more than one mandatory field is missing, the layer must ask for all currently missing mandatory details in one response instead of asking for only the first missing field. This keeps the dialogue efficient and makes the current completeness state explicit to the user.

The layer should avoid asking for information that can be safely resolved through MCP lookup or documented defaults.

---

# Confirmation Policy

Before submitting a request to the Procurement Orchestrator, the layer must present a concise structured summary and ask for user confirmation.

The summary must include:

- requested parts
- destination plants
- quantities and units of measure
- required delivery dates
- bid response deadline
- currency
- sourcing constraints
- evaluation policy
- whether purchase orders will be created automatically
- defaults applied
- unresolved assumptions, if any

Submission must happen only after explicit confirmation.

---

# Output States

The layer should model each turn as one of these states:

| State | Meaning |
| --- | --- |
| `needs_clarification` | The request is not ready and the user must provide more information. |
| `ready_for_confirmation` | The request is complete and valid, but user confirmation is still required. |
| `ready_for_orchestration` | The user confirmed the structured request and it may be submitted. |
| `submitted` | The request was submitted to the Procurement Orchestrator. |
| `cancelled` | The user cancelled the intake session. |
| `failed` | The layer could not complete processing because of validation, MCP, LLM, or orchestration errors. |

---

# Suggested Internal Response Shape

The implementation should keep an internal structured response similar to:

```json
{
  "state": "needs_clarification",
  "message": "I found two active parts that match 'battery module'. Which one do you need?",
  "known_fields": {
    "requested_by": "operator@example.com",
    "currency": "EUR"
  },
  "missing_fields": ["parts[0].required_delivery_date"],
  "ambiguities": [
    {
      "field": "parts[0].material_code",
      "reason": "Multiple active parts matched the user description.",
      "candidates": [
        {
          "part_id": "PART-001",
          "part_code": "EV-BAT-MOD-001",
          "part_name": "High Density Battery Module"
        }
      ]
    }
  ],
  "defaults_applied": [
    {
      "field": "currency",
      "value": "EUR",
      "reason": "Configured default for European procurement."
    }
  ],
  "mcp_lookups": [
    {
      "tool": "list_parts",
      "arguments": {
        "category": "battery",
        "active_only": true
      },
      "result_count": 2
    }
  ],
  "orchestration_request": null
}
```

This shape is an implementation aid, not yet a public A2A contract.

---

# Final Orchestration Payload Example

```json
{
  "request_id": "REQ-2026-0001",
  "requested_by": "operator@example.com",
  "currency": "EUR",
  "evaluation_policy_id": "standard-urgent-procurement-v1",
  "response_deadline": "2026-05-29T12:00:00Z",
  "auto_create_purchase_order": true,
  "max_rebid_attempts": 2,
  "sourcing_constraints": {
    "max_suppliers_per_part": 3,
    "allowed_regions": ["EU"],
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

---

# Validation Requirements

Before the layer reaches `ready_for_confirmation`, it must validate:

- all required orchestration fields are present
- dates are valid ISO 8601 values
- `response_deadline` is a timestamp
- `required_delivery_date` is a date
- quantities are positive
- plant and part identifiers are grounded in active MCP records
- supplier preferences, when present, are known and active
- the payload conforms to the canonical `ProcurementOrchestrationRequest` JSON Schema

Before submission, the layer must validate the same payload again after user confirmation.

---

# Error Handling

The layer must produce user-facing messages for:

- invalid or unsupported procurement intent
- missing mandatory information
- ambiguous plant, part, or supplier references
- MCP server unavailability
- MCP lookup errors
- JSON Schema validation failures
- orchestration submission failures

Technical error details should be logged for maintainers but should not be exposed directly to end users unless safe and useful.

---

# Auditability

Each intake session should retain:

- original user messages
- clarification questions and answers
- extracted fields
- MCP lookup tools, arguments, and result counts
- canonical entities selected from MCP data
- defaults applied and reasons
- generated orchestration request
- user confirmation timestamp
- orchestration submission result, when submitted

Durable persistence is optional in the first implementation but the data model should not prevent future persistence.
