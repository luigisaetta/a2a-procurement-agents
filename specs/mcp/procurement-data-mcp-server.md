# Procurement Data MCP Server Specification

Version: 0.1.0

Status: Draft

---

# Purpose

The Procurement Data MCP Server exposes read-only access to the procurement demo data model through the Model Context Protocol.

The server provides MCP tools that allow agents and clients to retrieve master data needed for sourcing and procurement workflows:

- plants
- parts
- suppliers
- supplier-part relationships

The initial server does not write business records and does not mutate database state.

---

# Runtime Choice

The project currently uses Oracle Locus for A2A agents.

Local verification found no MCP runtime module exposed by the installed Locus package:

- `locus.mcp`: not available
- `locus.mcp.server`: not available

The initial MCP server should therefore use FastMCP or the official Python MCP SDK.

Preferred initial runtime:

- FastMCP

The implementation must keep MCP tool logic isolated from the runtime wrapper so the server can move to a future Locus MCP runtime if one becomes available.

---

# MCP Compliance Requirements

The server must follow the Model Context Protocol tool model.

It must:

- expose capabilities through MCP tools
- support standard MCP tool discovery
- support standard MCP tool invocation
- use JSON-compatible tool inputs and outputs
- return structured errors for invalid arguments and backend failures
- avoid custom protocol extensions for the initial implementation

The implementation should support:

- `tools/list`
- `tools/call`

Supported transport:

- streamable HTTP for Docker Compose and local development

The server must not expose or document stdio as a supported transport. Local MCP clients must connect to the HTTP endpoint.

---

# Data Backend

The initial backend is the MySQL demo data store defined in the Docker Compose deployment.

Default schema:

- `procurement_demo`

Tables read by this MCP server:

- `plants`
- `parts`
- `suppliers`
- `supplier_parts`

The server must not write to:

- `procurement_requests`
- `supplier_offers`
- `purchase_orders`

CSV seed files remain the portable source dataset. MySQL is the demo runtime backend.

---

# Service Folder

Planned implementation folder:

```text
services/procurement-data-mcp/
  README.md
  src/procurement_data_mcp/
    __init__.py
    config.py
    database.py
    server.py
    tools.py
  tests/
```

---

# Configuration

The server must read configuration from environment variables.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `PROCUREMENT_DB_HOST` | no | `127.0.0.1` | MySQL host. |
| `PROCUREMENT_DB_PORT` | no | `3306` | MySQL port. |
| `PROCUREMENT_DB_NAME` | no | `procurement_demo` | MySQL schema name. |
| `PROCUREMENT_DB_USER` | yes | none | MySQL user. |
| `PROCUREMENT_DB_PASSWORD` | yes | none | MySQL password. |

Docker Compose should pass these values from the MySQL service configuration.

---

# Tool Design

Tool names must be stable and business-oriented.

All tools are read-only.

All list tools should support simple pagination.

Pagination arguments:

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `limit` | integer | no | `50` | Maximum number of records to return. |
| `offset` | integer | no | `0` | Number of records to skip. |

Validation rules:

- `limit` must be between `1` and `200`
- `offset` must be greater than or equal to `0`

---

# Tools

## list_plants

Returns active and inactive plants.

Input:

```json
{
  "limit": 50,
  "offset": 0,
  "active_only": true
}
```

Arguments:

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `limit` | integer | no | `50` | Maximum records to return. |
| `offset` | integer | no | `0` | Records to skip. |
| `active_only` | boolean | no | `true` | Whether to return only active plants. |

Output:

```json
{
  "items": [
    {
      "plant_id": "PLANT-001",
      "plant_code": "DE-MUN",
      "plant_name": "LuxEV Munich Assembly Plant",
      "country_code": "DE",
      "country_name": "Germany",
      "city": "Munich",
      "address": "Leopoldstrasse 240 Munich",
      "is_active": true
    }
  ],
  "limit": 50,
  "offset": 0,
  "count": 1
}
```

## get_plant

Returns one plant by `plant_id` or `plant_code`.

Input:

```json
{
  "plant_id": "PLANT-001"
}
```

Arguments:

| Argument | Type | Required | Description |
| --- | --- | --- | --- |
| `plant_id` | string | conditionally | Plant identifier. |
| `plant_code` | string | conditionally | Plant business code. |

Exactly one of `plant_id` or `plant_code` must be provided.

Output:

