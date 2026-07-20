"""Application configuration via environment variables."""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Enterprise AI Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/enterprise_ai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # LLM
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 4096
    AUDIT_RETENTION_DAYS: int = 90

    # Embedding
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536

    # File storage
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    UPLOAD_CHUNK_SIZE_BYTES: int = 1048576
    PARSER_VERSION: str = "m2-1"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RETRIEVAL_DEFAULT_TOP_K: int = 5
    RETRIEVAL_MAX_TOP_K: int = 20
    RETRIEVAL_MIN_SCORE: float = 0.35
    EMBEDDING_BATCH_SIZE: int = 64

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
