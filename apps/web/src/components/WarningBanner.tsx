import React from "react";

export interface WarningBannerProps {
  warnings?: string[] | null;
  className?: string;
  onDismiss?: (warning: string) => void;
}

export const WARNING_MESSAGES: Record<string, string> = {
  vector_search_unavailable: "Semantic search unavailable; using keyword search.",
  lexical_search_unavailable: "Keyword search unavailable; using semantic search.",
  budget_exceeded_by_mandatory: "Token budget exceeded by mandatory sections; non-mandatory sections excluded.",
  search_degraded: "Search is operating in a degraded mode.",
};

export function formatWarning(warning: string): string {
  return WARNING_MESSAGES[warning] || warning;
}

export const WarningBanner: React.FC<WarningBannerProps> = ({
  warnings,
  className = "",
  onDismiss,
}) => {
  if (!warnings || warnings.length === 0) {
    return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className={`warning-banner-group ${className}`}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-2)",
        margin: "var(--space-3) 0",
      }}
    >
      {warnings.map((w, idx) => (
        <div
          key={idx}
          className="warning-banner"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "var(--space-3) var(--space-4)",
            backgroundColor: "var(--color-warning-bg)",
            border: "1px solid var(--color-warning-border)",
            borderRadius: "var(--radius-md)",
            color: "var(--color-warning)",
            fontSize: "var(--font-size-sm)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span aria-hidden="true" style={{ fontWeight: "bold" }}>
              ⚠️
            </span>
            <span style={{ color: "var(--color-text)" }}>{formatWarning(w)}</span>
          </div>
          {onDismiss && (
            <button
              type="button"
              onClick={() => onDismiss(w)}
              aria-label="Dismiss warning"
              style={{
                background: "none",
                border: "none",
                color: "var(--color-text-muted)",
                cursor: "pointer",
                padding: "var(--space-1)",
                minHeight: "32px",
                minWidth: "32px",
              }}
            >
              ✕
            </button>
          )}
        </div>
      ))}
    </div>
  );
};
