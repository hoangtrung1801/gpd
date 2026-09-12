import type { ApiClient } from "@gpd/api-client";
import type { GpdConfig } from "@gpd/contracts";
import type { GitOps } from "../git.js";

export type DoctorCheckResult = {
  name: string;
  status: "ok" | "warn" | "error";
  message: string;
};

export type DoctorReport = {
  checks: DoctorCheckResult[];
  overall: "ok" | "warn" | "error";
};

export async function executeDoctor(
  client: ApiClient,
  git: GitOps,
  config?: GpdConfig,
  configPath?: string,
  cwd?: string
): Promise<DoctorReport> {
  const checks: DoctorCheckResult[] = [];

  // 1. Config check
  if (config && configPath) {
    checks.push({
      name: "config",
      status: "ok",
      message: `Config found and valid at ${configPath} (project: ${config.projectId})`,
    });
  } else {
    checks.push({
      name: "config",
      status: "error",
      message: "No valid .gpd/config.json found",
    });
  }

  // 2. Git availability
  let gitRoot: string | null = null;
  try {
    gitRoot = await git.getGitRoot(cwd);
    checks.push({
      name: "git",
      status: "ok",
      message: `Git repository active at ${gitRoot}`,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    checks.push({
      name: "git",
      status: "error",
      message: `Git check failed: ${message}`,
    });
  }

  // 3. Backend reachability & 4. Database / search health
  try {
    const healthRes = await client.getReadyHealth().catch(() => client.getHealth());
    if (healthRes.ok) {
      checks.push({
        name: "backend",
        status: "ok",
        message: `Backend reachable at ${client.baseUrl} (version: ${healthRes.data?.version ?? "unknown"})`,
      });

      const dbStatus = healthRes.data?.database;
      if (dbStatus === "ok") {
        checks.push({
          name: "database",
          status: "ok",
          message: "Database connection healthy",
        });
      } else {
        checks.push({
          name: "database",
          status: "warn",
          message: `Database state: ${dbStatus ?? "unknown"}`,
        });
      }

      const searchStatus = healthRes.data?.search ?? "ok";
      checks.push({
        name: "search",
        status: searchStatus === "ok" ? "ok" : "warn",
        message: `Search status: ${searchStatus}`,
      });
    } else {
      checks.push({
        name: "backend",
        status: "error",
        message: "Backend responded with error",
      });
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    checks.push({
      name: "backend",
      status: "error",
      message: `Cannot reach backend at ${client.baseUrl}: ${message}`,
    });
    checks.push({
      name: "database",
      status: "warn",
      message: "Database status could not be verified",
    });
    checks.push({
      name: "search",
      status: "warn",
      message: "Search status could not be verified",
    });
  }

  // 5. Registered root
  if (config && gitRoot) {
    try {
      const projRes = await client.getProject(config.projectId);
      if (projRes.ok) {
        checks.push({
          name: "registered_root",
          status: "ok",
          message: `Project registered as '${projRes.data?.name}'`,
        });
      }
    } catch {
      checks.push({
        name: "registered_root",
        status: "warn",
        message: `Could not verify registered root for project ${config.projectId}`,
      });
    }
  }

  // 6. Slack configuration
  try {
    const slackRes = await client.getSlackStatus();
    if (slackRes.ok && slackRes.data?.configured) {
      checks.push({
        name: "slack",
        status: "ok",
        message: "Slack integration configured",
      });
    } else {
      checks.push({
        name: "slack",
        status: "warn",
        message: "Slack integration not configured",
      });
    }
  } catch {
    checks.push({
      name: "slack",
      status: "warn",
      message: "Could not check Slack integration status",
    });
  }

  // 7. LLM configuration
  if (config) {
    try {
      const settingsRes = await client.getSettings(config.projectId);
      if (settingsRes.ok && settingsRes.data?.llm_configured !== false) {
        checks.push({
          name: "llm",
          status: "ok",
          message: `LLM configured (model: ${settingsRes.data?.llm_model ?? "default"})`,
        });
      } else {
        checks.push({
          name: "llm",
          status: "warn",
          message: "LLM not configured",
        });
      }
    } catch {
      checks.push({
        name: "llm",
        status: "warn",
        message: "Could not check LLM configuration",
      });
    }
  }

  const hasError = checks.some((c) => c.status === "error");
  const hasWarn = checks.some((c) => c.status === "warn");
  const overall = hasError ? "error" : hasWarn ? "warn" : "ok";

  return {
    checks,
    overall,
  };
}
