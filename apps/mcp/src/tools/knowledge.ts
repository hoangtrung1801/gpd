import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { McpRuntime, McpToolResponse } from "../runtime.js";
import { formatToolResponse } from "../runtime.js";

export const gpdKnowledgeProposalListSchema = {
  status: z
    .string()
    .optional()
    .describe("Filter proposals by status (default: 'pending')"),
};

export function registerKnowledgeTools(server: McpServer, runtime: McpRuntime): void {
  // ONLY gpd_knowledge_proposal_list is exposed to agents.
  // Human approval via CLI / dashboard is strictly required for confirm / edit / reject.
  server.tool(
    "gpd_knowledge_proposal_list",
    "List pending knowledge proposals with source evidence for review. (Confirmation is human-only via CLI or dashboard)",
    gpdKnowledgeProposalListSchema,
    async (args): Promise<McpToolResponse> => {
      const projectId = runtime.config?.projectId;
      if (!projectId) {
        return formatToolResponse({ error: "No active project configured" }, "Error: No active project", true);
      }

      try {
        const response = await runtime.client.listKnowledgeProposals(
          projectId,
          args.status || "pending"
        );

        const proposals = response.data ?? [];
        const summary = [
          `Found ${proposals.length} proposal(s).`,
          proposals.length > 0
            ? proposals
                .map(
                  (p) =>
                    `[${p.id}] (${p.type}) ${p.title}\nStatus: ${p.status}\nConfidence: ${p.confidence}\nContent: ${p.content}`
                )
                .join("\n\n")
            : "No proposals found.",
          "\nNote: To confirm, edit, or reject proposals, ask a human to run 'gpd knowledge review' in CLI or dashboard.",
        ].join("\n");

        return formatToolResponse(
          {
            proposals,
          },
          summary
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to list proposals: ${message}`, true);
      }
    }
  );
}
