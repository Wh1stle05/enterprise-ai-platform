export interface Conversation {
  id: string
  title: string
  message_count: number
  created_at: string
}

export interface ConversationCreate {
  title?: string
}

export interface ConversationDetail {
  id: string
  title: string
  created_at: string
}

export interface Message {
  id: string
  role: string
  content: string
  created_at: string
}
