import { describe, expect, it } from "vitest";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  ConfigNotFoundError,
  findProjectConfig,
  loadProjectConfig,
  writeProjectConfig,
} from "./project-config.js";
import type { GpdConfig } from "@gpd/contracts";

describe("project-config", () => {
  it("finds .gpd/config.json from a nested directory", async () => {
    const root = await mkdtemp(join(tmpdir(), "gpd-config-test-"));
    try {
      const gpdDir = join(root, ".gpd");
      await mkdir(gpdDir, { recursive: true });
      const nested = join(root, "src", "payment");
      await mkdir(nested, { recursive: true });

      const testConfig: GpdConfig = {
        apiUrl: "http://localhost:7337",
        projectId: "project-1",
        repositoryId: "repo-1",
        currentTaskId: "task-1",
      };

      await writeFile(join(gpdDir, "config.json"), JSON.stringify(testConfig));

      const found = await findProjectConfig(nested);
      expect(found.path).toBe(join(gpdDir, "config.json"));
      expect(found.value.projectId).toBe("project-1");
      expect(found.value.apiUrl).toBe("http://localhost:7337");
      expect(found.value.currentTaskId).toBe("task-1");
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });

  it("throws ConfigNotFoundError when .gpd/config.json is missing", async () => {
    const root = await mkdtemp(join(tmpdir(), "gpd-config-test-empty-"));
    try {
      await expect(findProjectConfig(root)).rejects.toThrow(ConfigNotFoundError);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });

  it("atomically writes config and re-reads it accurately", async () => {
    const root = await mkdtemp(join(tmpdir(), "gpd-config-atomic-"));
    try {
      const configPath = join(root, ".gpd", "config.json");
      const config: GpdConfig = {
        apiUrl: "http://127.0.0.1:7337",
        projectId: "proj-123",
        repositoryId: "repo-456",
        currentTaskId: null,
      };

      await writeProjectConfig(configPath, config);
      const loaded = await loadProjectConfig(configPath);
      expect(loaded).toEqual(config);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });
});
