import { ApiClient } from "@gpd/api-client";
import type { DeveloperSession, GitSnapshot } from "@gpd/contracts";

export interface SessionsApi {
  listSessions(projectId: string): Promise<DeveloperSession[]>;
  getSession(sessionId: string): Promise<DeveloperSession>;
  startSession(payload: {
    project_id: string;
    task_id?: string | null;
    git_branch?: string | null;
    git_snapshot?: GitSnapshot;
  }): Promise<DeveloperSession>;
  finishSession(
    sessionId: string,
    payload?: {
      changed_files?: string[];
      commit_summaries?: string[];
      summary?: string;
    }
  ): Promise<DeveloperSession>;
}

export function createSessionsApi(client: ApiClient): SessionsApi {
  return {
    async listSessions(projectId: string): Promise<DeveloperSession[]> {
      const res = await client.listSessions(projectId);
      return res.data || [];
    },

    async getSession(sessionId: string): Promise<DeveloperSession> {
      const res = await client.getSession(sessionId);
      if (!res.data) {
        throw new Error(`Session ${sessionId} not found`);
      }
      return res.data;
    },

    async startSession(payload): Promise<DeveloperSession> {
      const res = await client.startSession(payload);
      if (!res.data) {
        throw new Error("Failed to start session");
      }
      return res.data;
    },

    async finishSession(sessionId, payload): Promise<DeveloperSession> {
      const res = await client.finishSession(sessionId, payload);
      if (!res.data) {
        throw new Error("Failed to finish session");
      }
      return res.data.session;
    },
  };
}
