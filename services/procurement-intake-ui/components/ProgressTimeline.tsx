import { eventLabel, eventTone, finalSummary, formatDateTime, summarizePayload } from "../lib/progress";
import type { OrchestrationEvent, OrchestrationResponse } from "../lib/types";

interface ProgressTimelineProps {
  events: OrchestrationEvent[];
  terminalResult: OrchestrationResponse | null;
  connected: boolean;
}

export function ProgressTimeline({
  events,
  terminalResult,
  connected,
}: ProgressTimelineProps) {
  const badge = statusBadge(terminalResult, connected);

  return (
    <section className="panel progressPanel">
      <div className="panelHeader inline">
        <div>
          <span className="eyebrow">Progress</span>
          <h2>Workflow status</h2>
        </div>
        <span className={`connectionBadge ${badge.tone}`}>{badge.label}</span>
      </div>
      {events.length === 0 ? (
        <p className="muted">Progress updates will appear here after launch.</p>
      ) : (
        <ol className="timeline" aria-live="polite">
          {events.map((event) => {
            const detail = summarizePayload(event);
            return (
              <li className={`timelineItem ${eventTone(event)}`} key={event.sequence}>
                <div className="timelineDot" />
                <div className="timelineBody">
                  <div className="timelineTitle">
                    <strong>{eventLabel(event.event_type)}</strong>
                    <span>{formatDateTime(event.timestamp)}</span>
                  </div>
                  <p>{event.message}</p>
                  {detail && <small>{detail}</small>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {terminalResult && (
        <div className="resultBox">
          <span className="eyebrow">Result</span>
          <strong>{finalSummary(terminalResult)}</strong>
          <ResultDetails result={terminalResult} />
        </div>
      )}
    </section>
  );
}

function statusBadge(
  terminalResult: OrchestrationResponse | null,
  connected: boolean,
): { label: string; tone: "on" | "off" } {
  if (!terminalResult) {
    return connected ? { label: "Live", tone: "on" } : { label: "Waiting", tone: "off" };
  }
  return terminalResult.status === "failed"
    ? { label: "Failed", tone: "off" }
    : { label: "Completed", tone: "on" };
}

function ResultDetails({ result }: { result: OrchestrationResponse }) {
  const purchaseOrders = result.part_results
    .map((item) => readNestedString(item, ["purchase_order", "purchase_order_id"]))
    .filter(Boolean);
  const suppliers = result.part_results
    .map((item) => readNestedString(item, ["evaluation", "selected_offer", "supplier_name"]))
    .filter(Boolean);

  return (
    <div className="resultDetails">
      <span>Request {result.request_id}</span>
      {suppliers.length > 0 && <span>Selected supplier: {suppliers.join(", ")}</span>}
      {purchaseOrders.length > 0 && <span>Purchase order: {purchaseOrders.join(", ")}</span>}
    </div>
  );
}

function readNestedString(value: Record<string, unknown>, path: string[]): string | null {
  let cursor: unknown = value;
  for (const key of path) {
    if (!cursor || typeof cursor !== "object" || !(key in cursor)) {
      return null;
    }
    cursor = (cursor as Record<string, unknown>)[key];
  }
  return typeof cursor === "string" && cursor ? cursor : null;
}
