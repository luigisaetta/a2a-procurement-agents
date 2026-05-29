# Procurement Intake Web UI Specification

Version: 0.1.0

Status: Draft

---

# Purpose

The Procurement Intake Web UI is the browser-based user interface for starting and monitoring end-to-end procurement workflows through natural-language interaction.

The UI lets an operator describe a procurement need in natural language, clarify missing or ambiguous information, review the structured request prepared by the Conversational Procurement Intake Layer, explicitly confirm submission, and monitor the workflow progress in real time until the terminal result is available.

The UI must be implemented with Next.js.

---

# Runtime Role

The UI is not an A2A agent.

The UI does not call the Procurement Orchestrator or downstream agents directly.

The UI communicates only with the Conversational Procurement Intake Layer over HTTP and Server-Sent Events.

The Conversational Procurement Intake Layer remains responsible for:

- LLM-based request interpretation
- master-data grounding
- clarification logic
- final orchestration payload generation
- A2A client submission to the Procurement Orchestrator
- orchestration event relay

---

# Service Folder

Planned implementation folder:

```text
services/procurement-intake-ui/
  README.md
  Dockerfile
  package.json
  next.config.js
  app/
  components/
  lib/
  tests/
```

---

# Communication Boundaries

| Boundary | Direction | Protocol | Purpose |
| --- | --- | --- | --- |
| Browser user | inbound and outbound | HTML, CSS, JavaScript | Let the operator chat, review, confirm, and monitor progress. |
| Conversational Procurement Intake Layer | outbound | HTTP JSON API | Start sessions, send user messages, confirm requests, fetch session state, and poll fallback events. |
| Conversational Procurement Intake Layer | inbound stream | Server-Sent Events | Receive orchestration progress updates in real time after submission. |

The UI must not expose internal A2A details to the end user.

---

# User Experience Goals

The UI should feel like an enterprise procurement workbench, not a landing page.

The first screen must be the usable procurement intake workspace.

The interface should be calm, dense, and operational:

- natural-language conversation as the primary input
- structured request summary visible while the conversation evolves
- clear missing-information prompts
- explicit confirmation before workflow launch
- real-time workflow progress after launch
- final procurement outcome shown in business language

The UI must avoid exposing unnecessary technical details such as raw JSON payloads, A2A protocol terms, internal event names, stack traces, or agent implementation details in the main user flow.

Developer-oriented diagnostics may be available only behind a secondary debug panel or disabled by default.

---

# Core Layout

The main application screen should use a two-column desktop layout and a stacked mobile layout.

Desktop layout:

| Area | Purpose |
| --- | --- |
| Left pane | Conversation between the operator and the system. |
| Right pane | Procurement request summary, validation state, confirmation action, workflow progress, and final result. |

Mobile layout:

- conversation first
- request summary below the active input
- progress timeline below the summary after submission

The UI should remain usable on common laptop widths and mobile screens. Text must not overflow buttons, cards, or timeline entries.

---

# Conversation Experience

The conversation pane must support:

- starting a new intake session
- showing user messages
- showing system clarification messages
- sending free-form natural-language messages
- disabling message input while a request is being submitted
- preserving conversation history during a session
- showing recoverable errors in plain language

The UI should encourage the operator to describe:

- material or part needed
- quantity
- destination plant
- required delivery date
- bid response deadline
- supplier constraints, when relevant
- whether purchase order creation should be automatic

The UI must not require the operator to type JSON.

---

# Structured Request Review

When the Conversational Procurement Intake Layer returns `ready_for_confirmation`, the UI must show a structured summary before submission.

The summary must include:

- requested material or part
- destination plant
- quantity and unit of measure
- required delivery date
- bid response deadline
- currency
- supplier constraints
- evaluation policy
- automatic purchase order setting
- defaults applied

The UI must provide:

- a clear confirm action
- a way to continue the conversation and change details before confirming
- a clear indication that confirmation launches the procurement workflow

The UI should not show the raw `ProcurementOrchestrationRequest` by default.

---

# Workflow Launch

The UI launches the workflow by calling:

```text
POST /sessions/{session_id}/confirm
```

The UI must call this endpoint only after the user explicitly confirms the structured request.

After confirmation succeeds, the UI must:

- mark the request as submitted
- open the SSE event stream for the session
- display real-time progress updates as they arrive
- prevent accidental duplicate submission for the same session

---

# Real-Time Progress

The UI must use Server-Sent Events as the primary live update mechanism.

SSE endpoint:

```text
GET /sessions/{session_id}/events
```

The UI must render each SSE event as soon as it is received. It must not wait for the terminal result before updating the screen.

The UI must also support the polling fallback endpoint for recovery:

```text
GET /sessions/{session_id}/orchestration-events?cursor={cursor}
```

Polling is used for:

- initial catch-up after opening the progress view
- reconnect after SSE interruption
- browser or proxy environments where SSE is unavailable

---

# Progress Presentation

The UI must translate orchestration events into business-friendly progress states.

Raw event names may be used internally but should not be the primary user-facing text.

Suggested mapping:

