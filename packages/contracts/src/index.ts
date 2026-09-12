export type ApiError = {
  code: string;
  message: string;
  retryable: boolean;
  fields?: Record<string, string>;
};

export type ApiEnvelope<T> = {
  ok: boolean;
  data: T | null;
  warnings: string[];
  error: ApiError | null;
};

export type GpdConfig = {
  apiUrl: string;
  projectId: string;
  repositoryId: string;
  currentTaskId: string | null;
  agentAdapter?: AgentAdapter;
};

export type AgentAdapter =
  | { kind: "args"; flag: string }
  | { kind: "stdin" };

export type GitSnapshot = {
  root?: string;
  branch: string;
  changed_files: string[];
  recent_commits: string[];
  remote_url?: string | null;
};

export type Project = {
  id: string;
  name: string;
  team_identifier?: string | null;
  created_at: string;
  repositories?: Repository[];
};

export type Repository = {
  id: string;
  project_id: string;
  root_path: string;
  remote_url?: string | null;
  default_branch: string;
};

export type TaskPriority = "low" | "medium" | "high" | "critical";
export type TaskStatus = "todo" | "in_progress" | "blocked" | "in_review" | "done" | "cancelled";

export type Task = {
  id: string;
  project_id: string;
  public_id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  acceptance_criteria?: string | null;
  created_at: string;
  updated_at?: string;
  bug_details?: BugDetails | null;
};

export type ExtractedField<T = string> = {
  value: T;
  confidence: number;
  evidence: string[];
};

export type BugDetails = {
  task_id: string;
  summary: ExtractedField;
  reproduction_steps: ExtractedField<string[]>;
  actual_behavior: ExtractedField;
  expected_behavior: ExtractedField;
  environment?: ExtractedField<string | null>;
  severity: ExtractedField<"low" | "medium" | "high" | "critical">;
  affected_component?: ExtractedField<string | null>;
  technical_clues?: ExtractedField<string[]>;
  participants?: ExtractedField<string[]>;
};

export type OverlapWarning = {
  severity: "low" | "medium" | "high";
  explanation: string;
  suggested_action: string;
  evidence: Array<{
    type: string;
    id: string;
    score: number;
  }>;
};

export type DeveloperSession = {
  id: string;
  project_id: string;
  task_id: string | null;
  status: "active" | "finished" | "abandoned";
  git_branch?: string | null;
  last_heartbeat_at?: string | null;
  created_at: string;
  overlap_warnings?: OverlapWarning[];
};

export type ContextEntry = {
  id: string;
  section: string;
  content: string;
  score: number;
  score_explanation?: string;
};

export type ContextPackage = {
  id: string;
  session_id: string;
  task_id: string | null;
  token_budget: number;
  token_count: number;
  markdown_content: string;
  sections: ContextEntry[];
  warnings: string[];
  created_at: string;
};

export type KnowledgeProposal = {
  id: string;
  project_id: string;
  session_id?: string | null;
  type: string;
  title: string;
  content: string;
  confidence: number;
  evidence: Array<Record<string, unknown>>;
  status: "pending" | "confirmed" | "rejected" | "edited";
  created_at: string;
};

export type KnowledgeItem = {
  id: string;
  project_id: string;
  type: string;
  title: string;
  content: string;
  status: "active" | "superseded" | "deprecated";
  created_at: string;
};

export type HealthStatus = {
  status: string;
  version: string;
  database: string;
  search?: string;
  git?: string;
  slack?: boolean;
  llm?: boolean;
};

export type ProjectSettings = {
  name: string;
  team_identifier?: string | null;
  default_branch: string;
  llm_model: string;
  embedding_model: string;
  context_token_budget: number;
  slack_configured?: boolean;
  llm_configured?: boolean;
};
