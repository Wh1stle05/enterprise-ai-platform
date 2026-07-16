import type { Conversation } from '../types/chat'

interface Props {
  conversations: Conversation[]
  selectedId: string | null
  onSelect: (id: string) => void
  onNew: () => void
}

export default function ConversationList({ conversations, selectedId, onSelect, onNew }: Props) {
  return (
    <aside className="w-72 bg-gray-50 border-r border-gray-200 flex flex-col h-full">
      <div className="p-3 border-b border-gray-200">
        <button
          onClick={onNew}
          className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium cursor-pointer"
        >
          + New Conversation
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => onSelect(c.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition cursor-pointer ${
              selectedId === c.id
                ? 'bg-blue-100 text-blue-800 font-medium'
                : 'text-gray-700 hover:bg-gray-200'
            }`}
          >
            <div className="truncate">{c.title}</div>
            <div className="text-xs text-gray-400 mt-0.5">
              {c.message_count} messages
            </div>
          </button>
        ))}
        {conversations.length === 0 && (
          <p className="text-gray-400 text-sm text-center py-8">No conversations yet</p>
        )}
      </nav>
    </aside>
  )
}
