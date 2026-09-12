import React from "react";
import type { BugDetails, ExtractedField } from "@gpd/contracts";
import { ProvenanceLink } from "../../components/ProvenanceLink";

export interface TaskFactsProps {
  bugDetails?: BugDetails | null;
  confidenceThreshold?: number;
}

interface FactRowProps<T = unknown> {
  label: string;
  field?: ExtractedField<T> | null;
  confidenceThreshold?: number;
  renderValue?: (val: T) => React.ReactNode;
}

function FactRow<T = unknown>({
  label,
  field,
  confidenceThreshold = 0.8,
  renderValue,
}: FactRowProps<T>) {
  const isUnknown =
    !field ||
    field.value === null ||
    field.value === undefined ||
    (Array.isArray(field.value) && field.value.length === 0) ||
    (typeof field.value === "string" && field.value.trim() === "");

  return (
    <div
      style={{
        padding: "var(--space-3) 0",
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "grid",
        gridTemplateColumns: "180px 1fr",
        gap: "var(--space-4)",
        alignItems: "start",
      }}
    >
      <dt
        style={{
          fontWeight: "var(--font-weight-medium)",
          color: "var(--color-text-secondary)",
          fontSize: "var(--font-size-sm)",
        }}
      >
        {label}
      </dt>
      <dd style={{ margin: 0, fontSize: "var(--font-size-sm)" }}>
        {isUnknown ? (
          <span
            data-testid={`unknown-${label.toLowerCase().replace(/\s+/g, "-")}`}
            style={{
              color: "var(--color-text-muted)",
              fontStyle: "italic",
            }}
          >
            Unknown
          </span>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <div>
              {renderValue ? renderValue(field.value) : String(field.value)}
            </div>

            {/* Evidence and Confidence */}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: "var(--space-2)",
                marginTop: "2px",
              }}
            >
              {field.confidence !== undefined && field.confidence < confidenceThreshold && (
                <span
                  className="badge badge-warning"
                  title={`Confidence: ${Math.round(field.confidence * 100)}%`}
                  style={{ fontSize: "11px" }}
                >
                  Confidence: {Math.round(field.confidence * 100)}%
                </span>
              )}
              {field.evidence && field.evidence.length > 0 && (
                <div style={{ display: "inline-flex", gap: "var(--space-2)" }}>
                  {field.evidence.map((ev, i) => (
                    <ProvenanceLink
                      key={i}
                      type="slack"
                      messageId={ev}
                      label={`Evidence ${ev}`}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </dd>
    </div>
  );
};

export const TaskFacts: React.FC<TaskFactsProps> = ({
  bugDetails,
  confidenceThreshold = 0.8,
}) => {
  return (
    <div
      className="card"
      style={{
        padding: "var(--space-5)",
        backgroundColor: "var(--color-surface)",
      }}
    >
      <h3
        style={{
          marginBottom: "var(--space-4)",
          paddingBottom: "var(--space-2)",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        Extracted Facts & Bug Details
      </h3>

      <dl style={{ margin: 0 }}>
        <FactRow
          label="Summary"
          field={bugDetails?.summary}
          confidenceThreshold={confidenceThreshold}
        />
        <FactRow
          label="Reproduction Steps"
          field={bugDetails?.reproduction_steps}
          confidenceThreshold={confidenceThreshold}
          renderValue={(steps: string[]) => (
            <ol style={{ paddingLeft: "var(--space-5)", margin: 0 }}>
              {steps.map((step, idx) => (
                <li key={idx} style={{ marginBottom: "var(--space-1)" }}>
                  {step}
                </li>
              ))}
            </ol>
          )}
        />
        <FactRow
          label="Actual Behavior"
          field={bugDetails?.actual_behavior}
          confidenceThreshold={confidenceThreshold}
        />
        <FactRow
          label="Expected Behavior"
          field={bugDetails?.expected_behavior}
          confidenceThreshold={confidenceThreshold}
        />
        <FactRow
          label="Environment"
          field={bugDetails?.environment}
          confidenceThreshold={confidenceThreshold}
        />
        <FactRow
          label="Severity"
          field={bugDetails?.severity}
          confidenceThreshold={confidenceThreshold}
          renderValue={(sev: string) => (
            <span
              className={`badge ${
                sev === "critical"
                  ? "badge-danger"
                  : sev === "high"
                  ? "badge-warning"
                  : "badge-info"
              }`}
            >
              {sev.toUpperCase()}
            </span>
          )}
        />
        <FactRow
          label="Affected Component"
          field={bugDetails?.affected_component}
          confidenceThreshold={confidenceThreshold}
        />
        <FactRow
          label="Technical Clues"
          field={bugDetails?.technical_clues}
          confidenceThreshold={confidenceThreshold}
          renderValue={(clues: string[]) => (
            <ul style={{ paddingLeft: "var(--space-5)", margin: 0 }}>
              {clues.map((clue, idx) => (
                <li key={idx} style={{ marginBottom: "var(--space-1)" }}>
                  <code>{clue}</code>
                </li>
              ))}
            </ul>
          )}
        />
        <FactRow
          label="Participants"
          field={bugDetails?.participants}
          confidenceThreshold={confidenceThreshold}
          renderValue={(parts: string[]) => parts.join(", ")}
        />
      </dl>
    </div>
  );
};
