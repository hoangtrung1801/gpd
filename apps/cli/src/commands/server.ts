import { join } from "node:path";
import { spawn as nodeSpawn, type ChildProcess } from "node:child_process";
import type { ApiClient } from "@gpd/api-client";
import type { GitOps } from "../git.js";

export type ServerStartOptions = {
  host?: string;
  port?: number;
  detach?: boolean;
  timeoutSeconds?: number;
};

export async function executeServerStart(
  client: ApiClient,
  git: GitOps,
  options: ServerStartOptions = {},
  spawnImpl: typeof nodeSpawn = nodeSpawn,
  cwd?: string
): Promise<{ pid?: number; host: string; port: number; detached: boolean }> {
  const host = options.host || "127.0.0.1";
  const port = options.port || 7337;
  const detach = options.detach ?? false;
  const timeoutMs = (options.timeoutSeconds ?? 15) * 1000;

  let repoRoot: string;
  try {
    repoRoot = await git.getGitRoot(cwd);
  } catch {
    repoRoot = cwd || process.cwd();
  }

  const backendSrc = join(repoRoot, "backend", "src");
  const existingPythonPath = process.env.PYTHONPATH;
  const pythonPath = existingPythonPath
    ? `${backendSrc}:${existingPythonPath}`
    : backendSrc;

  const env = {
    ...process.env,
    PYTHONPATH: pythonPath,
  };

  const commandArgs = [
    "run",
    "uvicorn",
    "gpd.app:app",
    "--host",
    host,
    "--port",
    String(port),
  ];

  let child: ChildProcess;
  if (detach) {
    child = spawnImpl("uv", commandArgs, {
      cwd: repoRoot,
      env,
      detached: true,
      stdio: "ignore",
    });
    child.unref();
  } else {
    child = spawnImpl("uv", commandArgs, {
      cwd: repoRoot,
      env,
      stdio: "inherit",
    });
  }

  // Poll health until ready
  const startTime = Date.now();
  let ready = false;
  while (Date.now() - startTime < timeoutMs) {
    try {
      const health = await client.getReadyHealth().catch(() => client.getHealth());
      if (health.ok) {
        ready = true;
        break;
      }
    } catch {
      // Backend not yet ready
    }

    const { promise: delayPromise, resolve: resolveDelay } = Promise.withResolvers<void>();
    setTimeout(resolveDelay, 200);
    await delayPromise;
  }

  if (!ready && detach) {
    throw new Error(`Server failed to become ready within ${options.timeoutSeconds ?? 15}s`);
  }

  return {
    pid: child.pid,
    host,
    port,
    detached: detach,
  };
}
