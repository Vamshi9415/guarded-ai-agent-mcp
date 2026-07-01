import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getBudget, getConversationBudgetState, getDefaultBudget, listBudgets, resetBudget, updateBudget } from '../api';
import type { BudgetUpdate } from '../types/budgets';

export const BUDGETS_QUERY_KEY = ['budgets'] as const;

export function useBudgets() {
  return useQuery({
    queryKey: BUDGETS_QUERY_KEY,
    queryFn: async () => {
      const [defaultBudget, budgets] = await Promise.all([
        getDefaultBudget(),
        listBudgets(),
      ]);
      return [defaultBudget, ...budgets];
    },
    staleTime: 10_000,
  });
}

export function useBudget(conversationId: string | undefined) {
  return useQuery({
    queryKey: [...BUDGETS_QUERY_KEY, conversationId] as const,
    queryFn: () => getBudget(conversationId as string),
    enabled: Boolean(conversationId),
  });
}

export function useBudgetState(conversationId: string | undefined) {
  return useQuery({
    queryKey: [...BUDGETS_QUERY_KEY, conversationId, 'state'] as const,
    queryFn: () => getConversationBudgetState(conversationId as string),
    enabled: Boolean(conversationId),
    staleTime: 10_000,
  });
}

export function useUpdateBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ conversationId, payload }: { conversationId: string; payload: BudgetUpdate }) =>
      updateBudget(conversationId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: BUDGETS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: [...BUDGETS_QUERY_KEY, variables.conversationId] });
    },
  });
}

export function useResetBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) => resetBudget(conversationId),
    onSuccess: (_, conversationId) => {
      queryClient.invalidateQueries({ queryKey: BUDGETS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: [...BUDGETS_QUERY_KEY, conversationId] });
    },
  });
}
