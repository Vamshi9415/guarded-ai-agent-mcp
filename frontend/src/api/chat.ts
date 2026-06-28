import { apiClient } from './client'
import type {
  ChatRequest,
  ChatResponse,
  ConversationTranscript,
  ConversationSummary,
} from '../types/chat'

const CHAT_REQUEST_TIMEOUT_MS = 120_000

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>('/chat', payload, {
    timeout: CHAT_REQUEST_TIMEOUT_MS,
  })
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

export async function getConversationTranscript(
  conversationId: string,
): Promise<ConversationTranscript> {
  const response = await apiClient.get<ConversationTranscript>(`/chat/${conversationId}/messages`) 
  return response.data
}
