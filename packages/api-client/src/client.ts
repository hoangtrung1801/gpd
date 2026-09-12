function generateUuid(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (
      Number(c) ^
      (globalThis.crypto?.getRandomValues(new Uint8Array(1))[0] ?? Math.floor(Math.random() * 256) & (15 >> (Number(c) / 4)))
    ).toString(16)
  );
}
import type {
  ApiEnvelope,
  ApiError,
  ContextPackage,
  DeveloperSession,
  GitSnapshot,
  HealthStatus,
  KnowledgeProposal,
  Project,
  ProjectSettings,
  Repository,
  Task,
} from "@gpd/contracts";

export const EXIT_CODES = {
  SUCCESS: 0,
  UNEXPECTED: 1,
  VALIDATION: 2,
  CONFIGURATION: 3,
  UNAVAILABLE: 4,
  CONFLICT: 5,
} as const;

export type ExitCode = (typeof EXIT_CODES)[keyof typeof EXIT_CODES];

export function mapErrorCodeToExitCode(code?: string, status?: number): ExitCode {
  if (code) {
    const normalized = code.toLowerCase();
    if (
      normalized.includes("validation") ||
      normalized.includes("invalid") ||
      normalized.includes("bad_request") ||
      normalized === "unprocessable_entity"
    ) {
      return EXIT_CODES.VALIDATION;
    }
    if (
      normalized.includes("config") ||
      normalized.includes("unauthorized") ||
      normalized.includes("forbidden") ||
      normalized.includes("permission") ||
      normalized.includes("auth")
    ) {
      return EXIT_CODES.CONFIGURATION;
    }
    if (
      normalized.includes("unavailable") ||
      normalized.includes("not_found") ||
      normalized.includes("timeout") ||
      normalized.includes("unreachable") ||
      normalized.includes("connection")
    ) {
      return EXIT_CODES.UNAVAILABLE;
    }
    if (
      normalized.includes("conflict") ||
      normalized.includes("idempotency_conflict") ||
      normalized.includes("already_exists")
    ) {
      return EXIT_CODES.CONFLICT;
    }
  }

  if (status !== undefined) {
    if (status === 400 || status === 422) {
      return EXIT_CODES.VALIDATION;
    }
    if (status === 401 || status === 403) {
      return EXIT_CODES.CONFIGURATION;
    }
    if (status === 404 || status === 502 || status === 503 || status === 504) {
      return EXIT_CODES.UNAVAILABLE;
    }
    if (status === 409) {
      return EXIT_CODES.CONFLICT;
    }
    if (status >= 500) {
      return EXIT_CODES.UNEXPECTED;
    }
  }

  return EXIT_CODES.UNEXPECTED;
}

export class ApiClientError extends Error {
  readonly exitCode: ExitCode;
  readonly code: string;
  readonly retryable: boolean;
  readonly fields?: Record<string, string>;
  readonly envelope?: ApiEnvelope<unknown>;
  readonly status?: number;

  constructor(options: {
    message: string;
    code?: string;
    status?: number;
    retryable?: boolean;
    fields?: Record<string, string>;
    envelope?: ApiEnvelope<unknown>;
    cause?: unknown;
  }) {
    super(options.message);
    this.name = "ApiClientError";
    this.status = options.status;
    this.code = options.code ?? "UNEXPECTED_ERROR";
    this.retryable = options.retryable ?? false;
    this.fields = options.fields;
    this.envelope = options.envelope;
    this.exitCode = mapErrorCodeToExitCode(this.code, this.status);
    if (options.cause) {
      this.cause = options.cause;
    }
  }
}

export type ApiClientOptions = {
  baseUrl: string;
  timeoutMs?: number;
  fetch?: typeof fetch;
  headers?: Record<string, string>;
};

export type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
  headers?: Record<string, string>;
  idempotencyKey?: string | false;
  timeoutMs?: number;
  rawText?: boolean;
};

