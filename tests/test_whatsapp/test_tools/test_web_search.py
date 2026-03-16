"""Tests for web_search tool (Story 2.2, AC #1, #2, #3)."""

from unittest.mock import AsyncMock, patch

import pytest

from workflows.whatsapp.tools.web_search import (
    FALLBACK_COMPETITOR_DOMAINS,
    _get_blocked_domains,
    web_search,
)


def _make_tavily_response(results: list[dict]) -> dict:
    """Build a mock Tavily API response."""
    return {
        "query": "test query",
        "results": results,
        "response_time": 1.5,
    }


def _make_result(
    title: str = "Test Article",
    url: str = "https://example.com/article",
    content: str = "Test content",
    raw_content: str | None = None,
    score: float = 0.9,
) -> dict:
    return {
        "title": title,
        "url": url,
        "content": content,
        "raw_content": raw_content,
        "score": score,
    }


class TestWebSearchTool:
    """Tests for the web_search tool function."""

    @pytest.fixture(autouse=True)
    def _mock_settings(self, settings):
        settings.TAVILY_API_KEY = "test-tavily-key"

    async def test_search_returns_formatted_results(self):
        """AC#1: Verify [W-N] formatting with title, URL, content."""
        mock_response = _make_tavily_response(
            [
                _make_result(title="PubMed Article", url="https://pubmed.ncbi.nlm.nih.gov/123"),
                _make_result(title="WHO Guidelines", url="https://who.int/guidelines"),
            ]
        )

        with patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await web_search.ainvoke({"query": "pneumonia treatment"})

        assert "[W-1]" in result
        assert "[W-2]" in result
        assert "PubMed Article" in result
        assert "WHO Guidelines" in result
        assert "https://pubmed.ncbi.nlm.nih.gov/123" in result

    async def test_search_excludes_competitor_domains(self):
        """AC#1: Verify exclude_domains is passed to Tavily."""
        mock_response = _make_tavily_response([_make_result()])

        with (
            patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient") as mock_client,
            patch(
                "workflows.whatsapp.tools.web_search._get_blocked_domains",
                new_callable=AsyncMock,
                return_value=["medgrupo.com.br", "sanar.com.br"],
            ),
        ):
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            await web_search.ainvoke({"query": "test"})

            mock_instance.search.assert_called_once()
            call_kwargs = mock_instance.search.call_args[1]
            assert call_kwargs["exclude_domains"] == ["medgrupo.com.br", "sanar.com.br"]

    async def test_search_all_results_blocked(self):
        """AC#2: Verify message when no results after exclusion."""
        mock_response = _make_tavily_response([])

        with patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await web_search.ainvoke({"query": "test query"})

        assert "Não foram encontradas fontes web confiáveis" in result
        assert "[W-" not in result

    async def test_search_tavily_timeout(self):
        """AC#1: Verify specific timeout message (no internal details leaked)."""
        with patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(side_effect=TimeoutError("Request timed out"))
            mock_client.return_value = mock_instance

            result = await web_search.ainvoke({"query": "test"})

        assert "tempo limite" in result
        assert "Responda com base no seu conhecimento geral" in result
        assert "Request timed out" not in result  # internal detail NOT leaked

    async def test_search_generic_error_sanitized(self):
        """Review fix #2: Generic error does not leak exception details to LLM."""
        with patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(
                side_effect=RuntimeError("API key tvly-SECRET invalid")
            )
            mock_client.return_value = mock_instance

            result = await web_search.ainvoke({"query": "test"})

        assert "Erro ao buscar na web" in result
        assert "Responda com base no seu conhecimento geral" in result
        assert "tvly-SECRET" not in result  # no internal details leaked

    async def test_search_uses_basic_depth(self):
        """AC#1: Verify search_depth=basic is used for speed/cost."""
        mock_response = _make_tavily_response([_make_result()])

        with patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            await web_search.ainvoke({"query": "test"})

            call_kwargs = mock_instance.search.call_args[1]
            assert call_kwargs["search_depth"] == "basic"
            assert call_kwargs["max_results"] == 4
            assert call_kwargs["include_raw_content"] is False

    async def test_search_truncates_long_content(self):
        """AC#1: Verify content is truncated at 400 chars."""
        long_content = "A" * 600
        mock_response = _make_tavily_response(
            [
                _make_result(content=long_content),
            ]
        )

        with patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await web_search.ainvoke({"query": "test"})

        # Should be truncated: 400 chars + "..."
        assert "..." in result
        # The full 600-char content should NOT appear
        assert long_content not in result

    async def test_search_uses_content_field(self):
        """AC#1: Uses content field (not raw_content)."""
        mock_response = _make_tavily_response(
            [
                _make_result(content="summary content here"),
            ]
        )

        with patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await web_search.ainvoke({"query": "test"})

        assert "summary content here" in result


class TestGetBlockedDomains:
    """Tests for _get_blocked_domains helper."""

    async def test_uses_config_competitors_dict(self):
        """AC#3: Verify competitor list loaded from ConfigService (dict format)."""
        config_value = {"domains": ["custom1.com", "custom2.com"], "names": ["Custom1"]}

        with patch(
            "workflows.whatsapp.tools.web_search.ConfigService.get",
            new_callable=AsyncMock,
            return_value=config_value,
        ):
            result = await _get_blocked_domains()

        assert result == ["custom1.com", "custom2.com"]

    async def test_uses_config_competitors_list(self):
        """AC#3: Verify competitor list loaded from ConfigService (list format)."""
        config_value = ["custom1.com", "custom2.com"]

        with patch(
            "workflows.whatsapp.tools.web_search.ConfigService.get",
            new_callable=AsyncMock,
            return_value=config_value,
        ):
            result = await _get_blocked_domains()

        assert result == ["custom1.com", "custom2.com"]

    async def test_fallback_hardcoded_competitors(self):
        """AC#3: Verify fallback to hardcoded list when Config unavailable."""
        with patch(
            "workflows.whatsapp.tools.web_search.ConfigService.get",
            new_callable=AsyncMock,
            side_effect=Exception("Config not found"),
        ):
            result = await _get_blocked_domains()

        assert result == FALLBACK_COMPETITOR_DOMAINS
        assert "medgrupo.com.br" in result
        assert "sanar.com.br" in result

    async def test_fallback_when_config_returns_none(self):
        """Review fix #6: Fallback when ConfigService returns None."""
        with patch(
            "workflows.whatsapp.tools.web_search.ConfigService.get",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _get_blocked_domains()

        assert result == FALLBACK_COMPETITOR_DOMAINS
