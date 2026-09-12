import { access, mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { randomUUID } from "node:crypto";
import type { AgentAdapter, GpdConfig } from "@gpd/contracts";

export class ConfigNotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigNotFoundError";
  }
}

export class ConfigValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigValidationError";
  }
}

async function pathExists(candidatePath: string): Promise<boolean> {
  try {
    await access(candidatePath);
    return true;
  } catch {
    return false;
  }
}

function parseAgentAdapter(raw: unknown): AgentAdapter | undefined {
  if (!raw || typeof raw !== "object") {
    return undefined;
  }
  const candidate = raw as Record<string, unknown>;
  if (candidate.kind === "stdin") {
    return { kind: "stdin" };
  }
  if (candidate.kind === "args" && typeof candidate.flag === "string") {
    return { kind: "args", flag: candidate.flag };
  }
  return undefined;
}

export async function loadProjectConfig(configPath: string): Promise<GpdConfig> {
  const resolved = resolve(configPath);
  let content: string;
  try {
    content = await readFile(resolved, "utf8");
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    throw new ConfigNotFoundError(`Cannot read config file at ${resolved}: ${message}`);
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    throw new ConfigValidationError(`Invalid JSON in ${resolved}: ${message}`);
  }

  if (!parsed || typeof parsed !== "object") {
    throw new ConfigValidationError(`Config in ${resolved} is not a JSON object`);
  }

  const obj = parsed as Record<string, unknown>;
  if (typeof obj.apiUrl !== "string" || !obj.apiUrl) {
    throw new ConfigValidationError(`Missing or invalid 'apiUrl' in ${resolved}`);
  }
  if (typeof obj.projectId !== "string" || !obj.projectId) {
    throw new ConfigValidationError(`Missing or invalid 'projectId' in ${resolved}`);
  }
  if (typeof obj.repositoryId !== "string" || !obj.repositoryId) {
    throw new ConfigValidationError(`Missing or invalid 'repositoryId' in ${resolved}`);
  }

  const currentTaskId = typeof obj.currentTaskId === "string" ? obj.currentTaskId : null;
  const agentAdapter = parseAgentAdapter(obj.agentAdapter);

  return {
    apiUrl: obj.apiUrl,
    projectId: obj.projectId,
    repositoryId: obj.repositoryId,
    currentTaskId,
    ...(agentAdapter ? { agentAdapter } : {}),
  };
}

export async function findProjectConfig(
  startDir?: string
): Promise<{ path: string; value: GpdConfig }> {
  const envPath = process.env.GPD_CONFIG_PATH;
  if (envPath) {
    const resolvedEnv = resolve(envPath);
    if (await pathExists(resolvedEnv)) {
      const value = await loadProjectConfig(resolvedEnv);
      return { path: resolvedEnv, value };
    }
  }

  let current = resolve(startDir ?? process.cwd());
  while (true) {
    const candidate = join(current, ".gpd", "config.json");
    if (await pathExists(candidate)) {
      const value = await loadProjectConfig(candidate);
      return { path: candidate, value };
    }
    const parent = dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }

  throw new ConfigNotFoundError(
    `No .gpd/config.json found starting from ${startDir ?? process.cwd()}`
  );
}

export async function writeProjectConfig(
  configPath: string,
  config: GpdConfig
): Promise<void> {
  const resolved = resolve(configPath);
  const dir = dirname(resolved);
  await mkdir(dir, { recursive: true });

  const tempFile = `${resolved}.tmp.${Date.now()}.${randomUUID()}`;
  const serialized = JSON.stringify(config, null, 2) + "\n";

  await writeFile(tempFile, serialized, "utf8");
  await rename(tempFile, resolved);
}
