import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { McpRuntime, McpToolResponse } from "../runtime.js";
import { formatToolResponse } from "../runtime.js";

export const gpdProjectGetSchema = {
  projectId: z
    .string()
    .optional()
    .describe("Optional project ID (defaults to configured active project)"),
};

export function registerProjectTools(server: McpServer, runtime: McpRuntime): void {
  server.tool(
    "gpd_project_get",
    "Retrieve current project metadata and subsystem health (database, search, integrations)",
    gpdProjectGetSchema,
    async (args): Promise<McpToolResponse> => {
      const projectId = args.projectId || runtime.config?.projectId;
      if (!projectId) {
        return formatToolResponse(
          { error: "No active project configured and no projectId provided" },
          "Error: Project ID is required",
          true
        );
      }

      try {
        const projRes = await runtime.client.getProject(projectId);
        const healthRes = await runtime.client
          .getReadyHealth()
          .catch(() => runtime.client.getHealth());

        const project = projRes.data;
        const health = healthRes.data;

        const summary = [
          `Project: ${project?.name ?? "Unknown"} (${projectId})`,
          `Health: Database=${health?.database ?? "unknown"}, Search=${health?.search ?? "unknown"}`,
          `Integrations: Slack=${health?.slack ? "connected" : "not configured"}`,
        ].join("\n");

        return formatToolResponse(
          {
            project,
            health,
          },
          summary
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to fetch project: ${message}`, true);
      }
    }
  );
}
