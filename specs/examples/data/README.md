# Synthetic Automotive Procurement Seed Data

This directory contains portable CSV seed data for the minimal procurement data model.

The dataset supports a demo scenario for a high-end electric vehicle manufacturer.

## Files

| File | Entity | Rows |
| --- | --- | --- |
| `plants.csv` | `Plant` | 10 |
| `parts.csv` | `Part` | 50 |
| `suppliers.csv` | `Supplier` | 20 |
| `supplier_parts.csv` | `SupplierPart` | 150 |

## Design Notes

The data is intentionally synthetic. Supplier names are fictional and must not be interpreted as real companies.

The plant list includes one active plant in each of ten major European countries:

- Germany
- France
- United Kingdom
- Italy
- Spain
- Poland
- Netherlands
- Belgium
- Sweden
- Austria

The part catalog focuses on modern electric vehicles, including:

- battery systems
- electric powertrain
- charging and high-voltage electronics
- thermal management
- braking and chassis
- ADAS sensors
- cockpit electronics
- premium interior and body components
- connectivity modules

Each part is assigned to exactly three suppliers in `supplier_parts.csv`.

The assignment criteria are:

- every part must have multiple suppliers to support competitive offer collection
- each part has exactly one preferred supplier
- supplier assignments are grouped by capability area
- lead times and minimum order quantities vary by part complexity

The CSV files are intended to be portable. They can be loaded into a relational database, used as flat-file fixtures, or read by an MCP server that exposes lookup tools for `Plant`, `Part`, `Supplier`, and `SupplierPart`.
