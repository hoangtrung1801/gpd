import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type { GitSnapshot } from "@gpd/contracts";

const execFileAsync = promisify(execFile);

export type GitOps = {
  getGitRoot(cwd?: string): Promise<string>;
  getGitBranch(cwd?: string): Promise<string>;
  getGitRemoteUrl(cwd?: string): Promise<string | null>;
  getGitDefaultBranch(cwd?: string): Promise<string>;
  getGitChangedFiles(cwd?: string): Promise<string[]>;
  getGitRecentCommits(cwd?: string, limit?: number): Promise<string[]>;
  getGitSnapshot(cwd?: string): Promise<GitSnapshot>;
};

async function runGit(args: string[], cwd?: string): Promise<string> {
  try {
    const { stdout } = await execFileAsync("git", args, {
      cwd: cwd ?? process.cwd(),
      encoding: "utf8",
    });
    return stdout.trim();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(`Git command 'git ${args.join(" ")}' failed: ${message}`);
  }
}

export const defaultGitOps: GitOps = {
  async getGitRoot(cwd?: string): Promise<string> {
    return runGit(["rev-parse", "--show-toplevel"], cwd);
  },

  async getGitBranch(cwd?: string): Promise<string> {
    try {
      return await runGit(["rev-parse", "--abbrev-ref", "HEAD"], cwd);
    } catch {
      return "main";
    }
  },

  async getGitRemoteUrl(cwd?: string): Promise<string | null> {
    try {
      const url = await runGit(["config", "--get", "remote.origin.url"], cwd);
      return url || null;
    } catch {
      return null;
    }
  },

  async getGitDefaultBranch(cwd?: string): Promise<string> {
    try {
      const ref = await runGit(
        ["symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd
      );
      const parts = ref.split("/");
      return parts[parts.length - 1] || "main";
    } catch {
      return "main";
    }
  },

  async getGitChangedFiles(cwd?: string): Promise<string[]> {
    try {
      const output = await runGit(["status", "--porcelain"], cwd);
      if (!output) {
        return [];
      }
      return output
        .split("\n")
        .map((line) => line.slice(3).trim())
        .filter(Boolean);
    } catch {
      return [];
    }
  },

  async getGitRecentCommits(cwd?: string, limit: number = 5): Promise<string[]> {
    try {
      const output = await runGit(
        ["log", `-n${limit}`, "--oneline"],
        cwd
      );
      if (!output) {
        return [];
      }
      return output.split("\n").filter(Boolean);
    } catch {
      return [];
    }
  },

  async getGitSnapshot(cwd?: string): Promise<GitSnapshot> {
    const branch = await this.getGitBranch(cwd);
    const changed_files = await this.getGitChangedFiles(cwd);
    const recent_commits = await this.getGitRecentCommits(cwd);
    const remote_url = await this.getGitRemoteUrl(cwd);

    return {
      branch,
      changed_files,
      recent_commits,
      remote_url,
    };
  },
};
