import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import type { HealthStatus } from "@gpd/contracts";

export interface AppShellProps {
  health?: HealthStatus | null;
  projectName?: string;
  defaultBranch?: string;
  children: React.ReactNode;
}

const NAV_ITEMS = [
  { path: "/", label: "Overview", icon: "📊" },
  { path: "/tasks", label: "Tasks", icon: "📋" },
  { path: "/knowledge", label: "Knowledge", icon: "📚" },
  { path: "/knowledge/review", label: "Review", icon: "🔍" },
  { path: "/sources", label: "Sources", icon: "📦" },
  { path: "/sessions", label: "Sessions", icon: "💻" },
  { path: "/conflicts", label: "Conflicts", icon: "⚔️" },
  { path: "/jobs", label: "Jobs", icon: "⚙️" },
  { path: "/settings", label: "Settings", icon: "🔧" },
];

export const AppShell: React.FC<AppShellProps> = ({
  health,
  projectName = "GPD Local",
  defaultBranch = "main",
  children,
}) => {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();

  // Close drawer on ESC key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && drawerOpen) {
        setDrawerOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [drawerOpen]);

  // Close drawer on route change
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  const isHealthy = health?.status === "ok" && health?.database !== "error";
  const searchHealthy = health?.search !== "degraded" && health?.search !== "unavailable";

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        backgroundColor: "var(--color-canvas)",
        color: "var(--color-text)",
      }}
    >
      {/* Mobile Drawer Overlay */}
      {drawerOpen && (
        <div
          data-testid="drawer-overlay"
          onClick={() => setDrawerOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.7)",
            zIndex: 40,
            backdropFilter: "blur(2px)",
          }}
        />
      )}

      {/* Primary Sidebar Navigation (Desktop & Mobile Drawer) */}
      <aside
        data-testid="app-sidebar"
        aria-label="Main Navigation"
        style={{
          width: "260px",
          backgroundColor: "var(--color-surface)",
          borderRight: "1px solid var(--color-border)",
          display: "flex",
          flexDirection: "column",
          position: "sticky",
          top: 0,
          height: "100vh",
          zIndex: 50,
          transition: "transform 0.2s ease-in-out",
          ...(drawerOpen
            ? { position: "fixed", left: 0, transform: "translateX(0)" }
            : {}),
        }}
        className={drawerOpen ? "drawer-open" : "drawer-desktop"}
      >
        {/* Project Brand & Identity */}
        <div
          style={{
            padding: "var(--space-4) var(--space-5)",
            borderBottom: "1px solid var(--color-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div
              style={{
                fontSize: "var(--font-size-lg)",
                fontWeight: "var(--font-weight-bold)",
                color: "var(--color-text)",
                letterSpacing: "-0.5px",
              }}
            >
              {projectName}
            </div>
            <div
              style={{
                fontSize: "var(--font-size-xs)",
                color: "var(--color-text-muted)",
                display: "flex",
                alignItems: "center",
                gap: "var(--space-1)",
                marginTop: "2px",
              }}
            >
              <span>branch:</span>
              <code
                style={{
                  backgroundColor: "var(--color-canvas)",
                  padding: "1px 4px",
                  borderRadius: "var(--radius-sm)",
                }}
              >
                {defaultBranch}
              </code>
            </div>
          </div>
          {drawerOpen && (
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              aria-label="Close navigation drawer"
              style={{
                background: "none",
                border: "none",
                color: "var(--color-text-muted)",
                cursor: "pointer",
                padding: "var(--space-2)",
              }}
            >
              ✕
            </button>
          )}
        </div>

        {/* Navigation Links */}
        <nav
          style={{
            padding: "var(--space-4) var(--space-3)",
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-1)",
          }}
        >
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.path);

            return (
              <Link
                key={item.path}
                to={item.path}
                className="nav-link"
                aria-current={isActive ? "page" : undefined}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-3)",
                  padding: "var(--space-2) var(--space-3)",
                  borderRadius: "var(--radius-md)",
                  color: isActive ? "var(--color-text)" : "var(--color-text-secondary)",
                  backgroundColor: isActive
                    ? "var(--color-surface-active)"
                    : "transparent",
                  fontWeight: isActive
                    ? "var(--font-weight-semibold)"
                    : "var(--font-weight-normal)",
                  textDecoration: "none",
                  borderLeft: isActive
                    ? "3px solid var(--color-primary)"
                    : "3px solid transparent",
                }}
              >
                <span aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* System & Health Status Indicator */}
        <div
          data-testid="health-indicator"
          style={{
            padding: "var(--space-4) var(--space-5)",
            borderTop: "1px solid var(--color-border)",
            backgroundColor: "var(--color-canvas-subtle)",
            fontSize: "var(--font-size-xs)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "var(--space-1)",
            }}
          >
            <span style={{ color: "var(--color-text-muted)" }}>Backend</span>
            <span
              className={`badge ${isHealthy ? "badge-success" : "badge-danger"}`}
              style={{ padding: "1px 6px" }}
            >
              {health ? (isHealthy ? "Healthy" : "Degraded") : "Connecting..."}
            </span>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span style={{ color: "var(--color-text-muted)" }}>Search (FTS/Vec)</span>
            <span
              className={`badge ${searchHealthy ? "badge-success" : "badge-warning"}`}
              style={{ padding: "1px 6px" }}
            >
              {health?.search || "Active"}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}
      >
        {/* Top Header with Mobile Hamburger */}
        <header
          style={{
            height: "56px",
            borderBottom: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 var(--space-6)",
            position: "sticky",
            top: 0,
            zIndex: 30,
          }}
        >
          <button
            type="button"
            className="mobile-menu-btn"
            onClick={() => setDrawerOpen(!drawerOpen)}
            aria-label="Open navigation menu"
            aria-expanded={drawerOpen}
            style={{
              background: "none",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-md)",
              color: "var(--color-text)",
              padding: "var(--space-2)",
              display: "none",
            }}
          >
            ☰
          </button>

          <div
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-muted)",
            }}
          >
            GPD Local Operations Platform
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
            }}
          >
            <span
              className={`badge ${isHealthy ? "badge-success" : "badge-warning"}`}
            >
              ● {health?.status === "ok" ? "Connected" : "Standby"}
            </span>
          </div>
        </header>

        {/* Page Content */}
        <main
          id="main-content"
          style={{
            flex: 1,
            padding: "var(--space-6) var(--space-8)",
            maxWidth: "1400px",
            width: "100%",
            margin: "0 auto",
          }}
        >
          {children}
        </main>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .drawer-desktop {
            display: none !important;
          }
          .drawer-open {
            display: flex !important;
          }
          .mobile-menu-btn {
            display: inline-flex !important;
          }
        }
      `}</style>
    </div>
  );
};
