import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Task, DeveloperSession } from "@gpd/contracts";
import type { Conflict } from "../features/conflicts/api";
import type { Job } from "../features/jobs/api";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

export const OverviewPage: React.FC = () => {
  const { tasksApi, sessionsApi, conflictsApi, jobsApi, health, projectId } = useApp();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [sessions, setSessions] = useState<DeveloperSession[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [failedJobs, setFailedJobs] = useState<Job[]>([]);

  const loadOverviewData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [tasksRes, sessionsRes, conflictsRes, jobsRes] = await Promise.all([
        tasksApi.listTasks({ project_id: projectId, limit: 5 }),
        sessionsApi.listSessions(projectId),
        conflictsApi.listConflicts(projectId, "unresolved"),
        jobsApi.listJobs(projectId, { state: "failed" }),
      ]);

      setTasks(tasksRes.items || []);
      setSessions(sessionsRes || []);
      setConflicts(conflictsRes || []);
      setFailedJobs(jobsRes || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadOverviewData();
  }, [projectId]);

  const activeSessions = sessions.filter((s) => s.status === "active");

  return (
    <div>
      <div style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ marginBottom: "var(--space-2)" }}>Platform Overview</h1>
        <p style={{ color: "var(--color-text-muted)" }}>
          Real-time summary of tasks, active agent/developer sessions, knowledge conflicts, and operations.
        </p>
      </div>

      <AsyncState loading={loading} error={error} onRetry={loadOverviewData}>
        {/* Metric Cards Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "var(--space-4)",
            marginBottom: "var(--space-6)",
          }}
        >
          <div className="card" style={{ margin: 0 }}>
            <div style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)" }}>
              Active Sessions
            </div>
            <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "bold", margin: "var(--space-2) 0" }}>
              {activeSessions.length}
            </div>
            <Link to="/sessions" style={{ fontSize: "var(--font-size-xs)" }}>
              View sessions →
            </Link>
          </div>

          <div className="card" style={{ margin: 0 }}>
            <div style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)" }}>
              Recent Tasks
            </div>
            <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "bold", margin: "var(--space-2) 0" }}>
              {tasks.length}
            </div>
            <Link to="/tasks" style={{ fontSize: "var(--font-size-xs)" }}>
              View all tasks →
            </Link>
          </div>

          <div className="card" style={{ margin: 0 }}>
            <div style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)" }}>
              Unresolved Conflicts
            </div>
            <div
              style={{
                fontSize: "var(--font-size-2xl)",
                fontWeight: "bold",
                margin: "var(--space-2) 0",
                color: conflicts.length > 0 ? "var(--color-warning)" : "var(--color-text)",
              }}
            >
              {conflicts.length}
            </div>
            <Link to="/conflicts" style={{ fontSize: "var(--font-size-xs)" }}>
              Resolve conflicts →
            </Link>
          </div>

          <div className="card" style={{ margin: 0 }}>
            <div style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)" }}>
              Failed Jobs
            </div>
            <div
              style={{
                fontSize: "var(--font-size-2xl)",
                fontWeight: "bold",
                margin: "var(--space-2) 0",
                color: failedJobs.length > 0 ? "var(--color-danger)" : "var(--color-text)",
              }}
            >
              {failedJobs.length}
            </div>
            <Link to="/jobs" style={{ fontSize: "var(--font-size-xs)" }}>
              Inspect jobs →
            </Link>
          </div>

          <div className="card" style={{ margin: 0 }}>
            <div style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)" }}>
              Backend Health
            </div>
            <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "bold", margin: "var(--space-2) 0" }}>
              <span className={`badge ${health?.status === "ok" ? "badge-success" : "badge-warning"}`}>
                {health?.status || "Unknown"}
              </span>
            </div>
            <Link to="/settings" style={{ fontSize: "var(--font-size-xs)" }}>
              Settings & Health →
            </Link>
          </div>
        </div>

        {/* Recent Tasks & Active Sessions Row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "var(--space-6)" }}>
          {/* Recent Tasks Section */}
          <section className="card" style={{ margin: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)" }}>
              <h3>Recent Tasks</h3>
              <Link to="/tasks" style={{ fontSize: "var(--font-size-sm)" }}>
                View all
              </Link>
            </div>

            {tasks.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
                No recent tasks found.
              </p>
            ) : (
              <div className="table-container" style={{ margin: 0 }}>
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Title</th>
                      <th>Priority</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.map((t) => (
                      <tr key={t.id}>
                        <td>
                          <Link to={`/tasks/${t.public_id || t.id}`} style={{ fontWeight: "bold" }}>
                            {t.public_id || t.id.slice(0, 8)}
                          </Link>
                        </td>
                        <td>{t.title}</td>
                        <td>
                          <span className={`badge badge-${t.priority === "critical" ? "danger" : t.priority === "high" ? "warning" : "muted"}`}>
                            {t.priority}
                          </span>
                        </td>
                        <td>
                          <span className="badge badge-info">{t.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Active Sessions Section */}
          <section className="card" style={{ margin: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)" }}>
              <h3>Active Sessions</h3>
              <Link to="/sessions" style={{ fontSize: "var(--font-size-sm)" }}>
                View all
              </Link>
            </div>

            {activeSessions.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
                No active developer sessions.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {activeSessions.map((s) => (
                  <div
                    key={s.id}
                    style={{
                      padding: "var(--space-3)",
                      backgroundColor: "var(--color-canvas)",
                      border: "1px solid var(--color-border-subtle)",
                      borderRadius: "var(--radius-md)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: "bold", fontSize: "var(--font-size-sm)" }}>
                        Branch: <code>{s.git_branch || "main"}</code>
                      </div>
                      <div style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)" }}>
                        Task: {s.task_id || "Unassigned"}
                      </div>
                    </div>
                    {s.overlap_warnings && s.overlap_warnings.length > 0 && (
                      <span className="badge badge-warning" style={{ fontSize: "11px" }}>
                        ⚠️ Overlap Warning
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </AsyncState>
    </div>
  );
};
