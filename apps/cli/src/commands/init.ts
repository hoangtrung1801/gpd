import { basename, join } from "node:path";
import type { GpdConfig, Project, Repository } from "@gpd/contracts";
import { writeProjectConfig } from "@gpd/config";
import { ApiClientError, type ApiClient } from "@gpd/api-client";
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
  const configPath = join(root, ".gpd", "config.json");

  try {
    const response = await client.registerProject({
      name: projectName,
      repository_root: root,
      remote_url: remoteUrl,
      default_branch: defaultBranch,
    });

    if (!response.data) {
      throw new Error("Failed to register project: empty response from backend");
    }

    let project: Project;
    let repository: Repository | undefined;
    if (response.data && typeof response.data === "object" && "project" in response.data) {
      const legacy = response.data as unknown as { project: Project; repository: Repository };
      project = legacy.project;
      repository = legacy.repository;
    } else {
      project = response.data;
      const repositories = project.repositories ?? [];
      repository =
        repositories.find((r) => r.root_path === root) ??
        (remoteUrl ? repositories.find((r) => r.remote_url === remoteUrl) : undefined) ??
        repositories[0];
    }

    if (!repository) {
      throw new Error("Failed to register project: empty response from backend");
    }

    const configValue: GpdConfig = {
      apiUrl,
      projectId: project.id,
      repositoryId: repository.id,
      currentTaskId: null,
    };
    await writeProjectConfig(configPath, configValue);
    return { project, repository, configPath };
  } catch (err) {
    const status = err instanceof ApiClientError ? err.status : (err as { status?: unknown }).status;
    const code =
      err instanceof ApiClientError ? err.code : String((err as { code?: unknown }).code ?? "");
    const normalized = code.toLowerCase();
    const isConflict =
      status === 409 || normalized.includes("conflict") || normalized.includes("already_exists");
    if (!isConflict) {
      throw err;
    }

    const listed = await client.listProjects();
    const candidates = listed.data ?? [];
    const existing =
      candidates.find((p) => p.name === projectName) ??
      (remoteUrl
        ? candidates.find((p) => (p.repositories ?? []).some((r) => r.remote_url === remoteUrl))
        : undefined) ??
      candidates.find((p) => (p.repositories ?? []).some((r) => r.root_path === root));
    if (!existing) {
      throw err;
    }

    const repositories = existing.repositories ?? [];
    const repository =
      repositories.find((r) => r.root_path === root) ??
      (remoteUrl ? repositories.find((r) => r.remote_url === remoteUrl) : undefined) ??
      repositories[0];
    if (!repository) {
      throw new Error(
        `Project '${existing.name}' already exists on the server but has no repository to connect to`
      );
    }

    const configValue: GpdConfig = {
      apiUrl,
      projectId: existing.id,
      repositoryId: repository.id,
      currentTaskId: null,
    };
    await writeProjectConfig(configPath, configValue);
    return { project: existing, repository, configPath };
  }
}
