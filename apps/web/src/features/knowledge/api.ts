import { ApiClient } from "@gpd/api-client";
import type { KnowledgeItem, KnowledgeProposal } from "@gpd/contracts";

export interface KnowledgeFilterParams {
  project_id?: string;
  type?: string;
  status?: string;
  source?: string;
  component?: string;
  query?: string;
}

export interface KnowledgeListResponse {
  items: KnowledgeItem[];
  warnings?: string[];
}

export interface KnowledgeApi {
  listProposals(projectId: string, status?: string): Promise<KnowledgeProposal[]>;
  confirmProposal(proposalId: string): Promise<{ id: string; status: string }>;
  editProposal(
    proposalId: string,
    payload: { title?: string; content?: string }
  ): Promise<{ id: string; status: string }>;
  rejectProposal(
    proposalId: string,
    payload?: { reason?: string }
  ): Promise<{ id: string; status: string }>;
  listKnowledge(projectId: string, filters?: KnowledgeFilterParams): Promise<KnowledgeListResponse>;
}

export function createKnowledgeApi(client: ApiClient): KnowledgeApi {
  return {
    async listProposals(projectId: string, status?: string): Promise<KnowledgeProposal[]> {
      const res = await client.listKnowledgeProposals(projectId, status);
      return res.data || [];
    },

    async confirmProposal(proposalId: string): Promise<{ id: string; status: string }> {
      const res = await client.confirmProposal(proposalId);
      return res.data || { id: proposalId, status: "confirmed" };
    },

    async editProposal(
      proposalId: string,
      payload: { title?: string; content?: string }
    ): Promise<{ id: string; status: string }> {
      const res = await client.editProposal(proposalId, payload);
      return res.data || { id: proposalId, status: "edited" };
    },

    async rejectProposal(
      proposalId: string,
      payload?: { reason?: string }
    ): Promise<{ id: string; status: string }> {
      const res = await client.rejectProposal(proposalId, payload);
      return res.data || { id: proposalId, status: "rejected" };
    },

    async listKnowledge(
      projectId: string,
      filters?: KnowledgeFilterParams
    ): Promise<KnowledgeListResponse> {
      if (filters?.query) {
        const searchRes = await client.search(projectId, filters.query);
        const hits = searchRes.data?.hits || [];
        const items: KnowledgeItem[] = hits.map((h) => ({
          id: h.id,
          project_id: projectId,
          type: "documented_fact",
          title: h.title,
          content: h.snippet,
          status: "active",
          created_at: new Date().toISOString(),
        }));
        return {
          items,
          warnings: searchRes.warnings || searchRes.data?.warnings,
        };
      }

      const res = await client.request<KnowledgeItem[]>({
        path: `/api/v1/projects/${projectId}/knowledge`,
        query: filters ? { ...filters } : undefined,
      });

      return {
        items: res.data || [],
        warnings: res.warnings,
      };
    },
  };
}
