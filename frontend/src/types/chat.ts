export interface ChatRequest {
  conversation_id: string | null
  message: string
}

export interface ChatResponse {
  conversation_id: string
  reply: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ConversationSummary {
  conversation_id: string
  created_at: string
  message_count: number
}

export interface ConversationTranscript {
  conversation_id: string
  created_at: string
  message_count: number
  messages: ChatMessage[]
}