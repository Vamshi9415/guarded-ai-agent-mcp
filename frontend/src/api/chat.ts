import { apiClient } from './client'
import type {
  ChatRequest,
  ChatResponse,
  ConversationSummary,
} from '../types/chat'

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>('/chat', payload)
  return response.data
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const response = await apiClient.get<ConversationSummary[]>('/chat/conversations')
  return response.data
}

export async function resetConversation(
  conversationId: string,
): Promise<ConversationSummary> {
  const response = await apiClient.post<ConversationSummary>(
    `/chat/${conversationId}/reset`,
  )
  return response.data
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await apiClient.delete(`/chat/${conversationId}`)
}
