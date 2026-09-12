import { describe, expect, it, vi } from "vitest";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runCli, type CliRuntime } from "../main.js";
import { ApiClient } from "@gpd/api-client";
import type {
  ApiEnvelope,
  ContextPackage,
  DeveloperSession,
  GpdConfig,
  HealthStatus,
  ProjectSettings,
  Task,
} from "@gpd/contracts";
import type { GitOps } from "../git.js";

function createFakeRuntime(overrides: Partial<CliRuntime> = {}): CliRuntime {
  const fakeConfig: GpdConfig = {
    apiUrl: "http://127.0.0.1:7337",
    projectId: "project-1",
    repositoryId: "repo-1",
    currentTaskId: "BUG-1",
  };

  const fakeGit: GitOps = {
    getGitRoot: vi.fn(async () => "/fake/repo"),
    getGitBranch: vi.fn(async () => "main"),
    getGitRemoteUrl: vi.fn(async () => "https://github.com/org/repo.git"),
    getGitDefaultBranch: vi.fn(async () => "main"),
    getGitChangedFiles: vi.fn(async () => ["src/checkout.ts"]),
    getGitRecentCommits: vi.fn(async () => ["abc1234 feat: checkout"]),
    getGitSnapshot: vi.fn(async () => ({
      branch: "main",
      changed_files: ["src/checkout.ts"],
      recent_commits: ["abc1234 feat: checkout"],
      remote_url: "https://github.com/org/repo.git",
    })),
  };

  const fakeFetch = vi.fn(async (url: string | URL | Request) => {
    const urlStr = String(url);

    if (urlStr.includes("/health/ready") || urlStr.includes("/health")) {
      const health: ApiEnvelope<HealthStatus> = {
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
      return new Response(JSON.stringify(health));
    }

    if (urlStr.includes("/context")) {
      const ctx: ApiEnvelope<ContextPackage> = {
        ok: true,
        data: {
          id: "ctx-1",
          session_id: "session-1",
          task_id: "BUG-1",
          token_budget: 8000,
          token_count: 1200,
          markdown_content: "# Context Package\n\nTask: BUG-1\nFix the checkout timeout",
          sections: [],
          warnings: ["vector_search_unavailable"],
          created_at: new Date().toISOString(),
        },
        warnings: ["vector_search_unavailable"],
        error: null,
      };
      return new Response(JSON.stringify(ctx));
    }

    if (urlStr.includes("/api/v1/tasks/BUG-1")) {
      const task: ApiEnvelope<Task> = {
        ok: true,
        data: {
          id: "task-uuid-1",
          project_id: "project-1",
          public_id: "BUG-1",
          title: "Payment gateway timeout",
          description: "Stripe calls time out under load",
          status: "in_progress",
          priority: "high",
          created_at: new Date().toISOString(),
        },
        warnings: [],
        error: null,
      };
      return new Response(JSON.stringify(task));
    }

    if (urlStr.includes("/api/v1/sessions?project_id=project-1") || urlStr.includes("/api/v1/sessions")) {
      const session: DeveloperSession = {
        id: "session-1",
        project_id: "project-1",
        task_id: "BUG-1",
        status: "active",
        git_branch: "main",
        created_at: new Date().toISOString(),
        overlap_warnings: [
          {
            severity: "low",
            explanation: "Overlapping task BUG-2 in progress",
            suggested_action: "Coordinate with team",
            evidence: [{ type: "task", id: "BUG-2", score: 0.4 }],
          },
        ],
      };
      return new Response(JSON.stringify({ ok: true, data: [session], warnings: [], error: null }));
    }

    if (urlStr.includes("/settings")) {
      const settings: ApiEnvelope<ProjectSettings> = {
        ok: true,
        data: {
          name: "Repo",
          default_branch: "main",
          llm_model: "gpt-4o",
          embedding_model: "text-embedding-3-small",
          context_token_budget: 8000,
          slack_configured: true,
          llm_configured: true,
        },
        warnings: [],
        error: null,
      };
      return new Response(JSON.stringify(settings));
    }

    if (urlStr.includes("/integrations/slack/status")) {
      return new Response(JSON.stringify({ ok: true, data: { configured: true, installed: true }, warnings: [], error: null }));
    }

    if (urlStr.includes("/projects/project-1")) {
      return new Response(
        JSON.stringify({
          ok: true,
          data: { id: "project-1", name: "Repo", created_at: new Date().toISOString() },
          warnings: [],
          error: null,
        })
      );
    }

    return new Response(JSON.stringify({ ok: true, data: {}, warnings: [], error: null }));
  });

  const client = new ApiClient({
    baseUrl: "http://127.0.0.1:7337",
    fetch: fakeFetch as unknown as typeof fetch,
  });

  return {
    client,
    git: fakeGit,
    config: { path: "/fake/repo/.gpd/config.json", value: fakeConfig },
    ...overrides,
  };
}

describe("CLI Commands", () => {
  describe("Stable JSON Envelope", () => {
    it.each([["status"], ["task", "show", "BUG-1"], ["context"], ["doctor"]])(
      "prints the stable JSON envelope for %s --json",
      async (...cmdArgs) => {
        const runtime = createFakeRuntime();
        const result = await runCli([...cmdArgs, "--json"], runtime);

        expect(result.exitCode).toBe(0);
        const parsed = JSON.parse(result.stdout);
        expect(parsed).toEqual({
          ok: true,
          data: expect.anything(),
          warnings: expect.any(Array),
          error: null,
        });
      }
    );
  });

  describe("bare defaults", () => {
    it("bare gpd context prints markdown text by default", async () => {
      const runtime = createFakeRuntime();
      const result = await runCli(["context"], runtime);

      expect(result.exitCode).toBe(0);
      expect(result.stdout).toContain("# Context Package");
      expect(result.stdout).toContain("Fix the checkout timeout");
    });

    it("bare gpd finish works without requiring --summary", async () => {
      let finishPayload: Record<string, unknown> = {};
      const customFetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.includes("/finish")) {
          finishPayload = JSON.parse(init?.body as string || "{}");
          return new Response(
            JSON.stringify({
              ok: true,
              data: {
                session: { id: "session-1", status: "finished" },
                proposals: [],
              },
              warnings: [],
              error: null,
            })
          );
        }
        if (urlStr.includes("/sessions")) {
          return new Response(
            JSON.stringify({
              ok: true,
              data: [{ id: "session-1", status: "active" }],
              warnings: [],
              error: null,
            })
          );
        }
        return new Response(JSON.stringify({ ok: true, data: {} }));
      });

      const runtime = createFakeRuntime({
        client: new ApiClient({
          baseUrl: "http://127.0.0.1:7337",
          fetch: customFetch as unknown as typeof fetch,
        }),
      });

      const result = await runCli(["finish", "--json"], runtime);
      expect(result.exitCode).toBe(0);
      expect(finishPayload.summary).toBeUndefined();
      const parsed = JSON.parse(result.stdout);
      expect(parsed.ok).toBe(true);
      expect(parsed.data.session.status).toBe("finished");
    });
  });

  describe("warnings passthrough", () => {
    it("preserves retrieval warnings in the envelope for context", async () => {
      const runtime = createFakeRuntime();
      const result = await runCli(["context", "--json"], runtime);

      expect(result.exitCode).toBe(0);
      const parsed = JSON.parse(result.stdout);
      expect(parsed.warnings).toContain("vector_search_unavailable");
    });
  });

  describe("gpd add path safety and 2MiB limit", () => {
    it("rejects paths outside the git repository root with validation error", async () => {
      const runtime = createFakeRuntime();
      const result = await runCli(["add", "/etc/passwd", "--json"], runtime);

      expect(result.exitCode).toBe(2);
      const parsed = JSON.parse(result.stdout);
      expect(parsed.ok).toBe(false);
      expect(parsed.error.code).toBe("VALIDATION_ERROR");
      expect(parsed.error.message).toContain("outside the repository root");
    });

    it("rejects files exceeding 2 MiB with validation error", async () => {
      const root = await mkdtemp(join(tmpdir(), "gpd-add-test-"));
      try {
        const bigFile = join(root, "bigfile.txt");
        const bigBuffer = Buffer.alloc(2 * 1024 * 1024 + 1, "a");
        await writeFile(bigFile, bigBuffer);

        const runtime = createFakeRuntime({
          cwd: root,
          git: {
            getGitRoot: vi.fn(async () => root),
            getGitBranch: vi.fn(async () => "main"),
            getGitRemoteUrl: vi.fn(async () => null),
            getGitDefaultBranch: vi.fn(async () => "main"),
            getGitChangedFiles: vi.fn(async () => []),
            getGitRecentCommits: vi.fn(async () => []),
            getGitSnapshot: vi.fn(async () => ({ branch: "main", changed_files: [], recent_commits: [] })),
          },
        });

        const result = await runCli(["add", "bigfile.txt", "--json"], runtime);
        expect(result.exitCode).toBe(2);
        const parsed = JSON.parse(result.stdout);
        expect(parsed.ok).toBe(false);
        expect(parsed.error.code).toBe("VALIDATION_ERROR");
        expect(parsed.error.message).toContain("exceeds the 2 MiB limit");
      } finally {
        await rm(root, { recursive: true, force: true });
      }
    });
  });
});
