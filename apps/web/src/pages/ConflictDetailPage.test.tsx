import React from "react";
import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderApp, apiWithRetryConflict } from "../test/test-utils";

describe("ConflictDetailPage", () => {
  it("shows both claims before resolving a contradiction", async () => {
    renderApp("/conflicts/c1", apiWithRetryConflict());
    expect(await screen.findByText("Retry payment three times")).toBeVisible();
    expect(screen.getByText("Retries were reduced to one")).toBeVisible();
    expect(screen.getByLabelText("Resolution note")).toBeRequired();
  });

  it("submits resolution with selected action and required note", async () => {
    const resolveMock = vi.fn().mockResolvedValue({
      id: "c1",
      project_id: "project-1",
      type: "contradiction",
      severity: "high",
      state: "resolved",
      claim_a: "Retry payment three times",
      claim_b: "Retries were reduced to one",
      resolution: {
        action: "supersede",
        note: "Card network limits retries",
      },
      created_at: new Date().toISOString(),
    });

    const mockApis = apiWithRetryConflict();
    if (mockApis.conflictsApi) {
      mockApis.conflictsApi.resolveConflict = resolveMock;
    }

    renderApp("/conflicts/c1", mockApis);

    expect(await screen.findByText("Retry payment three times")).toBeVisible();

    const noteInput = screen.getByLabelText("Resolution note");
    fireEvent.change(noteInput, { target: { value: "Card network limits retries" } });

    const submitBtn = screen.getByRole("button", { name: "Submit Resolution" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(resolveMock).toHaveBeenCalledWith("c1", {
        action: "supersede",
        note: "Card network limits retries",
      });
    });

    expect(await screen.findByText("Conflict resolved successfully.")).toBeVisible();
  });
});
