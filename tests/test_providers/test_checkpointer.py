"""Tests for checkpointer singleton (AC2)."""

from unittest.mock import AsyncMock, MagicMock, patch

from psycopg.rows import dict_row


class TestGetCheckpointer:
    """Tests for get_checkpointer() singleton."""

    def _reset_singleton(self):
        """Reset checkpointer singleton between tests."""
        import workflows.providers.checkpointer as mod

        mod._pool = None
        mod._checkpointer = None

    @patch("workflows.providers.checkpointer.AsyncPostgresSaver")
    @patch("workflows.providers.checkpointer.AsyncConnectionPool")
    async def test_get_checkpointer_returns_async_postgres_saver(
        self, mock_pool_cls, mock_saver_cls
    ):
        """AC2: get_checkpointer() retorna AsyncPostgresSaver."""
        self._reset_singleton()

        mock_pool = AsyncMock()
        mock_pool_cls.return_value = mock_pool
        mock_saver = MagicMock()
        mock_saver_cls.return_value = mock_saver

        from workflows.providers.checkpointer import get_checkpointer

        result = await get_checkpointer()

        assert result is mock_saver
        mock_saver_cls.assert_called_once_with(conn=mock_pool)
        self._reset_singleton()

    @patch("workflows.providers.checkpointer.AsyncPostgresSaver")
    @patch("workflows.providers.checkpointer.AsyncConnectionPool")
    async def test_singleton_returns_same_instance(self, mock_pool_cls, mock_saver_cls):
        """AC2: Singleton — segunda chamada retorna mesma instância."""
        self._reset_singleton()

        mock_pool = AsyncMock()
        mock_pool_cls.return_value = mock_pool
        mock_saver = MagicMock()
        mock_saver_cls.return_value = mock_saver

        from workflows.providers.checkpointer import get_checkpointer

        result1 = await get_checkpointer()
        result2 = await get_checkpointer()

        assert result1 is result2
        # Pool created only once
        mock_pool_cls.assert_called_once()
        self._reset_singleton()

    @patch("workflows.providers.checkpointer.AsyncPostgresSaver")
    @patch("workflows.providers.checkpointer.AsyncConnectionPool")
    async def test_pool_configured_with_correct_kwargs(self, mock_pool_cls, mock_saver_cls):
        """AC2: Pool configurado com autocommit=True e row_factory=dict_row."""
        self._reset_singleton()

        mock_pool = AsyncMock()
        mock_pool_cls.return_value = mock_pool
        mock_saver_cls.return_value = MagicMock()

        from workflows.providers.checkpointer import get_checkpointer

        await get_checkpointer()

        mock_pool_cls.assert_called_once()
        call_kwargs = mock_pool_cls.call_args[1]
        assert call_kwargs["min_size"] == 5
        assert call_kwargs["max_size"] == 20
        assert call_kwargs["open"] is False
        assert call_kwargs["kwargs"]["autocommit"] is True
        assert call_kwargs["kwargs"]["row_factory"] is dict_row
        assert "search_path=langgraph" in call_kwargs["kwargs"]["options"]
        self._reset_singleton()

    @patch("workflows.providers.checkpointer.AsyncPostgresSaver")
    @patch("workflows.providers.checkpointer.AsyncConnectionPool")
    async def test_pool_open_called_on_init(self, mock_pool_cls, mock_saver_cls):
        """AC2: pool.open() é chamado na inicialização."""
        self._reset_singleton()

        mock_pool = AsyncMock()
        mock_pool_cls.return_value = mock_pool
        mock_saver_cls.return_value = MagicMock()

        from workflows.providers.checkpointer import get_checkpointer

        await get_checkpointer()

        mock_pool.open.assert_awaited_once()
        self._reset_singleton()


class TestSetupCheckpointer:
    """Tests for setup_checkpointer()."""

    @patch("workflows.providers.checkpointer.get_checkpointer")
    async def test_setup_calls_checkpointer_setup(self, mock_get):
        """AC2: setup_checkpointer() cria tabelas via setup()."""
        mock_checkpointer = AsyncMock()
        mock_get.return_value = mock_checkpointer

        from workflows.providers.checkpointer import setup_checkpointer

        await setup_checkpointer()

        mock_checkpointer.setup.assert_awaited_once()