| Orchestrator event type | User-facing label |
| --- | --- |
| `accepted` | Request accepted |
| `workflow_started` | Procurement workflow started |
| `bid_collection_started` | Contacting eligible suppliers |
| `bid_collection_completed` | Supplier offers received |
| `offer_evaluation_started` | Evaluating supplier offers |
| `offer_evaluation_completed` | Best offer selected |
| `rebid_requested` | Requesting another round of offers |
| `purchase_order_started` | Creating purchase order |
| `purchase_order_completed` | Purchase order created |
| `part_completed` | Requested item completed |
| `part_failed` | Requested item failed |
| `workflow_completed` | Procurement workflow completed |
| `workflow_failed` | Procurement workflow failed |

The progress view should include:

- current overall status
- ordered timeline of completed and active steps
- concise per-step messages
- timestamps in local browser time
- final outcome summary

The UI should suppress or simplify low-value technical payload details. For example, it may show counts, selected supplier, delivery date, and purchase order ID, but should not show full nested event payloads in the main timeline.

---

# Final Result

When the terminal result is available, the UI must show a concise procurement outcome.

For successful workflows, show:

- request ID
- final status
- requested items
- selected supplier, when available
- price and currency, when available
- expected delivery date, when available
- purchase order ID, when created

For partial or failed workflows, show:

- what completed
- what failed
- user-friendly failure reason
- suggested next action when available

The UI should keep the final conversation and progress timeline visible after completion.

---

# Error Handling

The UI must handle:

- intake service unavailable
- session not found
- validation errors
- clarification loops
- failed confirmation
- SSE disconnects
- orchestration stream failures
- terminal workflow failures

Errors shown to the user must be safe and actionable.

Raw stack traces, Python exceptions, JSON parsing internals, and A2A protocol dumps must not be shown in the primary interface.

---

# Session Behavior

The UI should create one intake session when the user starts a new procurement request.

The UI should keep the active `session_id` in client state for the current browser session.

The first implementation may use browser memory only. Durable browser-side persistence is optional.

The UI must provide a clear way to start a new request after the current workflow completes or is cancelled.

---

# HTTP API Contract

The UI must use the Conversational Procurement Intake Layer API.

## Start Session

```text
POST /sessions
```

Request:

```json
{
  "requested_by": "operator@example.com"
}
```

## Send Message

```text
POST /sessions/{session_id}/messages
```

Request:

```json
{
  "message": "We need 10 high density battery modules for Munich by June 15. Bid deadline May 29 at 12."
}
```

## Confirm Request

```text
POST /sessions/{session_id}/confirm
```

Request:

```json
{
  "confirmed": true
}
```

## Session Status

```text
GET /sessions/{session_id}
```

## SSE Stream

```text
GET /sessions/{session_id}/events
```

## Poll Events

```text
GET /sessions/{session_id}/orchestration-events?cursor=0
```

---

# Deployment Requirements

The UI must be added to the Docker Compose deployment as a separate service.

Planned service name:

```text
procurement-intake-ui
```

Default port:

```text
3000
```

The UI container must receive the Conversational Procurement Intake Layer URL through environment configuration.

Suggested environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `PROCUREMENT_INTAKE_UI_PORT` | `3000` | Host and container port for the Next.js UI. |
| `CONVERSATIONAL_INTAKE_BASE_URL` | `http://conversational-procurement-intake:8012` | Server-side URL used by the Next.js app to call the intake layer in Docker Compose. |
| `NEXT_PUBLIC_CONVERSATIONAL_INTAKE_BASE_URL` | `/api/intake` | Browser-facing URL. Prefer a Next.js proxy route to avoid browser CORS issues. |

The preferred initial deployment pattern is:

- Browser calls Next.js API routes under `/api/intake`
- Next.js API routes proxy requests and SSE streams to the Conversational Procurement Intake Layer
- Next.js server uses `CONVERSATIONAL_INTAKE_BASE_URL` inside the Docker network

This keeps the browser origin stable and avoids direct cross-origin calls to the intake service.

---

# Next.js Requirements

The implementation should use:

- Next.js App Router
- TypeScript
- React client components where browser interactivity is required
- server-side route handlers for HTTP proxying to the intake layer
- EventSource or Fetch streaming for SSE consumption

The UI should keep dependencies modest. A component library is optional; if introduced, it must not obscure the simple workbench flow.

---

# Accessibility

The UI must:

- provide visible labels for form controls
- support keyboard navigation for message input and confirmation
- preserve focus after sending messages
- use sufficient color contrast
- avoid relying only on color to communicate status
- announce progress changes in a screen-reader-friendly region when feasible

---

# Non Requirements

The initial UI does not need:

- user authentication
- durable session history
- multi-user collaboration
- supplier-side views
- manual editing of raw orchestration JSON
- direct A2A access
- direct MCP access

---

# Acceptance Criteria

The first implementation is acceptable when:

- the Next.js app starts locally and in Docker Compose
- an operator can start a session from the browser
- an operator can send natural-language procurement messages
- clarification messages are shown in the conversation
- the structured request summary is shown before submission
- the operator can confirm and launch the workflow
- orchestration progress appears in real time through SSE
- SSE reconnect or polling fallback can recover missed events
- final result is shown in business-friendly language
- technical protocol details are not shown in the primary UI
- tests cover API client behavior, event mapping, and core UI state transitions
