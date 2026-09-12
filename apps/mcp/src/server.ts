#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { ApiClient } from "@gpd/api-client";
import type { GpdConfig } from "@gpd/contracts";
import {
  type McpRuntime,
  type McpToolResponse,
  resolveMcpRuntime,
  logDiagnostic,
} from "./runtime.js";
import { registerProjectTools } from "./tools/project.js";
import { registerTaskTools } from "./tools/tasks.js";
import { registerSessionActivityTools, registerSessionStartTools } from "./tools/sessions.js";
import { registerContextTools } from "./tools/context.js";
import { registerKnowledgeTools } from "./tools/knowledge.js";

type RegisteredTool = {
  handler: (args: Record<string, unknown>, extra: unknown) => Promise<McpToolResponse>;
};

export class GpdMcpServer {
  readonly mcpServer: McpServer;
  readonly runtime: McpRuntime;

  constructor(runtime: McpRuntime) {
    this.runtime = runtime;
    this.mcpServer = new McpServer({
      name: "gpd-mcp-server",
      version: "0.1.0",
    });

    // Register tools in the canonical sequence:
    // 1. gpd_project_get
    registerProjectTools(this.mcpServer, this.runtime);
    // 2. gpd_task_list, 3. gpd_task_get, 4. gpd_task_select
    registerTaskTools(this.mcpServer, this.runtime);
    // 5. gpd_session_start, 6. gpd_session_status
    registerSessionStartTools(this.mcpServer, this.runtime);
    // 7. gpd_context_get
    registerContextTools(this.mcpServer, this.runtime);
    // 8. gpd_activity_report, 9. gpd_session_finish
    registerSessionActivityTools(this.mcpServer, this.runtime);
    // 10. gpd_knowledge_proposal_list
    // (Notice: proposal confirm/edit/reject are human-only and NEVER registered)
    registerKnowledgeTools(this.mcpServer, this.runtime);
  }

  registeredToolNames(): string[] {
    const raw = (this.mcpServer as unknown as { _registeredTools: Record<string, RegisteredTool> })._registeredTools;
    return Object.keys(raw);
  }

  async callTool(name: string, args: Record<string, unknown> = {}): Promise<McpToolResponse> {
    const raw = (this.mcpServer as unknown as { _registeredTools: Record<string, RegisteredTool> })._registeredTools;
    const tool = raw[name];
    if (!tool) {
      throw new Error(`Tool '${name}' is not registered on GPD MCP server`);
    }
    return await tool.handler(args, {});
  }

  async start(): Promise<void> {
    const transport = new StdioServerTransport();
    logDiagnostic("Connecting MCP stdio transport...");
    await this.mcpServer.connect(transport);
    logDiagnostic("GPD MCP Server listening on stdio.");
  }
}

export function createGpdMcpServer(
  client?: ApiClient,
  config?: GpdConfig,
  configPath?: string
): GpdMcpServer {
  const activeClient = client || new ApiClient({ baseUrl: config?.apiUrl || "http://127.0.0.1:7337" });
  return new GpdMcpServer({ client: activeClient, config, configPath });
}

export async function createGpdMcpServerAsync(
  customClient?: ApiClient,
  customConfig?: GpdConfig,
  customConfigPath?: string
): Promise<GpdMcpServer> {
  const runtime = await resolveMcpRuntime(customClient, customConfig, customConfigPath);
  return new GpdMcpServer(runtime);
}

// CLI direct execution
if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    const server = await createGpdMcpServerAsync();
    await server.start();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    logDiagnostic(`Fatal MCP server startup error: ${message}`);
    process.exit(1);
  }
}
