import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useChat } from '../hooks/useChat'
import ConversationList from '../components/ConversationList'
import MessageList from '../components/MessageList'
import { Link } from 'react-router-dom'

export default function Chat() {
  const { user, logout } = useAuth()
  const { conversations, messages, selectedId, loading, error, loadConversations, selectConversation, newConversation, sendMessage } = useChat()
  const [content, setContent] = useState('')

  useEffect(() => { loadConversations() }, [loadConversations])

  const handleNew = async () => {
    const conv = await newConversation()
    selectConversation(conv.id)
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 shadow-sm">
          <h1 className="text-lg font-semibold text-gray-800">Enterprise AI Platform</h1>
          <Link to="/knowledge" className="text-sm text-blue-700">Knowledge</Link>
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
          <MessageList messages={messages} loading={loading && !!selectedId} error={error} />
          {selectedId && (
            <form
              className="border-t border-gray-200 p-4"
              onSubmit={(event) => {
                event.preventDefault()
                if (!content.trim() || loading) return
                void sendMessage(content.trim())
                setContent('')
              }}
            >
              <div className="flex gap-2">
                <textarea
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      event.currentTarget.form?.requestSubmit()
                    }
                  }}
                  disabled={loading}
                  rows={2}
                  placeholder="Write a message..."
                  className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={loading || !content.trim()}
                  className="self-end rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Send
                </button>
              </div>
              {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
            </form>
          )}
        </main>
      </div>
    </div>
  )
}
