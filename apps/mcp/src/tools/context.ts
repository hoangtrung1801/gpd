import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { ContextPackage } from "@gpd/contracts";
import type { McpRuntime, McpToolResponse } from "../runtime.js";
import { formatToolResponse } from "../runtime.js";

export const gpdContextGetSchema = {
  sessionId: z.string().optional().describe("Session identifier (defaults to active session)"),
  format: z.enum(["json", "text"]).optional().describe("Format of package (default: json)"),
};

export function registerContextTools(server: McpServer, runtime: McpRuntime): void {
  server.tool(
    "gpd_context_get",
    "Retrieve budgeted, canonical context package for active session, including task requirements and project knowledge",
    gpdContextGetSchema,
    async (args): Promise<McpToolResponse> => {
      const projectId = runtime.config?.projectId;
      let sessionId = args.sessionId;

      if (!sessionId && projectId) {
        try {
          const listRes = await runtime.client.listSessions(projectId);
          const sessions = listRes.data ?? [];
          const active = sessions.find((s) => s.status === "active") ?? sessions[0];
          sessionId = active?.id;
        } catch {
          // Ignore
        }
      }

      if (!sessionId) {
        return formatToolResponse({ error: "No active session ID available" }, "Error: Session ID is required", true);
      }

      try {
        const response = await runtime.client.getContext(sessionId, "json");
        const contextData = response.data;

        if (!contextData) {
          return formatToolResponse(
            { error: "Context package not found" },
            "Error: Context package not found",
            true
          );
        }

        const pkg = contextData as ContextPackage;
        const warnings = [
          ...response.warnings,
          ...(pkg.warnings || []),
        ];
        const uniqueWarnings = Array.from(new Set(warnings));

        const summary = [
          `# GPD Project Context (Session ${sessionId})`,
          uniqueWarnings.length > 0 ? `\nWarnings:\n${uniqueWarnings.map((w) => `- ${w}`).join("\n")}` : "",
          `\n${pkg.markdown_content || ""}`,
        ].filter(Boolean).join("\n");

        return formatToolResponse(
          {
            context: pkg,
            warnings: uniqueWarnings,
          },
          summary
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to fetch context: ${message}`, true);
      }
    }
  );
}
