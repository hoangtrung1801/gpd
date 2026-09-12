import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AsyncState } from "./AsyncState";

describe("AsyncState", () => {
  it("renders loading indicator when loading is true", () => {
    render(
      <AsyncState loading={true}>
        <div>Content</div>
      </AsyncState>
    );
    expect(screen.getByTestId("async-loading")).toBeInTheDocument();
    expect(screen.queryByText("Content")).not.toBeInTheDocument();
  });

  it("renders custom skeleton when provided", () => {
    render(
      <AsyncState loading={true} skeleton={<div data-testid="custom-skeleton">Loading...</div>}>
        <div>Content</div>
      </AsyncState>
    );
    expect(screen.getByTestId("custom-skeleton")).toBeInTheDocument();
    expect(screen.queryByText("Content")).not.toBeInTheDocument();
  });

  it("renders error state with retry action", () => {
    const handleRetry = vi.fn();
    render(
      <AsyncState
        error={{ code: "UNAVAILABLE", message: "Failed to load" }}
        onRetry={handleRetry}
      >
        <div>Content</div>
      </AsyncState>
    );
    expect(screen.getByTestId("async-error")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Failed to load data/ })).toBeInTheDocument();
    expect(screen.getByText(/UNAVAILABLE/)).toBeInTheDocument();

    const retryBtn = screen.getByRole("button", { name: /Retry/ });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledOnce();
  });

  it("renders empty state with custom title and action", () => {
    render(
      <AsyncState
        empty={true}
        emptyTitle="No tasks found"
        emptyMessage="Try adjusting filters"
        emptyAction={<button type="button">Create Task</button>}
      >
        <div>Content</div>
      </AsyncState>
    );
    expect(screen.getByTestId("async-empty")).toBeInTheDocument();
    expect(screen.getByText("No tasks found")).toBeInTheDocument();
    expect(screen.getByText("Try adjusting filters")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Task" })).toBeInTheDocument();
  });

  it("renders stale banner and children when stale is true", () => {
    const handleRefresh = vi.fn();
    render(
      <AsyncState stale={true} onRetry={handleRefresh}>
        <div>Active Content</div>
      </AsyncState>
    );
    expect(screen.getByTestId("async-stale")).toBeInTheDocument();
    expect(screen.getByText("Active Content")).toBeInTheDocument();

    const refreshBtn = screen.getByRole("button", { name: "Refresh" });
    fireEvent.click(refreshBtn);
    expect(handleRefresh).toHaveBeenCalledOnce();
  });

  it("renders children normally when not loading, error, or empty", () => {
    render(
      <AsyncState>
        <div>Normal Content</div>
      </AsyncState>
    );
    expect(screen.getByText("Normal Content")).toBeInTheDocument();
  });
});
