"""Tests for drug_lookup tool — PharmaDB API with JWT auth (Story 2.4)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from workflows.whatsapp.tools.bulas_med import (
    _clean_text,
    _drug_lookup_impl,
    _format_bula,
    _format_interactions,
    _format_product_summary,
    drug_lookup,
)


def _bula_search_response() -> dict:
    """PharmaDB /v1/bulas/busca response fixture."""
    return {
        "total": 1,
        "page": 1,
        "per_page": 3,
        "items": [
            {
                "id": 101,
                "tipo": "paciente",
                "produto_id": 1284,
                "produto_nome": "AMOXICILINA",
                "tem_indicacoes": True,
                "tem_interacoes": True,
                "extraido": True,
            }
        ],
    }


def _bula_detail_response() -> dict:
    """PharmaDB /v1/bulas/{id} response fixture."""
    return {
        "id": 101,
        "tipo": "paciente",
        "produto": {
            "id": 1284,
            "nome": "AMOXICILINA",
            "registro_anvisa": "1130003780014",
            "laboratorio": "EMS S/A",
            "principios_ativos": ["amoxicilina tri-hidratada"],
        },
        "texto_indicacoes": "Infecções bacterianas do trato respiratório.",
        "texto_posologia": "Adultos: 500mg a cada 8h. Pediátrico: 25-50mg/kg/dia.",
        "texto_contraindicacoes": "Hipersensibilidade a penicilinas.",
        "texto_interacoes": "Metotrexato: reduz excreção renal.",
        "texto_reacoes_adversas": "Diarreia, náusea, rash cutâneo.",
    }


def _product_search_response() -> dict:
    """PharmaDB /v1/produtos/busca response fixture."""
    return {
        "total": 1,
        "page": 1,
        "per_page": 1,
        "items": [
            {
                "id": 1284,
                "nome": "AMOXICILINA",
                "principios_ativos": ["amoxicilina tri-hidratada"],
                "laboratorio": "EMS S/A",
                "tarja": "sem_tarja",
                "classe_terapeutica": "PENICILINAS",
            }
        ],
    }


def _jwt_response() -> dict:
    """PharmaDB /auth/token response fixture."""
    return {
        "access_token": "eyJhbGciOi.test.token",
        "token_type": "bearer",
        "expires_in": 3600,
        "tier": "free",
    }


def _interactions_response() -> dict:
    """PharmaDB /v1/bulas/{id}/interacoes response fixture."""
    return {
        "total": 2,
        "page": 1,
        "per_page": 10,
        "items": [
            {
                "id": 501,
                "pa_a": {"id": 10, "nome_dcb": "amoxicilina"},
                "pa_b": {"id": 20, "nome_dcb": "metotrexato"},
                "gravidade": "grave",
                "efeito_clinico": "Aumento da toxicidade do metotrexato",
                "mecanismo": "Redução da excreção renal",
                "manejo_clinico": "Monitorar níveis séricos",
                "referencias": [
                    {
                        "url": "https://pubmed.ncbi.nlm.nih.gov/12345678",
                        "text": "Smith et al. Drug Interactions Review, 2023",
                    }
                ],
            },
            {
                "id": 502,
                "pa_a": {"id": 10, "nome_dcb": "amoxicilina"},
                "pa_b": {"id": 30, "nome_dcb": "varfarina"},
                "gravidade": "moderada",
                "efeito_clinico": "Aumento do efeito anticoagulante",
                "mecanismo": "Alteração da flora intestinal",
                "manejo_clinico": "Monitorar INR",
                "referencias": [],
            },
        ],
    }


def _mock_response(data: dict | list, status_code: int = 200) -> httpx.Response:
    """Create a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=response
        )
    return response


class TestCleanText:
    """Tests for paywall text filtering."""

    def test_clean_text_normal(self):
        """Normal text passes through."""
        assert _clean_text("Infecções bacterianas") == "Infecções bacterianas"

    def test_clean_text_paywall(self):
        """Paywall placeholder is filtered out."""
        assert _clean_text("Disponível no plano Starter") == ""

    def test_clean_text_paywall_case_insensitive(self):
        """Paywall detection is case-insensitive."""
        assert _clean_text("disponível no plano Pro") == ""

    def test_clean_text_empty(self):
        """Empty string returns empty."""
        assert _clean_text("") == ""


class TestFormatInteractions:
    """Tests for structured interaction formatting."""

    def test_format_interactions_with_refs(self):
        """Interactions include severity, effect, and PubMed references."""
        items = _interactions_response()["items"]
        result = _format_interactions(items)

        assert "metotrexato" in result
        assert "grave" in result
        assert "pubmed.ncbi.nlm.nih.gov" in result
        assert "varfarina" in result
        assert "moderada" in result

    def test_format_interactions_empty(self):
        """Empty interactions list returns empty string."""
        assert _format_interactions([]) == ""

    def test_format_interactions_no_pa_b(self):
        """Interactions without pa_b name are skipped."""
        items = [{"pa_b": {}, "gravidade": "leve"}]
        assert _format_interactions(items) == ""


