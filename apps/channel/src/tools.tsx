import {
  defineChannelTool,
  Message,
  Header,
  Section,
  Markdown,
  Context,
  Actions,
  Button,
} from "@copilotkit/channels";
import type { InteractionContext } from "@copilotkit/channels";
import { z } from "zod";
import { ApiClient } from "@gpd/api-client";

export function getGpdClient(): ApiClient {
  const baseUrl = process.env.GPD_API_URL || "http://127.0.0.1:7337";
  const headers = process.env.GPD_ACCESS_TOKEN
    ? { Authorization: `Bearer ${process.env.GPD_ACCESS_TOKEN}` }
    : undefined;
  return new ApiClient({ baseUrl, headers });
}

/**
 * Read the recent messages in this conversation thread.
 */
export const readThread = defineChannelTool({
  name: "read_thread",
  description:
    "Read the recent messages in this conversation. Call this FIRST when answering questions about a thread or bug — the thread established what happened, who saw it, and what was discussed.",
  parameters: z.object({}),
  async handler(_args, { thread }) {
    const messages = await thread.getMessages();
    if (messages.length === 0) {
      return "This surface does not expose conversation history, or the thread is empty. Say that you cannot see earlier messages and ask for a brief summary.";
    }
    return messages;
  },
});

/**
 * Propose an action for human review.
 */
export const proposeAction = defineChannelTool({
  name: "propose_action",
  description:
    "Post an action proposal for human review. Returns immediately. A later click reports a decision only.",
  parameters: z.object({
    action: z.string().describe("The proposed action in one concise sentence."),
    description: z.string().describe("Details and blast radius of the proposed action."),
  }),
  async handler({ action, description }, { thread }) {
    let settled = false;
    let previousReport = Promise.resolve();

    const reportDecision = (
      approved: boolean,
      ctx: InteractionContext<boolean>,
    ) => {
      const report = async () => {
        if (settled) return;
        const decision = approved
          ? "Approved proposal. No destructive production action executed."
          : "Held by the reviewer. No action taken.";
        await ctx.thread.update(
          ctx.message.ref,
          `${decision}\n\nProposal: ${action}`,
        );
        settled = true;
      };
      previousReport = previousReport.then(report, report);
      return previousReport;
    };

    await thread.post(
      <Message accent="#C4145F">
        <Header>Action Proposal Review</Header>
        <Section>
          <Markdown>{`**${action}**\n\n${description}`}</Markdown>
        </Section>
        <Context>Clicking records a decision; external changes require review.</Context>
        <Actions>
          <Button
            value={true}
            style="primary"
            onClick={async (ctx) => {
              await reportDecision(true, ctx);
            }}
          >
            Approve
          </Button>
          <Button
            value={false}
            style="danger"
            onClick={async (ctx) => {
              await reportDecision(false, ctx);
            }}
          >
            Hold
          </Button>
        </Actions>
      </Message>,
    );

    return "Proposal posted; awaiting review in thread.";
  },
});

/**
 * Query GPD tasks.
 */
export const listTasks = defineChannelTool({
  name: "list_tasks",
  description: "List tasks and bugs registered in the GPD project.",
  parameters: z.object({
    projectId: z.string().describe("GPD project ID").default("default"),
    status: z.string().optional().describe("Filter by status: open, in_progress, completed"),
  }),
  async handler({ projectId, status }) {
    try {
      const client = getGpdClient();
      const res = await client.listTasks({ project_id: projectId, status });
      if (!res.ok || !res.data) {
        return `Failed to list tasks: ${res.error?.message || "Unknown error"}`;
      }
      return res.data;
    } catch (err) {
      return `Failed to contact GPD backend API: ${String(err)}`;
    }
  },
});

/**
 * Search GPD knowledge base and specification documents.
 */
export const searchKnowledge = defineChannelTool({
  name: "search_knowledge",
  description: "Search project documentation (PRDs, FRDs, ADRs) and confirmed knowledge entries in GPD.",
  parameters: z.object({
    projectId: z.string().describe("GPD project ID").default("default"),
    query: z.string().describe("Search query, e.g. 'expired card handling'"),
  }),
  async handler({ projectId, query }) {
    try {
      const client = getGpdClient();
      const res = await client.search(projectId, query, 5);
      if (!res.ok || !res.data) {
        return `Knowledge search failed: ${res.error?.message || "Unknown error"}`;
      }
      return res.data.hits;
    } catch (err) {
      return `Failed to search knowledge in GPD: ${String(err)}`;
    }
  },
});
