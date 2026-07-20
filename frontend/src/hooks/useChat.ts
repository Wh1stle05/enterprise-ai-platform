import { useState, useCallback } from 'react'
import type { Conversation, Message } from '../types/chat'
import { listConversations, createConversation, listMessages, sendMessage as postMessage } from '../api/chat'

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadConversations = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listConversations()
      setConversations(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load conversations')
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
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load messages')
    } finally {
      setLoading(false)
    }
  }, [])

  const sendMessage = useCallback(async (content: string) => {
    if (!selectedId) return
    setLoading(true)
    try {
      const data = await postMessage(selectedId, content)
      setMessages(data)
      await loadConversations()
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to send message')
    } finally {
      setLoading(false)
    }
  }, [selectedId, loadConversations])

  const newConversation = useCallback(async (title?: string) => {
    const conv = await createConversation({ title: title || 'New Conversation' })
    setConversations((prev) => [{ ...conv, message_count: 0 }, ...prev])
    return conv
  }, [])

  return {
    conversations, messages, selectedId, loading, error,
    loadConversations, selectConversation, newConversation, sendMessage, setMessages,
  }
}
