import React, { createContext, useContext, useState, useEffect, useMemo } from "react";
import { ApiClient } from "@gpd/api-client";
import type { HealthStatus, Project } from "@gpd/contracts";
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
  isProjectLoading?: boolean;
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
  projectId: customProjectId,
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
  const [projectId, setProjectId] = useState<string>(customProjectId || "project-1");
  const [isProjectLoading, setIsProjectLoading] = useState<boolean>(!customProjectId);
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
  useEffect(() => {
    if (customProjectId) {
      setProjectId(customProjectId);
      setIsProjectLoading(false);
      return;
    }

    let isMounted = true;
    const loadProject = async () => {
      setIsProjectLoading(true);
      try {
        const res = await client.request<Project[]>({
          path: "/api/v1/projects",
        });
        if (!isMounted) return;
        if (res.data && Array.isArray(res.data) && res.data.length > 0 && res.data[0]?.id) {
          setProjectId(res.data[0].id);
        } else {
          setProjectId("project-1");
        }
      } catch {
        if (!isMounted) return;
        setProjectId("project-1");
      } finally {
        if (isMounted) {
          setIsProjectLoading(false);
        }
      }
    };

    void loadProject();

    return () => {
      isMounted = false;
    };
  }, [client, customProjectId]);


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
      isProjectLoading,
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
      isProjectLoading,
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
