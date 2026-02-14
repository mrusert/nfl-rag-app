/**
 * React Query hook for Agent queries.
 */

import { useMutation } from '@tanstack/react-query';
import { agentApi } from '../api/client';
import type { AgentRequest, AgentResponse } from '../types/api';

/**
 * Hook for sending questions to the Agent with tools.
 */
export function useAgentMutation() {
  return useMutation<AgentResponse, Error, AgentRequest>({
    mutationFn: agentApi,
  });
}
