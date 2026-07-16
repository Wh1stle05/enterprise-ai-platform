import { useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useChat } from '../hooks/useChat'
import ConversationList from '../components/ConversationList'
import MessageList from '../components/MessageList'

export default function Chat() {
  const { user, logout } = useAuth()
  const { conversations, messages, selectedId, loading, loadConversations, selectConversation, newConversation } = useChat()

  useEffect(() => { loadConversations() }, [loadConversations])

  const handleNew = async () => {
    const conv = await newConversation()
    selectConversation(conv.id)
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 shadow-sm">
        <h1 className="text-lg font-semibold text-gray-800">Enterprise AI Platform</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{user?.username}</span>
          <button
            onClick={logout}
            className="text-sm text-red-500 hover:text-red-700 transition cursor-pointer"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <ConversationList
          conversations={conversations}
          selectedId={selectedId}
          onSelect={selectConversation}
          onNew={handleNew}
        />

        <main className="flex-1 flex flex-col bg-white">
          <MessageList messages={messages} loading={loading && !!selectedId} />
        </main>
      </div>
    </div>
  )
}
