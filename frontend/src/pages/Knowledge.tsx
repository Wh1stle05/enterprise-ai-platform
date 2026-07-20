import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { askKnowledgeBase, createKnowledgeBase, deleteKnowledgeBase, listDocuments, listKnowledgeBases, uploadDocument } from '../api/knowledge'
import { useAuth } from '../hooks/useAuth'
import type { Answer, Document, KnowledgeBase } from '../types/knowledge'
import DocumentPanel from '../components/DocumentPanel'
import KnowledgeList from '../components/KnowledgeList'
import KnowledgeQuestion from '../components/KnowledgeQuestion'

export default function Knowledge() {
  const { user, logout } = useAuth(); const [bases, setBases] = useState<KnowledgeBase[]>([]); const [selected, setSelected] = useState<string | null>(null); const [documents, setDocuments] = useState<Document[]>([]); const [answer, setAnswer] = useState<Answer | null>(null)
  const loadBases = useCallback(async () => { const data = await listKnowledgeBases(); setBases(data); if (!selected && data[0]) setSelected(data[0].id) }, [selected])
  const loadDocuments = useCallback(async () => { if (selected) setDocuments(await listDocuments(selected)) }, [selected])
  useEffect(() => { void loadBases() }, [loadBases]); useEffect(() => { void loadDocuments() }, [loadDocuments])
  useEffect(() => { if (!documents.some((doc) => doc.status === 'pending' || doc.status === 'processing')) return; const timer = window.setInterval(() => void loadDocuments(), 2000); return () => window.clearInterval(timer) }, [documents, loadDocuments])
  const current = bases.find((item) => item.id === selected)
  return <div className="min-h-screen bg-white"><header className="flex items-center justify-between border-b border-gray-200 px-5 py-3"><div className="flex items-center gap-5"><h1 className="font-semibold">Enterprise AI Platform</h1><Link to="/chat" className="text-sm text-blue-700">Chat</Link></div><div className="flex items-center gap-3 text-sm"><span>{user?.username}</span><button onClick={logout} className="text-red-600">Sign out</button></div></header><div className="flex min-h-[calc(100vh-57px)]"><KnowledgeList items={bases} selected={selected} onSelect={(id) => { setSelected(id); setAnswer(null) }} onCreate={async () => { const name = window.prompt('Knowledge base name'); if (name) { await createKnowledgeBase({ name, description: '' }); await loadBases() } }} /><main className="min-w-0 flex-1">{current ? <><div className="flex items-start justify-between p-5"><div><h2 className="text-xl font-semibold">{current.name}</h2><p className="text-sm text-gray-500">{current.description}</p></div>{current.access_level === 'owner' && <button className="text-sm text-red-600" onClick={async () => { await deleteKnowledgeBase(current.id); setSelected(null); await loadBases() }}>Delete</button>}</div><DocumentPanel documents={documents} canUpload={current.access_level === 'owner' || current.access_level === 'editor'} onUpload={async (file) => { await uploadDocument(current.id, file); await loadDocuments() }} /><KnowledgeQuestion answer={answer} onAsk={async (question) => setAnswer(await askKnowledgeBase(current.id, question))} /></> : <div className="p-6 text-sm text-gray-500">Create or select a knowledge base.</div>}</main></div></div>
}
