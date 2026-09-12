import React, { useEffect, useState } from "react";
import type { KnowledgeProposal } from "@gpd/contracts";
import { useApp } from "../app/providers";
import { AsyncState } from "../components/AsyncState";

export const KnowledgeReviewPage: React.FC = () => {
  const { knowledgeApi, projectId } = useApp();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [proposals, setProposals] = useState<KnowledgeProposal[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");

  const loadProposals = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await knowledgeApi.listProposals(projectId, "pending");
      setProposals(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadProposals();
  }, [projectId]);

  const handleConfirm = async (proposalId: string) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      await knowledgeApi.confirmProposal(proposalId);
      setActionSuccess("Knowledge proposal confirmed and promoted to knowledge base.");
      setProposals((prev) => prev.filter((p) => p.id !== proposalId));
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to confirm proposal.");
    }
  };

  const handleReject = async (proposalId: string) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      await knowledgeApi.rejectProposal(proposalId, { reason: "Rejected during review" });
      setActionSuccess("Knowledge proposal rejected.");
      setProposals((prev) => prev.filter((p) => p.id !== proposalId));
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to reject proposal.");
    }
  };

  const startEditing = (proposal: KnowledgeProposal) => {
    setEditingId(proposal.id);
    setEditTitle(proposal.title);
    setEditContent(proposal.content);
  };

  const handleSaveEdit = async (proposalId: string) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      await knowledgeApi.editProposal(proposalId, { title: editTitle, content: editContent });
      await knowledgeApi.confirmProposal(proposalId);
      setActionSuccess("Edited knowledge proposal confirmed.");
      setEditingId(null);
      setProposals((prev) => prev.filter((p) => p.id !== proposalId));
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to save and confirm edited proposal.");
    }
  };

  return (
    <div>
      <div style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ marginBottom: "var(--space-2)" }}>Knowledge Proposal Review</h1>
        <p style={{ color: "var(--color-text-muted)" }}>
          Human-in-the-loop review gate: review, edit, and confirm proposed architectural decisions and bug fixes before promoting to permanent project memory.
        </p>
      </div>

      {actionSuccess && (
        <div
          role="status"
          className="badge badge-success"
          style={{ padding: "var(--space-3) var(--space-4)", display: "block", marginBottom: "var(--space-4)", fontSize: "var(--font-size-sm)" }}
        >
          ✓ {actionSuccess}
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="badge badge-danger"
          style={{ padding: "var(--space-3) var(--space-4)", display: "block", marginBottom: "var(--space-4)", fontSize: "var(--font-size-sm)" }}
        >
          ✕ {actionError}
        </div>
      )}

      <AsyncState
        loading={loading}
        error={error}
        empty={proposals.length === 0}
        emptyTitle="No pending proposals"
        emptyMessage="All proposed knowledge items have been reviewed."
        onRetry={loadProposals}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
          {proposals.map((proposal) => {
            const isEditing = editingId === proposal.id;

            return (
              <article
                key={proposal.id}
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
                    marginBottom: "var(--space-4)",
                    borderBottom: "1px solid var(--color-border)",
                    paddingBottom: "var(--space-3)",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
                      <span className="badge badge-info">{proposal.type}</span>
                      <span className="badge badge-muted">
                        Confidence: {Math.round(proposal.confidence * 100)}%
                      </span>
                    </div>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        style={{ width: "100%", fontSize: "var(--font-size-lg)", fontWeight: "bold" }}
                      />
                    ) : (
                      <h2 style={{ fontSize: "var(--font-size-lg)" }}>{proposal.title}</h2>
                    )}
                  </div>
                </div>

                {/* Content */}
                <div style={{ marginBottom: "var(--space-4)" }}>
                  {isEditing ? (
                    <textarea
                      rows={6}
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      style={{ width: "100%", fontFamily: "var(--font-mono)" }}
                    />
                  ) : (
                    <pre
                      style={{
                        padding: "var(--space-4)",
                        backgroundColor: "var(--color-canvas)",
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--color-border-subtle)",
                        whiteSpace: "pre-wrap",
                        color: "var(--color-text)",
                        fontSize: "var(--font-size-sm)",
                      }}
                    >
                      {proposal.content}
                    </pre>
                  )}
                </div>

                {/* Evidence */}
                {proposal.evidence && proposal.evidence.length > 0 && (
                  <div style={{ marginBottom: "var(--space-4)", fontSize: "var(--font-size-xs)" }}>
                    <span style={{ color: "var(--color-text-muted)", fontWeight: "bold" }}>Evidence: </span>
                    <span style={{ color: "var(--color-text-secondary)" }}>
                      {proposal.evidence.map((ev, i) => JSON.stringify(ev)).join(", ")}
                    </span>
                  </div>
                )}

                {/* Action Buttons: Confirm, Edit, Reject */}
                <div
                  style={{
                    display: "flex",
                    gap: "var(--space-3)",
                    borderTop: "1px solid var(--color-border-subtle)",
                    paddingTop: "var(--space-4)",
                  }}
                >
                  {isEditing ? (
                    <>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => handleSaveEdit(proposal.id)}
                      >
                        Save & Confirm
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => setEditingId(null)}
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => handleConfirm(proposal.id)}
                        aria-label="Confirm knowledge"
                      >
                        Confirm knowledge
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => startEditing(proposal)}
                      >
                        Edit & Confirm
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => handleReject(proposal.id)}
                        aria-label="Reject"
                      >
                        Reject
                      </button>
                    </>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </AsyncState>
    </div>
  );
};
