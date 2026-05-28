# Changelog

All meaningful changes to this project are documented in this file.

## 2026-05-28

- Changed the default Procurement Data MCP HTTP port from `8010` to `8011` across Docker Compose, examples, documentation, and bid collection tests.
- Added a manual Procurement Orchestrator end-to-end Python client for the Docker Compose deployment and documented build, start, stop, log, and client commands.
- Implemented the initial Procurement Orchestrator Agent with A2A downstream calls, streaming JSON progress events, retry handling, purchase order creation, Docker Compose deployment, tests, and minimal structured logging.
- Added the draft Procurement Orchestrator Agent specification and canonical orchestration request, streaming event, and final response schemas.
- Implemented the initial Bid Collection Agent with MCP-backed supplier discovery, simulated supplier offer collection, A2A server wiring, Docker Compose deployment, and tests.
- Standardized the Procurement Data MCP Server on streamable HTTP for both Docker Compose and local development.
- Added the Procurement Data MCP Server to the Docker Compose deployment using streamable HTTP and the MySQL demo data store.
- Implemented the initial read-only Procurement Data MCP Server with FastMCP, MySQL-backed lookup tools, unit tests, and local startup documentation.
- Updated local development instructions to use the `a2a-procurement-agents` conda environment and configured pytest to collect both agent test suites together.
- Added the draft Procurement Data MCP Server specification for read-only access to plants, parts, suppliers, and supplier-part relationships.
- Added MySQL to the Docker Compose deployment with schema initialization and synthetic procurement seed data loading.
- Added synthetic CSV seed data for plants, electric vehicle parts, suppliers, and supplier-part assignments.
- Simplified the persistent procurement data model around the initial automotive scenario and the seven core entities needed for the first workflow.
- Added the initial persistent procurement data model specification.
- Added the draft Bid Collection Agent specification and canonical bid collection and supplier bid schemas, consolidating supplier identification, bid request, and offer collection into one agent.
- Added an initial Docker Compose deployment for running the Offer Evaluation and Purchase Order A2A agents together.
- Added a sample purchase order JSON payload and manual A2A test client for the Purchase Order Agent.
- Updated the Purchase Order Agent quickstart with sample invocation instructions.
- Added the initial Purchase Order Agent A2A server implementation with deterministic input validation and fake purchase order system registration.
- Added the Purchase Order Agent local environment files, quickstart, and unit tests.
- Updated the agent catalog and README to include Purchase Order Agent implementation and startup references.
- Added the initial Purchase Order Agent specification and JSON Schemas.
- Added a root-level future extensions document with Langfuse observability as the first candidate extension.
- Declared JSON input and output modes for the Offer Evaluation Agent A2A skill while keeping text/plain compatibility.

## 2026-05-27

- Reworked the Offer Evaluation Agent response model to avoid JSON Schema composition keywords unsupported by OCI structured output.
- Added a manual A2A test client and synthetic offer evaluation sample payload.
- Updated the Offer Evaluation Agent specification status to initial implementation.
- Moved Offer Evaluation Agent startup instructions from the main README to a dedicated quickstart.
- Added the first Offer Evaluation Agent A2A server implementation using Locus.
- Added local environment loading and required OCI/A2A runtime configuration.
- Documented the `locus` conda environment and server startup flow.
- Updated the agent catalog to reflect the initial Offer Evaluation Agent implementation.
- Specified that offer evaluation policies are interpreted by an LLM at runtime and policy changes must not require code changes.
- Added the first draft full agent network to the README and agent catalog.
- Clarified that the Offer Evaluation Agent applies policy selection logic rather than generic scoring logic.
- Clarified the urgent procurement policy cost priority and tie-breaker behavior.
- Added the initial local Markdown policy for urgent procurement offer evaluation.
- Updated the Offer Evaluation Agent response schema to support no-valid-offers decisions.
- Aligned the Offer Evaluation Agent specification with the simplified decision and explanation response model.
- Added the initial JSON Schema for the Offer Evaluation Agent response payload.
- Added the initial JSON Schema for the Offer Evaluation Agent request payload.
- Moved detailed agent descriptions from README and AGENTS.md into a root-level agent catalog.
- Added code design guidance requiring simple, readable, modular implementations and discouraging over-engineering.
- Added README badges for Black, Python 3.11+, Pylint, Pytest, and A2A v1.
- Replaced the initial README placeholder with a project overview covering purpose, A2A communication, Oracle Locus, the initial agent roadmap, and development standards.
