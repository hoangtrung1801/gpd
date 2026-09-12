import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import type { KnowledgeItem } from "@gpd/contracts";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";
import { WarningBanner } from "../components/WarningBanner";

export const KnowledgePage: React.FC = () => {
  const { knowledgeApi, projectId } = useApp();

  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [component, setComponent] = useState("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);

  const fetchKnowledge = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await knowledgeApi.listKnowledge(projectId, {
        query: query || undefined,
        type: type || undefined,
        status: status || undefined,
        component: component || undefined,
      });
      setItems(res.items || []);
      setWarnings(res.warnings || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [knowledgeApi, projectId, query, type, status, component]);

  useEffect(() => {
    void fetchKnowledge();
  }, [fetchKnowledge]);

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
          <h1 style={{ marginBottom: "var(--space-2)" }}>Knowledge Base</h1>
          <p style={{ color: "var(--color-text-muted)" }}>
            Project architectural decisions, reviewed conventions, and confirmed bug patterns.
          </p>
        </div>
        <Link to="/knowledge/review" className="btn btn-primary">
          Review Proposals →
        </Link>
      </div>

      {/* Degraded Search Warning Banner */}
      <WarningBanner warnings={warnings} />

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
        <div style={{ flex: "1 1 240px", minWidth: "200px" }}>
          <label htmlFor="knowledge-search" className="sr-only">
            Search knowledge
          </label>
          <input
            id="knowledge-search"
            type="search"
            placeholder="Search decisions, rules, facts..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ width: "100%" }}
          />
        </div>

        <div style={{ minWidth: "150px" }}>
          <label htmlFor="type-filter" className="sr-only">
            Type filter
          </label>
          <select
            id="type-filter"
            value={type}
            onChange={(e) => setType(e.target.value)}
            style={{ width: "100%" }}
          >
            <option value="">All Types</option>
            <option value="architectural_decision">Architectural Decision</option>
            <option value="bug_pattern">Bug Pattern</option>
            <option value="convention">Convention</option>
            <option value="documented_fact">Documented Fact</option>
          </select>
        </div>

        <div style={{ minWidth: "140px" }}>
          <label htmlFor="status-filter" className="sr-only">
            Status filter
          </label>
          <select
            id="status-filter"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            style={{ width: "100%" }}
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="superseded">Superseded</option>
            <option value="deprecated">Deprecated</option>
          </select>
        </div>

        <div style={{ minWidth: "140px" }}>
          <label htmlFor="component-filter" className="sr-only">
            Component filter
          </label>
          <input
            id="component-filter"
            type="text"
            placeholder="Component..."
            value={component}
            onChange={(e) => setComponent(e.target.value)}
            style={{ width: "100%" }}
          />
        </div>
      </div>

      {/* Knowledge Items */}
      <AsyncState
        loading={loading}
        error={error}
        empty={items.length === 0}
        emptyTitle="No knowledge items found"
        emptyMessage="Try modifying your search keywords or filter values."
        onRetry={fetchKnowledge}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {items.map((item) => (
            <div
              key={item.id}
              className="card"
              style={{
                padding: "var(--space-5)",
                backgroundColor: "var(--color-surface)",
                margin: 0,
                opacity: item.status === "superseded" || item.status === "deprecated" ? 0.75 : 1,
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
                    <span className="badge badge-info">{item.type}</span>
                    <span
                      className={`badge ${
                        item.status === "active"
                          ? "badge-success"
                          : item.status === "superseded"
                          ? "badge-warning"
                          : "badge-muted"
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>
                  <h3 style={{ fontSize: "var(--font-size-lg)" }}>{item.title}</h3>
                </div>
              </div>

              <pre
                style={{
                  backgroundColor: "var(--color-canvas)",
                  padding: "var(--space-4)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border-subtle)",
                  whiteSpace: "pre-wrap",
                  color: "var(--color-text)",
                  fontSize: "var(--font-size-sm)",
                  margin: 0,
                }}
              >
                {item.content}
              </pre>

              <div
                style={{
                  marginTop: "var(--space-3)",
                  fontSize: "var(--font-size-xs)",
                  color: "var(--color-text-muted)",
                  display: "flex",
                  gap: "var(--space-4)",
                }}
              >
                <span>ID: <code>{item.id}</code></span>
                <span>Added: {new Date(item.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      </AsyncState>
    </div>
  );
};
