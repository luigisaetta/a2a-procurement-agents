# A2A JSON Schema Discovery

Status: Initial implementation

This document defines the pragmatic JSON Schema discovery convention used by the
A2A Procurement Agents project.

## Context

The project follows A2A v1 for inter-agent communication.

The A2A v1 Agent Card advertises agent identity, endpoint, capabilities, skills,
input modes, output modes, and examples. In the Locus runtime used by this
project, `AgentSkill` does not expose native `inputSchema` or `outputSchema`
fields.

The project still needs machine-readable payload contracts so independently
implemented agents and clients can validate JSON requests and responses without
depending on another agent's internal code.

## Convention

Each A2A agent that accepts JSON payloads publishes schema discovery endpoints on
the same HTTP server as its A2A endpoint.

The discovery endpoint is:

```text
GET /.well-known/a2a-schemas
```

The endpoint returns a JSON document with:

- `agent`: stable agent name
- `protocol_version`: A2A protocol version used by the agent
- `skills`: mapping from A2A skill id to schema URLs

Each schema URL is relative to the agent base URL and is served from:

```text
GET /schemas/{schema_name}
```

Unknown schema names must return HTTP `404`.

## Shape

Example:

```json
{
  "agent": "purchase-order-agent",
  "protocol_version": "1.0",
  "skills": {
    "create_purchase_order": {
      "input_schema": "/schemas/create-purchase-order-request.schema.json",
      "output_schema": "/schemas/create-purchase-order-response.schema.json"
    }
  }
}
```

The Procurement Orchestrator also publishes `event_schema` for its streaming
workflow progress events.

## Scope

This convention is additive. It does not change A2A v1 JSON-RPC behavior and it
does not add non-standard fields to `AgentSkill`.

The current implementation intentionally does not yet declare an A2A
`AgentCapabilities.extensions` entry because Locus constructs the Agent Card
internally. When Locus supports extension injection, this convention should be
advertised through the Agent Card as a project-specific schema discovery
extension.

## In-Scope Agents

The following A2A agents publish schema discovery endpoints:

- Procurement Orchestrator
- Bid Collection Agent
- Offer Evaluation Agent
- Purchase Order Agent

The Conversational Procurement Intake Layer is an HTTP application layer, not an
A2A agent, and is therefore out of scope for this discovery convention.
