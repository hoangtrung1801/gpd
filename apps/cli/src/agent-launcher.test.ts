import { describe, expect, it, vi } from "vitest";
import { stat, access } from "node:fs/promises";
import { EventEmitter } from "node:events";
import { spawn, type ChildProcess } from "node:child_process";
import type { Writable } from "node:stream";
import { launchAgent } from "./agent-launcher.js";

type MockProcess = ChildProcess & {
  stdin: Writable | null;
  kill: (signal?: string) => boolean;
  emitClose: (code?: number) => void;
};

function createMockChild(exitCode: number = 0, autoClose: boolean = true): MockProcess {
  const emitter = new EventEmitter() as unknown as MockProcess;
  const stdinEmitter = new EventEmitter() as unknown as Writable;
  (stdinEmitter as unknown as Record<string, unknown>).write = vi.fn();
  (stdinEmitter as unknown as Record<string, unknown>).end = vi.fn();

  emitter.stdin = stdinEmitter;
  emitter.kill = vi.fn(() => true);
  emitter.emitClose = (code = exitCode) => {
    emitter.emit("close", code);
  };

  if (autoClose) {
    emitter.on("newListener", (event) => {
      if (event === "close") {
        queueMicrotask(() => {
          emitter.emit("close", exitCode);
        });
      }
    });
  }

  return emitter;
}

describe("agent-launcher", () => {
  it("creates context file with 0o600 mode and cleans up on exit", async () => {
    let capturedPath = "";
    let observedMode = 0;

    const mockSpawn = vi.fn((_cmd, _args, _opts) => {
      return createMockChild(0);
    });

    const exitCode = await launchAgent({
      command: ["mock-agent", "--run"],
      adapter: { kind: "args", flag: "--ctx" },
      contextText: "# Project Context",
      prompt: "Fix the checkout bug",
      spawn: mockSpawn as unknown as typeof spawn,
      onContextFileCreated: async (filePath) => {
        capturedPath = filePath;
        const s = await stat(filePath);
        observedMode = s.mode & 0o777;
      },
    });

    expect(exitCode).toBe(0);
    expect(observedMode).toBe(0o600);
    expect(mockSpawn).toHaveBeenCalledWith(
      "mock-agent",
      ["--run", "--ctx", capturedPath, "Fix the checkout bug"],
      expect.objectContaining({ shell: false })
    );

    let fileStillExists = true;
    try {
      await access(capturedPath);
    } catch {
      fileStillExists = false;
    }
    expect(fileStillExists).toBe(false);
  });

  it("pipes context via stdin when adapter is stdin", async () => {
    const emitter = createMockChild(7, true);
    const mockSpawn = vi.fn(() => emitter);

    const exitCode = await launchAgent({
      command: ["stdin-agent"],
      adapter: { kind: "stdin" },
      contextText: "STDIN_CONTEXT",
      prompt: "prompt-1",
      spawn: mockSpawn as unknown as typeof spawn,
    });

    expect(exitCode).toBe(7);
    expect(emitter.stdin?.write).toHaveBeenCalledWith("STDIN_CONTEXT");
    expect(emitter.stdin?.end).toHaveBeenCalled();
    expect(mockSpawn).toHaveBeenCalledWith(
      "stdin-agent",
      ["prompt-1"],
      expect.objectContaining({ shell: false, stdio: ["pipe", "inherit", "inherit"] })
    );
  });

  it("sends heartbeats while child is running", async () => {
    const { promise: spawnedPromise, resolve: resolveSpawned } = Promise.withResolvers<MockProcess>();
    const heartbeatFn = vi.fn(async () => {});

    const mockSpawn = vi.fn(() => {
      const child = createMockChild(0, false);
      resolveSpawned(child);
      return child;
    });

    const launchPromise = launchAgent({
      command: ["agent"],
      adapter: { kind: "args", flag: "--gpd" },
      contextText: "CTX",
      prompt: "PROMPT",
      spawn: mockSpawn as unknown as typeof spawn,
      heartbeat: heartbeatFn,
      heartbeatIntervalMs: 10,
    });

    const child = await spawnedPromise;
    const { promise: delayPromise, resolve: resolveDelay } = Promise.withResolvers<void>();
    setTimeout(resolveDelay, 35);
    await delayPromise;

    child.emitClose(0);
    const exitCode = await launchPromise;

    expect(exitCode).toBe(0);
    expect(heartbeatFn.mock.calls.length).toBeGreaterThanOrEqual(1);
  });
});
