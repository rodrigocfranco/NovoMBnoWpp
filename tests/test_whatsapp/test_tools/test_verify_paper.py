"""Tests for verify_medical_paper tool (Story 2.3: AC #1, #2, #3, #4)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

# ── Fixtures ──

ESEARCH_FOUND_RESPONSE = {
    "esearchresult": {
        "count": "1",
        "idlist": ["27540849"],
    }
}

ESEARCH_NOT_FOUND_RESPONSE = {
    "esearchresult": {
        "count": "0",
        "idlist": [],
    }
}

ESUMMARY_RESPONSE = {
    "result": {
        "uids": ["27540849"],
        "27540849": {
            "uid": "27540849",
            "pubdate": "2016 Sep 10",
            "source": "N Engl J Med",
            "title": "Angiotensin-Neprilysin Inhibition versus Enalapril in Heart Failure.",
            "sortfirstauthor": "McMurray JJ",
            "authors": [
                {"name": "McMurray JJ", "authtype": "Author"},
                {"name": "Packer M", "authtype": "Author"},
            ],
            "elocationid": "doi: 10.1056/NEJMoa1409077",
        },
    }
}


def _make_response(json_data):
    """Create a mock httpx response with synchronous .json()."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _setup_async_client(mock_client_cls):
    """Set up an AsyncMock client from a patched httpx.AsyncClient class."""
    mock_client = AsyncMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestVerifyMedicalPaperFound:
    """AC #1 + #2: Artigo encontrado no PubMed retorna dados verificados."""

    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_returns_verified_data_when_paper_found(self, mock_client_cls):
        """AC #2: Retorna título, autores, journal, DOI, ano."""
        mock_client = _setup_async_client(mock_client_cls)

        esearch_resp = _make_response(ESEARCH_FOUND_RESPONSE)
        esummary_resp = _make_response(ESUMMARY_RESPONSE)
        mock_client.get = AsyncMock(side_effect=[esearch_resp, esummary_resp])

        from workflows.whatsapp.tools.verify_paper import verify_medical_paper

        result = await verify_medical_paper.ainvoke({"title": "PARADIGM-HF", "authors": "McMurray"})

        assert "VERIFICADO" in result
        assert "27540849" in result
        assert "N Engl J Med" in result
        assert "McMurray" in result

    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_search_uses_title_and_authors(self, mock_client_cls):
        """AC #1: Busca por título e autores quando disponíveis."""
        mock_client = _setup_async_client(mock_client_cls)

        esearch_resp = _make_response(ESEARCH_NOT_FOUND_RESPONSE)
        mock_client.get = AsyncMock(return_value=esearch_resp)

        from workflows.whatsapp.tools.verify_paper import verify_medical_paper

        await verify_medical_paper.ainvoke({"title": "PARADIGM-HF", "authors": "McMurray"})

        call_args = mock_client.get.call_args_list[0]
        params = call_args[1]["params"]
        assert "PARADIGM-HF" in params["term"]
        assert "McMurray" in params["term"]

    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_search_uses_title_only_when_no_authors(self, mock_client_cls):
        """AC #1: Busca só por título quando autores não fornecidos."""
        mock_client = _setup_async_client(mock_client_cls)

        esearch_resp = _make_response(ESEARCH_NOT_FOUND_RESPONSE)
        mock_client.get = AsyncMock(return_value=esearch_resp)

        from workflows.whatsapp.tools.verify_paper import verify_medical_paper

        await verify_medical_paper.ainvoke({"title": "PARADIGM-HF"})

        call_args = mock_client.get.call_args_list[0]
        params = call_args[1]["params"]
        assert params["term"] == "PARADIGM-HF"


class TestVerifyMedicalPaperNotFound:
    """AC #3: Artigo NÃO encontrado no PubMed."""

    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_returns_warning_when_not_found(self, mock_client_cls):
        """AC #3: Retorna aviso para não citar o artigo."""
        mock_client = _setup_async_client(mock_client_cls)

        esearch_resp = _make_response(ESEARCH_NOT_FOUND_RESPONSE)
        mock_client.get = AsyncMock(return_value=esearch_resp)

        from workflows.whatsapp.tools.verify_paper import verify_medical_paper

        result = await verify_medical_paper.ainvoke({"title": "Artigo Inventado Que Não Existe"})

        assert "NÃO ENCONTRADO" in result
        assert "NÃO cite" in result


class TestVerifyMedicalPaperError:
    """AC #4: PubMed API indisponível (timeout/erro)."""

    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_returns_caveat_on_timeout(self, mock_client_cls):
        """AC #4: Timeout retorna mensagem de ressalva."""
        mock_client = _setup_async_client(mock_client_cls)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        from workflows.whatsapp.tools.verify_paper import verify_medical_paper

        result = await verify_medical_paper.ainvoke({"title": "PARADIGM-HF"})

        assert "indisponível" in result.lower() or "ressalva" in result.lower()

    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_returns_caveat_on_http_error(self, mock_client_cls):
        """AC #4: Erro HTTP retorna mensagem de ressalva."""
        mock_client = _setup_async_client(mock_client_cls)

        error_response = httpx.Response(
            status_code=500, request=httpx.Request("GET", "http://test")
        )
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=error_response.request, response=error_response
            )
        )

        from workflows.whatsapp.tools.verify_paper import verify_medical_paper

        result = await verify_medical_paper.ainvoke({"title": "PARADIGM-HF"})

        assert "indisponível" in result.lower() or "ressalva" in result.lower()

    @patch("workflows.whatsapp.tools.verify_paper.asyncio.sleep", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_retries_before_giving_up(self, mock_client_cls, mock_sleep):
        """AC #4: Timeout com 2 retries (3 tentativas total)."""
        mock_client = _setup_async_client(mock_client_cls)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        from workflows.whatsapp.tools.verify_paper import verify_medical_paper

        result = await verify_medical_paper.ainvoke({"title": "PARADIGM-HF"})

        # 3 attempts total (1 initial + 2 retries)
        assert mock_client.get.call_count == 3
        assert "indisponível" in result.lower() or "ressalva" in result.lower()

    @patch("workflows.whatsapp.tools.verify_paper.asyncio.sleep", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.verify_paper.httpx.AsyncClient")
    async def test_retries_esummary_before_giving_up(self, mock_client_cls, mock_sleep):
        """AC #4: Retry no esummary (segunda chamada) também funciona."""
        mock_client = _setup_async_client(mock_client_cls)

        esearch_resp = _make_response(ESEARCH_FOUND_RESPONSE)
        mock_client.get = AsyncMock(
            side_effect=[
                esearch_resp,
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
            ]
        )

        from workflows.whatsapp.tools.verify_paper import verify_medical_paper

        result = await verify_medical_paper.ainvoke({"title": "PARADIGM-HF"})

        # 1 esearch + 3 esummary attempts = 4 total
        assert mock_client.get.call_count == 4
        assert "indisponível" in result.lower() or "ressalva" in result.lower()
