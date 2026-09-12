import { ApiClient } from "@gpd/api-client";

export type JobState =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface Job {
  id: string;
  project_id: string;
  task_id?: string | null;
  type: string;
  state: JobState;
  progress: number;
  attempts: number;
  max_attempts: number;
  error_code?: string | null;
  error_message?: string | null;
  retryable: boolean;
  created_at: string;
  updated_at?: string;
}

export interface JobFilterParams {
  project_id?: string;
  state?: JobState;
  limit?: number;
}

export interface JobsApi {
  listJobs(projectId: string, filters?: JobFilterParams): Promise<Job[]>;
  retryJob(jobId: string): Promise<Job>;
  cancelJob(jobId: string): Promise<Job>;
}

export function createJobsApi(client: ApiClient): JobsApi {
  return {
    async listJobs(projectId: string, filters?: JobFilterParams): Promise<Job[]> {
      const res = await client.request<Job[]>({
        path: `/api/v1/projects/${projectId}/jobs`,
        query: filters ? { ...filters } : undefined,
      });
      return res.data || [];
    },

    async retryJob(jobId: string): Promise<Job> {
      const res = await client.request<Job>({
        method: "POST",
        path: `/api/v1/jobs/${jobId}/retry`,
      });
      if (!res.data) {
        throw new Error(`Failed to retry job ${jobId}`);
      }
      return res.data;
    },

    async cancelJob(jobId: string): Promise<Job> {
      const res = await client.request<Job>({
        method: "POST",
        path: `/api/v1/jobs/${jobId}/cancel`,
      });
      if (!res.data) {
        throw new Error(`Failed to cancel job ${jobId}`);
      }
      return res.data;
    },
  };
}
