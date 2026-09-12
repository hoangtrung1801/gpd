import React from "react";
import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderApp, apiWithProposal } from "../test/test-utils";

describe("KnowledgeReviewPage", () => {
  it("requires a deliberate action before promoting knowledge", async () => {
    renderApp("/knowledge/review", apiWithProposal());
    expect(await screen.findByText("Normalize payment_method_invalid in PaymentService")).toBeVisible();
    expect(screen.getByRole("button", { name: "Confirm knowledge" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it("confirms a proposal on button click", async () => {
    const confirmMock = vi.fn().mockResolvedValue({ id: "prop-1", status: "confirmed" });
    const mockApis = apiWithProposal();
    if (mockApis.knowledgeApi) {
      mockApis.knowledgeApi.confirmProposal = confirmMock;
    }

    renderApp("/knowledge/review", mockApis);

    const confirmBtn = await screen.findByRole("button", { name: "Confirm knowledge" });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(confirmMock).toHaveBeenCalledWith("prop-1");
    });
    expect(await screen.findByText(/confirmed and promoted/)).toBeVisible();
  });

  it("rejects a proposal on reject button click", async () => {
    const rejectMock = vi.fn().mockResolvedValue({ id: "prop-1", status: "rejected" });
    const mockApis = apiWithProposal();
    if (mockApis.knowledgeApi) {
      mockApis.knowledgeApi.rejectProposal = rejectMock;
    }

    renderApp("/knowledge/review", mockApis);

    const rejectBtn = await screen.findByRole("button", { name: "Reject" });
    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(rejectMock).toHaveBeenCalledWith("prop-1", { reason: "Rejected during review" });
    });
    expect(await screen.findByText(/proposal rejected/)).toBeVisible();
  });
});
