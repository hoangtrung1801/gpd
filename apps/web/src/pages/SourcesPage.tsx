import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import type { Source, SourceState } from "../features/sources/api";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

export const SourcesPage: React.FC = () => {
  const { sourcesApi, projectId } = useApp();

  const [stateFilter, setStateFilter] = useState<SourceState | "">("");
  const [typeFilter, setTypeFilter] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchSources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await sourcesApi.listSources(projectId, {
        state: stateFilter || undefined,
        source_type: typeFilter || undefined,
      });
      setSources(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [sourcesApi, projectId, stateFilter, typeFilter]);

  useEffect(() => {
    void fetchSources();
  }, [fetchSources]);

  const handleRetry = async (sourceId: string) => {
    try {
      await sourcesApi.retrySource(sourceId);
      void fetchSources();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to retry ingestion");
    }
  };

  return (
    <div>
      <div style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ marginBottom: "var(--space-2)" }}>Ingested Sources</h1>
        <p style={{ color: "var(--color-text-muted)" }}>
          Raw immutable source documents, Slack discussions, and codebase files with indexing and chunking pipelines.
        </p>
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
        <div style={{ minWidth: "160px" }}>
          <label htmlFor="source-state-filter" className="sr-only">
            State filter
          </label>
          <select
            id="source-state-filter"
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value as SourceState | "")}
            style={{ width: "100%" }}
          >
            <option value="">All States</option>
            <option value="ready">Ready</option>
            <option value="parsing">Parsing</option>
            <option value="indexing">Indexing</option>
            <option value="embedding_pending">Embedding Pending</option>
            <option value="queued">Queued</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        <div style={{ minWidth: "160px" }}>
          <label htmlFor="source-type-filter" className="sr-only">
            Type filter
          </label>
          <select
            id="source-type-filter"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{ width: "100%" }}
          >
            <option value="">All Types</option>
            <option value="document">Document</option>
            <option value="slack">Slack</option>
            <option value="git_file">Git File</option>
          </select>
        </div>
      </div>

      {/* Sources Table */}
      <AsyncState
        loading={loading}
        error={error}
        empty={sources.length === 0}
        emptyTitle="No sources found"
        emptyMessage="No source documents ingested or matching the filters."
        onRetry={fetchSources}
      >
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Title / Path</th>
                <th style={{ width: "120px" }}>Type</th>
                <th style={{ width: "140px" }}>State</th>
                <th style={{ width: "120px" }}>Hash</th>
                <th style={{ width: "90px" }}>Chunks</th>
                <th style={{ width: "100px" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.id}>
                  <td>
                    <Link to={`/sources/${source.id}`} style={{ fontWeight: "bold" }}>
                      {source.title || source.path_or_url || source.id}
                    </Link>
                  </td>
                  <td>
                    <span className="badge badge-muted">{source.source_type}</span>
                  </td>
                  <td>
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
                  </td>
                  <td>
                    <code>{source.content_hash ? source.content_hash.slice(0, 8) : "—"}</code>
                  </td>
                  <td>{source.chunks_count ?? 0}</td>
                  <td>
                    {source.state === "failed" ? (
                      <button
                        type="button"
                        onClick={() => handleRetry(source.id)}
                        className="btn btn-danger"
                        style={{ padding: "2px 8px", minHeight: "32px", fontSize: "var(--font-size-xs)" }}
                      >
                        Retry
                      </button>
                    ) : (
                      <Link to={`/sources/${source.id}`} style={{ fontSize: "var(--font-size-xs)" }}>
                        View
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncState>
    </div>
  );
};
