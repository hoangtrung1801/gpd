import { ApiClient } from "@gpd/api-client";
import type { HealthStatus } from "@gpd/contracts";

export interface SettingsData {
  name: string;
  team_identifier?: string | null;
  default_branch: string;
  llm_model: string;
  embedding_model: string;
  context_token_budget: number;
  version?: number;
  retention_days?: number;
  slack_credential_configured?: boolean;
  llm_credential_configured?: boolean;
  slack_configured?: boolean;
  llm_configured?: boolean;
}

export interface SettingsPatchPayload {
  name?: string;
  team_identifier?: string | null;
  default_branch?: string;
  llm_model?: string;
  embedding_model?: string;
  context_token_budget?: number;
  version?: number;
}

export interface DetailedHealthStatus extends HealthStatus {
  fts_healthy?: boolean;
  vector_healthy?: boolean;
  database_healthy?: boolean;
}

export interface SettingsApi {
  getSettings(projectId: string): Promise<SettingsData>;
  patchSettings(projectId: string, payload: SettingsPatchPayload): Promise<SettingsData>;
  getHealth(): Promise<DetailedHealthStatus>;
}

export function createSettingsApi(client: ApiClient): SettingsApi {
  return {
    async getSettings(projectId: string): Promise<SettingsData> {
      const res = await client.getSettings(projectId);
      if (!res.data) {
        throw new Error("Settings not found");
      }
      return res.data as SettingsData;
    },

    async patchSettings(projectId: string, payload: SettingsPatchPayload): Promise<SettingsData> {
      const res = await client.patchSettings(projectId, payload);
      if (!res.data) {
        throw new Error("Failed to update settings");
      }
      return res.data as SettingsData;
    },

    async getHealth(): Promise<DetailedHealthStatus> {
      const res = await client.getHealth();
      const raw = res.data || { status: "ok", version: "0.1.0", database: "connected" };
      return {
        ...raw,
        fts_healthy: raw.search !== "unavailable" && raw.search !== "fts_error",
        vector_healthy: raw.search !== "vector_unavailable",
        database_healthy: raw.database === "connected" || raw.database === "ok" || raw.database === "pending",
      };
    },
  };
}
