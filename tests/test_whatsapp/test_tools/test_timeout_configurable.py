"""Tests for configurable timeouts per external service (Story 5.1, AC#2)."""

from unittest.mock import AsyncMock, patch


class TestConfigurableTimeouts:
    """Verify tools/providers read timeout from ConfigService with fallback."""

    @patch("workflows.whatsapp.tools.web_search.ConfigService")
    @patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient")
    async def test_web_search_uses_configured_timeout(self, mock_client_cls, mock_config):
        """Tavily timeout comes from ConfigService when available."""
        mock_config.get = AsyncMock(return_value=15)
        mock_client = AsyncMock()
        mock_client.search.return_value = {"results": []}
        mock_client_cls.return_value = mock_client

        from workflows.whatsapp.tools.web_search import web_search

        await web_search.ainvoke({"query": "test"})

        # Verify timeout was passed from config
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["timeout"] == 15

    @patch("workflows.whatsapp.tools.web_search.ConfigService")
    @patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient")
    async def test_web_search_falls_back_to_hardcoded_timeout(self, mock_client_cls, mock_config):
        """Tavily timeout falls back to hardcoded when ConfigService fails."""
        mock_config.get = AsyncMock(side_effect=Exception("Config unavailable"))
        mock_client = AsyncMock()
        mock_client.search.return_value = {"results": []}
        mock_client_cls.return_value = mock_client

        from workflows.whatsapp.tools.web_search import web_search

        await web_search.ainvoke({"query": "test"})

        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["timeout"] == 10  # hardcoded fallback

    @patch("workflows.whatsapp.tools.verify_paper.ConfigService")
    async def test_verify_paper_uses_configured_timeout(self, mock_config):
        """PubMed timeout comes from ConfigService when available."""
        mock_config.get = AsyncMock(return_value=8)

        from workflows.whatsapp.tools.verify_paper import _get_pubmed_timeout

        result = await _get_pubmed_timeout()
        assert result == 8.0

    @patch("workflows.whatsapp.tools.verify_paper.ConfigService")
    async def test_verify_paper_falls_back_to_hardcoded_timeout(self, mock_config):
        """PubMed timeout falls back to hardcoded when ConfigService fails."""
        mock_config.get = AsyncMock(side_effect=Exception("Config unavailable"))

        from workflows.whatsapp.tools.verify_paper import _get_pubmed_timeout

        result = await _get_pubmed_timeout()
        assert result == 5.0  # hardcoded fallback

    @patch("workflows.providers.whatsapp.ConfigService")
    async def test_whatsapp_provider_uses_configured_timeout(self, mock_config):
        """WhatsApp provider timeout comes from ConfigService."""
        mock_config.get = AsyncMock(return_value=15)

        from workflows.providers.whatsapp import _get_whatsapp_timeout

        result = await _get_whatsapp_timeout()
        assert result == 15.0

    @patch("workflows.providers.whatsapp.ConfigService")
    async def test_whatsapp_provider_falls_back_to_hardcoded(self, mock_config):
        """WhatsApp provider timeout falls back to hardcoded."""
        mock_config.get = AsyncMock(side_effect=Exception("Config unavailable"))

        from workflows.providers.whatsapp import _get_whatsapp_timeout

        result = await _get_whatsapp_timeout()
        assert result == 10.0  # hardcoded fallback
