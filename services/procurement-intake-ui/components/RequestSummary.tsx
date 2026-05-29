import type { DefaultApplied, OrchestrationRequest } from "../lib/types";

interface RequestSummaryProps {
  request: OrchestrationRequest | null;
  defaults: DefaultApplied[];
  canConfirm: boolean;
  isSubmitting: boolean;
  onConfirm: () => void;
}

export function RequestSummary({
  request,
  defaults,
  canConfirm,
  isSubmitting,
  onConfirm,
}: RequestSummaryProps) {
  if (!request) {
    return (
      <section className="panel">
        <div className="panelHeader">
          <span className="eyebrow">Request</span>
          <h2>Waiting for details</h2>
        </div>
        <p className="muted">
          Describe the supply need in the conversation. The validated request will appear here before launch.
        </p>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <span className="eyebrow">Review</span>
        <h2>Procurement request</h2>
      </div>
      <div className="summaryGrid">
        <SummaryItem label="Request ID" value={request.request_id} />
        <SummaryItem label="Currency" value={request.currency} />
        <SummaryItem label="Bid deadline" value={formatDate(request.response_deadline)} />
        <SummaryItem
          label="Auto PO"
          value={request.auto_create_purchase_order ? "Enabled" : "Disabled"}
        />
      </div>
      <div className="partList">
        {request.parts.map((part) => (
          <div className="partRow" key={`${part.part_id}-${part.plant_code}`}>
            <div>
              <strong>{part.material_description}</strong>
              <span>{part.material_code}</span>
            </div>
            <div>
              <strong>
                {part.quantity} {part.unit_of_measure}
              </strong>
              <span>{part.plant_code}</span>
            </div>
            <div>
              <strong>{formatDate(part.required_delivery_date)}</strong>
              <span>Required delivery</span>
            </div>
          </div>
        ))}
      </div>
      <div className="summaryGrid compact">
        <SummaryItem
          label="Supplier count"
          value={String(request.sourcing_constraints.max_suppliers_per_part)}
        />
        <SummaryItem
          label="Regions"
          value={
            request.sourcing_constraints.allowed_regions.length
              ? request.sourcing_constraints.allowed_regions.join(", ")
              : "No restriction"
          }
        />
        <SummaryItem label="Policy" value={request.evaluation_policy_id} />
      </div>
      {defaults.length > 0 && (
        <div className="defaultsBox">
          <strong>Defaults applied</strong>
          {defaults.map((item) => (
            <span key={`${item.field}-${String(item.value)}`}>
              {humanize(item.field)}: {formatValue(item.value)}
            </span>
          ))}
        </div>
      )}
      <button
        className="primaryButton"
        disabled={!canConfirm || isSubmitting}
        onClick={onConfirm}
        type="button"
      >
        {isSubmitting ? "Launching workflow..." : "Confirm and launch workflow"}
      </button>
    </section>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="summaryItem">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: value.includes("T") ? "short" : undefined,
  }).format(date);
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replaceAll(".", " ");
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "none";
  }
  if (typeof value === "boolean") {
    return value ? "yes" : "no";
  }
  return String(value);
}
