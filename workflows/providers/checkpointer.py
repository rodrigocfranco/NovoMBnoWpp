"""Checkpointer singleton with AsyncPostgresSaver for LangGraph state persistence."""

import structlog
from django.conf import settings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = structlog.get_logger(__name__)

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """Return AsyncPostgresSaver singleton backed by AsyncConnectionPool.

    Pool is configured with:
    - min_size=5, max_size=20
    - autocommit=True, row_factory=dict_row
    - search_path=langgraph,public (separate schema)
    """
    global _pool, _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    conninfo = (
        settings.DATABASES["default"].get("OPTIONS", {}).get("conninfo", "") or _build_conninfo()
    )

    _pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=5,
        max_size=20,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "options": "-c search_path=langgraph,public",
        },
        open=False,
    )
    await _pool.open()

    _checkpointer = AsyncPostgresSaver(conn=_pool)

    logger.info(
        "checkpointer_initialized",
        pool_min_size=5,
        pool_max_size=20,
        schema="langgraph",
    )

    return _checkpointer


def _build_conninfo() -> str:
    """Build psycopg conninfo string from Django DATABASE settings."""
    db = settings.DATABASES["default"]
    host = db.get("HOST", "localhost")
    port = db.get("PORT", "5432")
    name = db.get("NAME", "mb_wpp")
    user = db.get("USER", "postgres")
    password = db.get("PASSWORD", "postgres")
    return f"host={host} port={port} dbname={name} user={user} password={password}"


async def setup_checkpointer() -> None:
    """Create checkpoint tables in the langgraph schema. Called on app startup."""
    checkpointer = await get_checkpointer()
    await checkpointer.setup()
    logger.info("checkpointer_tables_created", schema="langgraph")


async def close_checkpointer() -> None:
    """Close the connection pool gracefully. Called on app shutdown."""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        logger.info("checkpointer_pool_closed")
    _pool = None
    _checkpointer = None
