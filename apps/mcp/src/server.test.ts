import { describe, expect, it, vi } from "vitest";
import { createGpdMcpServer } from "./server.js";
import { ApiClient } from "@gpd/api-client";
import type { ApiEnvelope, ContextPackage, GpdConfig } from "@gpd/contracts";

function fakeApiClient(): ApiClient {
  const fakeFetch = vi.fn(async (url: string | URL | Request) => {
    const urlStr = String(url);

    if (urlStr.includes("/context")) {
      const envelope: ApiEnvelope<ContextPackage> = {
        ok: true,
        data: {
          id: "ctx-1",
          session_id: "s1",
          task_id: "BUG-1",
          token_budget: 8000,
          token_count: 1500,
          markdown_content: "# Context\nDetails",
          sections: [],
          warnings: ["vector_search_unavailable"],
          created_at: new Date().toISOString(),
        },
        warnings: ["vector_search_unavailable"],
        error: null,
      };
      return new Response(JSON.stringify(envelope));
    }

    return new Response(JSON.stringify({ ok: true, data: {}, warnings: [], error: null }));
  });

  return new ApiClient({
    baseUrl: "http://127.0.0.1:7337",
    fetch: fakeFetch as unknown as typeof fetch,
  });
}

describe("MCP Server", () => {
  it("registers the stable GPD tool names", async () => {
    const server = createGpdMcpServer(fakeApiClient());
    expect(server.registeredToolNames()).toEqual([
      "gpd_project_get",
      "gpd_task_list",
      "gpd_task_get",
      "gpd_task_select",
      "gpd_session_start",
      "gpd_session_status",
      "gpd_context_get",
      "gpd_activity_report",
      "gpd_session_finish",
      "gpd_knowledge_proposal_list",
    ]);
  });

  it("does not expose proposal confirm to agents", async () => {
    const server = createGpdMcpServer(fakeApiClient());
    expect(server.registeredToolNames()).not.toContain("gpd_knowledge_proposal_confirm");
    expect(server.registeredToolNames()).not.toContain("gpd_knowledge_proposal_edit");
    expect(server.registeredToolNames()).not.toContain("gpd_knowledge_proposal_reject");
  });

  it("returns retrieval warnings to the agent", async () => {
    const config: GpdConfig = {
      apiUrl: "http://127.0.0.1:7337",
      projectId: "proj-1",
      repositoryId: "repo-1",
      currentTaskId: "BUG-1",
    };
    const server = createGpdMcpServer(fakeApiClient(), config);
    const result = await server.callTool("gpd_context_get", { sessionId: "s1" });

    expect(result.structuredContent.warnings).toContain("vector_search_unavailable");
    expect(result.content[0].text).toContain("vector_search_unavailable");
  });
});
