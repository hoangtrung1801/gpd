import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { ApiClient } from "@gpd/api-client";
import { AppProviders, useApp } from "./providers";

function ProjectConsumer() {
  const { projectId, isProjectLoading } = useApp();
  return (
    <div>
      <span data-testid="project-id">{projectId}</span>
      <span data-testid="loading">{isProjectLoading ? "loading" : "idle"}</span>
    </div>
  );
}

describe("AppProviders projectId startup load", () => {
  it("loads first project id from GET /api/v1/projects on mount", async () => {
    const mockRequest = vi.fn().mockImplementation(async ({ path }) => {
      if (path === "/api/v1/projects") {
        return {
          ok: true,
          data: [
            { id: "proj-alpha", name: "Alpha Project" },
            { id: "proj-beta", name: "Beta Project" },
          ],
        };
      }
      return { ok: true, data: null };
    });

    const mockClient = {
      request: mockRequest,
      getHealth: vi.fn().mockResolvedValue({ ok: true, data: null }),
    } as unknown as ApiClient;

    render(
      <AppProviders client={mockClient}>
        <ProjectConsumer />
      </AppProviders>
    );

    await waitFor(() => {
      expect(screen.getByTestId("project-id").textContent).toBe("proj-alpha");
    });
    expect(screen.getByTestId("loading").textContent).toBe("idle");
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({ path: "/api/v1/projects" })
    );
  });

  it("falls back to project-1 when request fails", async () => {
    const mockRequest = vi.fn().mockImplementation(async ({ path }) => {
      if (path === "/api/v1/projects") {
        throw new Error("Failed to fetch projects");
      }
      return { ok: true, data: null };
    });

    const mockClient = {
      request: mockRequest,
      getHealth: vi.fn().mockResolvedValue({ ok: true, data: null }),
    } as unknown as ApiClient;

    render(
      <AppProviders client={mockClient}>
        <ProjectConsumer />
      </AppProviders>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("idle");
    });
    expect(screen.getByTestId("project-id").textContent).toBe("project-1");
  });

  it("falls back to project-1 when project list is empty", async () => {
    const mockRequest = vi.fn().mockImplementation(async ({ path }) => {
      if (path === "/api/v1/projects") {
        return { ok: true, data: [] };
      }
      return { ok: true, data: null };
    });

    const mockClient = {
      request: mockRequest,
      getHealth: vi.fn().mockResolvedValue({ ok: true, data: null }),
    } as unknown as ApiClient;

    render(
      <AppProviders client={mockClient}>
        <ProjectConsumer />
      </AppProviders>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("idle");
    });
    expect(screen.getByTestId("project-id").textContent).toBe("project-1");
  });

  it("uses explicit projectId prop without requesting projects", async () => {
    const mockRequest = vi.fn().mockResolvedValue({ ok: true, data: null });
    const mockClient = {
      request: mockRequest,
      getHealth: vi.fn().mockResolvedValue({ ok: true, data: null }),
    } as unknown as ApiClient;

    render(
      <AppProviders client={mockClient} projectId="custom-proj-99">
        <ProjectConsumer />
      </AppProviders>
    );

    expect(screen.getByTestId("project-id").textContent).toBe("custom-proj-99");
    expect(screen.getByTestId("loading").textContent).toBe("idle");
    expect(mockRequest).not.toHaveBeenCalledWith(
      expect.objectContaining({ path: "/api/v1/projects" })
    );
  });
});
