/**
 * React Query hook for health checks.
 */

import { useQuery } from '@tanstack/react-query';
import { getHealth, getStats, getTeams } from '../api/client';

/**
 * Hook for checking API health with polling.
 */
export function useHealth(enabled = true) {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30000, // Poll every 30 seconds
    retry: 1,
    enabled,
  });
}

/**
 * Hook for fetching API statistics.
 */
export function useStats(enabled = true) {
  return useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    staleTime: 60000, // Consider stale after 1 minute
    enabled,
  });
}

/**
 * Hook for fetching team list (for filters).
 */
export function useTeams() {
  return useQuery({
    queryKey: ['teams'],
    queryFn: getTeams,
    staleTime: Infinity, // Teams don't change
  });
}
