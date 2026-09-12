import React from "react";

export type AsyncError =
  | Error
  | { code?: string; message: string; retryable?: boolean }
  | string;

export interface AsyncStateProps {
  loading?: boolean;
  error?: AsyncError | null;
  empty?: boolean;
  emptyTitle?: string;
  emptyMessage?: string;
  emptyAction?: React.ReactNode;
  stale?: boolean;
  staleMessage?: string;
  onRetry?: () => void;
  skeleton?: React.ReactNode;
  children?: React.ReactNode;
}

export const AsyncState: React.FC<AsyncStateProps> = ({
  loading,
  error,
  empty,
  emptyTitle = "No items found",
  emptyMessage = "There are no records matching your criteria.",
  emptyAction,
  stale,
  staleMessage = "Showing cached data. New updates may be available.",
  onRetry,
  skeleton,
  children,
}) => {
  if (loading) {
    if (skeleton) {
      return <div data-testid="async-skeleton">{skeleton}</div>;
    }
    return (
      <div
        data-testid="async-loading"
        role="status"
        aria-live="polite"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "var(--space-8)",
          gap: "var(--space-3)",
          color: "var(--color-text-muted)",
        }}
      >
        <div
          style={{
            width: "32px",
            height: "32px",
            border: "3px solid var(--color-border)",
            borderTopColor: "var(--color-focus)",
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
          }}
        />
        <span>Loading...</span>
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  if (error) {
    const message =
      typeof error === "string"
        ? error
        : "message" in error
        ? error.message
        : "An unexpected error occurred.";
    const code =
      typeof error === "object" && "code" in error ? error.code : undefined;

    return (
      <div
        data-testid="async-error"
        role="alert"
        style={{
          padding: "var(--space-5)",
          borderRadius: "var(--radius-md)",
          backgroundColor: "var(--color-danger-bg)",
          border: "1px solid var(--color-danger-border)",
          color: "var(--color-danger)",
          margin: "var(--space-4) 0",
        }}
      >
        <h4 style={{ marginBottom: "var(--space-2)", color: "var(--color-danger)" }}>
          Failed to load data {code ? `(${code})` : ""}
        </h4>
        <p style={{ color: "var(--color-text)", marginBottom: onRetry ? "var(--space-4)" : 0 }}>
          {message}
        </p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="btn btn-danger"
            aria-label="Retry loading data"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  if (empty) {
    return (
      <div
        data-testid="async-empty"
        style={{
          padding: "var(--space-10) var(--space-6)",
          textAlign: "center",
          backgroundColor: "var(--color-surface)",
          border: "1px dashed var(--color-border)",
          borderRadius: "var(--radius-lg)",
          margin: "var(--space-4) 0",
        }}
      >
        <h3 style={{ marginBottom: "var(--space-2)", color: "var(--color-text)" }}>
          {emptyTitle}
        </h3>
        <p style={{ color: "var(--color-text-muted)", marginBottom: emptyAction ? "var(--space-4)" : 0 }}>
          {emptyMessage}
        </p>
        {emptyAction && <div>{emptyAction}</div>}
      </div>
    );
  }

  return (
    <>
      {stale && (
        <div
          data-testid="async-stale"
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "var(--space-2) var(--space-4)",
            marginBottom: "var(--space-3)",
            backgroundColor: "var(--color-warning-bg)",
            border: "1px solid var(--color-warning-border)",
            borderRadius: "var(--radius-md)",
            color: "var(--color-warning)",
            fontSize: "var(--font-size-sm)",
          }}
        >
          <span>{staleMessage}</span>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              style={{
                padding: "2px 8px",
                minHeight: "32px",
                fontSize: "var(--font-size-xs)",
              }}
            >
              Refresh
            </button>
          )}
        </div>
      )}
      {children}
    </>
  );
};
