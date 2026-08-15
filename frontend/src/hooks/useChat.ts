import { useState, useCallback } from 'react'
import type { Conversation, Message, ToolCall, Decision } from '../types/chat'
import { listConversations, createConversation, listMessages, listToolCalls, decideToolCall as postDecision, sendMessage as postMessage } from '../api/chat'

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([])
  const [pendingCall, setPendingCall] = useState<ToolCall | null>(null)
  const [deciding, setDeciding] = useState(false)
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
      const [data, activity] = await Promise.all([listMessages(id), listToolCalls(id)])
      setMessages(data)
      setToolCalls(activity)
      setPendingCall(null)
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
      if (data.messages) setMessages(data.messages)
      else setMessages((current) => [...current, {
        id: `user-${data.run_id}-${Date.now()}`,
        role: 'user', content, created_at: new Date().toISOString(),
      }])
      if (data.answer) {
        const answer = data.answer
        setMessages((current) => [...current, {
          id: `turn-${data.run_id}`,
          role: 'assistant',
          content: answer,
          created_at: new Date().toISOString(),
        }])
      }
      if (data.tool_call) {
        setToolCalls((current) => [...current.filter((call) => call.id !== data.tool_call?.id), data.tool_call as ToolCall])
        setPendingCall(null)
      }
      await loadConversations()
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to send message')
    } finally {
      setLoading(false)
    }
  }, [selectedId, loadConversations])

  const reviewToolCall = useCallback((call: ToolCall) => {
    if (call.status === 'pending_confirmation' && call.side_effect === 'write') setPendingCall(call)
  }, [])

  const closeReview = useCallback(() => setPendingCall(null), [])

  const decide = useCallback(async (decision: Decision) => {
    if (!pendingCall) return
    setDeciding(true)
    try {
      const turn = await postDecision(pendingCall.id, decision)
      const activity = await listToolCalls(pendingCall.run_id)
      setToolCalls(activity)
      setPendingCall(null)
      if (turn.answer) {
        const answer = turn.answer
        setMessages((current) => [...current, {
          id: `turn-${turn.run_id}-${Date.now()}`,
          role: 'assistant', content: answer, created_at: new Date().toISOString(),
        }])
      }
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to decide tool call')
    } finally {
      setDeciding(false)
    }
  }, [pendingCall])

  const newConversation = useCallback(async (title?: string) => {
    const conv = await createConversation({ title: title || 'New Conversation' })
    setConversations((prev) => [{ ...conv, message_count: 0 }, ...prev])
    return conv
  }, [])

  return {
    conversations, messages, toolCalls, pendingCall, deciding, selectedId, loading, error,
    loadConversations, selectConversation, newConversation, sendMessage, reviewToolCall, closeReview, decide, setMessages,
  }
}
