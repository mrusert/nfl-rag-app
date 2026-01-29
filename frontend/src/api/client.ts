/**
 * API client for the NFL RAG backend.
 */

import axios from 'axios';
import type {
  QueryRequest,
  QueryResponse,
  SearchRequest,
  SearchResponse,
  HealthResponse,
  StatsResponse,
  TeamsResponse,
} from '../types/api';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000, // 2 minutes for LLM queries
});

/**
 * Send a query to the RAG pipeline.
 */
export async function queryApi(request: QueryRequest): Promise<QueryResponse> {
  const response = await api.post<QueryResponse>('/query', request);
  return response.data;
}

/**
 * Perform a semantic search without LLM generation.
 */
export async function searchApi(request: SearchRequest): Promise<SearchResponse> {
  const response = await api.post<SearchResponse>('/search', request);
  return response.data;
}

/**
 * Check the health of the API.
 */
export async function getHealth(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>('/health');
  return response.data;
}

/**
 * Get statistics about the RAG system.
 */
export async function getStats(): Promise<StatsResponse> {
  const response = await api.get<StatsResponse>('/stats');
  return response.data;
}

/**
 * Get all NFL teams organized by division.
 */
export async function getTeams(): Promise<TeamsResponse> {
  const response = await api.get<TeamsResponse>('/teams');
  return response.data;
}

/**
 * Get a specific chunk by ID.
 */
export async function getChunk(chunkId: string): Promise<{
  chunk_id: string;
  text: string;
  metadata: Record<string, unknown>;
}> {
  const response = await api.get(`/chunks/${encodeURIComponent(chunkId)}`);
  return response.data;
}

export default api;
