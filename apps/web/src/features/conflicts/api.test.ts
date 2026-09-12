import { describe, it, expect, vi } from "vitest";
import type { ApiClient } from "@gpd/api-client";
import { createConflictsApi, type Conflict } from "./api";

describe("conflicts api", () => {
  it("calls /api/v1/conflicts?project_id=${projectId} when listing conflicts", async () => {
    const mockConflicts: Conflict[] = [
      {
        id: "c-1",
        project_id: "p-123",
        type: "contradiction",
        severity: "high",
        state: "unresolved",
        claim_a: "Payment retried 3 times",
        claim_b: "Payment retried once",
        created_at: new Date().toISOString(),
      },
    ];

    const mockRequest = vi.fn().mockResolvedValue({
      ok: true,
      data: mockConflicts,
    });

    const client = {
      request: mockRequest,
    } as unknown as ApiClient;

    const api = createConflictsApi(client);
    const result = await api.listConflicts("p-123");

    expect(mockRequest).toHaveBeenCalledWith({
      path: "/api/v1/conflicts?project_id=p-123",
      query: undefined,
    });
    expect(result).toEqual(mockConflicts);
  });

  it("passes state filter query parameter", async () => {
    const mockRequest = vi.fn().mockResolvedValue({
      ok: true,
      data: [],
    });

    const client = {
      request: mockRequest,
    } as unknown as ApiClient;

    const api = createConflictsApi(client);
    const result = await api.listConflicts("p-123", "unresolved");

    expect(mockRequest).toHaveBeenCalledWith({
      path: "/api/v1/conflicts?project_id=p-123",
      query: { state: "unresolved" },
    });
    expect(result).toEqual([]);
  });

  it("falls back to empty array when res.data is null or missing", async () => {
    const mockRequest = vi.fn().mockResolvedValue({
      ok: true,
      data: null,
    });

    const client = {
      request: mockRequest,
    } as unknown as ApiClient;

    const api = createConflictsApi(client);
    const result = await api.listConflicts("p-123");

    expect(result).toEqual([]);
  });
});
