import { useEffect, useRef } from 'react'
import type { Message } from '../types/chat'

interface Props {
  messages: Message[]
  loading: boolean
}

export default function MessageList({ messages, loading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400">Loading messages...</p>
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400">No messages yet. Start a conversation!</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((m) => (
        <div
          key={m.id}
          className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[70%] px-4 py-2 rounded-2xl text-sm ${
              m.role === 'user'
                ? 'bg-blue-600 text-white rounded-br-sm'
                : 'bg-gray-200 text-gray-800 rounded-bl-sm'
            }`}
          >
            {m.content}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
