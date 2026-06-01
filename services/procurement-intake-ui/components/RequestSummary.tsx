import type { ReactNode } from "react";

import type { DefaultApplied, OrchestrationRequest } from "../lib/types";

interface RequestSummaryProps {
  request: OrchestrationRequest | null;
  reviewRequest: OrchestrationRequest | null;
  defaults: DefaultApplied[];
  canConfirm: boolean;
  isSubmitting: boolean;
  onConfirm: () => void;
  onRequestChange: (request: OrchestrationRequest) => void;
}

export function RequestSummary({
  request,
  reviewRequest,
  defaults,
  canConfirm,
  isSubmitting,
  onConfirm,
  onRequestChange,
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

  const displayedRequest = reviewRequest ?? request;
  const isEditable = canConfirm && !isSubmitting;

  function updateResponseDeadline(value: string) {
    onRequestChange({
      ...displayedRequest,
      response_deadline: value
        ? new Date(value).toISOString()
        : displayedRequest.response_deadline,
    });
  }

  function updatePart(
    index: number,
    patch: Partial<OrchestrationRequest["parts"][number]>,
  ) {
    onRequestChange({
      ...displayedRequest,
      parts: displayedRequest.parts.map((part, partIndex) =>
        partIndex === index ? { ...part, ...patch } : part,
      ),
    });
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <span className="eyebrow">Review</span>
        <h2>Procurement request</h2>
      </div>
      <div className="summaryGrid">
        <SummaryItem label="Request ID" value={displayedRequest.request_id} />
        <SummaryItem label="Currency" value={displayedRequest.currency} />
        <EditableSummaryItem label="Bid deadline">
          <input
            aria-label="Bid deadline"
            className="summaryInput"
            disabled={!isEditable}
            onChange={(event) => updateResponseDeadline(event.target.value)}
            type="datetime-local"
            value={toDateTimeLocalValue(displayedRequest.response_deadline)}
          />
        </EditableSummaryItem>
        <SummaryItem
          label="Auto PO"
          value={displayedRequest.auto_create_purchase_order ? "Enabled" : "Disabled"}
        />
      </div>
      <div className="partList">
        {displayedRequest.parts.map((part, index) => (
          <div className="partRow" key={`${part.part_id}-${part.plant_code}`}>
            <div>
              <strong>{part.material_description}</strong>
              <span>{part.material_code}</span>
            </div>
            <div>
              <label className="editableField">
                <span>Quantity</span>
                <div className="quantityControl">
                  <input
                    aria-label={`Quantity for ${part.material_description}`}
                    disabled={!isEditable}
                    min="1"
                    onChange={(event) =>
                      updatePart(index, { quantity: toPositiveInteger(event.target.value) })
                    }
                    step="1"
                    type="number"
                    value={String(Math.trunc(part.quantity))}
                  />
                  <strong>{part.unit_of_measure}</strong>
                </div>
              </label>
              <span>{part.plant_code}</span>
            </div>
            <div>
              <label className="editableField">
                <span>Required delivery</span>
                <input
                  aria-label={`Required delivery date for ${part.material_description}`}
                  disabled={!isEditable}
                  onChange={(event) =>
                    updatePart(index, { required_delivery_date: event.target.value })
                  }
                  type="date"
                  value={toDateValue(part.required_delivery_date)}
                />
              </label>
            </div>
          </div>
        ))}
      </div>
      <div className="summaryGrid compact">
        <SummaryItem
          label="Supplier count"
          value={String(displayedRequest.sourcing_constraints.max_suppliers_per_part)}
        />
        <SummaryItem
          label="Regions"
          value={
            displayedRequest.sourcing_constraints.allowed_regions.length
              ? displayedRequest.sourcing_constraints.allowed_regions.join(", ")
              : "No restriction"
          }
        />
        <SummaryItem label="Policy" value={displayedRequest.evaluation_policy_id} />
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

function EditableSummaryItem({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="summaryItem editableSummaryItem">
      <span>{label}</span>
      {children}
    </div>
  );
}

function toDateValue(value: string): string {
  return value.slice(0, 10);
}

function toDateTimeLocalValue(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 16);
  }
  const offsetMilliseconds = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMilliseconds).toISOString().slice(0, 16);
}

function toPositiveInteger(value: string): number {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return 1;
  }
  return parsed;
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
