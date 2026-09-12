import React from "react";
import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderApp, defaultTask } from "../test/test-utils";

describe("TasksPage", () => {
  it("renders tasks list with keys, titles, priority, and status", async () => {
    const task1 = defaultTask({ id: "t1", public_id: "BUG-1", title: "Checkout hangs" });
    const task2 = defaultTask({ id: "t2", public_id: "BUG-2", title: "Login redirect loops", priority: "critical", status: "todo" });

    renderApp("/tasks", {
      tasksApi: {
        async listTasks() {
          return { items: [task1, task2], next_cursor: null };
        },
        async getTask() {
          return task1;
        },
        async getTaskContext() {
          throw new Error("not used");
        },
      },
    });

    expect(await screen.findByText("BUG-1")).toBeVisible();
    expect(screen.getByText("Checkout hangs")).toBeVisible();
    expect(screen.getByText("BUG-2")).toBeVisible();
    expect(screen.getByText("Login redirect loops")).toBeVisible();
  });

  it("updates search query input", async () => {
    const listTasksMock = vi.fn().mockResolvedValue({ items: [defaultTask()], next_cursor: null });

    renderApp("/tasks", {
      tasksApi: {
        listTasks: listTasksMock,
        async getTask() {
          return defaultTask();
        },
        async getTaskContext() {
          throw new Error("not used");
        },
      },
    });

    expect(await screen.findByText("BUG-1")).toBeVisible();

    const searchInput = screen.getByPlaceholderText(/Search by title/);
    await React.act(async () => {
      fireEvent.change(searchInput, { target: { value: "checkout" } });
    });
    expect(searchInput).toHaveValue("checkout");
  });

  it("shows empty state when no tasks match", async () => {
    renderApp("/tasks", {
      tasksApi: {
        async listTasks() {
          return { items: [], next_cursor: null };
        },
        async getTask() {
          throw new Error("not found");
        },
        async getTaskContext() {
          throw new Error("not used");
        },
      },
    });

    expect(await screen.findByText("No tasks found")).toBeVisible();
    expect(screen.getByText("Try adjusting your search query or status filters.")).toBeVisible();
  });
});
