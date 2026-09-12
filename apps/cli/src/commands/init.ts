import { basename, join } from "node:path";
import type { GpdConfig } from "@gpd/contracts";
import { writeProjectConfig } from "@gpd/config";
import type { ApiClient } from "@gpd/api-client";
import type { GitOps } from "../git.js";

export type InitOptions = {
  apiUrl?: string;
  name?: string;
};

export async function executeInit(
  client: ApiClient,
  git: GitOps,
  options: InitOptions = {},
  cwd?: string
): Promise<{ project: unknown; repository: unknown; configPath: string }> {
  const root = await git.getGitRoot(cwd);
  const remoteUrl = await git.getGitRemoteUrl(cwd);
  const defaultBranch = await git.getGitDefaultBranch(cwd);
  const projectName = options.name || basename(root);
  const apiUrl = options.apiUrl || client.baseUrl || "http://127.0.0.1:7337";

  const response = await client.registerProject({
    name: projectName,
    repository_root: root,
    remote_url: remoteUrl,
    default_branch: defaultBranch,
  });

  if (!response.data) {
    throw new Error("Failed to register project: empty response from backend");
  }

  const { project, repository } = response.data;
  const configPath = join(root, ".gpd", "config.json");
  const configValue: GpdConfig = {
    apiUrl,
    projectId: project.id,
    repositoryId: repository.id,
    currentTaskId: null,
  };

  await writeProjectConfig(configPath, configValue);

  return {
    project,
    repository,
    configPath,
  };
}
