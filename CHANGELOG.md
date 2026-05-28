# Changelog

All meaningful changes to this project are documented in this file.

## 2026-05-28

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
