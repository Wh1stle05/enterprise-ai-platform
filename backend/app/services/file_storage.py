import asyncio
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import UploadFile

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".md"}


class UnsupportedFileTypeError(ValueError):
    pass


class EmptyUploadError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


class InvalidStorageURIError(ValueError):
    pass


@dataclass(frozen=True)
class StoredFile:
    uri: str
    size: int
    checksum: str


class LocalFileStorage:
    def __init__(self, root: Path, max_bytes: int):
        self.root = root.resolve()
        self.max_bytes = max_bytes

    async def save(
        self, kb_id: UUID, document_id: UUID, filename: str, upload: UploadFile
    ) -> StoredFile:
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeError(suffix)
        directory = self.root / str(kb_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{document_id}{suffix}"
        digest, size = hashlib.sha256(), 0
        try:
            async with aiofiles.open(path, "wb") as target:
                while block := await upload.read(settings.UPLOAD_CHUNK_SIZE_BYTES):
                    size += len(block)
                    if size > self.max_bytes:
                        raise UploadTooLargeError(filename)
                    digest.update(block)
                    await target.write(block)
            if size == 0:
                raise EmptyUploadError(filename)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return StoredFile(f"local://{kb_id}/{document_id}{suffix}", size, digest.hexdigest())

    def resolve(self, uri: str) -> Path:
        if not uri.startswith("local://"):
            raise InvalidStorageURIError(uri)
        path = (self.root / uri.removeprefix("local://")).resolve()
        if self.root not in path.parents:
            raise InvalidStorageURIError(uri)
        return path

    async def delete(self, uri: str) -> None:
        self.resolve(uri).unlink(missing_ok=True)

    async def delete_knowledge_base(self, kb_id: UUID) -> None:
        directory = (self.root / str(kb_id)).resolve()
        if directory.parent != self.root:
            raise InvalidStorageURIError(str(kb_id))
        await asyncio.to_thread(shutil.rmtree, directory, True)
