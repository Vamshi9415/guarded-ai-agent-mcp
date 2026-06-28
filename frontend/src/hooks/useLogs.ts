import { useQuery } from '@tanstack/react-query'
import { listLogs } from '../api'

export const LOGS_QUERY_KEY = ['logs'] as const

export function useLogs() {
  return useQuery({
    queryKey: LOGS_QUERY_KEY,
    queryFn: listLogs,
    staleTime: 10_000,
  })
}
