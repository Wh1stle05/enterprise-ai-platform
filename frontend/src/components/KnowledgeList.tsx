import type { KnowledgeBase } from '../types/knowledge'

export default function KnowledgeList({ items, selected, onSelect, onCreate }: { items: KnowledgeBase[]; selected: string | null; onSelect: (id: string) => void; onCreate: () => void }) {
  return <aside className="w-[280px] shrink-0 border-r border-gray-200 bg-gray-50 p-4">
    <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">Knowledge bases</h2><button onClick={onCreate} className="rounded bg-blue-600 px-2 py-1 text-sm text-white">New</button></div>
    <div className="space-y-1">{items.map((item) => <button key={item.id} onClick={() => onSelect(item.id)} className={`block w-full rounded px-3 py-2 text-left text-sm ${selected === item.id ? 'bg-blue-100' : 'hover:bg-white'}`}><span className="block font-medium">{item.name}</span><span className="text-xs text-gray-500">{item.document_count} documents · {item.access_level}</span></button>)}</div>
  </aside>
}
