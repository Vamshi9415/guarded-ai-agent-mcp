import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../api'

export const HEALTH_QUERY_KEY = ['health'] as const

export function useHealth() {
  return useQuery({
    queryKey: HEALTH_QUERY_KEY,
    queryFn: getHealth,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    staleTime: 20_000,
  })
}
