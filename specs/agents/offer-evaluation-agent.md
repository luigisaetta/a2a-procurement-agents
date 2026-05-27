# Offer Evaluation Agent Specification

Version: 0.1.0

Status: Draft

---

# Purpose

The Offer Evaluation Agent evaluates supplier offers received during a procurement workflow and determines the best offer according to configurable procurement rules.

The evaluation logic is driven by a Markdown policy document.

The agent produces:

- supplier ranking
- scoring details
- explainable evaluation output
- winning supplier selection

---

# Responsibilities

The agent must:

- receive a list of supplier offers
- validate input payloads
- load evaluation policies
- apply scoring logic
- rank offers
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

```json
{
  "request_id": "REQ-001",
  "plant_code": "PLANT-01",
  "currency": "EUR",
  "required_delivery_date": "2026-06-01",
  "offers": [
    {
      "supplier_id": "SUP-001",
      "supplier_name": "Supplier A",
      "price": 12000,
      "currency": "EUR",
      "delivery_date": "2026-05-29",
      "quality_score": 92,
      "reliability_score": 88
    }
  ]
}
```

---

# Policy Input

The agent receives a Markdown policy file.

Example:

```markdown
# Evaluation Rules

## Delivery Time
Weight: 40

## Price
Weight: 30

## Reliability
Weight: 20

## Quality
Weight: 10
```

---

# Output Schema

## EvaluateOffersResponse

```json
{
  "request_id": "REQ-001",
  "winner_supplier_id": "SUP-002",
  "ranking": [
    {
      "supplier_id": "SUP-002",
      "score": 91.4,
      "rank": 1
    },
    {
      "supplier_id": "SUP-001",
      "score": 84.2,
      "rank": 2
    }
  ],
  "evaluation_summary": "Supplier SUP-002 selected due to best delivery time and competitive pricing."
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

- ranking rationale
- scoring details
- applied weights
- policy version
- evaluation timestamp

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