import { useQuery } from '@tanstack/react-query';
import { listLogs } from '../api';

export const LOGS_QUERY_KEY = ['logs'] as const;

export function useLogs(conversationId?: string) {
  return useQuery({
    queryKey: conversationId ? [...LOGS_QUERY_KEY, conversationId] : LOGS_QUERY_KEY,
    queryFn: () => listLogs(conversationId),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}
