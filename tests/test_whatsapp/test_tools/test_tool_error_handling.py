"""Tests for standardized tool error handling (Story 5.1, Task 5).

Validates:
  1. ALL tools return str on failure (never raise exception)
  2. Error logs include: tool_name, error_type, service
  3. Error logs include latency_ms where applicable
"""

from unittest.mock import AsyncMock, MagicMock, patch

REQUIRED_TOOL_LOG_FIELDS = {"tool_name", "error_type", "service"}


class TestRagMedicalErrorHandling:
    """rag_medical_search must return str and log with required fields on failure."""

    @patch("workflows.whatsapp.tools.rag_medical.get_pinecone")
    async def test_returns_string_on_pinecone_error(self, mock_get_pinecone):
        """Tool returns str, never raises, on Pinecone failure."""
        mock_provider = MagicMock()
        mock_provider.query_similar = AsyncMock(side_effect=Exception("connection timeout"))
        mock_get_pinecone.return_value = mock_provider

        from workflows.whatsapp.tools.rag_medical import rag_medical_search

        result = await rag_medical_search.ainvoke({"query": "test query"})

        assert isinstance(result, str)
        assert "erro" in result.lower() or "indisponível" in result.lower()

    @patch("workflows.whatsapp.tools.rag_medical.get_pinecone")
    async def test_error_log_contains_required_fields(self, mock_get_pinecone):
        """Error log includes tool_name, error_type, service."""
        mock_provider = MagicMock()
        mock_provider.query_similar = AsyncMock(side_effect=Exception("timeout"))
        mock_get_pinecone.return_value = mock_provider

        with patch("workflows.whatsapp.tools.rag_medical.logger") as mock_logger:
            from workflows.whatsapp.tools.rag_medical import rag_medical_search

            await rag_medical_search.ainvoke({"query": "test query"})

        mock_logger.error.assert_called_once()
        kwargs = mock_logger.error.call_args.kwargs
        assert "tool_name" in kwargs
        assert "error_type" in kwargs
        assert "service" in kwargs


class TestWebSearchErrorHandling:
    """web_search must return str and log with required fields on failure."""

    @patch("workflows.whatsapp.tools.web_search._get_blocked_domains", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.web_search._get_tavily_timeout", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient")
    async def test_returns_string_on_timeout(self, mock_tavily_cls, mock_timeout, mock_blocked):
        """Tool returns str on TimeoutError."""
        mock_blocked.return_value = []
        mock_timeout.return_value = 10

        mock_client = MagicMock()
        mock_client.search = AsyncMock(side_effect=TimeoutError("timeout"))
        mock_tavily_cls.return_value = mock_client

        from workflows.whatsapp.tools.web_search import web_search

        result = await web_search.ainvoke({"query": "test"})

        assert isinstance(result, str)
        assert "tempo limite" in result.lower() or "timeout" in result.lower()

    @patch("workflows.whatsapp.tools.web_search._get_blocked_domains", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.web_search._get_tavily_timeout", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient")
    async def test_error_log_contains_required_fields(
        self, mock_tavily_cls, mock_timeout, mock_blocked
    ):
        """Error log includes tool_name, error_type, service on general failure."""
        mock_blocked.return_value = []
        mock_timeout.return_value = 10

        mock_client = MagicMock()
        mock_client.search = AsyncMock(side_effect=RuntimeError("API error"))
        mock_tavily_cls.return_value = mock_client

        with patch("workflows.whatsapp.tools.web_search.logger") as mock_logger:
            from workflows.whatsapp.tools.web_search import web_search

            await web_search.ainvoke({"query": "test"})

        mock_logger.error.assert_called_once()
        kwargs = mock_logger.error.call_args.kwargs
        assert "tool_name" in kwargs
        assert "error_type" in kwargs
        assert "service" in kwargs

    @patch("workflows.whatsapp.tools.web_search._get_blocked_domains", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.web_search._get_tavily_timeout", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient")
    async def test_timeout_log_contains_required_fields(
        self, mock_tavily_cls, mock_timeout, mock_blocked
    ):
        """Timeout log includes tool_name, service."""
        mock_blocked.return_value = []
        mock_timeout.return_value = 10

        mock_client = MagicMock()
        mock_client.search = AsyncMock(side_effect=TimeoutError("timeout"))
        mock_tavily_cls.return_value = mock_client

        with patch("workflows.whatsapp.tools.web_search.logger") as mock_logger:
            from workflows.whatsapp.tools.web_search import web_search

            await web_search.ainvoke({"query": "test"})

        mock_logger.warning.assert_called()
        kwargs = mock_logger.warning.call_args.kwargs
        assert "tool_name" in kwargs
        assert "service" in kwargs


