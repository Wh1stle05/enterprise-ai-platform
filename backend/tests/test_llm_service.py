import pytest

from app.services.llm_service import LLMConfigurationError, complete_chat


@pytest.mark.asyncio
async def test_missing_key_is_deterministic():
    with pytest.raises(LLMConfigurationError):
        await complete_chat([{"role": "user", "content": "ping"}])
