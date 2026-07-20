import { useState } from 'react'
import type { Answer } from '../types/knowledge'

export default function KnowledgeQuestion({ onAsk, answer }: { onAsk: (question: string) => Promise<void>; answer: Answer | null }) {
  const [question, setQuestion] = useState('')
  return <section className="p-5"><h2 className="mb-3 font-semibold">Ask this knowledge base</h2><form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (question.trim()) void onAsk(question.trim()) }}><input value={question} onChange={(e) => setQuestion(e.target.value)} className="min-w-0 flex-1 rounded border border-gray-300 px-3 py-2 text-sm" placeholder="Ask a question" /><button className="rounded bg-gray-900 px-4 py-2 text-sm text-white">Ask</button></form>{answer && <div className="mt-4 whitespace-pre-wrap text-sm">{answer.answer}{!answer.no_evidence && <div className="mt-3 flex flex-wrap gap-2">{answer.citations.map((citation) => <a key={citation.label} href={`#chunk-${citation.chunk_id}`} className="text-blue-700 underline">{citation.label} {citation.filename} · {citation.source_locator}</a>)}</div>}</div>}</section>
}
