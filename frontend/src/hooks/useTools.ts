import { useQuery } from '@tanstack/react-query'
import { listTools } from '../api'

export const TOOLS_QUERY_KEY = ['tools'] as const

export function useTools() {
  return useQuery({
    queryKey: TOOLS_QUERY_KEY,
    queryFn: listTools,
    staleTime: 60_000,
  })
}