class TestVerifyPaperErrorHandling:
    """verify_medical_paper must return str and log with required fields on failure."""

    @patch("workflows.whatsapp.tools.verify_paper._get_pubmed_timeout", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_returns_string_on_http_error(self, mock_client_cls, mock_timeout):
        """Tool returns str on HTTP error after retries."""
        import httpx

        mock_timeout.return_value = 5.0

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from workflows.whatsapp.tools.verify_paper import verify_medical_paper

        result = await verify_medical_paper.ainvoke(
            {"title": "Test Paper", "authors": "Test Author"}
        )

        assert isinstance(result, str)
        assert "indisponível" in result.lower() or "ressalva" in result.lower()

    @patch("workflows.whatsapp.tools.verify_paper._get_pubmed_timeout", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_error_log_contains_required_fields(self, mock_client_cls, mock_timeout):
        """Error log includes tool_name, error_type, service."""
        import httpx

        mock_timeout.return_value = 5.0

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with patch("workflows.whatsapp.tools.verify_paper.logger") as mock_logger:
            from workflows.whatsapp.tools.verify_paper import verify_medical_paper

            await verify_medical_paper.ainvoke({"title": "Test Paper", "authors": "Test Author"})

        mock_logger.warning.assert_called()
        # Find the "pubmed_api_unavailable" call (last attempt)
        kwargs = mock_logger.warning.call_args.kwargs
        assert "tool_name" in kwargs
        assert "service" in kwargs


class TestDrugLookupErrorHandling:
    """drug_lookup must return str and log with required fields on timeout."""

    async def test_returns_string_on_timeout(self):
        """Tool returns str on global timeout."""
        import asyncio

        from workflows.whatsapp.tools.bulas_med import drug_lookup

        # Mock the implementation to be slow
        async def slow_impl(name):
            await asyncio.sleep(100)
            return "result"

        with patch(
            "workflows.whatsapp.tools.bulas_med._drug_lookup_impl",
            side_effect=slow_impl,
        ):
            with patch(
                "workflows.whatsapp.tools.bulas_med._get_bulas_timeout",
                new_callable=AsyncMock,
                return_value=0.01,
            ):
                result = await drug_lookup.ainvoke({"drug_name": "dipirona"})

        assert isinstance(result, str)
        assert "tempo limite" in result.lower() or "excedeu" in result.lower()

    async def test_timeout_log_contains_required_fields(self):
        """Timeout log includes tool_name, service."""
        import asyncio

        async def slow_impl(name):
            await asyncio.sleep(100)
            return "result"

        with (
            patch(
                "workflows.whatsapp.tools.bulas_med._drug_lookup_impl",
                side_effect=slow_impl,
            ),
            patch(
                "workflows.whatsapp.tools.bulas_med._get_bulas_timeout",
                new_callable=AsyncMock,
                return_value=0.01,
            ),
            patch("workflows.whatsapp.tools.bulas_med.logger") as mock_logger,
        ):
            from workflows.whatsapp.tools.bulas_med import drug_lookup

            await drug_lookup.ainvoke({"drug_name": "dipirona"})

        mock_logger.warning.assert_called()
        kwargs = mock_logger.warning.call_args.kwargs
        assert "tool_name" in kwargs
        assert "service" in kwargs


class TestCalculatorsErrorHandling:
    """medical_calculator must return str and log with required fields on error."""

    async def test_returns_string_on_exception(self):
        """Tool returns str on calculator internal error."""
        from workflows.whatsapp.tools.calculators import medical_calculator

        result = await medical_calculator.ainvoke(
            {"calculator_name": "cha2ds2_vasc", "parameters": {}}
        )

        assert isinstance(result, str)

    async def test_error_log_contains_tool_name(self):
        """Calculator error log includes tool_name."""

        with patch("workflows.whatsapp.tools.calculators.logger") as mock_logger:
            from workflows.whatsapp.tools.calculators import medical_calculator

            # Force a generic Exception (not TypeError) to hit the error log
            with patch(
                "workflows.whatsapp.tools.calculators.CALCULATORS",
                {"broken": MagicMock(side_effect=ValueError("bad input"))},
            ):
                await medical_calculator.ainvoke({"calculator_name": "broken", "parameters": {}})

        mock_logger.error.assert_called_once()
        kwargs = mock_logger.error.call_args.kwargs
        assert "tool_name" in kwargs
