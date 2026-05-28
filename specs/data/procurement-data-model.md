# Procurement Persistent Data Model Specification

Version: 0.2.0

Status: Draft

---

# Purpose

This specification defines the minimal persistent data model for the A2A Procurement Agents platform.

Agents remain independently deployable black boxes and continue to communicate through A2A contracts. The database stores the shared business entities needed by the procurement workflow, not agent implementation internals.

This document defines a logical data model only. Physical database DDL, indexes, seed data, and Oracle-specific implementation details will be specified later.

---

# Business Context

The enterprise is a high-end automotive manufacturer.

The company:

- operates 10 manufacturing plants in the main European countries
- manufactures luxury vehicles assembled from many parts
- buys parts from multiple suppliers
- allows the same part to be supplied by multiple suppliers
- asks suppliers for offers when a plant needs a quantity of a part
- expects each supplier offer to include both part cost and shipping cost to the target plant
- creates a purchase order from the selected supplier offer

The first data model intentionally supports a simple procurement flow:

```text
Plant + Part + Supplier master data
-> ProcurementRequest
-> SupplierOffer
-> PurchaseOrder
```

---

# Design Principles

The data model must:

- stay minimal for the first implementation
- represent business facts, not agent runtime internals
- keep agent coupling low
- support supplier competition for the same part
- make part cost and shipping cost explicit
- support purchase order creation from a selected offer
- remain easy to evolve when orchestration, compliance, audit, and workflow persistence are added

---

# Core Entities

The minimal persistent model contains seven entities:

| Entity | Purpose |
| --- | --- |
| `Plant` | Manufacturing plant that needs parts. |
| `Part` | Automotive part used in vehicle assembly. |
| `Supplier` | Supplier that can provide parts. |
| `SupplierPart` | Many-to-many relationship between suppliers and parts. |
| `ProcurementRequest` | Request for a quantity of one part at one plant. |
| `SupplierOffer` | Supplier offer including part cost and shipping cost. |
| `PurchaseOrder` | Purchase order created from the selected offer. |

For the initial model, a `ProcurementRequest` contains exactly one part. Multi-line procurement requests can be introduced later with a separate request-line entity if needed.

---

# Common Attributes

All entities should include these attributes unless explicitly stated otherwise:

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `created_at` | timestamp | yes | Timestamp when the record was created. |
| `updated_at` | timestamp | yes | Timestamp when the record was last updated. |

Optional technical attributes such as `created_by`, `updated_by`, and optimistic concurrency `version` may be added during physical schema design, but they are not required for the first logical model.

---

# Plant

Represents a manufacturing plant operated by the company.

The initial dataset should contain 10 active European plants.

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `plant_id` | string | yes | Unique plant identifier. |
| `plant_code` | string | yes | Short plant code used in requests and examples. |
| `plant_name` | string | yes | Human-readable plant name. |
| `country_code` | string | yes | ISO country code. |
| `country_name` | string | yes | Human-readable country name. |
| `city` | string | yes | Plant city. |
| `address` | string | no | Plant address used for supplier shipping estimates. |
| `is_active` | boolean | yes | Whether the plant can receive procurement requests. |

Primary key:

- `plant_id`

Unique constraints:

- `plant_code`

Read by:

- Bid Collection Agent
- Offer Evaluation Agent
- Purchase Order Agent

---

# Part

Represents an automotive part used in vehicle assembly.

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `part_id` | string | yes | Unique part identifier. |
| `part_code` | string | yes | Business part code. |
| `part_name` | string | yes | Human-readable part name. |
| `description` | string | no | Part description. |
| `category` | string | no | Part category, such as `braking`, `interior`, `electronics`, or `powertrain`. |
| `unit_of_measure` | string | yes | Unit of measure, such as `EA`. |
| `is_active` | boolean | yes | Whether the part can be requested. |

Primary key:

- `part_id`

Unique constraints:

