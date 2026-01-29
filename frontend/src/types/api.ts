/**
 * TypeScript interfaces matching the FastAPI backend models.
 */

// Source information returned with query results
export interface SourceInfo {
  chunk_id: string;
  chunk_type: string;
  score: number;
  preview: string;
  metadata: Record<string, unknown>;
}

// Request body for RAG queries
export interface QueryRequest {
  query: string;
  num_results?: number;
  temperature?: number;
  auto_filter?: boolean;
}

// Response from RAG query endpoint
export interface QueryResponse {
  answer: string;
  sources: SourceInfo[];
  query: string;
  model: string;
  retrieval_time_ms: number;
  generation_time_ms: number;
  total_time_ms: number;
}

// Request body for semantic search
export interface SearchRequest {
  query: string;
  num_results?: number;
  chunk_type?: string;
  team?: string;
  player_name?: string;
  season?: number;
}

// Response from semantic search
export interface SearchResponse {
  results: SourceInfo[];
  query: string;
  total_results: number;
  time_ms: number;
}

// Health check response
export interface HealthResponse {
  status: 'healthy' | 'degraded';
  vector_store: boolean;
  llm: boolean;
  chunk_count: number;
  model: string;
}

// Statistics response
export interface StatsResponse {
  chunk_count: number;
  chunk_types: Record<string, number>;
  embedding_model: string;
  llm_model: string;
}

// Teams organized by division
export interface TeamsResponse {
  [division: string]: {
    [abbreviation: string]: string;
  };
}

// Search filters for the UI
export interface SearchFilters {
  chunk_type?: string;
  team?: string;
  player_name?: string;
  season?: number;
}
