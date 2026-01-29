/**
 * React Query hook for RAG queries.
 */

import { useMutation } from '@tanstack/react-query';
import { queryApi } from '../api/client';
import type { QueryRequest, QueryResponse } from '../types/api';

/**
 * Hook for sending queries to the RAG pipeline.
 * Uses mutation since queries are not idempotent (different results possible).
 */
export function useQueryMutation() {
  return useMutation<QueryResponse, Error, QueryRequest>({
    mutationFn: queryApi,
  });
}
