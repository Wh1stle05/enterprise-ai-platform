from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AccessLevel = Literal["owner", "editor", "viewer"]
DocumentStatus = Literal["pending", "processing", "ready", "failed"]


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4000)


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    name: str
    description: str
    access_level: AccessLevel
    document_count: int
    created_at: datetime
    updated_at: datetime


class ACLUpsert(BaseModel):
    access_level: AccessLevel


class ACLResponse(BaseModel):
    subject_id: UUID
    username: str
    access_level: AccessLevel
    created_at: datetime


class DocumentResponse(BaseModel):
    id: UUID
    knowledge_base_id: UUID
    filename: str
    file_type: str | None
    file_size: int | None
    storage_uri: str
    checksum: str
    parser_version: str
    embedding_model: str
    embedding_dim: int
    status: DocumentStatus
    chunk_count: int
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchHitResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    source_locator: str
    score: float


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=5, ge=1, le=20)


class CitationResponse(BaseModel):
    label: str
    chunk_id: UUID
    document_id: UUID
    filename: str
    source_locator: str
    chunk_index: int
    score: float


class AnswerResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    no_evidence: bool
