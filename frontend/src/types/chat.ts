export interface ChatRequest {
  conversation_id: string | null
  message: string
}

export interface ChatResponse {
  conversation_id: string
  reply: string
}

export interface ConversationSummary {
  conversation_id: string
  created_at: string
  message_count: number
}