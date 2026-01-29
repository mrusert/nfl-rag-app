/**
 * React Query hook for semantic search.
 */

import { useMutation } from '@tanstack/react-query';
import { searchApi } from '../api/client';
import type { SearchRequest, SearchResponse } from '../types/api';

/**
 * Hook for performing semantic searches.
 */
export function useSearchMutation() {
  return useMutation<SearchResponse, Error, SearchRequest>({
    mutationFn: searchApi,
  });
}
