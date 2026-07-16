import client from './client'
import type { Conversation, ConversationCreate, ConversationDetail, Message } from '../types/chat'

export async function listConversations(limit = 50, offset = 0): Promise<Conversation[]> {
  const res = await client.get('/chat/conversations', { params: { limit, offset } })
  return res.data
}

export async function createConversation(data: ConversationCreate): Promise<ConversationDetail> {
  const res = await client.post('/chat/conversations', data)
  return res.data
}

export async function listMessages(conversationId: string): Promise<Message[]> {
  const res = await client.get(`/chat/conversations/${conversationId}/messages`)
  return res.data
}
