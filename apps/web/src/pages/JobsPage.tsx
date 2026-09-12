import React, { useEffect, useState, useCallback } from "react";
import type { Job, JobState } from "../features/jobs/api";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

export const JobsPage: React.FC = () => {
  const { jobsApi, projectId } = useApp();

  const [stateFilter, setStateFilter] = useState<JobState | "">("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await jobsApi.listJobs(projectId, {
        state: stateFilter || undefined,
      });
      setJobs(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [jobsApi, projectId, stateFilter]);

  useEffect(() => {
    void fetchJobs();
  }, [fetchJobs]);

  const handleRetry = async (jobId: string) => {
    try {
      await jobsApi.retryJob(jobId);
      void fetchJobs();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to retry job");
    }
  };

  const handleCancel = async (jobId: string) => {
    try {
      await jobsApi.cancelJob(jobId);
      void fetchJobs();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to cancel job");
    }
  };

  return (
    <div>
      <div style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ marginBottom: "var(--space-2)" }}>Background Jobs & Pipelines</h1>
        <p style={{ color: "var(--color-text-muted)" }}>
          Monitor background indexing, vector embeddings, document parsing, and integration tasks.
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
          <label htmlFor="job-state-filter" className="sr-only">
            State filter
          </label>
          <select
            id="job-state-filter"
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value as JobState | "")}
            style={{ width: "100%" }}
          >
            <option value="">All Job States</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Jobs Table */}
      <AsyncState
        loading={loading}
        error={error}
        empty={jobs.length === 0}
        emptyTitle="No background jobs found"
        emptyMessage="There are no jobs matching your filter criteria."
        onRetry={fetchJobs}
      >
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th style={{ width: "120px" }}>Job ID</th>
                <th>Type</th>
                <th style={{ width: "120px" }}>State</th>
                <th style={{ width: "150px" }}>Progress</th>
                <th style={{ width: "100px" }}>Attempts</th>
                <th>Error Code / Details</th>
                <th style={{ width: "110px" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>
                    <code>{job.id.slice(0, 8)}</code>
                  </td>
                  <td>
                    <strong>{job.type}</strong>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        job.state === "succeeded"
                          ? "badge-success"
                          : job.state === "failed"
                          ? "badge-danger"
                          : job.state === "running"
                          ? "badge-info"
                          : "badge-muted"
                      }`}
                    >
                      {job.state}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <div
                        style={{
                          flex: 1,
                          height: "6px",
                          backgroundColor: "var(--color-canvas)",
                          borderRadius: "var(--radius-full)",
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.min(100, Math.max(0, job.progress))}%`,
                            height: "100%",
                            backgroundColor:
                              job.state === "failed"
                                ? "var(--color-danger)"
                                : "var(--color-primary)",
                          }}
                        />
                      </div>
                      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                        {job.progress}%
                      </span>
                    </div>
                  </td>
                  <td>
                    {job.attempts} / {job.max_attempts}
                  </td>
                  <td>
                    {job.error_code ? (
                      <div style={{ color: "var(--color-danger)", fontSize: "var(--font-size-xs)" }}>
                        <strong>{job.error_code}:</strong> {job.error_message || "Execution error"}
                      </div>
                    ) : (
                      <span style={{ color: "var(--color-text-muted)" }}>—</span>
                    )}
                  </td>
                  <td>
                    {job.state === "failed" && job.retryable && (
                      <button
                        type="button"
                        onClick={() => handleRetry(job.id)}
                        className="btn btn-primary"
                        style={{ padding: "2px 8px", minHeight: "32px", fontSize: "var(--font-size-xs)" }}
                      >
                        Retry
                      </button>
                    )}
                    {(job.state === "queued" || job.state === "running") && (
                      <button
                        type="button"
                        onClick={() => handleCancel(job.id)}
                        className="btn btn-danger"
                        style={{ padding: "2px 8px", minHeight: "32px", fontSize: "var(--font-size-xs)" }}
                      >
                        Cancel
                      </button>
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