class TestFormatBula:
    """Tests for bula formatting."""

    def test_format_bula_complete(self):
        """All bula fields are rendered."""
        result = _format_bula(_bula_detail_response(), "amoxicilina")

        assert "AMOXICILINA" in result
        assert "amoxicilina tri-hidratada" in result
        assert "EMS S/A" in result
        assert "Indicações" in result
        assert "Posologia" in result
        assert "Contraindicações" in result
        assert "Interações" in result
        assert "Reações Adversas" in result
        assert "ANVISA" in result

    def test_format_bula_with_interactions(self):
        """Structured interactions with PubMed refs replace raw text."""
        items = _interactions_response()["items"]
        result = _format_bula(
            _bula_detail_response(), "amoxicilina", interactions=items
        )

        assert "metotrexato" in result
        assert "pubmed.ncbi.nlm.nih.gov" in result
        # Raw texto_interacoes should NOT appear when structured data is present
        assert "Metotrexato: reduz excreção renal." not in result

    def test_format_bula_paywall_fields_filtered(self):
        """Paywall placeholder text is filtered out."""
        data = {
            "produto": {"nome": "TESTE", "principios_ativos": []},
            "texto_indicacoes": "Indicação real",
            "texto_posologia": "Disponível no plano Starter",
            "texto_reacoes_adversas": "Disponível no plano Pro",
        }
        result = _format_bula(data, "teste")

        assert "Indicações" in result
        assert "Posologia" not in result
        assert "Reações Adversas" not in result

    def test_format_bula_partial(self):
        """Missing fields are gracefully skipped."""
        data = {
            "produto": {"nome": "TESTE", "principios_ativos": []},
            "texto_indicacoes": "Indicação teste",
        }
        result = _format_bula(data, "teste")

        assert "TESTE" in result
        assert "Indicações" in result
        assert "Posologia" not in result

    def test_format_product_summary(self):
        """Product summary includes key info and warning."""
        data = _product_search_response()["items"][0]
        result = _format_product_summary(data, "amoxicilina")

        assert "AMOXICILINA" in result
        assert "PENICILINAS" in result
        assert "Bula completa não disponível" in result


