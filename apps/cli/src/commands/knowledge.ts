import type { ApiClient } from "@gpd/api-client";
import type { GpdConfig, KnowledgeProposal } from "@gpd/contracts";

export async function executeKnowledgeList(
  client: ApiClient,
  config: GpdConfig
): Promise<KnowledgeProposal[]> {
  const response = await client.listKnowledgeProposals(config.projectId, "pending");
  return response.data ?? [];
}

export async function executeKnowledgeConfirm(
  client: ApiClient,
  proposalId: string
): Promise<{ id: string; status: string }> {
  const response = await client.confirmProposal(proposalId);
  if (!response.data) {
    throw new Error(`Failed to confirm proposal '${proposalId}'`);
  }
  return response.data;
}

export async function executeKnowledgeEdit(
  client: ApiClient,
  proposalId: string,
  content: string
): Promise<{ id: string; status: string }> {
  const response = await client.editProposal(proposalId, { content });
  if (!response.data) {
    throw new Error(`Failed to edit proposal '${proposalId}'`);
  }
  return response.data;
}

export async function executeKnowledgeReject(
  client: ApiClient,
  proposalId: string,
  reason?: string
): Promise<{ id: string; status: string }> {
  const response = await client.rejectProposal(proposalId, { reason });
  if (!response.data) {
    throw new Error(`Failed to reject proposal '${proposalId}'`);
  }
  return response.data;
}
