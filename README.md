# A2A Procurement Agents

[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Pylint](https://img.shields.io/badge/lint-pylint-yellowgreen.svg)](https://github.com/pylint-dev/pylint)
[![Pytest](https://img.shields.io/badge/tests-pytest-blueviolet.svg)](https://github.com/pytest-dev/pytest)
[![A2A](https://img.shields.io/badge/protocol-A2A%20v1-orange.svg)](https://github.com/a2aproject/A2A)

Enterprise procurement is becoming too fast, too distributed, and too policy-heavy for a single monolithic assistant.

This project explores a different shape: a network of independently deployable AI agents that collaborate over open A2A contracts to handle urgent procurement workflows.

The first scenario is rapid material sourcing. Multiple suppliers submit offers for an urgent request, autonomous agents evaluate those offers against procurement policy, and the system produces a ranked, explainable decision that can later feed orchestration, approval, purchasing, auditing, and fulfillment flows.

## Why This Project Exists

Most multi-agent demos are tightly coupled: agents share runtime objects, hidden memory, framework internals, or direct function calls. That is convenient for a demo, but it is not how enterprise systems usually evolve.

This repository is intentionally different.

Each agent is treated as a black box:

- independently deployable
- independently testable
- independently versioned
- discoverable through an Agent Card
- reachable over HTTP
- integrated only through A2A protocol contracts

The goal is to demonstrate agent interoperability, not framework coupling.

## The A2A Model

The platform uses the Agent2Agent protocol, also known as A2A, as the communication boundary between agents.

A2A is the contract layer that lets one agent discover what another agent can do, send it a task, exchange structured messages, and receive task results without knowing how the remote agent is implemented.

In this project, A2A communication means:

- **Protocol:** A2A v1
- **Transport:** HTTP
- **Message format:** JSON-RPC 2.0
- **Discovery:** Agent Cards
- **Integration rule:** no agent depends on another agent's internal code

This matters because procurement workflows are naturally cross-domain. Evaluation, supplier communication, compliance, purchase order generation, audit, and orchestration can each evolve at different speeds. A2A gives those agents a common language while preserving independent ownership.

Reference links:

- [Agent2Agent A2A specification on GitHub](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)
- [Agent2Agent A2A project on GitHub](https://github.com/a2aproject/A2A)

## Runtime Foundation

Agents are implemented with [Oracle Locus](https://locusagents.oracle.com/), used as the runtime layer for agent execution and A2A infrastructure.

Locus provides the mechanics this project needs:

- A2A server and client support
- Agent Card support
- task lifecycle handling
- protocol plumbing
- orchestration primitives
- model-provider abstraction
- observability and checkpointing foundations

Business behavior remains owned by each agent. Locus is used for runtime support, not as a shared business-code dependency between agents.

Reference link:

- [Oracle Locus on GitHub](https://github.com/oracle-samples/locus)

## System Components

Development proceeds component by component. This first draft roadmap defines the initial procurement system.

| Component | Type | Description |
| --- | --- | --- |
| Conversational Procurement Intake Layer | HTTP application layer | Serves the UI over HTTP, converts natural-language requests into validated orchestration JSON, uses read-only MCP lookup for grounding, and calls the Procurement Orchestrator through an A2A client. |
| Procurement Orchestrator | A2A agent | Coordinates the end-to-end structured procurement workflow across specialized A2A agents. |
| Bid Collection Agent | A2A agent | Identifies suppliers through MCP, requests offers, collects bids, and prepares them for evaluation. |
| Offer Evaluation Agent | A2A agent | Evaluates supplier offers, applies procurement policy, selects the winning offer, and returns an explanation. |
| Compliance Agent | A2A agent | Checks procurement decisions and supplier data against compliance rules. |
| Purchase Order Agent | A2A agent | Registers purchase orders in the company purchase order system and returns a technical confirmation. |

Detailed component descriptions are maintained in [AGENT_CATALOG.md](AGENT_CATALOG.md).

## Spec-First Development

This repository follows a spec-first development model.

Specifications define the contract before implementation:

- persistent data entities
- schemas
- workflows
- events
- policies
- agent capabilities
- task semantics
- error behavior

Implementation must follow the specifications. When behavior changes, the specification changes first or in the same development step.

## Repository Layout

```text
specs/
  agents/
  schemas/
  events/
  workflows/
  policies/
  examples/

services/
  bid-collection-agent/
  offer-evaluation-agent/
  procurement-data-mcp/
  purchase-order-agent/

deployments/
  docker-compose/

docs/
tests/
deploy/
```

## Engineering Principles

The project is designed with enterprise-grade concerns in mind:

- auditability
- deterministic contracts
- explainable decisions
- structured validation
- distributed tracing
- secure communication
- resumable workflows
- checkpointing persistence
- policy enforcement

The first implementation steps focus on the Offer Evaluation Agent. Security, checkpointing, orchestration, and observability features will be introduced incrementally as the agent network expands.

Operational startup instructions are available in the agent quickstarts:

- [Bid Collection Agent README](services/bid-collection-agent/README.md)
- [Offer Evaluation Agent Quickstart](services/offer-evaluation-agent/QUICKSTART.md)
- [Procurement Data MCP Server README](services/procurement-data-mcp/README.md)
- [Procurement Orchestrator README](services/procurement-orchestrator/README.md)
- [Purchase Order Agent Quickstart](services/purchase-order-agent/QUICKSTART.md)

The first cross-agent Docker Compose deployment is available in [deployments/docker-compose](deployments/docker-compose).

The initial persistent data model is specified in [specs/data/procurement-data-model.md](specs/data/procurement-data-model.md).

The read-only procurement data MCP server is specified in [specs/mcp/procurement-data-mcp-server.md](specs/mcp/procurement-data-mcp-server.md).

The draft conversational procurement intake layer is specified in [specs/layers/conversational-procurement-intake.md](specs/layers/conversational-procurement-intake.md).

The draft procurement orchestration workflow is specified in [specs/agents/procurement-orchestrator.md](specs/agents/procurement-orchestrator.md).

## Development Standards

Code and documentation follow the repository rules in [AGENTS.md](AGENTS.md).

Core standards include:

- all documentation is written in English
- Python code is formatted with `black`
- Python code is linted with `pylint`
- tests are written with `pytest`
- Python docstrings use Google docstring format
- every meaningful change is documented in the changelog

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
