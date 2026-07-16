import { useState, useCallback } from 'react'
import type { Conversation, Message } from '../types/chat'
import { listConversations, createConversation, listMessages } from '../api/chat'

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const loadConversations = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listConversations()
      setConversations(data)
    } finally {
      setLoading(false)
    }
  }, [])

  const selectConversation = useCallback(async (id: string) => {
    setSelectedId(id)
    setLoading(true)
    try {
      const data = await listMessages(id)
      setMessages(data)
    } finally {
      setLoading(false)
    }
  }, [])

  const newConversation = useCallback(async (title?: string) => {
    const conv = await createConversation({ title: title || 'New Conversation' })
    setConversations((prev) => [{ ...conv, message_count: 0 }, ...prev])
    return conv
  }, [])

  return {
    conversations, messages, selectedId, loading,
    loadConversations, selectConversation, newConversation, setMessages,
  }
}
