# Procurement Intake Web UI

Next.js web application for conversational procurement intake.

The UI talks only to the Conversational Procurement Intake Layer. It starts intake sessions, sends natural-language messages, shows the structured request review, confirms workflow launch, and displays real-time orchestration progress through Server-Sent Events.

## Local Development

Install dependencies:

```bash
npm install
```

Run the development server:

```bash
CONVERSATIONAL_INTAKE_BASE_URL=http://127.0.0.1:8012 \
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `CONVERSATIONAL_INTAKE_BASE_URL` | `http://127.0.0.1:8012` | Server-side URL used by Next.js API routes to proxy requests to the intake layer. |
| `PROCUREMENT_INTAKE_UI_PORT` | `3000` | Docker Compose port for the UI. |

The browser calls `/api/intake/*` on the Next.js app. The Next.js route handler proxies those calls to the intake layer, including SSE streams.

## Build

```bash
npm run build
```

## Docker

The Docker image uses Next.js standalone output.

In Docker Compose, the UI calls:

```text
http://conversational-procurement-intake:8012
```
