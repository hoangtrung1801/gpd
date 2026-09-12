import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiClientError, EXIT_CODES, mapErrorCodeToExitCode } from "./client.js";
import type { ApiEnvelope } from "@gpd/contracts";

describe("ApiClient", () => {
  describe("error code to exit code mapping", () => {
    it.each([
      ["validation_error", undefined, EXIT_CODES.VALIDATION],
      ["INVALID_INPUT", undefined, EXIT_CODES.VALIDATION],
      [undefined, 400, EXIT_CODES.VALIDATION],
      [undefined, 422, EXIT_CODES.VALIDATION],
      ["config_error", undefined, EXIT_CODES.CONFIGURATION],
      ["UNAUTHORIZED", undefined, EXIT_CODES.CONFIGURATION],
      [undefined, 401, EXIT_CODES.CONFIGURATION],
      [undefined, 403, EXIT_CODES.CONFIGURATION],
      ["service_unavailable", undefined, EXIT_CODES.UNAVAILABLE],
      ["NOT_FOUND", undefined, EXIT_CODES.UNAVAILABLE],
      ["TIMEOUT", undefined, EXIT_CODES.UNAVAILABLE],
      [undefined, 404, EXIT_CODES.UNAVAILABLE],
      [undefined, 503, EXIT_CODES.UNAVAILABLE],
      ["conflict", undefined, EXIT_CODES.CONFLICT],
      ["IDEMPOTENCY_CONFLICT", undefined, EXIT_CODES.CONFLICT],
      [undefined, 409, EXIT_CODES.CONFLICT],
      ["unknown_error", undefined, EXIT_CODES.UNEXPECTED],
      [undefined, 500, EXIT_CODES.UNEXPECTED],
    ])("maps code=%s, status=%s to exitCode=%d", (code, status, expectedExitCode) => {
      expect(mapErrorCodeToExitCode(code, status)).toBe(expectedExitCode);
    });
  });

  describe("Idempotency-Key headers", () => {
    it("sends Idempotency-Key for mutations by default", async () => {
      let sentHeaders: Headers | Record<string, string> = {};
      const fakeFetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
        sentHeaders = (init?.headers as Record<string, string>) || {};
        const envelope: ApiEnvelope<{ id: string }> = {
          ok: true,
          data: { id: "test-1" },
          warnings: [],
          error: null,
        };
        return new Response(JSON.stringify(envelope), { status: 200 });
      });

      const client = new ApiClient({ baseUrl: "http://api.local", fetch: fakeFetch as unknown as typeof fetch });
      await client.registerProject({ name: "Demo", repository_root: "/repo" });

      expect(sentHeaders).toHaveProperty("Idempotency-Key");
      expect(typeof (sentHeaders as Record<string, string>)["Idempotency-Key"]).toBe("string");
    });

    it("respects custom Idempotency-Key for mutations", async () => {
      let sentHeaders: Headers | Record<string, string> = {};
      const fakeFetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
        sentHeaders = (init?.headers as Record<string, string>) || {};
        const envelope: ApiEnvelope<{ id: string }> = {
          ok: true,
          data: { id: "test-1" },
          warnings: [],
          error: null,
        };
        return new Response(JSON.stringify(envelope), { status: 200 });
      });

      const client = new ApiClient({ baseUrl: "http://api.local", fetch: fakeFetch as unknown as typeof fetch });
      await client.registerProject({ name: "Demo", repository_root: "/repo" }, "custom-key-123");

      expect((sentHeaders as Record<string, string>)["Idempotency-Key"]).toBe("custom-key-123");
    });

    it("does NOT send Idempotency-Key for heartbeat (safe retry)", async () => {
      let sentHeaders: Headers | Record<string, string> = {};
      const fakeFetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
        sentHeaders = (init?.headers as Record<string, string>) || {};
        const envelope: ApiEnvelope<{ last_heartbeat_at: string }> = {
          ok: true,
          data: { last_heartbeat_at: new Date().toISOString() },
          warnings: [],
          error: null,
        };
        return new Response(JSON.stringify(envelope), { status: 200 });
      });

      const client = new ApiClient({ baseUrl: "http://api.local", fetch: fakeFetch as unknown as typeof fetch });
      await client.heartbeatSession("session-1");

      expect((sentHeaders as Record<string, string>)["Idempotency-Key"]).toBeUndefined();
    });
  });

  describe("timeout and error handling", () => {
    it("applies request timeout and throws ApiClientError with exit code 4", async () => {
      const slowFetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
        return new Promise<Response>((_, reject) => {
          init?.signal?.addEventListener("abort", () => {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
          });
        });
      });

      const client = new ApiClient({
        baseUrl: "http://api.local",
        timeoutMs: 50,
        fetch: slowFetch as unknown as typeof fetch,
      });

      await expect(client.getHealth()).rejects.toThrow(ApiClientError);
      try {
        await client.getHealth();
      } catch (err: unknown) {
        expect(err).toBeInstanceOf(ApiClientError);
        const apiErr = err as ApiClientError;
        expect(apiErr.exitCode).toBe(EXIT_CODES.UNAVAILABLE);
        expect(apiErr.code).toBe("TIMEOUT");
      }
    });

    it("parses ApiEnvelope error and assigns correct exitCode", async () => {
      const errorEnvelope: ApiEnvelope<null> = {
        ok: false,
        data: null,
        warnings: ["low_disk_space"],
        error: {
          code: "VALIDATION_FAILED",
          message: "Name is required",
          retryable: false,
          fields: { name: "Must not be empty" },
        },
      };

      const errorFetch = vi.fn(async () => {
        return new Response(JSON.stringify(errorEnvelope), { status: 422 });
      });

      const client = new ApiClient({ baseUrl: "http://api.local", fetch: errorFetch as unknown as typeof fetch });

      try {
        await client.getProject("bad-id");
        expect.unreachable();
      } catch (err: unknown) {
        expect(err).toBeInstanceOf(ApiClientError);
        const apiErr = err as ApiClientError;
        expect(apiErr.exitCode).toBe(EXIT_CODES.VALIDATION);
        expect(apiErr.message).toBe("Name is required");
        expect(apiErr.fields).toEqual({ name: "Must not be empty" });
        expect(apiErr.envelope?.warnings).toEqual(["low_disk_space"]);
      }
    });
  });
});