class TestDrugLookupImpl:
    """Tests for _drug_lookup_impl with mocked HTTP."""

    @patch("workflows.whatsapp.tools.bulas_med.settings")
    async def test_no_api_key_returns_not_configured(self, mock_settings):
        """No API key → returns 'not configured' message."""
        mock_settings.PHARMADB_API_KEY = ""

        result = await _drug_lookup_impl("amoxicilina")

        assert "não disponível" in result.lower()
        assert "não configurado" in result.lower() or "conhecimento geral" in result.lower()

    @patch("workflows.whatsapp.tools.bulas_med._jwt_token", None)
    @patch("workflows.whatsapp.tools.bulas_med._jwt_expires_at", 0.0)
    @patch("workflows.whatsapp.tools.bulas_med.settings")
    @patch("workflows.whatsapp.tools.bulas_med.httpx.AsyncClient")
    async def test_full_flow_bula_found(self, mock_client_cls, mock_settings):
        """Happy path: JWT → bula search → bula detail + interacoes → formatted."""
        mock_settings.PHARMADB_API_KEY = "pdb_test"

        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Sequence: POST /auth/token → GET /bulas/busca → GET /bulas/101 + GET /bulas/101/interacoes
        mock_client.post.return_value = _mock_response(_jwt_response())
        mock_client.get.side_effect = [
            _mock_response(_bula_search_response()),
            _mock_response(_bula_detail_response()),
            _mock_response(_interactions_response()),
        ]

        result = await _drug_lookup_impl("amoxicilina")

        assert "AMOXICILINA" in result
        assert "Posologia" in result
        assert "ANVISA" in result
        assert "metotrexato" in result
        assert "pubmed" in result.lower()

    @patch("workflows.whatsapp.tools.bulas_med._jwt_token", None)
    @patch("workflows.whatsapp.tools.bulas_med._jwt_expires_at", 0.0)
    @patch("workflows.whatsapp.tools.bulas_med.settings")
    @patch("workflows.whatsapp.tools.bulas_med.httpx.AsyncClient")
    async def test_jwt_failure_returns_unavailable(self, mock_client_cls, mock_settings):
        """JWT auth fails → returns unavailable message."""
        mock_settings.PHARMADB_API_KEY = "pdb_test"

        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_client.post.side_effect = httpx.RequestError("Connection refused")

        result = await _drug_lookup_impl("amoxicilina")

        assert "indisponível" in result.lower()

    @patch("workflows.whatsapp.tools.bulas_med._jwt_token", None)
    @patch("workflows.whatsapp.tools.bulas_med._jwt_expires_at", 0.0)
    @patch("workflows.whatsapp.tools.bulas_med.settings")
    @patch("workflows.whatsapp.tools.bulas_med.httpx.AsyncClient")
    async def test_bula_not_found_falls_back_to_product(self, mock_client_cls, mock_settings):
        """No bula found → falls back to product search summary."""
        mock_settings.PHARMADB_API_KEY = "pdb_test"

        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        empty_bula_search = {"total": 0, "page": 1, "per_page": 3, "items": []}

        mock_client.post.return_value = _mock_response(_jwt_response())
        mock_client.get.side_effect = [
            _mock_response(empty_bula_search),
            _mock_response(_product_search_response()),
        ]

        result = await _drug_lookup_impl("amoxicilina")

        assert "AMOXICILINA" in result
        assert "Bula completa não disponível" in result

    @patch("workflows.whatsapp.tools.bulas_med._jwt_token", None)
    @patch("workflows.whatsapp.tools.bulas_med._jwt_expires_at", 0.0)
    @patch("workflows.whatsapp.tools.bulas_med.settings")
    @patch("workflows.whatsapp.tools.bulas_med.httpx.AsyncClient")
    async def test_both_searches_empty_returns_not_found(self, mock_client_cls, mock_settings):
        """Both bula and product searches return empty → not found message."""
        mock_settings.PHARMADB_API_KEY = "pdb_test"

        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        empty_response = {"total": 0, "page": 1, "per_page": 3, "items": []}

        mock_client.post.return_value = _mock_response(_jwt_response())
        mock_client.get.side_effect = [
            _mock_response(empty_response),
            _mock_response(empty_response),
        ]

        result = await _drug_lookup_impl("MedicamentoInexistente")

        assert "não encontrado" in result.lower()

    @patch("workflows.whatsapp.tools.bulas_med._jwt_token", None)
    @patch("workflows.whatsapp.tools.bulas_med._jwt_expires_at", 0.0)
    @patch("workflows.whatsapp.tools.bulas_med.settings")
    @patch("workflows.whatsapp.tools.bulas_med.httpx.AsyncClient")
    @patch("workflows.whatsapp.tools.bulas_med.asyncio.sleep", new_callable=AsyncMock)
    async def test_4xx_no_retry(self, mock_sleep, mock_client_cls, mock_settings):
        """4xx errors are not retried."""
        mock_settings.PHARMADB_API_KEY = "pdb_test"

        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_client.post.return_value = _mock_response(_jwt_response())
        # Bula search returns 404, product search returns 404
        mock_client.get.side_effect = [
            _mock_response({}, status_code=404),
            _mock_response({}, status_code=404),
        ]

        result = await _drug_lookup_impl("amoxicilina")

        assert "não encontrado" in result.lower()
        mock_sleep.assert_not_called()


class TestDrugLookupTool:
    """Tests for the @tool wrapper."""

    async def test_empty_drug_name(self):
        """Empty drug name → returns guidance message."""
        result = await drug_lookup.ainvoke({"drug_name": ""})
        assert "informe" in result.lower()

    async def test_whitespace_drug_name(self):
        """Whitespace drug name → returns guidance message."""
        result = await drug_lookup.ainvoke({"drug_name": "   "})
        assert "informe" in result.lower()

    def test_tool_has_descriptive_docstring(self):
        """Tool has docstring for LLM to decide when to use it."""
        assert drug_lookup.description
        assert len(drug_lookup.description) > 20
        assert "medicamento" in drug_lookup.description.lower()

    def test_tool_is_async(self):
        """Tool must be async for I/O operations."""
        import asyncio

        assert asyncio.iscoroutinefunction(drug_lookup.coroutine)

    @patch("workflows.whatsapp.tools.bulas_med.cache_service")
    @patch("workflows.whatsapp.tools.bulas_med._drug_lookup_impl")
    async def test_global_timeout(self, mock_impl, mock_cache):
        """Tool returns timeout message if execution exceeds timeout."""
        import asyncio

        # Ensure cache miss so the timeout path is exercised
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        async def slow_impl(drug_name: str) -> str:
            await asyncio.sleep(100)
            return "never reached"

        mock_impl.side_effect = slow_impl

        with patch(
            "workflows.whatsapp.tools.bulas_med._get_bulas_timeout",
            new_callable=AsyncMock,
            return_value=0.01,
        ):
            result = await drug_lookup.ainvoke({"drug_name": "Amoxicilina"})

        assert "tempo limite" in result.lower()

    @patch("workflows.whatsapp.tools.bulas_med._drug_lookup_impl")
    async def test_successful_lookup(self, mock_impl):
        """Tool returns formatted result from impl."""
        mock_impl.return_value = "💊 **AMOXICILINA**\nPosologia: 500mg 8/8h"

        result = await drug_lookup.ainvoke({"drug_name": "Amoxicilina"})

        assert "AMOXICILINA" in result
        assert "Posologia" in result
