import React from "react";
import type { ContextPackage } from "@gpd/contracts";
import { WarningBanner } from "../../components/WarningBanner";
import { ProvenanceLink } from "../../components/ProvenanceLink";

export interface ContextPreviewProps {
  contextPackage?: ContextPackage | null;
  warnings?: string[];
  loading?: boolean;
}

export const ContextPreview: React.FC<ContextPreviewProps> = ({
  contextPackage,
  warnings,
  loading,
}) => {
  if (loading) {
    return (
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <p style={{ color: "var(--color-text-muted)" }}>Loading context package...</p>
      </div>
    );
  }

  const combinedWarnings = [
    ...(warnings || []),
    ...(contextPackage?.warnings || []),
  ];

  const uniqueWarnings = Array.from(new Set(combinedWarnings));

  return (
    <div
      className="card"
      data-testid="context-preview"
      style={{
        padding: "var(--space-5)",
        backgroundColor: "var(--color-surface)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "var(--space-4)",
          paddingBottom: "var(--space-2)",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <h3>Context Package Preview</h3>
        {contextPackage && (
          <div
            style={{
              fontSize: "var(--font-size-xs)",
              color: "var(--color-text-muted)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
            }}
          >
            <span>Budget:</span>
            <code
              style={{
                backgroundColor: "var(--color-canvas)",
                padding: "2px 6px",
                borderRadius: "var(--radius-sm)",
                color:
                  contextPackage.token_count > contextPackage.token_budget
                    ? "var(--color-danger)"
                    : "var(--color-text)",
              }}
            >
              {contextPackage.token_count} / {contextPackage.token_budget} tokens
            </code>
          </div>
        )}
      </div>

      {/* Warnings like vector_search_unavailable */}
      <WarningBanner warnings={uniqueWarnings} />

      {/* Context Provenance Links */}
      <div
        style={{
          margin: "var(--space-3) 0 var(--space-4) 0",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "var(--space-2)",
        }}
      >
        <span
          style={{
            fontSize: "var(--font-size-xs)",
            color: "var(--color-text-secondary)",
            fontWeight: "var(--font-weight-medium)",
          }}
        >
          Sources:
        </span>
        <ProvenanceLink type="slack" messageId="C12345/p1609459200" label="Slack message (discussion)" />
        <ProvenanceLink type="file" path="src/payment/checkout.ts" label="checkout.ts" />
      </div>

      {/* Markdown Content / Sections */}
      {contextPackage?.sections && contextPackage.sections.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {contextPackage.sections.map((section, idx) => (
            <section
              key={section.id || idx}
              style={{
                backgroundColor: "var(--color-canvas)",
                padding: "var(--space-4)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border-subtle)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "var(--space-2)",
                }}
              >
                <h4 style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text)" }}>
                  {section.section}
                </h4>
                {section.score !== undefined && (
                  <span
                    className="badge badge-info"
                    style={{ fontSize: "10px" }}
                    title={section.score_explanation}
                  >
                    Score: {section.score.toFixed(2)}
                  </span>
                )}
              </div>
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  color: "var(--color-text-secondary)",
                  fontSize: "var(--font-size-xs)",
                  margin: 0,
                }}
              >
                {section.content}
              </pre>
            </section>
          ))}
        </div>
      ) : contextPackage?.markdown_content ? (
        <pre
          style={{
            backgroundColor: "var(--color-canvas)",
            padding: "var(--space-4)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border-subtle)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            color: "var(--color-text-secondary)",
            fontSize: "var(--font-size-sm)",
            maxHeight: "400px",
            overflowY: "auto",
          }}
        >
          {contextPackage.markdown_content}
        </pre>
      ) : (
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          No context package generated for this task yet.
        </p>
      )}
    </div>
  );
};
