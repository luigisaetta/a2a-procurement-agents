import type {
  IntakeSessionResponse,
  OrchestrationRequest,
  PollEventsResponse,
} from "./types";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/intake${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function startSession(requestedBy: string): Promise<IntakeSessionResponse> {
  return requestJson<IntakeSessionResponse>("/sessions", {
    method: "POST",
    body: JSON.stringify({ requested_by: requestedBy }),
  });
}

export function sendMessage(
  sessionId: string,
  message: string,
): Promise<IntakeSessionResponse> {
  return requestJson<IntakeSessionResponse>(`/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function confirmSession(
  sessionId: string,
  orchestrationRequest?: OrchestrationRequest | null,
): Promise<IntakeSessionResponse> {
  return requestJson<IntakeSessionResponse>(`/sessions/${sessionId}/confirm`, {
    method: "POST",
    body: JSON.stringify({
      confirmed: true,
      ...(orchestrationRequest ? { orchestration_request: orchestrationRequest } : {}),
    }),
  });
}

export function pollEvents(
  sessionId: string,
  cursor: number,
): Promise<PollEventsResponse> {
  return requestJson<PollEventsResponse>(
    `/sessions/${sessionId}/orchestration-events?cursor=${cursor}`,
  );
}
