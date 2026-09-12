import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import type { Task, ContextPackage, DeveloperSession } from "@gpd/contracts";
import type { Conflict } from "../features/conflicts/api";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";
import { TaskFacts } from "../features/tasks/TaskFacts";
import { ContextPreview } from "../features/tasks/ContextPreview";

export const TaskDetailPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const { tasksApi, sessionsApi, conflictsApi, projectId } = useApp();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [contextPackage, setContextPackage] = useState<ContextPackage | null>(null);
  const [contextWarnings, setContextWarnings] = useState<string[]>([]);
  const [sessions, setSessions] = useState<DeveloperSession[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);

  useEffect(() => {
    if (!taskId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    const loadTaskData = async () => {
      try {
        const taskData = await tasksApi.getTask(taskId);
        if (!isMounted) return;
        setTask(taskData);

        // Fetch context package, sessions, and conflicts in parallel
        const [contextRes, sessionsRes, conflictsRes] = await Promise.allSettled([
          tasksApi.getTaskContext(taskData.id || taskId),
          sessionsApi.listSessions(projectId),
          conflictsApi.listConflicts(projectId),
        ]);

        if (!isMounted) return;

        if (contextRes.status === "fulfilled" && contextRes.value) {
          setContextPackage(contextRes.value);
          setContextWarnings(contextRes.value.warnings || []);
        }

        if (sessionsRes.status === "fulfilled" && sessionsRes.value) {
          setSessions(sessionsRes.value.filter((s) => s.task_id === taskData.id || s.task_id === taskId));
        }

        if (conflictsRes.status === "fulfilled" && conflictsRes.value) {
          setConflicts(conflictsRes.value);
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    void loadTaskData();

    return () => {
      isMounted = false;
    };
  }, [taskId, tasksApi, sessionsApi, conflictsApi, projectId]);

  return (
    <div>
      {/* Breadcrumbs */}
      <nav
        aria-label="Breadcrumb"
        style={{
          marginBottom: "var(--space-4)",
          fontSize: "var(--font-size-sm)",
          color: "var(--color-text-muted)",
        }}
      >
        <Link to="/tasks">Tasks</Link> /{" "}
        <span style={{ color: "var(--color-text)" }}>{task?.public_id || taskId}</span>
      </nav>

      <AsyncState loading={loading} error={error} onRetry={() => window.location.reload()}>
        {task && (
          <div>
            {/* Task Header */}
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
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-3)",
                    marginBottom: "var(--space-2)",
                  }}
                >
                  <code style={{ fontSize: "var(--font-size-base)", color: "var(--color-info)" }}>
                    {task.public_id || task.id}
                  </code>
                  <span
                    className={`badge badge-${
                      task.priority === "critical"
                        ? "danger"
                        : task.priority === "high"
                        ? "warning"
                        : "muted"
                    }`}
                  >
                    {task.priority}
                  </span>
                  <span className="badge badge-info">{task.status}</span>
                </div>
                <h1 style={{ fontSize: "var(--font-size-2xl)" }}>{task.title}</h1>
              </div>
            </div>

            {/* Main Grid: Details / Facts & Context Preview */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))",
                gap: "var(--space-6)",
                alignItems: "start",
              }}
            >
              {/* Left Column: Description, Extracted Facts, Linked Files */}
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
                {/* Description & Acceptance Criteria */}
                <div className="card" style={{ padding: "var(--space-5)", margin: 0 }}>
                  <h3 style={{ marginBottom: "var(--space-3)" }}>Description</h3>
                  <p style={{ whiteSpace: "pre-wrap", color: "var(--color-text)" }}>
                    {task.description || "No description provided."}
                  </p>

                  {task.acceptance_criteria && (
                    <div style={{ marginTop: "var(--space-4)" }}>
                      <h4 style={{ fontSize: "var(--font-size-sm)", marginBottom: "var(--space-2)" }}>
                        Acceptance Criteria
                      </h4>
                      <div
                        style={{
                          padding: "var(--space-3)",
                          backgroundColor: "var(--color-canvas)",
                          borderRadius: "var(--radius-md)",
                          fontSize: "var(--font-size-sm)",
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {task.acceptance_criteria}
                      </div>
                    </div>
                  )}
                </div>

                {/* Bug Details / Extracted Facts */}
                <TaskFacts bugDetails={task.bug_details} />

                {/* Active Sessions on this Task */}
                {sessions.length > 0 && (
                  <div className="card" style={{ padding: "var(--space-5)", margin: 0 }}>
                    <h3 style={{ marginBottom: "var(--space-3)" }}>Active Sessions</h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                      {sessions.map((s) => (
                        <div
                          key={s.id}
                          style={{
                            padding: "var(--space-3)",
                            backgroundColor: "var(--color-canvas)",
                            borderRadius: "var(--radius-md)",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                          }}
                        >
                          <div>
                            <strong>Branch:</strong> <code>{s.git_branch || "main"}</code>
                          </div>
                          <span className="badge badge-success">Active</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Right Column: Context Preview, Related Conflicts */}
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
                {/* Context Package Preview */}
                <ContextPreview
                  contextPackage={contextPackage}
                  warnings={contextWarnings}
                />

                {/* Related Conflicts */}
                {conflicts.length > 0 && (
                  <div className="card" style={{ padding: "var(--space-5)", margin: 0 }}>
                    <h3 style={{ marginBottom: "var(--space-3)" }}>Project Conflicts</h3>
                    <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)" }}>
                      Review contradictions and overlapping work in this project.
                    </p>
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
                      {conflicts.slice(0, 3).map((c) => (
                        <Link
                          key={c.id}
                          to={`/conflicts/${c.id}`}
                          style={{
                            padding: "var(--space-3)",
                            backgroundColor: "var(--color-canvas)",
                            borderRadius: "var(--radius-md)",
                            display: "block",
                            border: "1px solid var(--color-border-subtle)",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-1)" }}>
                            <strong style={{ fontSize: "var(--font-size-sm)" }}>{c.type}</strong>
                            <span className={`badge badge-${c.severity === "high" || c.severity === "critical" ? "danger" : "warning"}`}>
                              {c.severity}
                            </span>
                          </div>
                          <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
                            {c.claim_a} vs {c.claim_b}
                          </div>
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </AsyncState>
    </div>
  );
};
