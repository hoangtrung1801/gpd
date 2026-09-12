import { ApiClient } from "@gpd/api-client";
import type { Task, ContextPackage } from "@gpd/contracts";

export interface TaskFilterParams {
  project_id?: string;
  status?: string;
  type?: string;
  assignee?: string;
  query?: string;
  cursor?: string;
  limit?: number;
}

export interface TaskListResponse {
  items: Task[];
  next_cursor?: string | null;
  total?: number;
}

export interface TasksApi {
  listTasks(params?: TaskFilterParams): Promise<TaskListResponse>;
  getTask(taskRef: string): Promise<Task>;
  getTaskContext(sessionIdOrTaskId: string): Promise<ContextPackage>;
}

export function createTasksApi(client: ApiClient): TasksApi {
  return {
    async listTasks(params?: TaskFilterParams): Promise<TaskListResponse> {
      const res = await client.listTasks(params);
      if (Array.isArray(res.data)) return { items: res.data };
      return res.data || { items: [] };
    },

    async getTask(taskRef: string): Promise<Task> {
      const res = await client.getTask(taskRef);
      if (!res.data) {
        throw new Error(`Task ${taskRef} not found`);
      }
      return res.data;
    },

    async getTaskContext(sessionIdOrTaskId: string): Promise<ContextPackage> {
      const res = await client.getContext(sessionIdOrTaskId, "json");
      if (!res.data || typeof res.data === "string") {
        throw new Error("Context package not available");
      }
      return res.data as ContextPackage;
    },
  };
}
