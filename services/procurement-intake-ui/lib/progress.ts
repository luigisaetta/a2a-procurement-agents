import type { OrchestrationEvent, OrchestrationResponse } from "./types";

const EVENT_LABELS: Record<string, string> = {
  accepted: "Request accepted",
  workflow_started: "Procurement workflow started",
  bid_collection_started: "Contacting eligible suppliers",
  bid_collection_completed: "Supplier offers received",
  offer_evaluation_started: "Evaluating supplier offers",
  offer_evaluation_completed: "Best offer selected",
  rebid_requested: "Requesting another round of offers",
  purchase_order_started: "Creating purchase order",
  purchase_order_completed: "Purchase order created",
  part_completed: "Requested item completed",
  part_failed: "Requested item failed",
  workflow_completed: "Procurement workflow completed",
  workflow_failed: "Procurement workflow failed",
};

export function eventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] ?? "Workflow update";
}

export function eventTone(event: OrchestrationEvent): "ok" | "active" | "warn" | "fail" {
  if (event.status === "failed" || event.event_type.endsWith("_failed")) {
    return "fail";
  }
  if (event.status === "retrying" || event.event_type === "rebid_requested") {
    return "warn";
  }
  if (event.status === "running" || event.status === "accepted") {
    return "active";
  }
  return "ok";
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function summarizePayload(event: OrchestrationEvent): string {
  const payload = event.payload ?? {};
  const parts: string[] = [];
  const partId = readString(payload, "part_id");
  const attemptNumber = readNumber(payload, "attempt_number");
  const selectedOfferId = readString(payload, "selected_offer_id");
  const status = readString(payload, "decision_status") ?? readString(payload, "status");
  const offersCount = readNumber(payload, "offers_count");
  const suppliersCount = readNumber(payload, "identified_suppliers_count");

  if (partId) {
    parts.push(`Item ${partId}`);
  }
  if (attemptNumber) {
    parts.push(`attempt ${attemptNumber}`);
  }
  if (suppliersCount !== null) {
    parts.push(`${suppliersCount} suppliers identified`);
  }
  if (offersCount !== null) {
    parts.push(`${offersCount} offers received`);
  }
  if (status) {
    parts.push(status.replaceAll("_", " "));
  }
  if (selectedOfferId) {
    parts.push("winning offer selected");
  }

  return parts.join(" · ");
}

export function finalSummary(result: OrchestrationResponse | null): string {
  if (!result) {
    return "Waiting for the workflow to finish.";
  }
  const readableStatus = result.status.replaceAll("_", " ");
  return `${readableStatus}. ${result.message}`;
}

function readString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === "string" && value ? value : null;
}

function readNumber(payload: Record<string, unknown>, key: string): number | null {
  const value = payload[key];
  return typeof value === "number" ? value : null;
}
