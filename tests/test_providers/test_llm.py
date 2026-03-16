"""Tests for LLM provider factory (AC1)."""

from unittest.mock import MagicMock, patch


class TestGetModel:
    """Tests for get_model() factory function."""

    def setup_method(self):
        """Reset singleton between tests."""
        import workflows.providers.llm as mod

        mod._default_model = None

    def teardown_method(self):
        """Reset singleton after tests."""
        import workflows.providers.llm as mod

        mod._default_model = None

    @patch("workflows.providers.llm.ChatAnthropic")
    @patch("workflows.providers.llm.ChatAnthropicVertex")
    def test_get_model_returns_runnable_with_fallbacks(
        self, mock_anthropic_vertex_cls, mock_anthropic_cls
    ):
        """AC1: get_model() retorna RunnableWithFallbacks."""
        mock_primary = MagicMock()
        mock_fallback = MagicMock()
        mock_combined = MagicMock()
        mock_anthropic_vertex_cls.return_value = mock_primary
        mock_anthropic_cls.return_value = mock_fallback
        mock_primary.with_fallbacks.return_value = mock_combined

        from workflows.providers.llm import get_model

        result = get_model()

        mock_primary.with_fallbacks.assert_called_once_with([mock_fallback])
        assert result is mock_combined

    @patch("workflows.providers.llm.ChatAnthropic")
    @patch("workflows.providers.llm.ChatAnthropicVertex")
    def test_primary_is_vertex_with_correct_params(
        self, mock_anthropic_vertex_cls, mock_anthropic_cls
    ):
        """AC1: Primary é ChatAnthropicVertex com params corretos (Claude on Vertex)."""
        mock_primary = MagicMock()
        mock_anthropic_vertex_cls.return_value = mock_primary
        mock_primary.with_fallbacks.return_value = MagicMock()

        from workflows.providers.llm import get_model

        get_model()

        mock_anthropic_vertex_cls.assert_called_once()
        call_kwargs = mock_anthropic_vertex_cls.call_args[1]
        assert call_kwargs["model_name"] == "claude-haiku-4-5@20251001"
        assert call_kwargs["max_tokens"] == 1024
        assert call_kwargs["temperature"] == 0
        assert call_kwargs["streaming"] is True
        assert call_kwargs["max_retries"] == 2

    @patch("workflows.providers.llm.ChatAnthropic")
    @patch("workflows.providers.llm.ChatAnthropicVertex")
    def test_fallback_is_anthropic_with_correct_params(
        self, mock_anthropic_vertex_cls, mock_anthropic_cls
    ):
        """AC1: Fallback é ChatAnthropic com params corretos."""
        mock_primary = MagicMock()
        mock_anthropic_vertex_cls.return_value = mock_primary
        mock_primary.with_fallbacks.return_value = MagicMock()

        from workflows.providers.llm import get_model

        get_model()

        mock_anthropic_cls.assert_called_once()
        call_kwargs = mock_anthropic_cls.call_args[1]
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["max_tokens"] == 1024
        assert call_kwargs["temperature"] == 0
        assert call_kwargs["streaming"] is True
        assert call_kwargs["max_retries"] == 2
        assert call_kwargs["stream_usage"] is True

    @patch("workflows.providers.llm.ChatAnthropic")
    @patch("workflows.providers.llm.ChatAnthropicVertex")
    def test_custom_temperature_and_max_tokens(self, mock_anthropic_vertex_cls, mock_anthropic_cls):
        """AC1: Parâmetros configuráveis temperature e max_tokens."""
        mock_primary = MagicMock()
        mock_anthropic_vertex_cls.return_value = mock_primary
        mock_primary.with_fallbacks.return_value = MagicMock()

        from workflows.providers.llm import get_model

        get_model(temperature=0.7, max_tokens=4096)

        vertex_kwargs = mock_anthropic_vertex_cls.call_args[1]
        assert vertex_kwargs["temperature"] == 0.7
        assert vertex_kwargs["max_tokens"] == 4096

        anthropic_kwargs = mock_anthropic_cls.call_args[1]
        assert anthropic_kwargs["temperature"] == 0.7
        assert anthropic_kwargs["max_tokens"] == 4096

    @patch("workflows.providers.llm.ChatAnthropic")
    @patch("workflows.providers.llm.ChatAnthropicVertex")
    def test_vertex_credentials_loaded_when_configured(
        self, mock_anthropic_vertex_cls, mock_anthropic_cls
    ):
        """AC1: Credenciais Vertex via service_account quando GCP_CREDENTIALS configurado."""
        mock_primary = MagicMock()
        mock_anthropic_vertex_cls.return_value = mock_primary
        mock_primary.with_fallbacks.return_value = MagicMock()

        creds_json = '{"type": "service_account", "project_id": "test"}'

        with patch("django.conf.settings.GCP_CREDENTIALS", creds_json):
            with patch(
                "google.oauth2.service_account.Credentials.from_service_account_info"
            ) as mock_from_sa:
                mock_creds = MagicMock()
                mock_from_sa.return_value = mock_creds

                from workflows.providers.llm import get_model

                get_model()

                mock_from_sa.assert_called_once()
                vertex_kwargs = mock_anthropic_vertex_cls.call_args[1]
                assert vertex_kwargs["credentials"] is mock_creds

    @patch("workflows.providers.llm.ChatAnthropic")
    @patch("workflows.providers.llm.ChatAnthropicVertex")
    def test_no_credentials_when_gcp_credentials_empty(
        self, mock_anthropic_vertex_cls, mock_anthropic_cls
    ):
        """AC1: Sem credentials explícitas quando GCP_CREDENTIALS vazio (usa ADC)."""
        mock_primary = MagicMock()
        mock_anthropic_vertex_cls.return_value = mock_primary
        mock_primary.with_fallbacks.return_value = MagicMock()

        from workflows.providers.llm import get_model

        get_model()

        vertex_kwargs = mock_anthropic_vertex_cls.call_args[1]
        assert "credentials" not in vertex_kwargs
