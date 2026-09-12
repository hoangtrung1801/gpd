import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import type { Conflict } from "../features/conflicts/api";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

export const ConflictsPage: React.FC = () => {
  const { conflictsApi, projectId } = useApp();

  const [stateFilter, setStateFilter] = useState<string>("unresolved");
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchConflicts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await conflictsApi.listConflicts(projectId, stateFilter || undefined);
      setConflicts(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [conflictsApi, projectId, stateFilter]);

  useEffect(() => {
    void fetchConflicts();
  }, [fetchConflicts]);

  return (
    <div>
      <div style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ marginBottom: "var(--space-2)" }}>Knowledge & Code Conflicts</h1>
        <p style={{ color: "var(--color-text-muted)" }}>
          Detected contradictions between documentation, requirements, and codebase behavior.
        </p>
      </div>

      {/* Filter Toolbar */}
      <div
        className="card"
        style={{
          padding: "var(--space-4)",
          marginBottom: "var(--space-6)",
          display: "flex",
          gap: "var(--space-3)",
          alignItems: "center",
        }}
      >
        <div style={{ minWidth: "160px" }}>
          <label htmlFor="conflict-state-filter" className="sr-only">
            State filter
          </label>
          <select
            id="conflict-state-filter"
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            style={{ width: "100%" }}
          >
            <option value="">All Conflicts</option>
            <option value="unresolved">Unresolved</option>
            <option value="resolved">Resolved</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </div>
      </div>

      {/* Conflicts List */}
      <AsyncState
        loading={loading}
        error={error}
        empty={conflicts.length === 0}
        emptyTitle="No conflicts found"
        emptyMessage="There are no contradictions matching your filter criteria."
        onRetry={fetchConflicts}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {conflicts.map((conflict) => (
            <div
              key={conflict.id}
              className="card"
              style={{
                padding: "var(--space-5)",
                backgroundColor: "var(--color-surface)",
                margin: 0,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  marginBottom: "var(--space-3)",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
                    <span
                      className={`badge badge-${
                        conflict.severity === "critical" || conflict.severity === "high"
                          ? "danger"
                          : "warning"
                      }`}
                    >
                      {conflict.severity.toUpperCase()}
                    </span>
                    <span className="badge badge-info">{conflict.type}</span>
                    <span className={`badge ${conflict.state === "resolved" ? "badge-success" : "badge-muted"}`}>
                      {conflict.state}
                    </span>
                  </div>
                  <h3 style={{ fontSize: "var(--font-size-base)" }}>
                    <Link to={`/conflicts/${conflict.id}`} style={{ color: "var(--color-text)" }}>
                      {conflict.type}: {conflict.claim_a.slice(0, 60)} vs {conflict.claim_b.slice(0, 60)}
                    </Link>
                  </h3>
                </div>

                <Link to={`/conflicts/${conflict.id}`} className="btn btn-primary" style={{ fontSize: "var(--font-size-xs)" }}>
                  {conflict.state === "resolved" ? "View Details" : "Resolve →"}
                </Link>
              </div>

              {/* Claims Summary */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "var(--space-4)",
                  padding: "var(--space-3)",
                  backgroundColor: "var(--color-canvas)",
                  borderRadius: "var(--radius-md)",
                  fontSize: "var(--font-size-sm)",
                }}
              >
                <div>
                  <strong style={{ color: "var(--color-text-secondary)" }}>Claim A: </strong>
                  <span>{conflict.claim_a}</span>
                </div>
                <div>
                  <strong style={{ color: "var(--color-text-secondary)" }}>Claim B: </strong>
                  <span>{conflict.claim_b}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </AsyncState>
    </div>
  );
};
