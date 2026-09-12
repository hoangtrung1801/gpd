import { readFile, stat } from "node:fs/promises";
import { basename, isAbsolute, relative, resolve, sep } from "node:path";
import { ApiClientError, type ApiClient } from "@gpd/api-client";
import type { GpdConfig } from "@gpd/contracts";
import type { GitOps } from "../git.js";

const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2 MiB

export async function executeAdd(
  client: ApiClient,
  git: GitOps,
  config: GpdConfig,
  targetPath: string,
  cwd?: string
): Promise<{ id: string; state: string; path: string; size: number }> {
  const currentDir = cwd || process.cwd();
  const gitRoot = await git.getGitRoot(currentDir);
  const absolutePath = isAbsolute(targetPath)
    ? resolve(targetPath)
    : resolve(currentDir, targetPath);

  // Path safety: path must be strictly within gitRoot
  const rel = relative(gitRoot, absolutePath);
  const isInside = !rel.startsWith("..") && !isAbsolute(rel);
  if (!isInside) {
    throw new ApiClientError({
      message: `Path '${targetPath}' is outside the repository root '${gitRoot}'`,
      code: "VALIDATION_ERROR",
      status: 400,
    });
  }

  let fileStat;
  try {
    fileStat = await stat(absolutePath);
  } catch {
    throw new ApiClientError({
      message: `File '${targetPath}' does not exist or cannot be accessed`,
      code: "NOT_FOUND",
      status: 404,
    });
  }

  if (fileStat.size > MAX_FILE_SIZE) {
    throw new ApiClientError({
      message: `File '${targetPath}' size (${fileStat.size} bytes) exceeds the 2 MiB limit`,
      code: "VALIDATION_ERROR",
      status: 400,
    });
  }

  const content = await readFile(absolutePath, "utf8");
  const fileName = basename(absolutePath);

  const response = await client.addSource(config.projectId, {
    type: "document",
    title: fileName,
    content,
    file_path: rel,
  });

  if (!response.data) {
    throw new Error("Failed to add source: empty response from backend");
  }

  return {
    id: response.data.id,
    state: response.data.state,
    path: rel,
    size: fileStat.size,
  };
}
