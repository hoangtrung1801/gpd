import type { ApiClient } from "@gpd/api-client";
import type { ContextPackage, GpdConfig } from "@gpd/contracts";

export async function executeContext(
  client: ApiClient,
  config: GpdConfig,
  options: { format?: "text" | "json"; sessionId?: string } = {}
): Promise<{
  context: ContextPackage | string;
  format: "text" | "json";
  text: string;
  warnings: string[];
}> {
  const format = options.format || "text";

  let sessionId = options.sessionId;
  if (!sessionId) {
    const sessionsRes = await client.listSessions(config.projectId);
    const sessions = sessionsRes.data ?? [];
    const active = sessions.find((s) => s.status === "active") ?? sessions[0];
    if (!active) {
      // Start a temporary session if none exists
      const started = await client.startSession({
        project_id: config.projectId,
        task_id: config.currentTaskId,
      });
      if (!started.data) {
        throw new Error("No active session found and could not start a session");
      }
      sessionId = started.data.id;
    } else {
      sessionId = active.id;
    }
  }

  const response = await client.getContext(sessionId, format);
  if (!response.data) {
    throw new Error("Failed to retrieve context package: empty response");
  }

  const contextData = response.data;
  const text = typeof contextData === "string"
    ? contextData
    : (contextData as ContextPackage).markdown_content || "";

  const packageWarnings = typeof contextData === "object" && contextData !== null && "warnings" in contextData
    ? (contextData as ContextPackage).warnings || []
    : [];

  const combinedWarnings = Array.from(new Set([...response.warnings, ...packageWarnings]));

  return {
    context: contextData,
    format,
    text,
    warnings: combinedWarnings,
  };
}
