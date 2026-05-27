# Offer Evaluation Agent Specification

Version: 0.1.0

Status: Draft

---

# Purpose

The Offer Evaluation Agent evaluates supplier offers received during a procurement workflow and determines the best offer according to configurable procurement rules.

The evaluation logic is driven by a Markdown policy document.

The agent produces:

- selected supplier offer details
- winning supplier selection
- concise explanation of the decision

---

# Responsibilities

The agent must:

- receive a list of supplier offers
- validate input payloads
- load evaluation policies
- apply scoring logic
- select the best offer according to the configured policy
- generate explainable reasoning
- return evaluation results

---

# Non Responsibilities

The agent does NOT:

- contact suppliers
- negotiate offers
- generate purchase orders
- persist workflow state
- manage orchestration

---

# Communication Protocol

## Transport

- HTTP

## Protocol

- A2A v1
- JSON-RPC 2.0

---

# Agent Card

## Skills

### evaluate_offers

Evaluates supplier offers according to procurement policies.

---

# Input Schema

## EvaluateOffersRequest

Canonical schema: [specs/schemas/evaluate-offers-request.schema.json](../schemas/evaluate-offers-request.schema.json)

```json
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
      "supplier_name": "Supplier A",
      "price": 12000.0,
      "currency": "EUR",
      "delivery_date": "2026-06-10",
      "quality_score": 92,
      "reliability_score": 88,
      "valid_until": "2026-06-01"
    }
  ]
}
```

---

# Policy Input

The agent reads a local Markdown policy file.

Default local policy:

- [services/offer-evaluation-agent/policies/standard-urgent-procurement-v1.md](../../services/offer-evaluation-agent/policies/standard-urgent-procurement-v1.md)

Policy ID:

- `standard-urgent-procurement-v1`

Policy version:

- `0.1.0`

The policy excludes offers with a currency different from the request currency and offers with a delivery date later than the requested delivery date.

Eligible offers are selected primarily by lowest cost, with supplier reliability and earlier delivery date used as tie-breakers.

---

# Output Schema

## EvaluateOffersResponse

Canonical schema: [specs/schemas/evaluate-offers-response.schema.json](../schemas/evaluate-offers-response.schema.json)

```json
{
  "request_id": "REQ-2026-0001",
  "decision": {
    "status": "selected_offer",
    "selected_offer": {
      "offer_id": "OFF-002",
      "supplier_id": "SUP-002",
      "supplier_name": "Supplier B",
      "price": 11800.0,
      "currency": "EUR",
      "delivery_date": "2026-06-09",
      "quality_score": 90,
      "reliability_score": 94,
      "valid_until": "2026-06-01"
    }
  },
  "explanation": "Supplier B was selected because it provides the lowest eligible cost and meets the required delivery date."
}
```

When no offers remain valid after policy exclusions, the agent returns:

```json
{
  "request_id": "REQ-2026-0001",
  "decision": {
    "status": "no_valid_offers",
    "reasons": [
      "All offers were excluded because their delivery dates are later than the requested delivery date."
    ]
  },
  "explanation": "No supplier offer was selected because every offer was excluded by the evaluation policy."
}
```

---

# Validation Rules

The agent must validate:

- mandatory fields
- numeric score ranges
- supported currencies
- delivery date consistency
- duplicate supplier entries

Invalid payloads must generate structured validation errors.

---

# Explainability Requirements

The evaluation result must include:

- the selected offer details
- a no-valid-offers decision when all offers are excluded
- a concise rationale for the decision
- the relevant policy criteria considered during evaluation

---

# Error Handling

The agent must return structured errors for:

- invalid payload
- malformed policy
- unsupported scoring rule
- missing required fields
- internal processing failure

---

# Future Extensions

Planned future capabilities:

- LLM-assisted evaluation reasoning
- negotiation scoring
- sustainability scoring
- supplier historical analytics
- confidence scoring
- policy simulation mode
- human approval workflows

---

# Operational Requirements

## Logging

Structured JSON logs.

## Tracing

Distributed tracing support.

## Checkpointing

Future support via Oracle Database.

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
