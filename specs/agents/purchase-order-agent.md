# Purchase Order Agent Specification

Version: 0.2.0

Status: Persistence specification

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
- call a local wrapper around the company purchase order system API or demo persistence backend
- return a structured registration result
- expose its capability through A2A v1
- persist purchase order registration data when a persistence backend is configured
- allocate purchase order numbers when the upstream request does not provide one

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

`purchase_order_id` is optional. When omitted, the Purchase Order Agent must allocate the identifier through the configured purchase order backend.

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

Docker Compose behavior:

- use the MySQL database configured by the deployment
- create required purchase order persistence tables on first save or read if they do not exist
- allocate purchase order identifiers atomically when `purchase_order_id` is omitted
- persist successful registration results before returning `registered`
- return an existing registration for duplicate idempotent requests instead of creating a second purchase order

Implemented wrapper:

- [services/purchase-order-agent/src/purchase_order_agent/po_system.py](../../services/purchase-order-agent/src/purchase_order_agent/po_system.py)

Future behavior:

- replace the demo database backend with an API, ERP, or other enterprise integration
- keep the agent business workflow stable when the backend integration changes

---

# Purchase Order Persistence

The default local behavior remains deterministic and in-memory/fake unless a persistence backend is configured.

When the agent runs in the Docker Compose deployment, the wrapper must use the shared MySQL database. The wrapper owns database access internally; other agents continue to interact with the Purchase Order Agent only through A2A.

## Configuration

The Docker Compose deployment must provide the Purchase Order Agent with database configuration through environment variables:

- `PURCHASE_ORDER_STORAGE_BACKEND=mysql`
- `PROCUREMENT_DB_HOST`
- `PROCUREMENT_DB_PORT`
- `PROCUREMENT_DB_NAME`
- `PROCUREMENT_DB_USER`
- `PROCUREMENT_DB_PASSWORD`

If `PURCHASE_ORDER_STORAGE_BACKEND` is unset or set to `fake`, the wrapper must keep the deterministic fake behavior.

## Lazy Schema Creation

On the first save or read operation, the MySQL wrapper must ensure that the required tables exist.

Schema creation must be idempotent and safe to run more than once. It must not depend on Docker entrypoint initialization having already created the purchase order tables.

The minimum required tables are:

```sql
CREATE TABLE IF NOT EXISTS purchase_order_sequences (
  sequence_name VARCHAR(64) NOT NULL,
  next_value BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (sequence_name)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
  purchase_order_id VARCHAR(32) NOT NULL,
  request_id VARCHAR(32) NOT NULL,
  offer_id VARCHAR(32) NOT NULL,
  supplier_id VARCHAR(32) NOT NULL,
  supplier_name VARCHAR(128) NOT NULL,
  plant_code VARCHAR(32) NOT NULL,
  material_code VARCHAR(64) NOT NULL,
  material_description VARCHAR(255) NOT NULL,
  quantity DECIMAL(18,4) NOT NULL,
  unit_of_measure VARCHAR(16) NOT NULL,
  unit_price DECIMAL(18,2) NOT NULL,
  total_amount DECIMAL(18,2) NOT NULL,
  currency CHAR(3) NOT NULL,
  requested_delivery_date DATE NOT NULL,
  confirmed_delivery_date DATE NOT NULL,
  status ENUM('registered', 'failed', 'cancelled') NOT NULL,
  external_reference VARCHAR(128) NOT NULL,
  registered_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (purchase_order_id),
  UNIQUE KEY uq_purchase_orders_request_offer (request_id, offer_id)
);
```

The table intentionally stores the A2A request fields needed for audit and demo inspection. It may be reconciled with the broader procurement data model as the shared enterprise database model evolves.

The Docker Compose initialization DDL should create a compatible `purchase_orders` table for fresh deployments. The runtime schema guard is still required because local demo volumes may be created, removed, or reused independently from application startup.

## Purchase Order Numbering

When `purchase_order_id` is omitted, the MySQL wrapper must allocate the next purchase order number inside the same database transaction used to insert the purchase order.

The numbering mechanism must be safe under concurrent requests. The recommended MySQL mechanism is a single-row counter in `purchase_order_sequences` updated atomically with `LAST_INSERT_ID`:

```sql
INSERT INTO purchase_order_sequences (sequence_name, next_value)
VALUES ('purchase_order', 0)
ON DUPLICATE KEY UPDATE sequence_name = sequence_name;

UPDATE purchase_order_sequences
SET next_value = LAST_INSERT_ID(next_value + 1)
WHERE sequence_name = 'purchase_order';

SELECT LAST_INSERT_ID();
```

The generated identifier format is:

```text
PO-YYYY-NNNNNN
```

Where:

- `YYYY` is the UTC registration year
- `NNNNNN` is the zero-padded sequence value

Example:

```text
PO-2026-000001
```

If `purchase_order_id` is supplied by the caller, the wrapper may use it as the internal purchase order identifier, but it must still enforce uniqueness.

## Idempotency

The tuple `(request_id, source_offer.offer_id)` is the idempotency key for persisted purchase order registration.

If a persisted purchase order already exists for the same key, the wrapper must return the existing `purchase_order_id`, `external_reference`, and `registered_at` instead of inserting a duplicate.

If the same key is submitted with materially different supplier, plant, material, quantity, currency, or amount fields, the wrapper must return a `failed` response with error code `IDEMPOTENCY_CONFLICT`.

## Read Behavior

The initial A2A capability only creates purchase orders. Internal read operations used by tests or future diagnostics must also ensure the schema exists before reading.

No new public A2A read skill is introduced in this version.

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

Persistence-specific error codes:

- `STORAGE_UNAVAILABLE`: the configured database cannot be reached
- `STORAGE_SCHEMA_ERROR`: required persistence schema creation or validation failed
- `PURCHASE_ORDER_NUMBER_ALLOCATION_FAILED`: the wrapper could not allocate a purchase order identifier
- `IDEMPOTENCY_CONFLICT`: the same idempotency key was submitted with conflicting purchase order content

---

# Operational Requirements

## Logging

Structured JSON logs.

## Tracing

The agent must follow the shared Agent Telemetry Specification:

[specs/observability/agent-telemetry.md](../observability/agent-telemetry.md)

It must participate in Locus lifecycle hooks so the built-in Locus `TelemetryHook` can emit native Locus telemetry for:

- `create_purchase_order` invocation count
- purchase order registration execution duration
- purchase order registration error count

The Locus lifecycle hook bridge must be attached at the A2A workflow execution boundary or the narrowest equivalent local task-handler wrapper.

Purchase order IDs, supplier IDs, and backend system references must not be used as metric attributes.

## Persistence

The fake backend does not persist data.

The Docker Compose MySQL backend must persist successful purchase order registrations as described in this specification.

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
