export type IntakeState =
  | "needs_clarification"
  | "ready_for_confirmation"
  | "ready_for_orchestration"
  | "submitted"
  | "cancelled"
  | "failed";

export type ChatRole = "user" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
}

export interface DefaultApplied {
  field: string;
  value: unknown;
  reason: string;
}

export interface IntakePart {
  part_id: string;
  plant_code: string;
  material_code: string;
  material_description: string;
  quantity: number;
  unit_of_measure: string;
  required_delivery_date: string;
  supplier_search_hints?: {
    commodity_category?: string;
    required_certifications?: string[];
  } | null;
}

export interface OrchestrationRequest {
  request_id: string;
  requested_by: string;
  currency: string;
  evaluation_policy_id: string;
  response_deadline: string;
  auto_create_purchase_order: boolean;
  max_rebid_attempts?: number;
  sourcing_constraints: {
    max_suppliers_per_part: number;
    allowed_regions: string[];
    preferred_supplier_ids?: string[];
  };
  parts: IntakePart[];
}

export interface IntakeSessionResponse {
  session_id: string;
  state: IntakeState;
  message: string;
  known_fields: Record<string, unknown>;
  missing_fields: string[];
  ambiguities: Array<{
    field: string;
    reason: string;
    candidates: Array<Record<string, unknown>>;
  }>;
  defaults_applied: DefaultApplied[];
  confirmation_summary: Record<string, unknown> | null;
  orchestration_request: OrchestrationRequest | null;
  orchestration_id: string | null;
}

export interface OrchestrationEvent {
  orchestration_id: string;
  request_id: string;
  sequence: number;
  timestamp: string;
  event_type: string;
  status: string;
  message: string;
  payload: Record<string, unknown>;
}

export interface OrchestrationResponse {
  orchestration_id: string;
  request_id: string;
  status: string;
  started_at: string;
  completed_at: string;
  part_results: Array<Record<string, unknown>>;
  message: string;
  error?: Record<string, unknown>;
}

export interface PollEventsResponse {
  session_id: string;
  orchestration_id: string | null;
  state: IntakeState;
  events: OrchestrationEvent[];
  next_cursor: number;
  terminal_result: OrchestrationResponse | null;
}

// The API returns every stored purchase order field; the UI declares only
// the fields it shows in the recent purchase orders table.
export interface PurchaseOrderRecord {
  purchase_order_id: string;
  material_code: string;
  material_description: string;
  quantity: number;
  unit_of_measure: string;
  confirmed_delivery_date: string;
  plant_code: string;
  supplier_id: string;
}

export interface RecentPurchaseOrdersResponse {
  status: "completed" | "failed";
  limit: number;
  purchase_orders: PurchaseOrderRecord[];
  message: string;
}