- `part_code`

Read by:

- Bid Collection Agent
- Offer Evaluation Agent
- Purchase Order Agent

---

# Supplier

Represents a supplier that can provide one or more parts.

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `supplier_id` | string | yes | Unique supplier identifier. |
| `supplier_name` | string | yes | Human-readable supplier name. |
| `country_code` | string | yes | ISO country code. |
| `country_name` | string | yes | Human-readable country name. |
| `contact_endpoint` | string | yes | API endpoint or logical endpoint used to request offers. |
| `currency` | string | yes | Supplier default ISO 4217 currency. |
| `quality_score` | number | no | Supplier quality score on a 0 to 100 scale. |
| `reliability_score` | number | no | Supplier reliability score on a 0 to 100 scale. |
| `is_active` | boolean | yes | Whether the supplier can receive offer requests. |

Primary key:

- `supplier_id`

Read by:

- Bid Collection Agent
- Offer Evaluation Agent
- Purchase Order Agent

---

# SupplierPart

Represents the many-to-many relationship between suppliers and parts.

This entity is required because:

- one supplier may provide many parts
- one part may be provided by many suppliers
- offer collection is meaningful only when multiple suppliers can bid for the same part

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `supplier_part_id` | string | yes | Unique supplier-part relationship identifier. |
| `supplier_id` | string | yes | Supplier identifier. |
| `part_id` | string | yes | Part identifier. |
| `lead_time_days` | integer | no | Typical delivery lead time in days. |
| `min_order_quantity` | number | no | Minimum order quantity supported by the supplier for this part. |
| `is_preferred` | boolean | yes | Whether the supplier is preferred for this part. |
| `is_active` | boolean | yes | Whether this supplier-part relationship can be used. |

Primary key:

- `supplier_part_id`

Foreign keys:

- `supplier_id` references `Supplier.supplier_id`
- `part_id` references `Part.part_id`

Unique constraints:

- `supplier_id`, `part_id`

Read by:

- Bid Collection Agent

---

# ProcurementRequest

Represents a request for a quantity of one part to be delivered to one plant.

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `request_id` | string | yes | Unique procurement request identifier. |
| `plant_id` | string | yes | Plant that needs the part. |
| `part_id` | string | yes | Requested part. |
| `quantity` | number | yes | Requested quantity. |
| `required_delivery_date` | date | yes | Required delivery date. |
| `currency` | string | yes | Expected ISO 4217 currency for offer comparison. |
| `status` | enum | yes | Request status: `open`, `offers_requested`, `offers_received`, `evaluated`, `ordered`, `cancelled`, `failed`. |
| `requested_by` | string | no | User, system, or process that created the request. |

Primary key:

- `request_id`

Foreign keys:

- `plant_id` references `Plant.plant_id`
- `part_id` references `Part.part_id`

Written by:

- Procurement Orchestrator or a future request intake process

Read by:

- Bid Collection Agent
- Offer Evaluation Agent
- Purchase Order Agent

---

# SupplierOffer

Represents a supplier offer for a procurement request.

The offer must include the cost of the requested parts and the shipping cost to the target plant. The total cost is the value evaluated by the Offer Evaluation Agent.

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `offer_id` | string | yes | Unique supplier offer identifier. |
| `request_id` | string | yes | Procurement request being answered. |
| `supplier_id` | string | yes | Supplier submitting the offer. |
| `part_id` | string | yes | Offered part. |
| `plant_id` | string | yes | Destination plant used for shipping cost. |
| `quantity` | number | yes | Offered quantity. |
| `parts_cost` | number | yes | Total cost of the requested parts, excluding shipping. |
| `shipping_cost` | number | yes | Shipping cost to the destination plant. |
| `total_cost` | number | yes | `parts_cost` plus `shipping_cost`. |
| `currency` | string | yes | ISO 4217 offer currency. |
| `delivery_date` | date | yes | Supplier committed delivery date. |
| `valid_until` | date | yes | Date until which the offer remains valid. |
| `status` | enum | yes | Offer status: `received`, `selected`, `rejected`, `expired`. |

