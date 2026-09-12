import type { ApiClient } from "@gpd/api-client";
import type { DeveloperSession, GpdConfig, HealthStatus, KnowledgeProposal, Task } from "@gpd/contracts";
import type { GitOps } from "../git.js";

export async function executeStart(
  client: ApiClient,
  git: GitOps,
  config: GpdConfig,
  cwd?: string
): Promise<DeveloperSession> {
  const snapshot = await git.getGitSnapshot(cwd);

  const response = await client.startSession({
    project_id: config.projectId,
    task_id: config.currentTaskId,
    git_branch: snapshot.branch,
    git_snapshot: snapshot,
  });

  if (!response.data) {
    throw new Error("Failed to start session: empty response from backend");
  }

  return response.data;
}

export async function executeStatus(
  client: ApiClient,
  config: GpdConfig
): Promise<{
  task: Task | null;
  session: DeveloperSession | null;
  health: HealthStatus | null;
}> {
  let task: Task | null = null;
  if (config.currentTaskId) {
    try {
      const taskRes = await client.getTask(config.currentTaskId);
      task = taskRes.data;
    } catch {
      task = null;
    }
  }

  let session: DeveloperSession | null = null;
  try {
    const sessionsRes = await client.listSessions(config.projectId);
    const sessions = sessionsRes.data ?? [];
    session = sessions.find((s) => s.status === "active") ?? sessions[0] ?? null;
  } catch {
    session = null;
  }

  let health: HealthStatus | null = null;
  try {
    const healthRes = await client.getReadyHealth().catch(() => client.getHealth());
    health = healthRes.data;
  } catch {
    health = null;
  }

  return {
    task,
    session,
    health,
  };
}

export async function executeFinish(
  client: ApiClient,
  git: GitOps,
  config: GpdConfig,
  options: { summary?: string } = {},
  cwd?: string
): Promise<{ session: DeveloperSession; proposals: KnowledgeProposal[] }> {
  const sessionsRes = await client.listSessions(config.projectId);
  const sessions = sessionsRes.data ?? [];
  const activeSession = sessions.find((s) => s.status === "active");
  if (!activeSession) {
    throw new Error("No active session found to finish");
  }

  const changed_files = await git.getGitChangedFiles(cwd);
  const commit_summaries = await git.getGitRecentCommits(cwd, 5);

  const response = await client.finishSession(activeSession.id, {
    changed_files,
    commit_summaries,
    summary: options.summary,
  });

  if (!response.data) {
    throw new Error("Failed to finish session: empty response from backend");
  }

  return response.data;
}
