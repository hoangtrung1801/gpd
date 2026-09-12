import { z } from "zod";
import { tool } from "ai";
import { ApiClient } from "@gpd/api-client";
import { getGpdAccessToken, getGpdApiUrl } from "./env.js";
import {
  formatProposalMessage,
  formatSearchResults,
  formatTaskCard,
  formatTaskList,
  type SearchHitItem,
  type TaskCardData,
  type TaskSummaryItem,
} from "./formatters.js";

export function getGpdClient(): ApiClient {
  const baseUrl = getGpdApiUrl();
  const token = getGpdAccessToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
  return new ApiClient({ baseUrl, headers });
}

// In-memory proposal store
export interface StoredProposal {
  id: string;
  action: string;
  description: string;
  status: "pending" | "approved" | "held";
  reviewer?: string;
  createdAt: string;
  updatedAt: string;
}

const proposalStore = new Map<string, StoredProposal>();

export function createProposal(action: string, description: string): StoredProposal {
  const id = Math.random().toString(36).substring(2, 10);
  const now = new Date().toISOString();
  const proposal: StoredProposal = {
    id,
    action,
    description,
    status: "pending",
    createdAt: now,
    updatedAt: now,
  };
  proposalStore.set(id, proposal);
  return proposal;
}

export function getProposal(id: string): StoredProposal | undefined {
  return proposalStore.get(id);
}

export function updateProposalStatus(
  id: string,
  status: "approved" | "held",
  reviewer?: string,
): StoredProposal | undefined {
  const proposal = proposalStore.get(id);
  if (!proposal) return undefined;
  proposal.status = status;
  proposal.reviewer = reviewer;
  proposal.updatedAt = new Date().toISOString();
  return proposal;
}

export async function executeListTasks(
  projectId = "default",
  status?: string,
): Promise<{ ok: boolean; tasks: TaskSummaryItem[]; message: string }> {
  try {
    const client = getGpdClient();
    const res = await client.listTasks({ project_id: projectId, status });
    if (!res.ok || !res.data) {
      return {
        ok: false,
        tasks: [],
        message: `Failed to list tasks: ${res.error?.message || "Unknown error"}`,
      };
    }
    const rawTasks = Array.isArray(res.data)
      ? res.data
      : (res.data as { items?: TaskSummaryItem[] }).items || [];
    const tasks = rawTasks as TaskSummaryItem[];
    return {
      ok: true,
      tasks,
      message: formatTaskList(tasks),
    };
  } catch (err) {
    return {
      ok: false,
      tasks: [],
      message: `Failed to contact GPD backend API: ${String(err)}`,
    };
  }
}

export async function executeSearchKnowledge(
  projectId = "default",
  query: string,
): Promise<{ ok: boolean; hits: SearchHitItem[]; message: string }> {
  try {
    const client = getGpdClient();
    const res = await client.search(projectId, query, 5);
    if (!res.ok || !res.data) {
      return {
        ok: false,
        hits: [],
        message: `Knowledge search failed: ${res.error?.message || "Unknown error"}`,
      };
    }
    const hits = (res.data.hits || []) as SearchHitItem[];
    return {
      ok: true,
      hits,
      message: formatSearchResults(hits, query),
    };
  } catch (err) {
    return {
      ok: false,
      hits: [],
      message: `Failed to search knowledge in GPD: ${String(err)}`,
    };
  }
}

// AI SDK Tool definitions for Agent
export const listTasksTool = tool({
  description: "List tasks and bugs registered in the GPD project.",
  inputSchema: z.object({
    projectId: z.string().describe("GPD project ID").default("default"),
    status: z
      .string()
      .optional()
      .describe("Filter by status: open, in_progress, completed"),
  }),
  execute: async ({ projectId, status }) => {
    const res = await executeListTasks(projectId, status);
    if (!res.ok) return res.message;
    return res.tasks;
  },
});

export const searchKnowledgeTool = tool({
  description:
    "Search project documentation (PRDs, FRDs, ADRs) and confirmed knowledge entries in GPD.",
  inputSchema: z.object({
    projectId: z.string().describe("GPD project ID").default("default"),
    query: z.string().describe("Search query, e.g. 'expired card handling'"),
  }),
  execute: async ({ projectId, query }) => {
    const res = await executeSearchKnowledge(projectId, query);
    if (!res.ok) return res.message;
    return res.hits;
  },
});

export const proposeActionTool = tool({
  description:
    "Propose an engineering action for human review. Call this when suggesting a fix, deployment, or configuration change that requires human confirmation.",
  inputSchema: z.object({
    action: z.string().describe("The proposed action in one concise sentence."),
    description: z
      .string()
      .describe("Details and blast radius of the proposed action."),
  }),
  execute: async ({ action, description }) => {
    const proposal = createProposal(action, description);
    return {
      proposalId: proposal.id,
      action: proposal.action,
      description: proposal.description,
      status: proposal.status,
      formattedText: formatProposalMessage(action, description, "pending"),
    };
  },
});

export const formatTaskCardTool = tool({
  description:
    "Format a structured GPD task or bug card. Use this when presenting a detailed task or bug to the user.",
  inputSchema: z.object({
    publicId: z.string().describe("Task identifier, e.g. BUG-1 or TASK-12"),
    title: z.string().describe("Concise task title"),
    priority: z
      .enum(["high", "medium", "low"])
      .default("medium")
      .describe("Priority level"),
    status: z.string().default("open").describe("Current status"),
    area: z
      .string()
      .optional()
      .describe("Component or area, e.g. Payment or Checkout"),
    summary: z.string().describe("Summary of the task or bug"),
  }),
  execute: async (task: TaskCardData) => {
    return {
      cardHtml: formatTaskCard(task),
      task,
    };
  },
});
