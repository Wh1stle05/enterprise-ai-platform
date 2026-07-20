"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.config import settings
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return uuid.uuid4()


# ---------- User ----------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    display_name = Column(String(128), default="")
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    role = Column(String(16), nullable=False, default="user", server_default="user", index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action_type = Column(String(32), nullable=False)
    input = Column(Text)
    output = Column(Text)
    tool_used = Column(String(128))
    ip_address = Column(String(64))
    retention_days = Column(Integer, nullable=False, default=90, server_default="90")
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default="now()", nullable=False)

    user = relationship("User", back_populates="audit_logs")


# ---------- Conversation / Chat ----------

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(256), default="New Conversation")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(16), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", Text, default="{}")  # JSON blob for tool calls, citations, etc.
    created_at = Column(DateTime(timezone=True), default=utcnow)

    conversation = relationship("Conversation", back_populates="messages")


# ---------- Knowledge Base ----------

class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    knowledge_base_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(512), nullable=False)
    file_type = Column(String(64))
    file_size = Column(Integer)
    status = Column(String(32), default="pending")  # pending / processing / ready / failed
    content_text = Column(Text, default="")  # extracted plain text
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM))  # type: ignore
    created_at = Column(DateTime(timezone=True), default=utcnow)

    document = relationship("Document", back_populates="chunks")