```json
{
  "plant": {
    "plant_id": "PLANT-001",
    "plant_code": "DE-MUN",
    "plant_name": "LuxEV Munich Assembly Plant",
    "country_code": "DE",
    "country_name": "Germany",
    "city": "Munich",
    "address": "Leopoldstrasse 240 Munich",
    "is_active": true
  }
}
```

## list_parts

Returns parts, optionally filtered by category.

Input:

```json
{
  "category": "battery",
  "limit": 50,
  "offset": 0,
  "active_only": true
}
```

Arguments:

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `category` | string | no | none | Optional part category filter. |
| `limit` | integer | no | `50` | Maximum records to return. |
| `offset` | integer | no | `0` | Records to skip. |
| `active_only` | boolean | no | `true` | Whether to return only active parts. |

Output:

```json
{
  "items": [
    {
      "part_id": "PART-001",
      "part_code": "EV-BAT-MOD-001",
      "part_name": "High Density Battery Module",
      "description": "Modular lithium battery pack segment",
      "category": "battery",
      "unit_of_measure": "EA",
      "reference_unit_price": 1450.0,
      "reference_currency": "EUR",
      "is_active": true
    }
  ],
  "limit": 50,
  "offset": 0,
  "count": 1
}
```

## get_part

Returns one part by `part_id` or `part_code`.

Input:

```json
{
  "part_code": "EV-BAT-MOD-001"
}
```

Arguments:

| Argument | Type | Required | Description |
| --- | --- | --- | --- |
| `part_id` | string | conditionally | Part identifier. |
| `part_code` | string | conditionally | Part business code. |

Exactly one of `part_id` or `part_code` must be provided.

Output:

```json
{
  "part": {
    "part_id": "PART-001",
    "part_code": "EV-BAT-MOD-001",
    "part_name": "High Density Battery Module",
    "description": "Modular lithium battery pack segment",
    "category": "battery",
    "unit_of_measure": "EA",
    "reference_unit_price": 1450.0,
    "reference_currency": "EUR",
    "is_active": true
  }
}
```

## list_suppliers

Returns suppliers.

Input:

```json
{
  "limit": 50,
  "offset": 0,
  "active_only": true
}
```

Arguments:

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `limit` | integer | no | `50` | Maximum records to return. |
| `offset` | integer | no | `0` | Records to skip. |
| `active_only` | boolean | no | `true` | Whether to return only active suppliers. |

Output:

```json
{
  "items": [
    {
      "supplier_id": "SUP-001",
      "supplier_name": "VoltEdge Components",
      "country_code": "DE",
      "country_name": "Germany",
      "contact_endpoint": "mock://suppliers/SUP-001/offers",
      "currency": "EUR",
      "quality_score": 94,
      "reliability_score": 92,
      "is_active": true
    }
  ],
  "limit": 50,
  "offset": 0,
  "count": 1
}
```

## get_supplier

Returns one supplier by `supplier_id`.

Input:

```json
{
  "supplier_id": "SUP-001"
}
```

Arguments:

| Argument | Type | Required | Description |
| --- | --- | --- | --- |
| `supplier_id` | string | yes | Supplier identifier. |

Output:

```json
{
  "supplier": {
    "supplier_id": "SUP-001",
    "supplier_name": "VoltEdge Components",
    "country_code": "DE",
    "country_name": "Germany",
    "contact_endpoint": "mock://suppliers/SUP-001/offers",
    "currency": "EUR",
    "quality_score": 94,
    "reliability_score": 92,
    "is_active": true
  }
}
```

## list_suppliers_for_part

Returns suppliers that can provide a given part.

Input:

```json
{
  "part_id": "PART-001",
  "active_only": true
}
```

Arguments:

| Argument | Type | Required | Description |
| --- | --- | --- | --- |
| `part_id` | string | conditionally | Part identifier. |
| `part_code` | string | conditionally | Part business code. |
| `active_only` | boolean | no | Whether to return only active supplier-part relationships and active suppliers. |

Exactly one of `part_id` or `part_code` must be provided.

Output:

```json
{
  "part": {
    "part_id": "PART-001",
    "part_code": "EV-BAT-MOD-001",
    "part_name": "High Density Battery Module",
    "reference_unit_price": 1450.0,
    "reference_currency": "EUR"
  },
  "items": [
    {
      "supplier_part_id": "SP-001",
      "supplier_id": "SUP-001",
      "supplier_name": "VoltEdge Components",
      "country_code": "DE",
      "country_name": "Germany",
      "contact_endpoint": "mock://suppliers/SUP-001/offers",
      "currency": "EUR",
      "quality_score": 94,
      "reliability_score": 92,
      "lead_time_days": 14,
      "min_order_quantity": 10,
      "is_preferred": true
    }
  ],
  "count": 1
}
```

