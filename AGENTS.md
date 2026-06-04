# AGENTS.md

# A2A Procurement Agents

Enterprise-grade multi-agent procurement platform based on the A2A protocol.

---

# Vision

This project demonstrates how independently developed AI agents can collaborate through the A2A protocol over HTTP to solve enterprise procurement workflows.

The platform models a rapid procurement scenario where multiple suppliers submit offers for urgent material requests and autonomous agents evaluate, rank, and process those offers according to configurable procurement policies.

The system is intentionally designed as a network of interoperable black-box agents.

Agents communicate exclusively through A2A contracts and HTTP transport.

No shared runtime code is used between agents.

---

# Architectural Principles

## 1. Independent Black Box Agents

Each agent:

- is independently deployable
- owns its internal implementation
- exposes only A2A contracts
- communicates via HTTP
- may evolve independently

Agents must never depend on internal implementation details of other agents.

---

## 2. A2A Native Communication

All inter-agent communication uses:

- A2A v1
- JSON-RPC 2.0
- HTTP transport
- Agent Cards for discovery

The platform is designed to showcase interoperability rather than framework coupling.

---

## 3. Spec Driven Development

Development follows a spec-first approach.

Specifications define:

- contracts
- schemas
- workflows
- events
- policies
- agent capabilities
- task semantics

Implementation follows specifications.

Specs are the source of truth.

---

## Specification Layout

All project specifications are maintained under the root-level
[`specs`](specs) directory.

The `specs` directory is organized by architectural concern:

- [`specs/agents`](specs/agents): agent contracts, capabilities, task semantics,
  Agent Card expectations, and A2A interaction boundaries for each agent.
- [`specs/schemas`](specs/schemas): JSON Schema definitions for A2A task inputs,
  outputs, and domain events.
- [`specs/data`](specs/data): procurement domain data model specifications.
- [`specs/discovery`](specs/discovery): agent and schema discovery behavior.
- [`specs/layers`](specs/layers): cross-cutting application layers that sit above
  or around agent interactions.
- [`specs/mcp`](specs/mcp): MCP server contracts and tool-facing integration
  specifications.
- [`specs/observability`](specs/observability): telemetry, tracing, and
  observability specifications.
- [`specs/ui`](specs/ui): user interface specifications.
- [`specs/examples`](specs/examples): example inputs, datasets, and reference
  material used to validate specifications and implementations.

When implementing or changing behavior, first locate the relevant specification
in `specs`, update it if the desired behavior is not already defined, and then
align the implementation and tests with that specification.

Schemas in `specs/schemas` define the external contracts used across agent
boundaries. Agent implementations must consume and produce data that conforms to
those schemas instead of relying on internal implementation assumptions.

---

## 4. Oracle 'Locus' Runtime

Agents are implemented using the Oracle Locus framework.

Locus provides:

- A2A transport support
- Agent Cards
- task lifecycle management
- protocol handling
- orchestration primitives

Locus is used for infrastructure/runtime support, not shared business code.

---

## 5. Enterprise Grade Architecture

The platform is designed with enterprise concerns in mind.

Planned enterprise capabilities include:

- checkpointing
- auditability
- distributed tracing
- secure communication
- authentication/authorization
- resumable workflows
- observability
- policy enforcement

Checkpointing persistence will use Oracle Database.

Security features will be introduced incrementally in later phases.

---

# Development Workflow

Development proceeds incrementally agent-by-agent.

The agent catalog grows as new agents are specified and implemented.

Detailed descriptions of current and planned agents are maintained in [AGENT_CATALOG.md](AGENT_CATALOG.md).

---

# Engineering Standards

## Documentation Language

All project documentation must be written in English.

This includes:

- specifications
- Markdown documentation
- changelog entries
- inline explanatory comments intended for maintainers
- user-facing examples committed to the repository

---

## Code Design

Generated and maintained code must stay simple, readable, and modular.

Prefer straightforward implementations over unnecessary abstraction.

Design choices should:

- avoid over-engineering
- favor readability over cleverness
- keep modules focused on clear responsibilities
- introduce abstractions only when they reduce meaningful complexity
- make the code easy to test, review, and evolve

---

## Python Documentation

All Python docstrings must be accurate, complete, and written in Google docstring format.

Docstrings should clearly describe:

- module responsibilities
- public classes
- public functions and methods
- arguments
- return values
- raised exceptions when relevant
- behavior that is not obvious from the implementation

Every Python file must start with a module-level multiline string header containing:

- `Author: L. Saetta`
- `Date Last Modified: YYYY-MM-DD`
- `License: MIT`
- a brief description of the file

Example:

```python
"""
Author: L. Saetta
Date Last Modified: 2026-05-27
License: MIT
Description:    Brief description of the module.
                xxxxx
"""
```

---

## Python Runtime Environment

Python development and local execution for this repository must use the `a2a-procurement-agents` conda environment.

Use:

```bash
conda activate a2a-procurement-agents
```

or:

```bash
conda run -n a2a-procurement-agents <command>
```

---

## Formatting

Code formatting uses:

- black

All committed code must be black-compliant.

---

## Static Analysis

Linting uses:

- pylint

All committed code must pass pylint validation.

---

## Testing

Testing uses:

- pytest

Unit tests are mandatory.

Integration tests should be added incrementally.

Every development step must include tests.

---

## Repository Quality Gate

Run the root-level quality gate before considering a development step complete:

```bash
./check.sh
```

The script runs:

- black format checking
- pylint validation
- pytest
- Procurement Intake Web UI TypeScript type checking

Python checks run through the `a2a-procurement-agents` conda environment.

---

# Definition of Done

A task is considered DONE only if:

- specifications updated
- implementation completed
- tests added/updated
- black passes
- pylint passes
- pytest passes
- `./check.sh` passes
- changelog updated

---

# Changelog

A changelog must be maintained continuously.

Every meaningful change must be documented.

---

# Repository Structure

/specs
    /agents
    /data
    /discovery
    /examples
    /layers
    /mcp
    /observability
    /schemas
    /ui

/services
    /offer-evaluation-agent

/docs

/tests

/deploy

---

# Long-Term Vision

The platform should evolve toward:

- dynamic agent discovery
- decentralized collaboration
- policy-driven orchestration
- cross-organizational interoperability
- resilient multi-agent workflows
- enterprise-grade autonomous procurement systems