Primary key:

- `offer_id`

Foreign keys:

- `request_id` references `ProcurementRequest.request_id`
- `supplier_id` references `Supplier.supplier_id`
- `part_id` references `Part.part_id`
- `plant_id` references `Plant.plant_id`

Written by:

- Bid Collection Agent

Read by:

- Offer Evaluation Agent
- Purchase Order Agent

Validation rules:

- `quantity` must match the requested quantity unless partial offers are explicitly supported in a later version.
- `part_id` must match the requested part.
- `plant_id` must match the requested plant.
- `total_cost` must equal `parts_cost + shipping_cost`.

---

# PurchaseOrder

Represents a purchase order created from the selected supplier offer.

For the initial model, one purchase order is created from one selected offer for one request.

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `purchase_order_id` | string | yes | Unique purchase order identifier. |
| `request_id` | string | yes | Procurement request fulfilled by the purchase order. |
| `offer_id` | string | yes | Selected supplier offer. |
| `supplier_id` | string | yes | Supplier receiving the purchase order. |
| `plant_id` | string | yes | Destination plant. |
| `part_id` | string | yes | Ordered part. |
| `quantity` | number | yes | Ordered quantity. |
| `total_amount` | number | yes | Total purchase order amount. |
| `currency` | string | yes | ISO 4217 purchase order currency. |
| `status` | enum | yes | Purchase order status: `created`, `registered`, `failed`, `cancelled`. |
| `external_reference` | string | no | External ERP or purchase order system reference. |
| `registered_at` | timestamp | no | Timestamp when the purchase order was registered externally. |

Primary key:

- `purchase_order_id`

Foreign keys:

- `request_id` references `ProcurementRequest.request_id`
- `offer_id` references `SupplierOffer.offer_id`
- `supplier_id` references `Supplier.supplier_id`
- `plant_id` references `Plant.plant_id`
- `part_id` references `Part.part_id`

Written by:

- Purchase Order Agent

Read by:

- Procurement Orchestrator

Validation rules:

- `total_amount` should match the selected offer `total_cost`.
- `supplier_id`, `plant_id`, `part_id`, and `quantity` should match the selected offer.

---

# Minimal Relationships

The initial relationship chain is:

1. `Plant` receives many `ProcurementRequest` records.
2. `Part` appears in many `ProcurementRequest` records.
3. `Supplier` can provide many `Part` records through `SupplierPart`.
4. `Part` can be provided by many `Supplier` records through `SupplierPart`.
5. `ProcurementRequest` receives many `SupplierOffer` records.
6. `SupplierOffer` belongs to one `Supplier`, one `Part`, and one `Plant`.
7. `PurchaseOrder` is created from one selected `SupplierOffer`.

---

# Agent Usage

## Bid Collection Agent

Reads:

- `Plant`
- `Part`
- `Supplier`
- `SupplierPart`
- `ProcurementRequest`

Writes:

- `SupplierOffer`

## Offer Evaluation Agent

Reads:

- `ProcurementRequest`
- `SupplierOffer`
- `Supplier`

Updates:

- `SupplierOffer.status`

## Purchase Order Agent

Reads:

- `ProcurementRequest`
- `SupplierOffer`
- `Supplier`
- `Plant`
- `Part`

Writes:

- `PurchaseOrder`

---

# Deferred Entities

The following entities are intentionally deferred:

- procurement request lines for multi-part requests
- supplier bid request and bid response audit records
- offer evaluation runs and decision explanations
- compliance checks
- workflow run records
- A2A task records
- audit events
- supplier contracts and price lists
- shipment and delivery tracking
- invoices and payments

These entities can be added when the workflow requires stronger auditability, compliance, orchestration, or financial integration.