## list_parts_for_supplier

Returns parts that a supplier can provide.

Input:

```json
{
  "supplier_id": "SUP-001",
  "active_only": true
}
```

Arguments:

| Argument | Type | Required | Description |
| --- | --- | --- | --- |
| `supplier_id` | string | yes | Supplier identifier. |
| `active_only` | boolean | no | Whether to return only active supplier-part relationships and active parts. |

Output:

```json
{
  "supplier": {
    "supplier_id": "SUP-001",
    "supplier_name": "VoltEdge Components"
  },
  "items": [
    {
      "supplier_part_id": "SP-001",
      "part_id": "PART-001",
      "part_code": "EV-BAT-MOD-001",
      "part_name": "High Density Battery Module",
      "category": "battery",
      "unit_of_measure": "EA",
      "lead_time_days": 14,
      "min_order_quantity": 10,
      "is_preferred": true
    }
  ],
  "count": 1
}
```

## find_suppliers_for_part

Returns supplier candidates for a sourcing request.

This is the main workflow-oriented lookup tool for the Bid Collection Agent.

Input:

```json
{
  "part_code": "EV-BAT-MOD-001",
  "plant_id": "PLANT-001",
  "quantity": 10,
  "active_only": true
}
```

Arguments:

| Argument | Type | Required | Description |
| --- | --- | --- | --- |
| `part_id` | string | conditionally | Part identifier. |
| `part_code` | string | conditionally | Part business code. |
| `plant_id` | string | no | Optional destination plant identifier for context. |
| `plant_code` | string | no | Optional destination plant code for context. |
| `quantity` | number | no | Optional requested quantity. |
| `active_only` | boolean | no | Whether to return only active data. |

Exactly one of `part_id` or `part_code` must be provided.

At most one of `plant_id` or `plant_code` may be provided.

Output:

```json
{
  "part": {
    "part_id": "PART-001",
    "part_code": "EV-BAT-MOD-001",
    "part_name": "High Density Battery Module",
    "unit_of_measure": "EA",
    "reference_unit_price": 1450.0,
    "reference_currency": "EUR"
  },
  "plant": {
    "plant_id": "PLANT-001",
    "plant_code": "DE-MUN",
    "plant_name": "LuxEV Munich Assembly Plant"
  },
  "requested_quantity": 10,
  "items": [
    {
      "supplier_id": "SUP-001",
      "supplier_name": "VoltEdge Components",
      "country_code": "DE",
      "country_name": "Germany",
      "contact_endpoint": "mock://suppliers/SUP-001/offers",
      "currency": "EUR",
      "quality_score": 94,
      "reliability_score": 92,
      "lead_time_days": 14,
      "min_order_quantity": 10,
      "is_preferred": true,
      "eligible_for_quantity": true
    }
  ],
  "count": 1
}
```

Eligibility rule:

- `eligible_for_quantity` is `true` when `quantity` is omitted or `quantity >= min_order_quantity`
- if `min_order_quantity` is null, the supplier is eligible for any positive quantity

Sorting:

1. preferred suppliers first
2. higher reliability score
3. higher quality score
4. lower lead time
5. supplier ID

---

# Error Handling

The server must return structured MCP tool errors for:

- invalid argument combinations
- missing required identifiers
- unknown plant, part, or supplier
- invalid pagination values
- database connection failure
- database query failure

Tool errors should include:

- stable error code
- concise message
- optional details object

Example error payload:

```json
{
  "code": "PART_NOT_FOUND",
  "message": "No part was found for part_code EV-UNKNOWN.",
  "details": {
    "part_code": "EV-UNKNOWN"
  }
}
```

---

# Security

Initial implementation:

- local streamable HTTP MCP server
- read-only database user preferred
- no write tools

Future implementation:

- transport-level authentication
- least-privilege database credentials
- optional tenant or organization filters

---

# Definition Of Done

The MCP server is complete only if:

- this specification is implemented
- FastMCP or official MCP SDK is used without custom protocol extensions
- all tools are read-only
- unit tests cover tool validation and query behavior
- integration test verifies reads from the Docker Compose MySQL service
- README documents local startup and tool usage
- Docker Compose includes the MCP service when runtime dependencies are available
- changelog is updated
