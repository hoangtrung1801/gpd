import { ApiClient } from "@gpd/api-client";
import { findProjectConfig } from "@gpd/config";
import type { GpdConfig } from "@gpd/contracts";

export type McpToolResponse<T = Record<string, any>> = {
  content: Array<{ type: "text"; text: string }>;
  structuredContent: T;
  isError?: boolean;
};

export function logDiagnostic(message: string): void {
  process.stderr.write(`[GPD MCP] ${message}\n`);
}

export function formatToolResponse<T extends Record<string, unknown>>(
  data: T,
  textMessage: string,
  isError: boolean = false
): McpToolResponse<T> {
  return {
    content: [{ type: "text", text: textMessage }],
    structuredContent: data,
    ...(isError ? { isError: true } : {}),
  };
}

export type McpRuntime = {
  client: ApiClient;
  config?: GpdConfig;
  configPath?: string;
};

export async function resolveMcpRuntime(
  customClient?: ApiClient,
  customConfig?: GpdConfig,
  customConfigPath?: string
): Promise<McpRuntime> {
  let config = customConfig;
  let configPath = customConfigPath;

  if (!config) {
    try {
      const found = await findProjectConfig();
      config = found.value;
      configPath = found.path;
      logDiagnostic(`Loaded project config from ${configPath}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      logDiagnostic(`Warning: config not loaded: ${message}`);
    }
  }

  const headers: Record<string, string> = {};
  const token = process.env.GPD_ACCESS_TOKEN;
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const client =
    customClient ||
    new ApiClient({
      baseUrl: config?.apiUrl || process.env.GPD_API_URL || "http://127.0.0.1:7337",
      headers,
    });
  return {
    client,
    config,
    configPath,
  };
}
