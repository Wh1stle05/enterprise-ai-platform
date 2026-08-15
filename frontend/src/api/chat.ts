import client from './client'
import type { AgentTurn, Conversation, ConversationCreate, ConversationDetail, Decision, Message, ToolCall } from '../types/chat'

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

export async function sendMessage(id: string, content: string): Promise<AgentTurn> {
  const res = await client.post(`/chat/conversations/${id}/messages`, { content })
  return res.data
}

export async function listToolCalls(conversationId: string): Promise<ToolCall[]> {
  const res = await client.get(`/chat/conversations/${conversationId}/tool-calls`)
  return res.data
}

export async function decideToolCall(id: string, decision: Decision): Promise<AgentTurn> {
  const res = await client.post(`/chat/tool-calls/${id}/decision`, { confirm: decision === 'confirm' })
  return res.data
}
