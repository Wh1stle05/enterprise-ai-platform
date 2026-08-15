import io
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.services.file_storage import (
    EmptyUploadError,
    InvalidStorageURIError,
    LocalFileStorage,
    UploadTooLargeError,
)


def upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(content))


@pytest.mark.asyncio
async def test_storage_hashes_and_uses_uuid_path(tmp_path: Path):
    kb_id, document_id = uuid4(), uuid4()
    storage = LocalFileStorage(tmp_path, 100)
    stored = await storage.save(kb_id, document_id, "../../policy.md", upload("x", b"policy"))
    assert stored.uri == f"local://{kb_id}/{document_id}.md"
    assert ".." not in stored.uri
    assert stored.size == 6
    assert storage.resolve(stored.uri).read_bytes() == b"policy"


@pytest.mark.asyncio
async def test_storage_rejects_empty_and_oversize_and_cleans_up(tmp_path: Path):
    storage = LocalFileStorage(tmp_path, 2)
    with pytest.raises(EmptyUploadError):
        await storage.save(uuid4(), uuid4(), "empty.md", upload("empty.md", b""))
    with pytest.raises(UploadTooLargeError):
        await storage.save(uuid4(), uuid4(), "large.md", upload("large.md", b"123"))
    with pytest.raises(InvalidStorageURIError):
        storage.resolve("local://../../outside")
