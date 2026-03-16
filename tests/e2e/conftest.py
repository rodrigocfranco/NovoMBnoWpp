"""Fixtures for E2E smoke tests with real LLM + tools.

Requires:
    docker compose up -d  (postgres + redis)
    Real credentials in .env (GCP, Pinecone, Tavily, NCBI)
    DJANGO_SETTINGS_MODULE=config.settings.integration
"""

import psycopg
import pytest
from django.conf import settings


@pytest.fixture(autouse=True)
def _check_services():
    """Skip e2e tests if docker-compose services aren't running."""
    import socket

    for host, port, name in [
        ("localhost", 6379, "Redis"),
        ("localhost", 5432, "PostgreSQL"),
    ]:
        try:
            s = socket.create_connection((host, port), timeout=1)
            s.close()
        except OSError:
            pytest.skip(f"{name} not available (run: docker compose up -d)")


@pytest.fixture(autouse=True)
async def _setup_langgraph_schema():
    """Create langgraph schema and checkpoint tables in the test database.

    The Django test runner creates a fresh test_mb_wpp database and runs
    Django migrations, but the LangGraph checkpoint tables are NOT Django
    models — they must be created via AsyncPostgresSaver.setup().
    """
    import workflows.providers.checkpointer as ckpt_mod
    import workflows.whatsapp.graph as graph_mod

    # Reset singletons so they connect to the test database
    ckpt_mod._pool = None
    ckpt_mod._checkpointer = None
    graph_mod._compiled_graph = None

    # Create the langgraph schema (sync, before async setup)
    db = settings.DATABASES["default"]
    conninfo = (
        f"host={db.get('HOST', 'localhost')} "
        f"port={db.get('PORT', '5432')} "
        f"dbname={db.get('NAME', 'mb_wpp')} "
        f"user={db.get('USER', 'postgres')} "
        f"password={db.get('PASSWORD', 'postgres')}"
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS langgraph")

    # Create checkpoint tables via LangGraph's setup
    await ckpt_mod.setup_checkpointer()

    yield

    # Cleanup singletons
    await ckpt_mod.close_checkpointer()
    ckpt_mod._pool = None
    ckpt_mod._checkpointer = None
    graph_mod._compiled_graph = None


@pytest.fixture(autouse=True)
async def _reset_embeddings_singleton():
    """Reset embeddings singleton between tests."""
    import workflows.providers.embeddings as emb_mod

    emb_mod._embeddings_instance = None
    yield
    emb_mod._embeddings_instance = None


@pytest.fixture(autouse=True)
async def _reset_redis_singleton():
    """Reset Redis singleton between tests."""
    import workflows.utils.deduplication as dedup_mod

    original = dedup_mod._redis_client
    dedup_mod._redis_client = None
    yield
    if dedup_mod._redis_client is not None:
        await dedup_mod._redis_client.aclose()
    dedup_mod._redis_client = original
