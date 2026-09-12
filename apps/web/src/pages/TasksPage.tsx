import React, { useEffect, useState, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Task } from "@gpd/contracts";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

export const TasksPage: React.FC = () => {
  const { tasksApi, projectId } = useApp();
  const [searchParams, setSearchParams] = useSearchParams();

  // Read URL filter state
  const query = searchParams.get("q") || "";
  const status = searchParams.get("status") || "";
  const priority = searchParams.get("priority") || "";
  const assignee = searchParams.get("assignee") || "";
  const component = searchParams.get("component") || "";
  const cursor = searchParams.get("cursor") || "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await tasksApi.listTasks({
        project_id: projectId,
        query: query || undefined,
        status: status || undefined,
        assignee: assignee || undefined,
        cursor: cursor || undefined,
        limit: 20,
      });

      let items = res.items || [];
      // Filter by priority or component client-side if backend only filters by status/query
      if (priority) {
        items = items.filter((t) => t.priority === priority);
      }
      if (component) {
        items = items.filter((t) => t.bug_details?.affected_component?.value === component);
      }

      setTasks(items);
      setNextCursor(res.next_cursor || null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [tasksApi, projectId, query, status, priority, assignee, component, cursor]);

  useEffect(() => {
    void fetchTasks();
  }, [fetchTasks]);

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.delete("cursor"); // Reset cursor on filter change
    setSearchParams(next);
  };

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "var(--space-6)",
        }}
      >
        <div>
          <h1 style={{ marginBottom: "var(--space-2)" }}>Tasks & Issues</h1>
          <p style={{ color: "var(--color-text-muted)" }}>
            Browse and filter ingested bug extractions, user stories, and work items.
          </p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div
        className="card"
        style={{
          padding: "var(--space-4)",
          marginBottom: "var(--space-6)",
          display: "flex",
          flexWrap: "wrap",
          gap: "var(--space-3)",
          alignItems: "center",
        }}
      >
        <div style={{ flex: "1 1 220px", minWidth: "200px" }}>
          <label htmlFor="task-search" className="sr-only">
            Search tasks
          </label>
          <input
            id="task-search"
            type="search"
            placeholder="Search by title, description..."
            value={query}
            onChange={(e) => updateFilter("q", e.target.value)}
            style={{ width: "100%" }}
          />
        </div>

        <div style={{ minWidth: "140px" }}>
          <label htmlFor="status-filter" className="sr-only">
            Filter by status
          </label>
          <select
            id="status-filter"
            value={status}
            onChange={(e) => updateFilter("status", e.target.value)}
            style={{ width: "100%" }}
          >
            <option value="">All Statuses</option>
            <option value="todo">To Do</option>
            <option value="in_progress">In Progress</option>
            <option value="in_review">In Review</option>
            <option value="blocked">Blocked</option>
            <option value="done">Done</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <div style={{ minWidth: "140px" }}>
          <label htmlFor="priority-filter" className="sr-only">
            Filter by priority
          </label>
          <select
            id="priority-filter"
            value={priority}
            onChange={(e) => updateFilter("priority", e.target.value)}
            style={{ width: "100%" }}
          >
            <option value="">All Priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div style={{ minWidth: "140px" }}>
          <label htmlFor="component-filter" className="sr-only">
            Filter by component
          </label>
          <input
            id="component-filter"
            type="text"
            placeholder="Component..."
            value={component}
            onChange={(e) => updateFilter("component", e.target.value)}
            style={{ width: "100%" }}
          />
        </div>

        {(query || status || priority || component || assignee) && (
          <button
            type="button"
            className="btn"
            onClick={() => setSearchParams(new URLSearchParams())}
            style={{ fontSize: "var(--font-size-xs)" }}
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Task List Table */}
      <AsyncState
        loading={loading}
        error={error}
        empty={tasks.length === 0}
        emptyTitle="No tasks found"
        emptyMessage="Try adjusting your search query or status filters."
        onRetry={fetchTasks}
      >
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th style={{ width: "120px" }}>Key</th>
                <th>Title</th>
                <th style={{ width: "140px" }}>Component</th>
                <th style={{ width: "120px" }}>Priority</th>
                <th style={{ width: "130px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>
                    <Link
                      to={`/tasks/${task.public_id || task.id}`}
                      style={{ fontWeight: "bold" }}
                    >
                      {task.public_id || task.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td>
                    <Link
                      to={`/tasks/${task.public_id || task.id}`}
                      style={{ color: "var(--color-text)", fontWeight: "var(--font-weight-medium)" }}
                    >
                      {task.title}
                    </Link>
                  </td>
                  <td>
                    {task.bug_details?.affected_component?.value ? (
                      <code>{task.bug_details.affected_component.value}</code>
                    ) : (
                      <span style={{ color: "var(--color-text-muted)" }}>—</span>
                    )}
                  </td>
                  <td>
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
                  </td>
                  <td>
                    <span className="badge badge-info">{task.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Cursor Pagination Controls */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: "var(--space-4)",
          }}
        >
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
            Showing {tasks.length} task(s)
          </span>
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            {cursor && (
              <button
                type="button"
                className="btn"
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.delete("cursor");
                  setSearchParams(next);
                }}
              >
                ← First Page
              </button>
            )}
            {nextCursor && (
              <button
                type="button"
                className="btn"
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.set("cursor", nextCursor);
                  setSearchParams(next);
                }}
              >
                Next Page →
              </button>
            )}
          </div>
        </div>
      </AsyncState>
    </div>
  );
};
