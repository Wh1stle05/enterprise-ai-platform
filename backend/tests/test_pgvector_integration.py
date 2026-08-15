import os

import pytest


@pytest.mark.postgres
def test_pgvector_integration_requires_postgres():
    if not os.getenv("TEST_POSTGRES_URL"):
        pytest.skip("TEST_POSTGRES_URL is not configured")
