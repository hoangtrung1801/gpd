import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { DeveloperSession, GitSnapshot, HealthStatus, KnowledgeProposal, Task } from "@gpd/contracts";
import type { McpRuntime, McpToolResponse } from "../runtime.js";
import { formatToolResponse } from "../runtime.js";

export const gpdSessionStartSchema = {
  taskId: z.string().optional().describe("Optional task identifier to associate with the session"),
  branch: z.string().optional().describe("Current Git branch name"),
  changedFiles: z.array(z.string()).optional().describe("List of repo-relative modified/added files"),
  recentCommits: z.array(z.string()).optional().describe("Recent git commit summaries"),
};

export const gpdSessionStatusSchema = {
  sessionId: z.string().optional().describe("Optional session ID (defaults to active session)"),
};

export const gpdActivityReportSchema = {
  sessionId: z.string().describe("Active session ID"),
  changedFiles: z.array(z.string()).optional().describe("Currently modified repo-relative files"),
  gitBranch: z.string().optional().describe("Current active Git branch"),
};

export const gpdSessionFinishSchema = {
  sessionId: z.string().optional().describe("Optional session ID (defaults to active session)"),
  changedFiles: z.array(z.string()).optional().describe("Final repo-relative modified files"),
  commitSummaries: z.array(z.string()).optional().describe("Summary of git commits completed during session"),
  summary: z.string().optional().describe("High-level summary of work and architectural decisions"),
};

export function registerSessionStartTools(server: McpServer, runtime: McpRuntime): void {
  // 1. gpd_session_start
  server.tool(
    "gpd_session_start",
    "Start a new development session with Git metadata and detect active-work conflict warnings",
    gpdSessionStartSchema,
    async (args): Promise<McpToolResponse> => {
      const projectId = runtime.config?.projectId;
      if (!projectId) {
        return formatToolResponse({ error: "No active project configured" }, "Error: No active project", true);
      }

      const taskId = args.taskId || runtime.config?.currentTaskId || null;
      const gitSnapshot: GitSnapshot | undefined =
        args.branch || args.changedFiles || args.recentCommits
          ? {
              branch: args.branch || "main",
              changed_files: args.changedFiles || [],
              recent_commits: args.recentCommits || [],
            }
          : undefined;

      try {
        const response = await runtime.client.startSession({
          project_id: projectId,
          task_id: taskId,
          git_branch: args.branch,
          git_snapshot: gitSnapshot,
        });

        const session = response.data;
        if (!session) {
          throw new Error("Empty response from backend starting session");
        }

        const overlapWarnings = session.overlap_warnings ?? [];
        let summary = `Session started: ${session.id}`;
        if (overlapWarnings.length > 0) {
          summary += `\n\nActive Work Overlap Warnings:\n${overlapWarnings.map((w) => `[${w.severity.toUpperCase()}] ${w.explanation} (${w.suggested_action})`).join("\n")}`;
        }

        return formatToolResponse(
          {
            session,
            overlap_warnings: overlapWarnings,
          },
          summary
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to start session: ${message}`, true);
      }
    }
  );

  // 2. gpd_session_status
  server.tool(
    "gpd_session_status",
    "Inspect active development session, selected task details, and subsystem health",
    gpdSessionStatusSchema,
    async (args): Promise<McpToolResponse> => {
      const projectId = runtime.config?.projectId;
      if (!projectId) {
        return formatToolResponse({ error: "No active project configured" }, "Error: No active project", true);
      }

      try {
        let session: DeveloperSession | null = null;
        if (args.sessionId) {
          const sRes = await runtime.client.getSession(args.sessionId);
          session = sRes.data;
        } else {
          const listRes = await runtime.client.listSessions(projectId);
          const sessions = listRes.data ?? [];
          session = sessions.find((s) => s.status === "active") ?? sessions[0] ?? null;
        }

        let task: Task | null = null;
        const taskId = session?.task_id || runtime.config?.currentTaskId;
        if (taskId) {
          try {
            const taskRes = await runtime.client.getTask(taskId);
            task = taskRes.data;
          } catch {
            task = null;
          }
        }

        let health: HealthStatus | null = null;
        try {
          const hRes = await runtime.client.getReadyHealth().catch(() => runtime.client.getHealth());
          health = hRes.data;
        } catch {
          health = null;
        }

        const summary = [
          `Session: ${session ? `${session.id} (${session.status})` : "none"}`,
          `Task: ${task ? `${task.public_id || task.id} - ${task.title}` : "none"}`,
          `Health: Database=${health?.database ?? "unknown"}, Search=${health?.search ?? "unknown"}`,
        ].join("\n");

        return formatToolResponse(
          {
            session,
            task,
            health,
          },
          summary
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to fetch session status: ${message}`, true);
      }
    }
  );
}

export function registerSessionActivityTools(server: McpServer, runtime: McpRuntime): void {
  // 3. gpd_activity_report
  server.tool(
    "gpd_activity_report",
    "Send periodic activity heartbeat with relative modified files and git branch to preserve session lease",
    gpdActivityReportSchema,
    async (args): Promise<McpToolResponse> => {
      try {
        const response = await runtime.client.heartbeatSession(args.sessionId, {
          changed_files: args.changedFiles,
          git_branch: args.gitBranch,
        });

        const lastHeartbeat = response.data?.last_heartbeat_at ?? new Date().toISOString();
        return formatToolResponse(
          {
            sessionId: args.sessionId,
            last_heartbeat_at: lastHeartbeat,
          },
          `Activity reported for session ${args.sessionId} at ${lastHeartbeat}`
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to report activity: ${message}`, true);
      }
    }
  );

  // 4. gpd_session_finish
  server.tool(
    "gpd_session_finish",
    "Complete development session, submit commit/file metadata, and extract candidate knowledge proposals",
    gpdSessionFinishSchema,
    async (args): Promise<McpToolResponse> => {
      const projectId = runtime.config?.projectId;
      if (!projectId) {
        return formatToolResponse({ error: "No active project configured" }, "Error: No active project", true);
      }

      let sessionId = args.sessionId;
      if (!sessionId) {
        const listRes = await runtime.client.listSessions(projectId);
        const sessions = listRes.data ?? [];
        const active = sessions.find((s) => s.status === "active");
        if (!active) {
          return formatToolResponse({ error: "No active session found to finish" }, "Error: No active session", true);
        }
        sessionId = active.id;
      }

      try {
        const response = await runtime.client.finishSession(sessionId, {
          changed_files: args.changedFiles,
          commit_summaries: args.commitSummaries,
          summary: args.summary,
        });

        const session = response.data?.session;
        const proposals = response.data?.proposals ?? [];

        const summary = [
          `Session ${sessionId} completed successfully.`,
          `Extracted ${proposals.length} knowledge proposals.`,
          proposals.length > 0
            ? `Proposals pending review:\n${proposals.map((p) => `[${p.id}] (${p.type}) ${p.title}`).join("\n")}`
            : "",
        ].filter(Boolean).join("\n");

        return formatToolResponse(
          {
            session,
            proposals,
          },
          summary
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to finish session: ${message}`, true);
      }
    }
  );
}
