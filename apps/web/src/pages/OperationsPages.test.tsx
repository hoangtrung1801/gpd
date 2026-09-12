import React from "react";
import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderApp, defaultTask } from "../test/test-utils";
import type { Source } from "../features/sources/api";
import type { Job } from "../features/jobs/api";
import type { DeveloperSession } from "@gpd/contracts";

describe("OperationsPages", () => {
  it("renders OverviewPage with metrics and recent entities", async () => {
    const task = defaultTask();
    const session: DeveloperSession = {
      id: "sess-1",
      project_id: "project-1",
      task_id: "BUG-1",
      status: "active",
      git_branch: "feature/checkout",
      created_at: new Date().toISOString(),
      overlap_warnings: [],
    };

    renderApp("/", {
      tasksApi: {
        async listTasks() {
          return { items: [task], next_cursor: null };
        },
        async getTask() {
          return task;
        },
        async getTaskContext() {
          throw new Error("not used");
        },
      },
      sessionsApi: {
        async listSessions() {
          return [session];
        },
        async getSession() {
          return session;
        },
        async startSession() {
          return session;
        },
        async finishSession() {
          return session;
        },
      },
      conflictsApi: {
        async listConflicts() {
          return [];
        },
        async getConflict() {
          throw new Error("not used");
        },
        async resolveConflict() {
          throw new Error("not used");
        },
      },
      jobsApi: {
        async listJobs() {
          return [];
        },
        async retryJob() {
          throw new Error("not used");
        },
        async cancelJob() {
          throw new Error("not used");
        },
      },
    });

    expect(await screen.findByText("Platform Overview")).toBeVisible();
    expect(screen.getAllByText("Active Sessions")[0]).toBeVisible();
    expect(screen.getAllByText("Recent Tasks")[0]).toBeVisible();
    expect(screen.getByText("Checkout hangs on expired card")).toBeVisible();
  });

  it("renders SourcesPage and shows source state", async () => {
    const source: Source = {
      id: "src-1",
      project_id: "project-1",
      content_hash: "a1b2c3d4e5f6",
      source_type: "document",
      title: "Checkout PRD",
      content: "# PRD Content",
      state: "ready",
      chunks_count: 5,
      created_at: new Date().toISOString(),
    };

    renderApp("/sources", {
      sourcesApi: {
        async listSources() {
          return [source];
        },
        async getSource() {
          return source;
        },
        async retrySource() {
          return { id: "src-1", state: "queued" };
        },
      },
    });

    expect(await screen.findByText("Ingested Sources")).toBeVisible();
    expect(screen.getByText("Checkout PRD")).toBeVisible();
    expect(screen.getByText("ready")).toBeVisible();
    expect(screen.getByText("a1b2c3d4")).toBeVisible();
  });

  it("renders SessionsPage with overlap collision warnings", async () => {
    const session: DeveloperSession = {
      id: "sess-overlap-1",
      project_id: "project-1",
      task_id: "BUG-1",
      status: "active",
      git_branch: "fix/payment-retries",
      created_at: new Date().toISOString(),
      last_heartbeat_at: new Date().toISOString(),
      overlap_warnings: [
        {
          severity: "high",
          explanation: "Both sessions modifying checkout.ts simultaneously",
          suggested_action: "Coordinate branch merge with session sess-2",
          evidence: [{ type: "file", id: "checkout.ts", score: 1.0 }],
        },
      ],
    };

    renderApp("/sessions", {
      sessionsApi: {
        async listSessions() {
          return [session];
        },
        async getSession() {
          return session;
        },
        async startSession() {
          return session;
        },
        async finishSession() {
          return session;
        },
      },
    });

    expect(await screen.findByText("Developer & Agent Sessions")).toBeVisible();
    expect(screen.getByText("fix/payment-retries")).toBeVisible();
    expect(screen.getByText(/Both sessions modifying checkout.ts/)).toBeVisible();
    expect(screen.getByText(/Coordinate branch merge/)).toBeVisible();
  });

  it("renders JobsPage and allows canceling a queued job", async () => {
    const cancelMock = vi.fn().mockResolvedValue({
      id: "job-1",
      project_id: "project-1",
      type: "embed_source",
      state: "cancelled",
      progress: 0,
      attempts: 0,
      max_attempts: 3,
      retryable: true,
      created_at: new Date().toISOString(),
    });

    const job: Job = {
      id: "job-1",
      project_id: "project-1",
      type: "embed_source",
      state: "queued",
      progress: 0,
      attempts: 0,
      max_attempts: 3,
      retryable: true,
      created_at: new Date().toISOString(),
    };

    renderApp("/jobs", {
      jobsApi: {
        async listJobs() {
          return [job];
        },
        async retryJob() {
          return job;
        },
        cancelJob: cancelMock,
      },
    });

    expect(await screen.findByText("Background Jobs & Pipelines")).toBeVisible();
    expect(screen.getByText("embed_source")).toBeVisible();
    expect(screen.getByText("queued")).toBeVisible();

    const cancelBtn = screen.getByRole("button", { name: "Cancel" });
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(cancelMock).toHaveBeenCalledWith("job-1");
    });
  });

  it("renders SettingsPage with editable allowlist, secret-presence booleans, display-only retention, and health", async () => {
    const patchMock = vi.fn().mockResolvedValue({
      name: "GPD Platform Updated",
      team_identifier: "core-platform",
      default_branch: "main",
      llm_model: "gpt-4o",
      embedding_model: "text-embedding-3-small",
      context_token_budget: 10000,
      version: 2,
      retention_days: 90,
      slack_credential_configured: true,
      llm_credential_configured: true,
    });

    renderApp("/settings", {
      settingsApi: {
        async getSettings() {
          return {
            name: "GPD Platform",
            team_identifier: "core-platform",
            default_branch: "main",
            llm_model: "gpt-4o",
            embedding_model: "text-embedding-3-small",
            context_token_budget: 8000,
            version: 1,
            retention_days: 90,
            slack_credential_configured: true,
            llm_credential_configured: false,
          };
        },
        patchSettings: patchMock,
        async getHealth() {
          return {
            status: "ok",
            version: "0.1.0",
            database: "connected",
            database_healthy: true,
            fts_healthy: true,
            vector_healthy: true,
          };
        },
      },
    });

    expect(await screen.findByText("Project Settings & Health")).toBeVisible();
    expect(screen.getByLabelText("Project Name")).toHaveValue("GPD Platform");
    expect(screen.getByLabelText("Context Token Budget")).toHaveValue(8000);

    // Verify secret-presence booleans
    expect(screen.getByText("Configured")).toBeVisible(); // Slack
    expect(screen.getByText("Not configured")).toBeVisible(); // LLM

    // Verify display-only retention policy
    expect(screen.getByText("90 days")).toBeVisible();
    expect(screen.getByText(/Automated destructive data purge is disabled/)).toBeVisible();

    // Verify system health
    expect(screen.getByText("SQLite Database")).toBeVisible();
    expect(screen.getByText("FTS5 Keyword Search")).toBeVisible();
    expect(screen.getByText("Vector Indexing (sqlite-vec)")).toBeVisible();

    // Test form update
    const budgetInput = screen.getByLabelText("Context Token Budget");
    fireEvent.change(budgetInput, { target: { value: "10000" } });

    const saveBtn = screen.getByRole("button", { name: "Save Settings" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledWith("project-1", expect.objectContaining({
        context_token_budget: 10000,
      }));
    });
  });
});
