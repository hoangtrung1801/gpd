import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import type { Source } from "../features/sources/api";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

export const SourceDetailPage: React.FC = () => {
  const { sourceId } = useParams<{ sourceId: string }>();
  const { sourcesApi } = useApp();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    if (!sourceId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    const loadSource = async () => {
      try {
        const data = await sourcesApi.getSource(sourceId);
        if (isMounted) setSource(data);
      } catch (err: unknown) {
        if (isMounted) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    void loadSource();

    return () => {
      isMounted = false;
    };
  }, [sourceId, sourcesApi]);

  const handleRetry = async () => {
    if (!sourceId) return;
    setRetrying(true);
    try {
      const res = await sourcesApi.retrySource(sourceId);
      if (source) {
        setSource({ ...source, state: res.state, error_message: null });
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to retry source");
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div>
      {/* Breadcrumb */}
      <nav
        aria-label="Breadcrumb"
        style={{
          marginBottom: "var(--space-4)",
          fontSize: "var(--font-size-sm)",
          color: "var(--color-text-muted)",
        }}
      >
        <Link to="/sources">Sources</Link> /{" "}
        <span style={{ color: "var(--color-text)" }}>{sourceId}</span>
      </nav>

      <AsyncState loading={loading} error={error} onRetry={() => window.location.reload()}>
        {source && (
          <div>
            {/* Source Header */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: "var(--space-6)",
                borderBottom: "1px solid var(--color-border)",
                paddingBottom: "var(--space-4)",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginBottom: "var(--space-2)" }}>
                  <span className="badge badge-muted">{source.source_type}</span>
                  <span
                    className={`badge ${
                      source.state === "ready"
                        ? "badge-success"
                        : source.state === "failed"
                        ? "badge-danger"
                        : "badge-warning"
                    }`}
                  >
                    {source.state}
                  </span>
                </div>
                <h1 style={{ fontSize: "var(--font-size-2xl)" }}>{source.title || "Untitled Source"}</h1>
                {source.path_or_url && (
                  <div style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-1)" }}>
                    <code>{source.path_or_url}</code>
                  </div>
                )}
              </div>

              {source.state === "failed" && (
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={retrying}
                  className="btn btn-danger"
                >
                  {retrying ? "Retrying..." : "Retry Ingestion"}
                </button>
              )}
            </div>

            {/* Ingestion Failure Banner */}
            {source.error_message && (
              <div
                role="alert"
                style={{
                  padding: "var(--space-4)",
                  backgroundColor: "var(--color-danger-bg)",
                  border: "1px solid var(--color-danger-border)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--color-danger)",
                  marginBottom: "var(--space-6)",
                }}
              >
                <h4 style={{ marginBottom: "var(--space-1)", color: "var(--color-danger)" }}>
                  Ingestion / Indexing Failure
                </h4>
                <p style={{ margin: 0, color: "var(--color-text)" }}>{source.error_message}</p>
              </div>
            )}

            {/* Metadata Summary */}
            <div
              className="card"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "var(--space-4)",
                padding: "var(--space-4)",
                marginBottom: "var(--space-6)",
              }}
            >
              <div>
                <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                  Content Hash (SHA-256)
                </span>
                <div style={{ marginTop: "2px" }}>
                  <code style={{ fontSize: "var(--font-size-xs)" }}>{source.content_hash || "—"}</code>
                </div>
              </div>

              <div>
                <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                  Chunk Count
                </span>
                <div style={{ fontSize: "var(--font-size-lg)", fontWeight: "bold" }}>
                  {source.chunks_count ?? 0}
                </div>
              </div>

              <div>
                <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                  Created At
                </span>
                <div style={{ fontSize: "var(--font-size-sm)" }}>
                  {new Date(source.created_at).toLocaleString()}
                </div>
              </div>
            </div>

            {/* Immutable Content Display */}
            <div className="card">
              <h3 style={{ marginBottom: "var(--space-3)" }}>Immutable Source Content</h3>
              <pre
                style={{
                  padding: "var(--space-5)",
                  backgroundColor: "var(--color-canvas)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border-subtle)",
                  overflowX: "auto",
                  maxHeight: "600px",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  color: "var(--color-text)",
                  fontFamily: "var(--font-mono)",
                  fontSize: "var(--font-size-sm)",
                  lineHeight: "var(--line-height-relaxed)",
                }}
              >
                {source.content || "(Empty document)"}
              </pre>
            </div>
          </div>
        )}
      </AsyncState>
    </div>
  );
};
