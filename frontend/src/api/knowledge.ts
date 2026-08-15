import client from './client'
import type { ACL, Answer, Document, KnowledgeBase, SearchHit } from '../types/knowledge'

export async function listKnowledgeBases() { return (await client.get<KnowledgeBase[]>('/knowledge-bases')).data }
export async function createKnowledgeBase(payload: { name: string; description: string }) { return (await client.post<KnowledgeBase>('/knowledge-bases', payload)).data }
export async function getKnowledgeBase(id: string) { return (await client.get<KnowledgeBase>(`/knowledge-bases/${id}`)).data }
export async function deleteKnowledgeBase(id: string) { await client.delete(`/knowledge-bases/${id}`) }
export async function listDocuments(id: string) { return (await client.get<Document[]>(`/knowledge-bases/${id}/documents`)).data }
export async function uploadDocument(id: string, file: File) { const data = new FormData(); data.append('file', file); return (await client.post<Document>(`/knowledge-bases/${id}/documents`, data, { headers: { 'Content-Type': undefined } })).data }
export async function searchKnowledgeBase(id: string, query: string, top_k = 5) { return (await client.post<SearchHit[]>(`/knowledge-bases/${id}/search`, { query, top_k })).data }
export async function askKnowledgeBase(id: string, question: string, top_k = 5) { return (await client.post<Answer>(`/knowledge-bases/${id}/ask`, { question, top_k })).data }
export async function listAcl(id: string) { return (await client.get<ACL[]>(`/knowledge-bases/${id}/acl`)).data }
export async function upsertAcl(id: string, subject_id: string, access_level: string) { return (await client.put<ACL>(`/knowledge-bases/${id}/acl/${subject_id}`, { access_level })).data }
export async function deleteAcl(id: string, subject_id: string) { await client.delete(`/knowledge-bases/${id}/acl/${subject_id}`) }
