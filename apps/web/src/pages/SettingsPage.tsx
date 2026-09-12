import React, { useEffect, useState } from "react";
import type { SettingsData, DetailedHealthStatus } from "../features/settings/api";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

export const SettingsPage: React.FC = () => {
  const { settingsApi, projectId } = useApp();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [health, setHealth] = useState<DetailedHealthStatus | null>(null);

  // Editable non-secret allowlist fields
  const [name, setName] = useState("");
  const [teamIdentifier, setTeamIdentifier] = useState("");
  const [defaultBranch, setDefaultBranch] = useState("main");
  const [llmModel, setLlmModel] = useState("gpt-4o");
  const [embeddingModel, setEmbeddingModel] = useState("text-embedding-3-small");
  const [contextTokenBudget, setContextTokenBudget] = useState(8000);

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const loadSettingsAndHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const [settingsData, healthData] = await Promise.all([
        settingsApi.getSettings(projectId),
        settingsApi.getHealth(),
      ]);

      setSettings(settingsData);
      setHealth(healthData);

      setName(settingsData.name || "");
      setTeamIdentifier(settingsData.team_identifier || "");
      setDefaultBranch(settingsData.default_branch || "main");
      setLlmModel(settingsData.llm_model || "gpt-4o");
      setEmbeddingModel(settingsData.embedding_model || "text-embedding-3-small");
      setContextTokenBudget(settingsData.context_token_budget || 8000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSettingsAndHealth();
  }, [projectId]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(null);
    setSaveError(null);

    try {
      const updated = await settingsApi.patchSettings(projectId, {
        name,
        team_identifier: teamIdentifier.trim() ? teamIdentifier.trim() : null,
        default_branch: defaultBranch,
        llm_model: llmModel,
        embedding_model: embeddingModel,
        context_token_budget: Number(contextTokenBudget),
        version: settings?.version,
      });

      setSettings(updated);
      setSaveSuccess("Settings saved successfully.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update settings";
      if (msg.includes("409") || msg.toLowerCase().includes("conflict")) {
        setSaveError("Settings were modified concurrently by another user/process. Reloading latest...");
        void loadSettingsAndHealth();
      } else {
        setSaveError(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  const isSlackConfigured = settings?.slack_credential_configured ?? settings?.slack_configured ?? false;
  const isLlmConfigured = settings?.llm_credential_configured ?? settings?.llm_configured ?? false;

  return (
    <div>
      <div style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ marginBottom: "var(--space-2)" }}>Project Settings & Health</h1>
        <p style={{ color: "var(--color-text-muted)" }}>
          Manage non-secret project parameters, view integration secret presence, and monitor system health.
        </p>
      </div>

      {saveSuccess && (
        <div
          role="status"
          className="badge badge-success"
          style={{ padding: "var(--space-3) var(--space-4)", display: "block", marginBottom: "var(--space-4)", fontSize: "var(--font-size-sm)" }}
        >
          ✓ {saveSuccess}
        </div>
      )}

      {saveError && (
        <div
          role="alert"
          className="badge badge-danger"
          style={{ padding: "var(--space-3) var(--space-4)", display: "block", marginBottom: "var(--space-4)", fontSize: "var(--font-size-sm)" }}
        >
          ✕ {saveError}
        </div>
      )}

      <AsyncState loading={loading} error={error} onRetry={loadSettingsAndHealth}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "var(--space-6)", alignItems: "start" }}>
          {/* Settings Form */}
          <div className="card" style={{ margin: 0 }}>
            <h3 style={{ marginBottom: "var(--space-4)" }}>Editable Project Parameters</h3>
            <form onSubmit={handleSave}>
              <div style={{ marginBottom: "var(--space-4)" }}>
                <label htmlFor="project-name">Project Name</label>
                <input
                  id="project-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ marginBottom: "var(--space-4)" }}>
                <label htmlFor="team-identifier">Team Identifier</label>
                <input
                  id="team-identifier"
                  type="text"
                  value={teamIdentifier}
                  onChange={(e) => setTeamIdentifier(e.target.value)}
                  placeholder="e.g. checkout-team"
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ marginBottom: "var(--space-4)" }}>
                <label htmlFor="default-branch">Default Git Branch</label>
                <input
                  id="default-branch"
                  type="text"
                  value={defaultBranch}
                  onChange={(e) => setDefaultBranch(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ marginBottom: "var(--space-4)" }}>
                <label htmlFor="llm-model">LLM Model</label>
                <input
                  id="llm-model"
                  type="text"
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ marginBottom: "var(--space-4)" }}>
                <label htmlFor="embedding-model">Embedding Model</label>
                <input
                  id="embedding-model"
                  type="text"
                  value={embeddingModel}
                  onChange={(e) => setEmbeddingModel(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ marginBottom: "var(--space-5)" }}>
                <label htmlFor="token-budget">Context Token Budget</label>
                <input
                  id="token-budget"
                  type="number"
                  min={1000}
                  max={128000}
                  step={500}
                  value={contextTokenBudget}
                  onChange={(e) => setContextTokenBudget(Number(e.target.value))}
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving}
              >
                {saving ? "Saving Changes..." : "Save Settings"}
              </button>
            </form>
          </div>

          {/* Right Column: Integrations (Secret Presence) & System Health & Retention */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
            {/* Secret Presence Booleans */}
            <div className="card" style={{ margin: 0 }}>
              <h3 style={{ marginBottom: "var(--space-3)" }}>Integration Credentials</h3>
              <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)", marginBottom: "var(--space-4)" }}>
                Secret presence booleans only. Real tokens and API keys are stored in environment files and never exposed to the UI or API.
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "var(--space-3)",
                    backgroundColor: "var(--color-canvas)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <div>
                    <strong>Slack Integration</strong>
                    <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                      Webhook & thread ingestion
                    </div>
                  </div>
                  <span className={`badge ${isSlackConfigured ? "badge-success" : "badge-muted"}`}>
                    {isSlackConfigured ? "Configured" : "Not configured"}
                  </span>
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "var(--space-3)",
                    backgroundColor: "var(--color-canvas)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <div>
                    <strong>LLM Credentials</strong>
                    <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                      OpenAI / Anthropic API token
                    </div>
                  </div>
                  <span className={`badge ${isLlmConfigured ? "badge-success" : "badge-muted"}`}>
                    {isLlmConfigured ? "Configured" : "Not configured"}
                  </span>
                </div>
              </div>
            </div>

            {/* Retention Control (Display-Only v1) */}
            <div className="card" style={{ margin: 0 }}>
              <h3 style={{ marginBottom: "var(--space-2)" }}>Data Retention Policy</h3>
              <div
                style={{
                  padding: "var(--space-3)",
                  backgroundColor: "var(--color-canvas)",
                  borderRadius: "var(--radius-md)",
                  fontSize: "var(--font-size-sm)",
                }}
              >
                <div>
                  <strong>Window: </strong>
                  <span>{settings?.retention_days ?? 90} days</span>
                </div>
                <div style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)", marginTop: "var(--space-1)" }}>
                  Display-only in v1: Automated destructive data purge is disabled to preserve audit history.
                </div>
              </div>
            </div>

            {/* System Health Status */}
            <div className="card" style={{ margin: 0 }}>
              <h3 style={{ marginBottom: "var(--space-3)" }}>System Engine Health</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "var(--space-3)",
                    backgroundColor: "var(--color-canvas)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <span>SQLite Database</span>
                  <span className={`badge ${health?.database_healthy ? "badge-success" : "badge-danger"}`}>
                    {health?.database || "Connected"}
                  </span>
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "var(--space-3)",
                    backgroundColor: "var(--color-canvas)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <span>FTS5 Keyword Search</span>
                  <span className={`badge ${health?.fts_healthy ? "badge-success" : "badge-warning"}`}>
                    {health?.fts_healthy ? "Healthy" : "Degraded"}
                  </span>
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "var(--space-3)",
                    backgroundColor: "var(--color-canvas)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <span>Vector Indexing (sqlite-vec)</span>
                  <span className={`badge ${health?.vector_healthy ? "badge-success" : "badge-warning"}`}>
                    {health?.vector_healthy ? "Healthy" : "Unavailable"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </AsyncState>
    </div>
  );
};
