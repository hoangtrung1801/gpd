import { ApiClient } from "@gpd/api-client";

export type ConflictResolutionAction =
  | "supersede"
  | "clarify"
  | "conditional"
  | "dismiss";

export interface ConflictResolution {
  action: ConflictResolutionAction;
  note: string;
  resolved_by?: string;
  resolved_at?: string;
}

export interface Conflict {
  id: string;
  project_id: string;
  type: string;
  severity: "low" | "medium" | "high" | "critical";
  state: "unresolved" | "resolved" | "dismissed";
  claim_a: string;
  claim_b: string;
  source_a?: string;
  source_b?: string;
  overlap_score?: number;
  evidence_comparison?: Array<{
    label: string;
    claim_a_evidence: string;
    claim_b_evidence: string;
  }>;
  resolution?: ConflictResolution;
  created_at: string;
}

export interface ResolveConflictPayload {
  action: ConflictResolutionAction;
  note: string;
}

export interface ConflictsApi {
  listConflicts(projectId: string, state?: string): Promise<Conflict[]>;
  getConflict(conflictId: string): Promise<Conflict>;
  resolveConflict(conflictId: string, payload: ResolveConflictPayload): Promise<Conflict>;
}

export function createConflictsApi(client: ApiClient): ConflictsApi {
  return {
    async listConflicts(projectId: string, state?: string): Promise<Conflict[]> {
      const res = await client.request<Conflict[]>({
        path: `/api/v1/conflicts?project_id=${projectId}`,
        query: state ? { state } : undefined,
      });
      return res.data || [];
    },

    async getConflict(conflictId: string): Promise<Conflict> {
      const res = await client.request<Conflict>({
        path: `/api/v1/conflicts/${conflictId}`,
      });
      if (!res.data) {
        throw new Error(`Conflict ${conflictId} not found`);
      }
      return res.data;
    },

    async resolveConflict(
      conflictId: string,
      payload: ResolveConflictPayload
    ): Promise<Conflict> {
      if (!payload.note || payload.note.trim() === "") {
        throw new Error("Resolution note is required");
      }
      const res = await client.request<Conflict>({
        method: "POST",
        path: `/api/v1/conflicts/${conflictId}/resolve`,
        body: payload,
      });
      if (!res.data) {
        throw new Error("Failed to resolve conflict");
      }
      return res.data;
    },
  };
}
