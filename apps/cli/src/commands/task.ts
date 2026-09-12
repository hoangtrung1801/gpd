import type { ApiClient } from "@gpd/api-client";
import type { GpdConfig, Task } from "@gpd/contracts";
import { writeProjectConfig } from "@gpd/config";

export async function executeTaskList(
  client: ApiClient,
  config: GpdConfig,
  filters: { status?: string; query?: string; cursor?: string } = {}
): Promise<{ items: Task[]; next_cursor?: string | null }> {
  const response = await client.listTasks({
    project_id: config.projectId,
    status: filters.status,
    query: filters.query,
    cursor: filters.cursor,
  });

  const raw = response.data;
  let items: Task[] = [];
  let next_cursor: string | null = null;

  if (Array.isArray(raw)) {
    items = raw;
  } else if (raw && typeof raw === "object") {
    if ("items" in raw && Array.isArray(raw.items)) {
      items = raw.items;
    }
    if ("next_cursor" in raw && typeof raw.next_cursor === "string") {
      next_cursor = raw.next_cursor;
    }
  }

  if (filters.query) {
    const q = filters.query.toLowerCase();
    items = items.filter(
      (t) =>
        t.title?.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q) ||
        t.public_id?.toLowerCase().includes(q)
    );
  }

  return { items, next_cursor };
}

export async function executeTaskShow(
  client: ApiClient,
  taskId: string
): Promise<Task> {
  const response = await client.getTask(taskId);
  if (!response.data) {
    throw new Error(`Task '${taskId}' not found`);
  }
  return response.data;
}

export async function executeTaskSet(
  client: ApiClient,
  config: GpdConfig,
  configPath: string,
  taskId: string
): Promise<{ previousTaskId: string | null; currentTaskId: string; task: Task }> {
  // Validate task existence
  const response = await client.getTask(taskId);
  if (!response.data) {
    throw new Error(`Task '${taskId}' not found`);
  }

  const validTask = response.data;
  const previousTaskId = config.currentTaskId;
  const updatedConfig: GpdConfig = {
    ...config,
    currentTaskId: validTask.public_id || validTask.id,
  };

  await writeProjectConfig(configPath, updatedConfig);

  return {
    previousTaskId,
    currentTaskId: updatedConfig.currentTaskId!,
    task: validTask,
  };
}
