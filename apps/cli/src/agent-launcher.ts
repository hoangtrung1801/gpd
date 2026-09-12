import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn as nodeSpawn, type ChildProcess } from "node:child_process";
import type { AgentAdapter } from "@gpd/contracts";

export type LaunchAgentOptions = {
  command: string[];
  adapter: AgentAdapter;
  contextText: string;
  prompt: string;
  spawn?: typeof nodeSpawn;
  heartbeat?: () => Promise<void>;
  heartbeatIntervalMs?: number;
  onContextFileCreated?: (path: string) => Promise<void> | void;
};

export async function launchAgent(options: LaunchAgentOptions): Promise<number> {
  if (!options.command || options.command.length === 0) {
    throw new Error("Command array must not be empty");
  }

  const directory = await mkdtemp(join(tmpdir(), "gpd-context-"));
  const contextPath = join(directory, "context.md");
  await writeFile(contextPath, options.contextText, { mode: 0o600, encoding: "utf8" });

  if (options.onContextFileCreated) {
    await options.onContextFileCreated(contextPath);
  }

  let cleanedUp = false;
  const cleanup = async () => {
    if (cleanedUp) {
      return;
    }
    cleanedUp = true;
    try {
      await rm(directory, { recursive: true, force: true });
    } catch {
      // Ignored
    }
  };

  const spawnImpl = options.spawn ?? nodeSpawn;
  let child: ChildProcess;

  if (options.adapter.kind === "stdin") {
    child = spawnImpl(
      options.command[0],
      [...options.command.slice(1), options.prompt],
      {
        shell: false,
        stdio: ["pipe", "inherit", "inherit"],
      }
    );
    if (child.stdin) {
      child.stdin.write(options.contextText);
      child.stdin.end();
    }
  } else {
    child = spawnImpl(
      options.command[0],
      [...options.command.slice(1), options.adapter.flag, contextPath, options.prompt],
      {
        shell: false,
        stdio: "inherit",
      }
    );
  }

  let heartbeatTimer: NodeJS.Timeout | undefined;
  if (options.heartbeat) {
    const interval = options.heartbeatIntervalMs ?? 15_000;
    heartbeatTimer = setInterval(() => {
      options.heartbeat?.().catch(() => {
        // Safe retry ignore
      });
    }, interval);
  }

  const sigintHandler = () => {
    try {
      child.kill("SIGINT");
    } catch {
      // Process might already be dead
    }
    void cleanup();
  };

  const sigtermHandler = () => {
    try {
      child.kill("SIGTERM");
    } catch {
      // Process might already be dead
    }
    void cleanup();
  };

  process.once("SIGINT", sigintHandler);
  process.once("SIGTERM", sigtermHandler);

  const { promise, resolve, reject } = Promise.withResolvers<number>();

  child.once("error", async (err) => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
    }
    process.removeListener("SIGINT", sigintHandler);
    process.removeListener("SIGTERM", sigtermHandler);
    await cleanup();
    reject(err);
  });

  child.once("close", async (code) => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
    }
    process.removeListener("SIGINT", sigintHandler);
    process.removeListener("SIGTERM", sigtermHandler);
    await cleanup();
    resolve(code ?? 0);
  });

  return promise;
}
