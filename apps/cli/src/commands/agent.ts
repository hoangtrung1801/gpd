import type { ApiClient } from "@gpd/api-client";
import type { AgentAdapter, ContextPackage, GpdConfig } from "@gpd/contracts";
import { launchAgent } from "../agent-launcher.js";
import type { GitOps } from "../git.js";

export async function executeAgent(
  client: ApiClient,
  git: GitOps,
  config: GpdConfig,
  prompt: string,
  options: { command?: string[]; adapter?: AgentAdapter } = {},
  cwd?: string
): Promise<{ exitCode: number; sessionId: string }> {
  // Find or start active session
  const sessionsRes = await client.listSessions(config.projectId);
  const sessions = sessionsRes.data ?? [];
  let activeSession = sessions.find((s) => s.status === "active");

  if (!activeSession) {
    const snapshot = await git.getGitSnapshot(cwd);
    const startRes = await client.startSession({
      project_id: config.projectId,
      task_id: config.currentTaskId,
      git_branch: snapshot.branch,
      git_snapshot: snapshot,
    });
    if (!startRes.data) {
      throw new Error("Failed to start session for agent execution");
    }
    activeSession = startRes.data;
  }

  // Fetch canonical context package
  const contextRes = await client.getContext(activeSession.id, "text");
  const contextText = typeof contextRes.data === "string"
    ? contextRes.data
    : ((contextRes.data as unknown as ContextPackage)?.markdown_content ?? "");

  const command = options.command || ["claude"];
  const adapter = options.adapter || config.agentAdapter || { kind: "args", flag: "--context" };

  const exitCode = await launchAgent({
    command,
    adapter,
    contextText,
    prompt,
    heartbeat: async () => {
      await client.heartbeatSession(activeSession!.id);
    },
    heartbeatIntervalMs: 15_000,
  });

  return {
    exitCode,
    sessionId: activeSession.id,
  };
}
