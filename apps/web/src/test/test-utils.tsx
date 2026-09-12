import React from "react";
import { render, type RenderResult } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type {
  Task,
  BugDetails,
  ContextPackage,
  KnowledgeProposal,
  DeveloperSession,
  HealthStatus,
} from "@gpd/contracts";
import type { Conflict } from "../features/conflicts/api";
import type { Source } from "../features/sources/api";
import type { Job } from "../features/jobs/api";
import type { SettingsData, DetailedHealthStatus } from "../features/settings/api";
import { AppProviders, type AppProvidersProps } from "../app/providers";
import { AppRoutes } from "../app/router";

export interface MockApiOptions extends Partial<AppProvidersProps> {}

export function renderApp(
  initialRoute = "/",
  options: MockApiOptions = {}
): RenderResult {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <AppProviders {...options}>
        <AppRoutes />
      </AppProviders>
    </MemoryRouter>
  );
}

export function defaultTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-1",
    project_id: "project-1",
    public_id: "BUG-1",
    title: "Checkout hangs on expired card",
    description: "Payment fails silently when card is expired.",
    status: "in_progress",
    priority: "high",
    acceptance_criteria: "Prompt user with expired card error dialog.",
    created_at: new Date().toISOString(),
    bug_details: {
      task_id: "task-1",
      summary: {
        value: "Checkout hangs on expired card",
        confidence: 0.95,
        evidence: ["msg-1"],
      },
      reproduction_steps: {
        value: ["Go to checkout", "Enter expired card", "Click Pay"],
        confidence: 0.9,
        evidence: ["msg-1"],
      },
      actual_behavior: {
        value: "Spinner spins indefinitely",
        confidence: 0.92,
        evidence: ["msg-2"],
      },
      expected_behavior: {
        value: "Immediate 400 error banner with card expired message",
        confidence: 0.94,
        evidence: ["msg-2"],
      },
      environment: {
        value: "Staging sandbox",
        confidence: 0.88,
        evidence: ["msg-3"],
      },
      severity: {
        value: "high",
        confidence: 0.85,
        evidence: ["msg-1"],
      },
      affected_component: {
        value: "PaymentService",
        confidence: 0.91,
        evidence: ["msg-4"],
      },
      technical_clues: {
        value: ["Unhandled promise rejection in processPayment"],
        confidence: 0.86,
        evidence: ["msg-4"],
      },
      participants: {
        value: ["@alice", "@bob"],
        confidence: 0.95,
        evidence: ["msg-1"],
      },
    },
    ...overrides,
  };
}

export type MockBugDetails = {
  [K in keyof BugDetails]?: BugDetails[K] | null;
};

export function apiWithTask(bugDetailsOverrides: MockBugDetails = {}): MockApiOptions {
  const baseTask = defaultTask();
  const task: Task = {
    ...baseTask,
    bug_details: baseTask.bug_details
      ? ({
          ...baseTask.bug_details,
          ...bugDetailsOverrides,
        } as unknown as BugDetails)
      : null,
  };

  return {
    tasksApi: {
      async listTasks() {
        return { items: [task], next_cursor: null };
      },
      async getTask() {
        return task;
      },
      async getTaskContext() {
        return {
          id: "ctx-1",
          session_id: "sess-1",
          task_id: task.id,
          token_budget: 8000,
          token_count: 3200,
          markdown_content: "# Task Context\nCheckout hangs on expired card",
          sections: [],
          warnings: [],
          created_at: new Date().toISOString(),
        };
      },
    },
  };
}

export function apiWithContext(contextOverrides: Partial<ContextPackage> = {}): MockApiOptions {
  const task = defaultTask();
  const contextPackage: ContextPackage = {
    id: "ctx-1",
    session_id: "sess-1",
    task_id: task.id,
    token_budget: 8000,
    token_count: 2400,
    markdown_content: "# Context\nDetails from slack and code",
    sections: [
      {
        id: "sec-1",
        section: "task",
        content: "Checkout hangs on expired card",
        score: 0.95,
      },
    ],
    warnings: [],
    created_at: new Date().toISOString(),
    ...contextOverrides,
  };

  return {
    tasksApi: {
      async listTasks() {
        return { items: [task], next_cursor: null };
      },
      async getTask() {
        return task;
      },
      async getTaskContext() {
        return contextPackage;
      },
    },
  };
}

export function apiWithProposal(proposalOverrides: Partial<KnowledgeProposal> = {}): MockApiOptions {
  const proposal: KnowledgeProposal = {
    id: "prop-1",
    project_id: "project-1",
    session_id: "sess-1",
    type: "bug_pattern",
    title: "Normalize payment_method_invalid in PaymentService",
    content: "When PaymentService returns payment_method_invalid, wrap in PaymentMethodInvalidError.",
    confidence: 0.92,
    evidence: [{ message_id: "msg-1", source: "Slack" }],
    status: "pending",
    created_at: new Date().toISOString(),
    ...proposalOverrides,
  };

  return {
    knowledgeApi: {
      async listProposals() {
        return [proposal];
      },
      async confirmProposal(id: string) {
        return { id, status: "confirmed" };
      },
      async editProposal(id: string, payload: { title?: string; content?: string }) {
        return { id, status: "edited" };
      },
      async rejectProposal(id: string) {
        return { id, status: "rejected" };
      },
      async listKnowledge() {
        return { items: [], warnings: [] };
      },
    },
  };
}

export function apiWithRetryConflict(conflictOverrides: Partial<Conflict> = {}): MockApiOptions {
  const conflict: Conflict = {
    id: "c1",
    project_id: "project-1",
    type: "contradiction",
    severity: "high",
    state: "unresolved",
    claim_a: "Retry payment three times",
    claim_b: "Retries were reduced to one",
    source_a: "PaymentService v1 PRD",
    source_b: "Checkout Architecture Decision 004",
    overlap_score: 0.85,
    evidence_comparison: [
      {
        label: "Retry Count",
        claim_a_evidence: "PRD §4.2: Payment service should retry up to 3 times on network timeout.",
        claim_b_evidence: "ADR-004: Payment retries reduced to 1 to prevent card network penalties.",
      },
    ],
    created_at: new Date().toISOString(),
    ...conflictOverrides,
  };

  return {
    conflictsApi: {
      async listConflicts() {
        return [conflict];
      },
      async getConflict() {
        return conflict;
      },
      async resolveConflict(id: string, payload) {
        return {
          ...conflict,
          state: "resolved",
          resolution: {
            action: payload.action,
            note: payload.note,
            resolved_by: "human_reviewer",
            resolved_at: new Date().toISOString(),
          },
        };
      },
    },
  };
}
