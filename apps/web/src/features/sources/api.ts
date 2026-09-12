import { ApiClient } from "@gpd/api-client";

export type SourceState =
  | "queued"
  | "parsing"
  | "indexing"
  | "ready"
  | "embedding_pending"
  | "failed";

export interface Source {
  id: string;
  project_id: string;
  content_hash: string;
  source_type: string;
  title: string;
  path_or_url?: string;
  content: string;
  state: SourceState;
  error_message?: string | null;
  chunks_count?: number;
  created_at: string;
  updated_at?: string;
}

export interface SourceFilterParams {
  project_id?: string;
  state?: SourceState;
  source_type?: string;
  limit?: number;
}

export interface SourcesApi {
  listSources(projectId: string, filters?: SourceFilterParams): Promise<Source[]>;
  getSource(sourceId: string): Promise<Source>;
  retrySource(sourceId: string): Promise<{ id: string; state: SourceState }>;
}

export function createSourcesApi(client: ApiClient): SourcesApi {
  return {
    async listSources(projectId: string, filters?: SourceFilterParams): Promise<Source[]> {
      const res = await client.request<Source[]>({
        path: `/api/v1/projects/${projectId}/sources`,
        query: filters ? { ...filters } : undefined,
      });
      return res.data || [];
    },

    async getSource(sourceId: string): Promise<Source> {
      const res = await client.request<Source>({
        path: `/api/v1/sources/${sourceId}`,
      });
      if (!res.data) {
        throw new Error(`Source ${sourceId} not found`);
      }
      return res.data;
    },

    async retrySource(sourceId: string): Promise<{ id: string; state: SourceState }> {
      const res = await client.request<{ id: string; state: SourceState }>({
        method: "POST",
        path: `/api/v1/sources/${sourceId}/retry`,
      });
      return res.data || { id: sourceId, state: "queued" };
    },
  };
}
