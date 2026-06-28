import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createRule,
  deleteRule,
  getRule,
  listRules,
  updateRule,
} from '../api'
import type { RuleCreate, RuleUpdate } from '../types/rules'

export const RULES_QUERY_KEY = ['rules'] as const

export function useRules() {
  return useQuery({
    queryKey: RULES_QUERY_KEY,
    queryFn: listRules,
    staleTime: 10_000,
  })
}

export function useRule(ruleId: string | undefined) {
  return useQuery({
    queryKey: [...RULES_QUERY_KEY, ruleId] as const,
    queryFn: () => getRule(ruleId as string),
    enabled: Boolean(ruleId),
  })
}

export function useCreateRule() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: RuleCreate) => createRule(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: RULES_QUERY_KEY })
    },
  })
}

export function useUpdateRule() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      ruleId,
      payload,
    }: {
      ruleId: string
      payload: RuleUpdate
    }) => updateRule(ruleId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: RULES_QUERY_KEY })
      queryClient.invalidateQueries({
        queryKey: [...RULES_QUERY_KEY, variables.ruleId],
      })
    },
  })
}

export function useDeleteRule() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (ruleId: string) => deleteRule(ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: RULES_QUERY_KEY })
    },
  })
}
