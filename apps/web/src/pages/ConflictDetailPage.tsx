import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import type { Conflict, ConflictResolutionAction } from "../features/conflicts/api";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

const ACTION_IMPACTS: Record<ConflictResolutionAction, string> = {
  supersede: "Claim B will officially supersede Claim A in all future context packages and agent prompts.",
  clarify: "Both claims will be retained, but annotated with refined operational scope.",
  conditional: "Both claims will be kept with specified branch or environment conditions.",
  dismiss: "The conflict will be dismissed without modifying underlying knowledge.",
};

export const ConflictDetailPage: React.FC = () => {
  const { conflictId } = useParams<{ conflictId: string }>();
  const { conflictsApi } = useApp();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [conflict, setConflict] = useState<Conflict | null>(null);

  const [action, setAction] = useState<ConflictResolutionAction>("supersede");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!conflictId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    const loadConflict = async () => {
      try {
        const data = await conflictsApi.getConflict(conflictId);
        if (isMounted) {
          setConflict(data);
          if (data.resolution) {
            setAction(data.resolution.action);
            setNote(data.resolution.note);
          }
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

    void loadConflict();

    return () => {
      isMounted = false;
    };
  }, [conflictId, conflictsApi]);

  const handleResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!conflictId || !note.trim()) {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);

    try {
      const resolved = await conflictsApi.resolveConflict(conflictId, {
        action,
        note: note.trim(),
      });
      setConflict(resolved);
      setSubmitSuccess("Conflict resolved successfully.");
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Failed to resolve conflict.");
    } finally {
      setSubmitting(false);
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
        <Link to="/conflicts">Conflicts</Link> /{" "}
        <span style={{ color: "var(--color-text)" }}>{conflictId}</span>
      </nav>

      <AsyncState loading={loading} error={error} onRetry={() => window.location.reload()}>
        {conflict && (
          <div>
            {/* Header */}
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
                  <span className={`badge badge-${conflict.severity === "critical" || conflict.severity === "high" ? "danger" : "warning"}`}>
                    {conflict.severity.toUpperCase()}
                  </span>
                  <span className="badge badge-info">{conflict.type}</span>
                  <span className={`badge ${conflict.state === "resolved" ? "badge-success" : "badge-muted"}`}>
                    {conflict.state}
                  </span>
                </div>
                <h1 style={{ fontSize: "var(--font-size-2xl)" }}>Conflict Resolution</h1>
              </div>
            </div>

            {submitSuccess && (
              <div
                role="status"
                className="badge badge-success"
                style={{ padding: "var(--space-3) var(--space-4)", display: "block", marginBottom: "var(--space-4)", fontSize: "var(--font-size-sm)" }}
              >
                {submitSuccess}
              </div>
            )}

            {submitError && (
              <div
                role="alert"
                className="badge badge-danger"
                style={{ padding: "var(--space-3) var(--space-4)", display: "block", marginBottom: "var(--space-4)", fontSize: "var(--font-size-sm)" }}
              >
                ✕ {submitError}
              </div>
            )}

            {/* Claims Comparison Grid - Shows Both Conflicting Claims */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(350px, 1fr))",
                gap: "var(--space-6)",
                marginBottom: "var(--space-6)",
              }}
            >
              {/* Claim A Card */}
              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-warning)",
                  backgroundColor: "var(--color-surface)",
                }}
              >
                <h3 style={{ fontSize: "var(--font-size-base)", color: "var(--color-text-secondary)", marginBottom: "var(--space-3)" }}>
                  Claim A (Original / Prior Fact)
                </h3>
                <div
                  style={{
                    padding: "var(--space-4)",
                    backgroundColor: "var(--color-canvas)",
                    borderRadius: "var(--radius-md)",
                    fontSize: "var(--font-size-base)",
                    color: "var(--color-text)",
                    lineHeight: "var(--line-height-relaxed)",
                    minHeight: "80px",
                  }}
                >
                  {conflict.claim_a}
                </div>
                {conflict.source_a && (
                  <div style={{ marginTop: "var(--space-3)", fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                    <strong>Source:</strong> {conflict.source_a}
                  </div>
                )}
              </div>

              {/* Claim B Card */}
              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-info)",
                  backgroundColor: "var(--color-surface)",
                }}
              >
                <h3 style={{ fontSize: "var(--font-size-base)", color: "var(--color-text-secondary)", marginBottom: "var(--space-3)" }}>
                  Claim B (Contradicting / Incoming Fact)
                </h3>
                <div
                  style={{
                    padding: "var(--space-4)",
                    backgroundColor: "var(--color-canvas)",
                    borderRadius: "var(--radius-md)",
                    fontSize: "var(--font-size-base)",
                    color: "var(--color-text)",
                    lineHeight: "var(--line-height-relaxed)",
                    minHeight: "80px",
                  }}
                >
                  {conflict.claim_b}
                </div>
                {conflict.source_b && (
                  <div style={{ marginTop: "var(--space-3)", fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                    <strong>Source:</strong> {conflict.source_b}
                  </div>
                )}
              </div>
            </div>

            {/* Evidence Comparison Table */}
            {conflict.evidence_comparison && conflict.evidence_comparison.length > 0 && (
              <div className="card" style={{ marginBottom: "var(--space-6)" }}>
                <h3 style={{ marginBottom: "var(--space-3)" }}>Evidence Comparison</h3>
                <div className="table-container" style={{ margin: 0 }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Aspect</th>
                        <th>Claim A Evidence</th>
                        <th>Claim B Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {conflict.evidence_comparison.map((ev, i) => (
                        <tr key={i}>
                          <td><strong>{ev.label}</strong></td>
                          <td>{ev.claim_a_evidence}</td>
                          <td>{ev.claim_b_evidence}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Resolution Form */}
            <div className="card">
              <h3 style={{ marginBottom: "var(--space-2)" }}>Resolve Contradiction</h3>
              <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", marginBottom: "var(--space-4)" }}>
                Choose an action and provide a required explanation note for auditability.
              </p>

              <form onSubmit={handleResolve}>
                {/* Action Selection */}
                <div style={{ marginBottom: "var(--space-4)" }}>
                  <label htmlFor="resolution-action">Resolution Action</label>
                  <select
                    id="resolution-action"
                    value={action}
                    onChange={(e) => setAction(e.target.value as ConflictResolutionAction)}
                    disabled={conflict.state === "resolved"}
                    style={{ width: "100%", maxWidth: "400px" }}
                  >
                    <option value="supersede">Supersede (Claim B overrides Claim A)</option>
                    <option value="clarify">Clarify Scope (Both valid in different domains)</option>
                    <option value="conditional">Accept Conditional (Valid under environment rules)</option>
                    <option value="dismiss">Dismiss (False alarm / Not a contradiction)</option>
                  </select>
                </div>

                {/* Plain-Language Impact Box */}
                <div
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    backgroundColor: "var(--color-canvas)",
                    borderLeft: "3px solid var(--color-primary)",
                    borderRadius: "var(--radius-sm)",
                    marginBottom: "var(--space-4)",
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  <strong style={{ color: "var(--color-text)" }}>Impact: </strong>
                  {ACTION_IMPACTS[action]}
                </div>

                {/* Required Resolution Note */}
                <div style={{ marginBottom: "var(--space-5)" }}>
                  <label htmlFor="resolution-note">Resolution note</label>
                  <textarea
                    id="resolution-note"
                    rows={4}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Describe why this contradiction is resolved this way..."
                    required
                    disabled={conflict.state === "resolved"}
                    style={{ width: "100%" }}
                  />
                </div>

                {conflict.state !== "resolved" && (
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={submitting || !note.trim()}
                  >
                    {submitting ? "Resolving..." : "Submit Resolution"}
                  </button>
                )}
              </form>
            </div>
          </div>
        )}
      </AsyncState>
    </div>
  );
};