export class ApiClient {
  readonly baseUrl: string;
  readonly defaultTimeoutMs: number;
  private readonly fetchImpl: typeof fetch;
  private readonly defaultHeaders: Record<string, string>;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.defaultTimeoutMs = options.timeoutMs ?? 10_000;
    this.fetchImpl = options.fetch ?? globalThis.fetch;
    this.defaultHeaders = options.headers ?? {};
  }

  async request<T>(options: RequestOptions): Promise<ApiEnvelope<T>> {
    const method = options.method ?? "GET";
    const timeout = options.timeoutMs ?? this.defaultTimeoutMs;

    let urlStr = `${this.baseUrl}${options.path.startsWith("/") ? options.path : `/${options.path}`}`;
    if (options.query) {
      const sp = new URLSearchParams();
      for (const [k, v] of Object.entries(options.query)) {
        if (v !== undefined && v !== null) {
          sp.append(k, String(v));
        }
      }
      const qs = sp.toString();
      if (qs) {
        urlStr += (urlStr.includes("?") ? "&" : "?") + qs;
      }
    }

    const headers: Record<string, string> = {
      Accept: "application/json",
      ...this.defaultHeaders,
      ...options.headers,
    };

    const isMutation = method === "POST" || method === "PUT" || method === "PATCH" || method === "DELETE";
    if (isMutation && options.idempotencyKey !== false) {
      headers["Idempotency-Key"] = options.idempotencyKey || generateUuid();
    }

    let requestBody: string | undefined;
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      requestBody = JSON.stringify(options.body);
    }

    const controller = new AbortController();
    let timeoutId: NodeJS.Timeout | undefined;
    let didTimeout = false;

    if (timeout > 0) {
      timeoutId = setTimeout(() => {
        didTimeout = true;
        controller.abort();
      }, timeout);
    }

    let response: Response;
    try {
      response = await this.fetchImpl(urlStr, {
        method,
        headers,
        body: requestBody,
        signal: controller.signal,
      });
    } catch (err: unknown) {
      if (didTimeout) {
        throw new ApiClientError({
          message: `Request to ${urlStr} timed out after ${timeout}ms`,
          code: "TIMEOUT",
          status: 504,
          retryable: true,
          cause: err,
        });
      }
      const message = err instanceof Error ? err.message : String(err);
      throw new ApiClientError({
        message: `Failed to connect to ${urlStr}: ${message}`,
        code: "CONNECTION_UNAVAILABLE",
        status: 503,
        retryable: true,
        cause: err,
      });
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    }

    if (options.rawText) {
      const text = await response.text();
      if (!response.ok) {
        throw new ApiClientError({
          message: `HTTP ${response.status}: ${text}`,
          status: response.status,
          code: "HTTP_ERROR",
        });
      }
      return {
        ok: true,
        data: text as unknown as T,
        warnings: [],
        error: null,
      };
    }

    let rawJson: unknown = null;
    const responseText = await response.text();
    if (responseText.trim()) {
      try {
        rawJson = JSON.parse(responseText);
      } catch {
        rawJson = null;
      }
    }

    if (rawJson && typeof rawJson === "object" && "ok" in rawJson) {
      const envelope = rawJson as ApiEnvelope<T>;
      if (!envelope.ok || !response.ok) {
        throw new ApiClientError({
          message: envelope.error?.message ?? `API request failed with status ${response.status}`,
          code: envelope.error?.code ?? (response.status === 409 ? "CONFLICT" : "API_ERROR"),
          status: response.status,
          retryable: envelope.error?.retryable ?? false,
          fields: envelope.error?.fields,
          envelope: envelope as ApiEnvelope<unknown>,
        });
      }
      return envelope;
    }

    if (!response.ok) {
      throw new ApiClientError({
        message: `HTTP ${response.status}: ${responseText || response.statusText}`,
        status: response.status,
        code: response.status === 409 ? "CONFLICT" : response.status === 404 ? "NOT_FOUND" : "HTTP_ERROR",
      });
    }

    return {
      ok: true,
      data: rawJson as T,
      warnings: [],
      error: null,
    };
  }

  // Health
  async getHealth(): Promise<ApiEnvelope<HealthStatus>> {
    return this.request<HealthStatus>({ path: "/health" });
  }

  async getLiveHealth(): Promise<ApiEnvelope<HealthStatus>> {
    return this.request<HealthStatus>({ path: "/health/live" });
  }

  async getReadyHealth(): Promise<ApiEnvelope<HealthStatus>> {
    return this.request<HealthStatus>({ path: "/health/ready" });
  }

  // Projects
  async listProjects(): Promise<ApiEnvelope<Project[]>> {
    return this.request<Project[]>({ path: "/api/v1/projects" });
  }

  async getProject(projectId: string): Promise<ApiEnvelope<Project>> {
    return this.request<Project>({ path: `/api/v1/projects/${projectId}` });
  }

  async registerProject(
    payload: {
      name: string;
      repository_root: string;
      team_identifier?: string | null;
      remote_url?: string | null;
      default_branch?: string;
    },
    idempotencyKey?: string
  ): Promise<ApiEnvelope<Project>> {
    return this.request<Project>({
      method: "POST",
      path: "/api/v1/projects",
      body: payload,
      idempotencyKey,
    });
  }

  // Sources
  async addSource(
    projectId: string,
    payload: {
      type: string;
      title: string;
      content: string;
      file_path?: string;
    },
    idempotencyKey?: string
  ): Promise<ApiEnvelope<{ id: string; state: string }>> {
    return this.request<{ id: string; state: string }>({
      method: "POST",
      path: `/api/v1/projects/${projectId}/sources`,
      body: payload,
      idempotencyKey,
    });
  }

  // Tasks
  async listTasks(query?: {
    project_id?: string;
    status?: string;
    type?: string;
    assignee?: string;
    query?: string;
    cursor?: string;
    limit?: number;
  }): Promise<ApiEnvelope<{ items: Task[]; next_cursor?: string | null }>> {
    return this.request<{ items: Task[]; next_cursor?: string | null }>({
      path: "/api/v1/tasks",
      query,
    });
  }

  async getTask(taskRef: string): Promise<ApiEnvelope<Task>> {
    return this.request<Task>({ path: `/api/v1/tasks/${taskRef}` });
  }

  // Sessions
  async startSession(
    payload: {
      project_id: string;
      task_id?: string | null;
      git_branch?: string | null;
      git_snapshot?: GitSnapshot;
    },
    idempotencyKey?: string
  ): Promise<ApiEnvelope<DeveloperSession>> {
    return this.request<DeveloperSession>({
      method: "POST",
      path: "/api/v1/sessions",
      body: payload,
      idempotencyKey,
    });
  }

  async heartbeatSession(
    sessionId: string,
    payload?: { changed_files?: string[]; git_branch?: string }
  ): Promise<ApiEnvelope<{ last_heartbeat_at: string }>> {
    // heartbeat is safe-retry, no idempotency key
    return this.request<{ last_heartbeat_at: string }>({
      method: "POST",
      path: `/api/v1/sessions/${sessionId}/heartbeat`,
      body: payload ?? {},
      idempotencyKey: false,
    });
  }

  async getSession(sessionId: string): Promise<ApiEnvelope<DeveloperSession>> {
    return this.request<DeveloperSession>({ path: `/api/v1/sessions/${sessionId}` });
  }

  async listSessions(projectId: string): Promise<ApiEnvelope<DeveloperSession[]>> {
    return this.request<DeveloperSession[]>({
      path: "/api/v1/sessions",
      query: { project_id: projectId },
    });
  }

  async finishSession(
    sessionId: string,
    payload?: {
      changed_files?: string[];
      commit_summaries?: string[];
      summary?: string;
    },
    idempotencyKey?: string
  ): Promise<ApiEnvelope<{ session: DeveloperSession; proposals: KnowledgeProposal[] }>> {
    return this.request<{ session: DeveloperSession; proposals: KnowledgeProposal[] }>({
      method: "POST",
      path: `/api/v1/sessions/${sessionId}/finish`,
      body: payload ?? {},
      idempotencyKey,
    });
  }

  // Context
  async getContext(
    sessionId: string,
    format: "json" | "text" = "json"
  ): Promise<ApiEnvelope<ContextPackage | string>> {
    if (format === "text") {
      return this.request<string>({
        path: `/api/v1/sessions/${sessionId}/context`,
        query: { format: "text" },
        rawText: true,
      });
    }
    return this.request<ContextPackage>({
      path: `/api/v1/sessions/${sessionId}/context`,
      query: { format: "json" },
    });
  }

  // Knowledge Proposals
  async listKnowledgeProposals(
    projectId: string,
    status?: string
  ): Promise<ApiEnvelope<KnowledgeProposal[]>> {
    return this.request<KnowledgeProposal[]>({
      path: "/api/v1/knowledge/proposals",
      query: { project_id: projectId, status },
    });
  }

  async confirmProposal(
    proposalId: string,
    idempotencyKey?: string
  ): Promise<ApiEnvelope<{ id: string; status: string }>> {
    return this.request<{ id: string; status: string }>({
      method: "POST",
      path: `/api/v1/knowledge/proposals/${proposalId}/confirm`,
      idempotencyKey,
    });
  }

  async editProposal(
    proposalId: string,
    payload: { title?: string; content?: string },
    idempotencyKey?: string
  ): Promise<ApiEnvelope<{ id: string; status: string }>> {
    return this.request<{ id: string; status: string }>({
      method: "POST",
      path: `/api/v1/knowledge/proposals/${proposalId}/edit`,
      body: payload,
      idempotencyKey,
    });
  }

  async rejectProposal(
    proposalId: string,
    payload?: { reason?: string },
    idempotencyKey?: string
  ): Promise<ApiEnvelope<{ id: string; status: string }>> {
    return this.request<{ id: string; status: string }>({
      method: "POST",
      path: `/api/v1/knowledge/proposals/${proposalId}/reject`,
      body: payload ?? {},
      idempotencyKey,
    });
  }

  // Search
  async search(
    projectId: string,
    query: string,
    limit?: number
  ): Promise<ApiEnvelope<{ hits: Array<{ id: string; title: string; snippet: string; score: number }>; warnings: string[] }>> {
    return this.request<{ hits: Array<{ id: string; title: string; snippet: string; score: number }>; warnings: string[] }>({
      path: `/api/v1/projects/${projectId}/search`,
      query: { q: query, limit },
    });
  }

  // Settings
  async getSettings(projectId: string): Promise<ApiEnvelope<ProjectSettings>> {
    return this.request<ProjectSettings>({
      path: `/api/v1/projects/${projectId}/settings`,
    });
  }

  async patchSettings(
    projectId: string,
    settings: Partial<ProjectSettings>,
    idempotencyKey?: string
  ): Promise<ApiEnvelope<ProjectSettings>> {
    return this.request<ProjectSettings>({
      method: "PATCH",
      path: `/api/v1/projects/${projectId}/settings`,
      body: settings,
      idempotencyKey,
    });
  }

  // Slack integration status
  async getSlackStatus(): Promise<ApiEnvelope<{ configured: boolean; installed: boolean }>> {
    return this.request<{ configured: boolean; installed: boolean }>({
      path: "/api/v1/integrations/slack/status",
    });
  }
}
