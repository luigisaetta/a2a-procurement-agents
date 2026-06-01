"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { ProgressTimeline } from "../components/ProgressTimeline";
import { RequestSummary } from "../components/RequestSummary";
import { confirmSession, pollEvents, sendMessage, startSession } from "../lib/api";
import type {
  ChatMessage,
  IntakeSessionResponse,
  OrchestrationEvent,
  OrchestrationRequest,
  OrchestrationResponse,
} from "../lib/types";

const SAMPLE_REQUEST =
  "We need 10 high density battery modules for the Munich plant by June 15. Bid deadline May 29 at 12. Ask up to 3 European suppliers and create the purchase order automatically.";

export default function Home() {
  const [requestedBy, setRequestedBy] = useState("operator@example.com");
  const [session, setSession] = useState<IntakeSessionResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "system",
      text: "Describe the supply need. I will ask for missing details, prepare the request, and show a review before launch.",
    },
  ]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState<OrchestrationEvent[]>([]);
  const [terminalResult, setTerminalResult] = useState<OrchestrationResponse | null>(null);
  const [reviewRequest, setReviewRequest] = useState<OrchestrationRequest | null>(null);
  const [sseConnected, setSseConnected] = useState(false);
  const [error, setError] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);

  const canConfirm = session?.state === "ready_for_confirmation";
  const request = session?.orchestration_request ?? null;

  useEffect(() => {
    setReviewRequest(request);
  }, [request]);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  const latestCursor = useMemo(() => {
    return events.reduce((cursor, event) => Math.max(cursor, event.sequence), 0);
  }, [events]);

  async function ensureSession(): Promise<IntakeSessionResponse> {
    if (session) {
      return session;
    }
    const created = await startSession(requestedBy);
    setSession(created);
    return created;
  }

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.trim() || busy) {
      return;
    }
    setBusy(true);
    setError("");
    const text = draft.trim();
    setDraft("");
    appendMessage("user", text);
    try {
      const active = await ensureSession();
      const response = await sendMessage(active.session_id, text);
      setSession(response);
      appendMessage("system", response.message);
    } catch (exc) {
      setError(safeError(exc));
      appendMessage("system", "I could not process that message. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!session || busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await confirmSession(session.session_id, reviewRequest);
      setSession(response);
      appendMessage("system", "The workflow has been launched. Progress updates will appear live.");
      openEventStream(response.session_id);
    } catch (exc) {
      setError(safeError(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleNewRequest() {
    eventSourceRef.current?.close();
    setSession(null);
    setEvents([]);
    setTerminalResult(null);
    setReviewRequest(null);
    setSseConnected(false);
    setError("");
    setDraft("");
    setMessages([
      {
        id: crypto.randomUUID(),
        role: "system",
        text: "New request started. Describe the material, quantity, plant, delivery date, bid deadline, and purchasing preference.",
      },
    ]);
  }

  async function handleRecover() {
    if (!session) {
      return;
    }
    try {
      const response = await pollEvents(session.session_id, latestCursor);
      if (response.events.length > 0) {
        setEvents((current) => mergeEvents(current, response.events));
      }
      setTerminalResult(response.terminal_result);
    } catch (exc) {
      setError(safeError(exc));
    }
  }

  function openEventStream(sessionId: string) {
    eventSourceRef.current?.close();
    const source = new EventSource(`/api/intake/sessions/${sessionId}/events`);
    eventSourceRef.current = source;

    source.onopen = () => setSseConnected(true);
    source.onerror = () => {
      setSseConnected(false);
      void handleRecover();
    };
    source.addEventListener("orchestration_event", (event) => {
      const parsed = JSON.parse((event as MessageEvent).data) as OrchestrationEvent;
      setEvents((current) => mergeEvents(current, [parsed]));
    });
    source.addEventListener("orchestration_completed", (event) => {
      const parsed = JSON.parse((event as MessageEvent).data) as OrchestrationResponse;
      setTerminalResult(parsed);
      setSseConnected(false);
      source.close();
    });
    source.addEventListener("orchestration_failed", (event) => {
      const parsed = JSON.parse((event as MessageEvent).data) as { message?: string };
      setError(parsed.message ?? "The workflow stream failed.");
      setSseConnected(false);
      source.close();
    });
  }

  function appendMessage(role: "user" | "system", text: string) {
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role,
        text,
      },
    ]);
  }

  return (
    <main className="workspace">
      <header className="topBar">
        <div>
          <span className="eyebrow">A2A Procurement</span>
          <h1>Procurement Intake</h1>
        </div>
        <button className="secondaryButton" onClick={handleNewRequest} type="button">
          New request
        </button>
      </header>

      {error && <div className="errorBanner">{error}</div>}

      <section className="shell">
        <section className="conversationPanel">
          <div className="operatorRow">
            <label htmlFor="requested-by">Operator</label>
            <input
              id="requested-by"
              onChange={(event) => setRequestedBy(event.target.value)}
              value={requestedBy}
            />
          </div>
          <div className="messages" aria-live="polite">
            {messages.map((message) => (
              <div className={`message ${message.role}`} key={message.id}>
                <span>{message.role === "user" ? "You" : "System"}</span>
                <p>{message.text}</p>
              </div>
            ))}
          </div>
          <form className="composer" onSubmit={handleSend}>
            <textarea
              aria-label="Procurement request message"
              disabled={busy || session?.state === "submitted"}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Describe what you need to buy..."
              value={draft}
            />
            <div className="composerActions">
              <button
                className="secondaryButton"
                disabled={busy || session?.state === "submitted"}
                onClick={() => setDraft(SAMPLE_REQUEST)}
                type="button"
              >
                Use sample
              </button>
              <button
                className="primaryButton sendButton"
                disabled={busy || !draft.trim() || session?.state === "submitted"}
                type="submit"
              >
                {busy ? "Working..." : "Send"}
              </button>
            </div>
          </form>
        </section>

        <aside className="sideStack">
          <RequestSummary
            canConfirm={canConfirm}
            defaults={session?.defaults_applied ?? []}
            isSubmitting={busy && canConfirm}
            onConfirm={handleConfirm}
            onRequestChange={setReviewRequest}
            request={request}
            reviewRequest={reviewRequest}
          />
          <ProgressTimeline
            connected={sseConnected}
            events={events}
            terminalResult={terminalResult}
          />
        </aside>
      </section>
    </main>
  );
}

function mergeEvents(
  current: OrchestrationEvent[],
  incoming: OrchestrationEvent[],
): OrchestrationEvent[] {
  const byKey = new Map<string, OrchestrationEvent>();
  for (const event of [...current, ...incoming]) {
    byKey.set(`${event.orchestration_id}-${event.request_id}-${event.sequence}`, event);
  }
  return Array.from(byKey.values()).sort((a, b) => a.sequence - b.sequence);
}

function safeError(exc: unknown): string {
  if (exc instanceof Error) {
    return exc.message;
  }
  return "The request could not be completed.";
}
