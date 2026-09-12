import React, { createContext, useContext, useState, useEffect, useMemo } from "react";
import { ApiClient } from "@gpd/api-client";
import type { HealthStatus } from "@gpd/contracts";
import { createTasksApi, type TasksApi } from "../features/tasks/api";
import { createKnowledgeApi, type KnowledgeApi } from "../features/knowledge/api";
import { createSourcesApi, type SourcesApi } from "../features/sources/api";
import { createSessionsApi, type SessionsApi } from "../features/sessions/api";
import { createConflictsApi, type ConflictsApi } from "../features/conflicts/api";
import { createJobsApi, type JobsApi } from "../features/jobs/api";
import { createSettingsApi, type SettingsApi } from "../features/settings/api";

export interface AppContextValue {
  client: ApiClient;
  tasksApi: TasksApi;
  knowledgeApi: KnowledgeApi;
  sourcesApi: SourcesApi;
  sessionsApi: SessionsApi;
  conflictsApi: ConflictsApi;
  jobsApi: JobsApi;
  settingsApi: SettingsApi;
  health: HealthStatus | null;
  projectId: string;
  refreshHealth: () => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

export interface AppProvidersProps {
  client?: ApiClient;
  tasksApi?: TasksApi;
  knowledgeApi?: KnowledgeApi;
  sourcesApi?: SourcesApi;
  sessionsApi?: SessionsApi;
  conflictsApi?: ConflictsApi;
  jobsApi?: JobsApi;
  settingsApi?: SettingsApi;
  initialHealth?: HealthStatus | null;
  projectId?: string;
  children: React.ReactNode;
}

export const AppProviders: React.FC<AppProvidersProps> = ({
  client: customClient,
  tasksApi: customTasksApi,
  knowledgeApi: customKnowledgeApi,
  sourcesApi: customSourcesApi,
  sessionsApi: customSessionsApi,
  conflictsApi: customConflictsApi,
  jobsApi: customJobsApi,
  settingsApi: customSettingsApi,
  initialHealth = null,
  projectId = "project-1",
  children,
}) => {
  const client = useMemo(
    () => customClient || new ApiClient({ baseUrl: window.location.origin }),
    [customClient]
  );

  const tasksApi = useMemo(() => customTasksApi || createTasksApi(client), [customTasksApi, client]);
  const knowledgeApi = useMemo(() => customKnowledgeApi || createKnowledgeApi(client), [customKnowledgeApi, client]);
  const sourcesApi = useMemo(() => customSourcesApi || createSourcesApi(client), [customSourcesApi, client]);
  const sessionsApi = useMemo(() => customSessionsApi || createSessionsApi(client), [customSessionsApi, client]);
  const conflictsApi = useMemo(() => customConflictsApi || createConflictsApi(client), [customConflictsApi, client]);
  const jobsApi = useMemo(() => customJobsApi || createJobsApi(client), [customJobsApi, client]);
  const settingsApi = useMemo(() => customSettingsApi || createSettingsApi(client), [customSettingsApi, client]);

  const [health, setHealth] = useState<HealthStatus | null>(initialHealth);

  const refreshHealth = async () => {
    try {
      const res = await client.getHealth();
      if (res.data) {
        setHealth(res.data);
      }
    } catch {
      // Degraded health fallback
      setHealth({
        status: "degraded",
        version: "0.1.0",
        database: "unreachable",
      });
    }
  };

  useEffect(() => {
    if (!initialHealth) {
      void refreshHealth();
    }
  }, [client, initialHealth]);

  const value = useMemo(
    () => ({
      client,
      tasksApi,
      knowledgeApi,
      sourcesApi,
      sessionsApi,
      conflictsApi,
      jobsApi,
      settingsApi,
      health,
      projectId,
      refreshHealth,
    }),
    [
      client,
      tasksApi,
      knowledgeApi,
      sourcesApi,
      sessionsApi,
      conflictsApi,
      jobsApi,
      settingsApi,
      health,
      projectId,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export function useApp(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProviders component");
  }
  return context;
}
