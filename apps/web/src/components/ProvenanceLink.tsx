import React from "react";

export interface ProvenanceLinkProps {
  type?: "slack" | "file" | "commit" | "source" | "document" | string;
  id?: string;
  label?: string;
  url?: string;
  path?: string;
  messageId?: string;
  confidence?: number;
  threshold?: number;
  className?: string;
  children?: React.ReactNode;
}

export const ProvenanceLink: React.FC<ProvenanceLinkProps> = ({
  type = "source",
  id,
  label,
  url,
  path,
  messageId,
  confidence,
  threshold = 0.8,
  className = "",
  children,
}) => {
  // Determine display label
  let displayLabel = label;
  if (!displayLabel) {
    if (type === "slack" || messageId) {
      displayLabel = `Slack message ${messageId || id || ""}`.trim();
    } else if (type === "file" || path) {
      displayLabel = path || `File ${id || ""}`.trim();
    } else if (type === "commit") {
      displayLabel = `Commit ${id?.slice(0, 7) || ""}`.trim();
    } else {
      displayLabel = `Source ${id || ""}`.trim();
    }
  }

  // Determine link target
  const targetUrl = url || (messageId ? `#/sources/slack/${messageId}` : id ? `#/sources/${id}` : "#");

  // Determine if confidence is sub-threshold
  const isSubThreshold = confidence !== undefined && confidence < threshold;

  return (
    <span
      className={`provenance-container ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--space-2)",
        fontSize: "var(--font-size-xs)",
      }}
    >
      <a
        href={targetUrl}
        className="provenance-link"
        aria-label={displayLabel}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "var(--space-1)",
          color: "var(--color-info)",
          textDecoration: "underline",
          textUnderlineOffset: "2px",
        }}
      >
        {children || displayLabel}
      </a>
      {isSubThreshold && (
        <span
          className="badge badge-warning"
          title={`Low confidence: ${Math.round(confidence * 100)}% (threshold: ${Math.round(threshold * 100)}%)`}
          style={{ fontSize: "10px", padding: "1px 6px" }}
        >
          Confidence: {Math.round(confidence * 100)}%
        </span>
      )}
    </span>
  );
};
