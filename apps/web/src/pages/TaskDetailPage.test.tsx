import React from "react";
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderApp, apiWithTask, apiWithContext } from "../test/test-utils";

describe("TaskDetailPage", () => {
  it("shows unknown bug fields without inventing values", async () => {
    renderApp("/tasks/BUG-1", apiWithTask({ environment: null }));
    expect(await screen.findByRole("heading", { name: "Checkout hangs on expired card" })).toBeVisible();
    expect(screen.getByText("Environment")).toBeVisible();
    expect(screen.getByText("Unknown")).toBeVisible();
  });

  it("shows context provenance and vector fallback", async () => {
    renderApp("/tasks/BUG-1", apiWithContext({ warnings: ["vector_search_unavailable"] }));
    expect(await screen.findByText("Semantic search unavailable; using keyword search.")).toBeVisible();
    expect(screen.getByRole("link", { name: /Slack message/ })).toBeVisible();
  });

  it("shows confidence score when below trust threshold", async () => {
    renderApp(
      "/tasks/BUG-1",
      apiWithTask({
        affected_component: {
          value: "PaymentService",
          confidence: 0.65,
          evidence: ["msg-4"],
        },
      })
    );

    expect(await screen.findByText("PaymentService")).toBeVisible();
    expect(screen.getByText("Confidence: 65%")).toBeVisible();
  });

  it("renders description and acceptance criteria", async () => {
    renderApp("/tasks/BUG-1", apiWithTask());
    expect(await screen.findByRole("heading", { name: "Checkout hangs on expired card" })).toBeVisible();
    expect(screen.getByText("Payment fails silently when card is expired.")).toBeVisible();
    expect(screen.getByText("Prompt user with expired card error dialog.")).toBeVisible();
  });
});
