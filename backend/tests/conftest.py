"""conftest — shared fixtures for pytest."""

import pytest


@pytest.fixture
def sample_payload():
    return {"sub": "00000000-0000-0000-0000-000000000001"}
