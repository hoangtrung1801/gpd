import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { DeveloperSession } from "@gpd/contracts";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

export const SessionsPage: React.FC = () => {
  const { sessionsApi, projectId } = useApp();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [sessions, setSessions] = useState<DeveloperSession[]>([]);

  const fetchSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await sessionsApi.listSessions(projectId);
      setSessions(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchSessions();
  }, [projectId]);

  return (
    <div>
      <div style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ marginBottom: "var(--space-2)" }}>Developer & Agent Sessions</h1>
        <p style={{ color: "var(--color-text-muted)" }}>
          Concurrent developer and agent workspace sessions with real-time overlap detection and collision prevention.
        </p>
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={sessions.length === 0}
        emptyTitle="No sessions found"
        emptyMessage="No developer or agent sessions have been recorded for this project."
        onRetry={fetchSessions}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
          {sessions.map((session) => {
            const hasOverlaps = session.overlap_warnings && session.overlap_warnings.length > 0;

            return (
              <div
                key={session.id}
                className="card"
                style={{
                  padding: "var(--space-5)",
                  backgroundColor: "var(--color-surface)",
                  margin: 0,
                  borderLeft: hasOverlaps ? "4px solid var(--color-warning)" : undefined,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "var(--space-4)",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginBottom: "var(--space-1)" }}>
                      <code style={{ fontSize: "var(--font-size-base)", color: "var(--color-info)" }}>
                        {session.id.slice(0, 12)}
                      </code>
                      <span className={`badge ${session.status === "active" ? "badge-success" : "badge-muted"}`}>
                        {session.status}
                      </span>
                    </div>
                    <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text)" }}>
                      <strong>Branch:</strong> <code>{session.git_branch || "main"}</code>
                    </div>
                  </div>

                  {session.task_id && (
                    <Link to={`/tasks/${session.task_id}`} className="btn" style={{ fontSize: "var(--font-size-xs)" }}>
                      View Task: {session.task_id} →
                    </Link>
                  )}
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: "var(--space-3)",
                    padding: "var(--space-3)",
                    backgroundColor: "var(--color-canvas)",
                    borderRadius: "var(--radius-md)",
                    fontSize: "var(--font-size-xs)",
                    marginBottom: hasOverlaps ? "var(--space-4)" : 0,
                  }}
                >
                  <div>
                    <span style={{ color: "var(--color-text-muted)" }}>Started: </span>
                    <span>{new Date(session.created_at).toLocaleString()}</span>
                  </div>
                  <div>
                    <span style={{ color: "var(--color-text-muted)" }}>Last Heartbeat: </span>
                    <span>
                      {session.last_heartbeat_at
                        ? new Date(session.last_heartbeat_at).toLocaleTimeString()
                        : "Active"}
                    </span>
                  </div>
                </div>

                {/* Overlap Warnings */}
                {hasOverlaps && (
                  <div style={{ marginTop: "var(--space-4)" }}>
                    <h4 style={{ fontSize: "var(--font-size-sm)", color: "var(--color-warning)", marginBottom: "var(--space-2)" }}>
                      ⚠️ File Overlap & Collision Warnings
                    </h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                      {session.overlap_warnings?.map((warning, idx) => (
                        <div
                          key={idx}
                          style={{
                            padding: "var(--space-3)",
                            backgroundColor: "var(--color-warning-bg)",
                            border: "1px solid var(--color-warning-border)",
                            borderRadius: "var(--radius-md)",
                            fontSize: "var(--font-size-xs)",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-1)" }}>
                            <strong>Severity: {warning.severity.toUpperCase()}</strong>
                          </div>
                          <p style={{ margin: "0 0 var(--space-2) 0", color: "var(--color-text)" }}>
                            {warning.explanation}
                          </p>
                          <div style={{ color: "var(--color-text-muted)" }}>
                            <strong>Suggested Action:</strong> {warning.suggested_action}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </AsyncState>
    </div>
  );
};
