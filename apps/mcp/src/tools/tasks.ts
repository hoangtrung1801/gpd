import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { writeProjectConfig } from "@gpd/config";
import type { McpRuntime, McpToolResponse } from "../runtime.js";
import { formatToolResponse } from "../runtime.js";

export const gpdTaskListSchema = {
  status: z.string().optional().describe("Filter tasks by status (e.g. todo, in_progress, blocked, done)"),
  type: z.string().optional().describe("Filter tasks by type (e.g. bug, feature)"),
  assignee: z.string().optional().describe("Filter tasks by assignee"),
  query: z.string().optional().describe("Search query for task title and description"),
  cursor: z.string().optional().describe("Pagination cursor"),
  limit: z.number().optional().describe("Maximum number of tasks to return"),
};

export const gpdTaskGetSchema = {
  taskRef: z.string().describe("Task public identifier (e.g. BUG-1) or internal UUID"),
};

export const gpdTaskSelectSchema = {
  taskId: z.string().describe("Task public identifier (e.g. BUG-1) or internal UUID to set as active"),
};

export function registerTaskTools(server: McpServer, runtime: McpRuntime): void {
  // 1. gpd_task_list
  server.tool(
    "gpd_task_list",
    "List and search tasks for the active project with optional status, type, and text filters",
    gpdTaskListSchema,
    async (args): Promise<McpToolResponse> => {
      const projectId = runtime.config?.projectId;
      if (!projectId) {
        return formatToolResponse({ error: "No active project configured" }, "Error: No active project", true);
      }

      try {
        const response = await runtime.client.listTasks({
          project_id: projectId,
          status: args.status,
          type: args.type,
          assignee: args.assignee,
          query: args.query,
          cursor: args.cursor,
          limit: args.limit,
        });

        const raw = response.data;
        const tasks = Array.isArray(raw)
          ? raw
          : raw?.items ?? [];
        const nextCursor = Array.isArray(raw) ? null : (raw?.next_cursor ?? null);

        const summary = tasks.length > 0
          ? tasks.map((t) => `[${t.public_id || t.id}] ${t.title} (${t.status}, ${t.priority})`).join("\n")
          : "No tasks matched the criteria.";

        return formatToolResponse(
          {
            tasks,
            next_cursor: nextCursor,
          },
          summary
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to list tasks: ${message}`, true);
      }
    }
  );

  // 2. gpd_task_get
  server.tool(
    "gpd_task_get",
    "Retrieve complete task details, bug report fields, acceptance criteria, and source provenance",
    gpdTaskGetSchema,
    async (args): Promise<McpToolResponse> => {
      try {
        const response = await runtime.client.getTask(args.taskRef);
        const task = response.data;
        if (!task) {
          return formatToolResponse(
            { error: `Task '${args.taskRef}' not found` },
            `Task '${args.taskRef}' not found`,
            true
          );
        }

        const summary = [
          `Task: ${task.public_id || task.id}`,
          `Title: ${task.title}`,
          `Status: ${task.status}`,
          `Priority: ${task.priority}`,
          task.acceptance_criteria ? `Acceptance Criteria: ${task.acceptance_criteria}` : null,
          `\nDescription:\n${task.description}`,
        ].filter(Boolean).join("\n");

        return formatToolResponse({ task }, summary);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to get task: ${message}`, true);
      }
    }
  );

  // 3. gpd_task_select
  server.tool(
    "gpd_task_select",
    "Select an active task and atomically persist it to .gpd/config.json",
    gpdTaskSelectSchema,
    async (args): Promise<McpToolResponse> => {
      if (!runtime.config || !runtime.configPath) {
        return formatToolResponse(
          { error: "No project config file found to update" },
          "Error: Missing project configuration file",
          true
        );
      }

      try {
        const response = await runtime.client.getTask(args.taskId);
        const validTask = response.data;
        if (!validTask) {
          return formatToolResponse(
            { error: `Task '${args.taskId}' does not exist` },
            `Error: Task '${args.taskId}' does not exist`,
            true
          );
        }

        const selectedId = validTask.public_id || validTask.id;
        const updatedConfig = {
          ...runtime.config,
          currentTaskId: selectedId,
        };

        await writeProjectConfig(runtime.configPath, updatedConfig);
        runtime.config.currentTaskId = selectedId;

        return formatToolResponse(
          {
            selectedTaskId: selectedId,
            task: validTask,
          },
          `Active task updated to ${selectedId}: ${validTask.title}`
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return formatToolResponse({ error: message }, `Failed to select task: ${message}`, true);
      }
    }
  );
}
