import { describe, it, expect, vi } from "vitest";
import { readThread, proposeAction, listTasks, searchKnowledge } from "./tools.js";
import { TaskCard } from "./components.js";

type ToolWithHandler = {
  handler: (args: Record<string, unknown>, context: { thread: unknown }) => Promise<unknown>;
};

describe("channel components and tools", () => {
  it("defines tools with appropriate metadata", () => {
    expect(readThread.name).toBe("read_thread");
    expect(proposeAction.name).toBe("propose_action");
    expect(listTasks.name).toBe("list_tasks");
    expect(searchKnowledge.name).toBe("search_knowledge");
  });

  it("defines TaskCard component", () => {
    expect(TaskCard.name).toBe("task_card");
  });

  it("handles readThread when thread has no messages", async () => {
    const mockThread = {
      getMessages: vi.fn().mockResolvedValue([]),
    };
    const tool = readThread as unknown as ToolWithHandler;
    const result = await tool.handler({}, { thread: mockThread });
    expect(result).toContain("cannot see earlier messages");
  });

  it("handles readThread when thread has messages", async () => {
    const messages = [{ text: "Bug report on checkout", user: "U123" }];
    const mockThread = {
      getMessages: vi.fn().mockResolvedValue(messages),
    };
    const tool = readThread as unknown as ToolWithHandler;
    const result = await tool.handler({}, { thread: mockThread });
    expect(result).toEqual(messages);
  });
});
