export type AccessLevel = 'owner' | 'editor' | 'viewer'
export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface KnowledgeBase {
  id: string; name: string; description: string; access_level: AccessLevel
  document_count: number; created_at: string; updated_at: string
}
export interface Document {
  id: string; knowledge_base_id: string; filename: string; file_type: string | null
  file_size: number | null; storage_uri: string; checksum: string; parser_version: string
  embedding_model: string; embedding_dim: number; status: DocumentStatus; chunk_count: number
  error_message: string | null; created_at: string; processed_at: string | null
}
export interface SearchHit { chunk_id: string; document_id: string; filename: string; chunk_index: number; content: string; source_locator: string; score: number }
export interface Citation { label: string; chunk_id: string; document_id: string; filename: string; source_locator: string; chunk_index: number; score: number }
export interface Answer { answer: string; citations: Citation[]; no_evidence: boolean }
export interface ACL { subject_id: string; username: string; access_level: AccessLevel; created_at: string }
