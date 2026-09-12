import React from "react";
import { Routes, Route } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { useApp } from "./providers";
import { OverviewPage } from "../pages/OverviewPage";
import { TasksPage } from "../pages/TasksPage";
import { TaskDetailPage } from "../pages/TaskDetailPage";
import { KnowledgePage } from "../pages/KnowledgePage";
import { KnowledgeReviewPage } from "../pages/KnowledgeReviewPage";
import { SourcesPage } from "../pages/SourcesPage";
import { SourceDetailPage } from "../pages/SourceDetailPage";
import { SessionsPage } from "../pages/SessionsPage";
import { ConflictsPage } from "../pages/ConflictsPage";
import { ConflictDetailPage } from "../pages/ConflictDetailPage";
import { JobsPage } from "../pages/JobsPage";
import { SettingsPage } from "../pages/SettingsPage";

export const AppRoutes: React.FC = () => {
  const { health } = useApp();

  return (
    <AppShell health={health}>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/tasks" element={<TasksPage />} />
        <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/knowledge/review" element={<KnowledgeReviewPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/sources/:sourceId" element={<SourceDetailPage />} />
        <Route path="/sessions" element={<SessionsPage />} />
        <Route path="/conflicts" element={<ConflictsPage />} />
        <Route path="/conflicts/:conflictId" element={<ConflictDetailPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route
          path="*"
          element={
            <div style={{ padding: "var(--space-8)", textAlign: "center" }}>
              <h2>404 - Page Not Found</h2>
              <p style={{ color: "var(--color-text-muted)", marginTop: "var(--space-2)" }}>
                The page you are looking for does not exist.
              </p>
            </div>
          }
        />
      </Routes>
    </AppShell>
  );
};
