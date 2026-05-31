# Purchase Order Agent Specification

Version: 0.1.0

Status: Initial implementation

---

# Purpose

The Purchase Order Agent registers a purchase order in the company's purchase order system and returns a technical confirmation of the registration result.

The agent is deterministic and does not use an LLM.

The agent produces:

- purchase order registration status
- purchase order external reference when registration succeeds
- concise technical message for the orchestrator
- structured error details when registration fails

---

# Responsibilities

The agent must:

- receive a purchase order registration request
- validate the input payload
- call a local wrapper around the company purchase order system API
- return a structured registration result
- expose its capability through A2A v1

---

# Non Responsibilities

The agent does NOT:

- evaluate supplier offers
- select suppliers
- perform compliance checks
- communicate with end users
- generate final user-facing workflow confirmation
- orchestrate the procurement workflow
- use an LLM for purchase order registration

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

### create_purchase_order

Registers a purchase order in the company purchase order system.

---

# Input Schema

## CreatePurchaseOrderRequest

Canonical schema: [specs/schemas/create-purchase-order-request.schema.json](../schemas/create-purchase-order-request.schema.json)

```json
{
  "request_id": "REQ-2026-0001",
  "purchase_order_id": "PO-2026-0001",
  "plant_code": "PLANT-01",
  "supplier": {
    "supplier_id": "SUP-002",
    "supplier_name": "Northern Industrial Supply"
  },
  "line_items": [
    {
      "material_code": "MAT-12345",
      "material_description": "Industrial pump replacement kit",
      "quantity": 10,
      "unit_of_measure": "EA",
      "unit_price": 1180.0,
      "currency": "EUR",
      "requested_delivery_date": "2026-06-15",
      "confirmed_delivery_date": "2026-06-12"
    }
  ],
  "source_offer": {
    "offer_id": "OFF-002",
    "price": 11800.0,
    "currency": "EUR"
  }
}
```

---

# Output Schema

## CreatePurchaseOrderResponse

Canonical schema: [specs/schemas/create-purchase-order-response.schema.json](../schemas/create-purchase-order-response.schema.json)

Successful registration:

```json
{
  "request_id": "REQ-2026-0001",
  "status": "registered",
  "purchase_order": {
    "purchase_order_id": "PO-2026-0001",
    "external_reference": "ERP-PO-884421",
    "registered_at": "2026-05-28T10:30:00Z"
  },
  "message": "Purchase order PO-2026-0001 was registered successfully.",
  "error": {
    "code": "",
    "message": ""
  }
}
```

Failed registration:

```json
{
  "request_id": "REQ-2026-0001",
  "status": "failed",
  "purchase_order": {
    "purchase_order_id": "PO-2026-0001",
    "external_reference": "",
    "registered_at": ""
  },
  "message": "Purchase order registration failed.",
  "error": {
    "code": "EXTERNAL_SYSTEM_UNAVAILABLE",
    "message": "The purchase order system is unavailable."
  }
}
```

---

# Purchase Order System Wrapper

The implementation must isolate the company purchase order system integration behind a local module.

Initial module:

- `services/purchase-order-agent/src/purchase_order_agent/po_system.py`

Initial behavior:

- no real external write
- deterministic stub registration
- synthetic external reference generation

Implemented wrapper:

- [services/purchase-order-agent/src/purchase_order_agent/po_system.py](../../services/purchase-order-agent/src/purchase_order_agent/po_system.py)

Future behavior:

- replace the stub with an API, database, ERP, or other enterprise integration
- keep the agent business workflow stable when the backend integration changes

---

# Validation Rules

The agent must validate:

- mandatory fields
- at least one line item
- positive quantities
- non-negative prices
- ISO 4217 currency format
- delivery date format
- source offer consistency fields

Invalid payloads must generate structured validation errors.

---

# Error Handling

The agent must return a `failed` response when purchase order registration cannot be completed.

The response must include:

- `status` set to `failed`
- a concise technical `message`
- an `error.code`
- an `error.message`

---

# Operational Requirements

## Logging

Structured JSON logs.

## Tracing

The agent must follow the shared Agent Telemetry Specification:

[specs/observability/agent-telemetry.md](../observability/agent-telemetry.md)

It must emit OpenTelemetry metrics for:

- `create_purchase_order` invocation count
- purchase order registration execution duration
- purchase order registration error count

The telemetry hook must be attached at the Locus A2A task execution boundary or the narrowest equivalent local task-handler wrapper.

Purchase order IDs, supplier IDs, and backend system references must not be used as metric attributes.

## Persistence

The initial implementation does not persist data.

Future implementations may write through the company purchase order system API, database, ERP, or another enterprise backend.

## Security

Future support for:

- JWT authentication
- mTLS
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
