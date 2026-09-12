import { describe, expect, it, vi } from "vitest";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createGpdMcpServer } from "../server.js";
import { logDiagnostic } from "../runtime.js";
import { ApiClient } from "@gpd/api-client";
import { loadProjectConfig } from "@gpd/config";
import type {
  ApiEnvelope,
  ContextPackage,
  DeveloperSession,
  GpdConfig,
  HealthStatus,
  KnowledgeProposal,
  Project,
  Task,
} from "@gpd/contracts";

function createMockClient(): ApiClient {
  const fakeFetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const urlStr = String(url);
    const method = init?.method || "GET";

    if (urlStr.includes("/health/ready") || urlStr.includes("/health")) {
      const envelope: ApiEnvelope<HealthStatus> = {
        ok: true,
        data: {
          status: "ok",
          version: "0.1.0",
          database: "ok",
          search: "ok",
          git: "ok",
          slack: true,
          llm: true,
        },
        warnings: [],
        error: null,
      };
      return new Response(JSON.stringify(envelope));
    }

    if (urlStr.includes("/projects/proj-1")) {
      const envelope: ApiEnvelope<Project> = {
        ok: true,
        data: {
          id: "proj-1",
          name: "PaymentService",
          team_identifier: "core",
          created_at: new Date().toISOString(),
        },
        warnings: [],
        error: null,
      };
      return new Response(JSON.stringify(envelope));
    }

    if (urlStr.includes("/api/v1/tasks/BUG-1") || urlStr.includes("/api/v1/tasks/task-1")) {
      const envelope: ApiEnvelope<Task> = {
        ok: true,
        data: {
          id: "task-1",
          project_id: "proj-1",
          public_id: "BUG-1",
          title: "Stripe webhook dropped",
          description: "Signatures with clock skew are dropped",
          status: "in_progress",
          priority: "high",
          acceptance_criteria: "Verify webhook signatures tolerate 300s clock skew",
          created_at: new Date().toISOString(),
        },
        warnings: [],
        error: null,
      };
      return new Response(JSON.stringify(envelope));
    }

    if (urlStr.includes("/api/v1/tasks")) {
      const envelope: ApiEnvelope<{ items: Task[]; next_cursor?: string | null }> = {
        ok: true,
        data: {
          items: [
            {
              id: "task-1",
              project_id: "proj-1",
              public_id: "BUG-1",
              title: "Stripe webhook dropped",
              description: "Desc",
              status: "in_progress",
              priority: "high",
              created_at: new Date().toISOString(),
            },
          ],
          next_cursor: null,
        },
        warnings: [],
        error: null,
      };
      return new Response(JSON.stringify(envelope));
    }

    if (method === "POST" && urlStr.includes("/sessions/session-1/heartbeat")) {
      const envelope: ApiEnvelope<{ last_heartbeat_at: string }> = {
        ok: true,
        data: { last_heartbeat_at: "2026-09-12T12:00:00Z" },
        warnings: [],
        error: null,
      };
      return new Response(JSON.stringify(envelope));
    }

    if (method === "POST" && urlStr.includes("/sessions/session-1/finish")) {
      const envelope: ApiEnvelope<{ session: DeveloperSession; proposals: KnowledgeProposal[] }> = {
        ok: true,
        data: {
          session: {
            id: "session-1",
            project_id: "proj-1",
            task_id: "BUG-1",
            status: "finished",
            created_at: new Date().toISOString(),
          },
          proposals: [
            {
              id: "prop-1",
              project_id: "proj-1",
              type: "decision",
              title: "Tolerate 300s clock skew on Stripe webhooks",
              content: "Verified standard Stripe timestamp drift window is 300s",
              confidence: 0.95,
              evidence: [{ message_id: "m1" }],
              status: "pending",
              created_at: new Date().toISOString(),
            },
          ],
        },
        warnings: [],
        error: null,
      };
      return new Response(JSON.stringify(envelope));
    }

    if (method === "POST" && urlStr.includes("/sessions")) {
      const envelope: ApiEnvelope<DeveloperSession> = {
        ok: true,
        data: {
          id: "session-1",
          project_id: "proj-1",
          task_id: "BUG-1",
          status: "active",
          git_branch: "main",
          created_at: new Date().toISOString(),
          overlap_warnings: [
            {
              severity: "high",
              explanation: "Another developer modified checkout.ts recently",
              suggested_action: "Coordinate with team",
              evidence: [{ type: "file", id: "checkout.ts", score: 1.0 }],
            },
          ],
        },
        warnings: [],
        error: null,
      };
      return new Response(JSON.stringify(envelope));
    }

    if (urlStr.includes("/sessions/session-1") || urlStr.includes("/sessions")) {
      const session: DeveloperSession = {
        id: "session-1",
        project_id: "proj-1",
        task_id: "BUG-1",
        status: "active",
        git_branch: "main",
        created_at: new Date().toISOString(),
      };
      return new Response(JSON.stringify({ ok: true, data: [session], warnings: [], error: null }));
    }

    if (urlStr.includes("/context")) {
      const envelope: ApiEnvelope<ContextPackage> = {
        ok: true,
        data: {
          id: "ctx-1",
          session_id: "session-1",
          task_id: "BUG-1",
          token_budget: 8000,
          token_count: 2100,
          markdown_content: "# Project Context\nWebhook Clock Skew",
          sections: [],
          warnings: ["vector_search_unavailable"],
          created_at: new Date().toISOString(),
        },
        warnings: ["vector_search_unavailable"],
        error: null,
      };
      return new Response(JSON.stringify(envelope));
    }

    if (urlStr.includes("/knowledge/proposals")) {
      const envelope: ApiEnvelope<KnowledgeProposal[]> = {
        ok: true,
        data: [
          {
            id: "prop-1",
            project_id: "proj-1",
            type: "decision",
            title: "Tolerate 300s clock skew",
            content: "PRD Section 4 says 300s window",
            confidence: 0.9,
            evidence: [{ doc: "prd" }],
            status: "pending",
            created_at: new Date().toISOString(),
          },
        ],
        warnings: [],
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

describe("MCP Tools Suite", () => {
  it("gpd_project_get returns project details and health", async () => {
    const config: GpdConfig = {
      apiUrl: "http://127.0.0.1:7337",
      projectId: "proj-1",
      repositoryId: "repo-1",
      currentTaskId: "BUG-1",
    };
    const server = createGpdMcpServer(createMockClient(), config);
    const result = await server.callTool("gpd_project_get", {});

    expect(result.structuredContent.project.name).toBe("PaymentService");
    expect(result.structuredContent.health.database).toBe("ok");
    expect(result.content[0].text).toContain("PaymentService");
  });

  it("gpd_task_list and gpd_task_get return structured task data", async () => {
    const config: GpdConfig = {
      apiUrl: "http://127.0.0.1:7337",
      projectId: "proj-1",
      repositoryId: "repo-1",
      currentTaskId: "BUG-1",
    };
    const server = createGpdMcpServer(createMockClient(), config);

    const listRes = await server.callTool("gpd_task_list", { status: "in_progress" });
    expect(listRes.structuredContent.tasks).toHaveLength(1);
    expect(listRes.structuredContent.tasks[0].public_id).toBe("BUG-1");

    const getRes = await server.callTool("gpd_task_get", { taskRef: "BUG-1" });
    expect(getRes.structuredContent.task.title).toBe("Stripe webhook dropped");
    expect(getRes.structuredContent.task.acceptance_criteria).toContain("300s clock skew");
  });

  it("gpd_task_select atomically updates .gpd/config.json", async () => {
    const root = await mkdtemp(join(tmpdir(), "gpd-mcp-select-"));
    try {
      const configPath = join(root, ".gpd", "config.json");
      const initialConfig: GpdConfig = {
        apiUrl: "http://127.0.0.1:7337",
        projectId: "proj-1",
        repositoryId: "repo-1",
        currentTaskId: null,
      };
      await writeFile(
        join(root, "dummy"),
        ""
      ); // ensure dir
      const { writeProjectConfig } = await import("@gpd/config");
      await writeProjectConfig(configPath, initialConfig);

      const server = createGpdMcpServer(createMockClient(), initialConfig, configPath);
      const result = await server.callTool("gpd_task_select", { taskId: "BUG-1" });

      expect(result.structuredContent.selectedTaskId).toBe("BUG-1");
      const reloaded = await loadProjectConfig(configPath);
      expect(reloaded.currentTaskId).toBe("BUG-1");
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });

  it("gpd_session_start surfaces overlap warnings", async () => {
    const config: GpdConfig = {
      apiUrl: "http://127.0.0.1:7337",
      projectId: "proj-1",
      repositoryId: "repo-1",
      currentTaskId: "BUG-1",
    };
    const server = createGpdMcpServer(createMockClient(), config);
    const result = await server.callTool("gpd_session_start", {
      branch: "main",
      changedFiles: ["checkout.ts"],
    });

    expect(result.structuredContent.session.id).toBe("session-1");
    expect(result.structuredContent.overlap_warnings).toHaveLength(1);
    expect(result.content[0].text).toContain("Active Work Overlap Warnings");
  });

  it("gpd_activity_report sends heartbeats without errors", async () => {
    const config: GpdConfig = {
      apiUrl: "http://127.0.0.1:7337",
      projectId: "proj-1",
      repositoryId: "repo-1",
      currentTaskId: "BUG-1",
    };
    const server = createGpdMcpServer(createMockClient(), config);
    const result = await server.callTool("gpd_activity_report", {
      sessionId: "session-1",
      changedFiles: ["src/webhook.ts"],
    });

    expect(result.structuredContent.last_heartbeat_at).toBe("2026-09-12T12:00:00Z");
    expect(result.content[0].text).toContain("session-1");
  });

  it("gpd_session_finish extracts knowledge proposals", async () => {
    const config: GpdConfig = {
      apiUrl: "http://127.0.0.1:7337",
      projectId: "proj-1",
      repositoryId: "repo-1",
      currentTaskId: "BUG-1",
    };
    const server = createGpdMcpServer(createMockClient(), config);
    const result = await server.callTool("gpd_session_finish", {
      sessionId: "session-1",
      summary: "Fixed webhook clock drift tolerance",
    });

    expect(result.structuredContent.session.status).toBe("finished");
    expect(result.structuredContent.proposals).toHaveLength(1);
    expect(result.structuredContent.proposals[0].title).toContain("clock skew");
  });

  it("gpd_knowledge_proposal_list returns pending proposals with evidence", async () => {
    const config: GpdConfig = {
      apiUrl: "http://127.0.0.1:7337",
      projectId: "proj-1",
      repositoryId: "repo-1",
      currentTaskId: "BUG-1",
    };
    const server = createGpdMcpServer(createMockClient(), config);
    const result = await server.callTool("gpd_knowledge_proposal_list", {});

    expect(result.structuredContent.proposals).toHaveLength(1);
    expect(result.content[0].text).toContain("human to run 'gpd knowledge review'");
  });

  it("diagnostic logs write to stderr and never stdout", () => {
    const stderrSpy = vi.spyOn(process.stderr, "write").mockImplementation(() => true);
    const stdoutSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true);

    try {
      logDiagnostic("Testing diagnostics stream separation");
      expect(stderrSpy).toHaveBeenCalled();
      expect(stdoutSpy).not.toHaveBeenCalled();
    } finally {
      stderrSpy.mockRestore();
      stdoutSpy.mockRestore();
    }
  });
});
