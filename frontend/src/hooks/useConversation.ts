import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteConversation,
  listConversations,
  resetConversation,
} from '../api'

export const CONVERSATIONS_QUERY_KEY = ['chat', 'conversations'] as const

export function useConversations() {
  return useQuery({
    queryKey: CONVERSATIONS_QUERY_KEY,
    queryFn: listConversations,
    staleTime: 10_000,
  })
}

export function useResetConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (conversationId: string) => resetConversation(conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONVERSATIONS_QUERY_KEY })
    },
  })
}

export function useDeleteConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (conversationId: string) => deleteConversation(conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONVERSATIONS_QUERY_KEY })
    },
  })
}
