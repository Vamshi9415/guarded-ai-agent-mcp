import { useMutation, useQueryClient } from '@tanstack/react-query'
import { sendChatMessage } from '../api'
import type { ChatRequest } from '../types/chat'
import { CONVERSATIONS_QUERY_KEY } from './useConversation'

export function useSendMessage() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: ChatRequest) => sendChatMessage(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONVERSATIONS_QUERY_KEY })
    },
  })
}
