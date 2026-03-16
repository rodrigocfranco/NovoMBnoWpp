"""Tool: drug_lookup — consulta bulas de medicamentos via PharmaDB API.

PharmaDB REST API com autenticação JWT:
  1. POST /auth/token (troca API key por JWT, TTL 60min)
  2. GET /v1/bulas/busca?q= (busca bulas por nome)
  3. GET /v1/bulas/{id} (bula completa com posologia, contraindicações, etc.)
  4. GET /v1/bulas/{id}/interacoes (interações com referências PubMed)
"""

import asyncio
import re
import time

import httpx
import structlog
from django.conf import settings
from langchain_core.tools import tool

from workflows.services import cache_service
from workflows.services.config_service import ConfigService

logger = structlog.get_logger(__name__)

# Cache TTL: 7 dias (bulas ANVISA são estáveis)
DRUG_CACHE_TTL = 7 * 24 * 3600  # 604800 seconds

PHARMADB_BASE_URL = "https://api.pharmadb.com.br"
PHARMADB_TIMEOUT = 10.0
MAX_RETRIES = 2
FALLBACK_TOOL_TIMEOUT = 20.0

# Paywall pattern — filter out tier-restricted placeholder text
_PAYWALL_PATTERN = re.compile(r"Disponível no plano \w+", re.IGNORECASE)

# JWT token cache (module-level singleton)
_jwt_token: str | None = None
_jwt_expires_at: float = 0.0


async def _get_bulas_timeout() -> float:
    """Load bulas_med global timeout from ConfigService with hardcoded fallback."""
    try:
        return float(await ConfigService.get("timeout:bulas_med"))
    except Exception:
        return FALLBACK_TOOL_TIMEOUT


# Status codes que NÃO devem ser retentados (erro do cliente, não do servidor)
_NON_RETRYABLE_STATUS = frozenset(range(400, 500))


async def _get_jwt_token(client: httpx.AsyncClient) -> str | None:
    """Get JWT token from PharmaDB, using cache if still valid."""
    global _jwt_token, _jwt_expires_at

    # Return cached token if still valid (with 60s margin)
    if _jwt_token and time.time() < (_jwt_expires_at - 60):
        return _jwt_token

    api_key = getattr(settings, "PHARMADB_API_KEY", None)
    if not api_key:
        return None

    try:
        response = await client.post(
            f"{PHARMADB_BASE_URL}/auth/token",
            headers={"x-api-key": api_key},
        )
        response.raise_for_status()
        data = response.json()
        _jwt_token = data["access_token"]
        _jwt_expires_at = time.time() + data.get("expires_in", 3600)
        logger.info("pharmadb_jwt_obtained", tier=data.get("tier", "unknown"))
        return _jwt_token
    except Exception as exc:
        logger.warning("pharmadb_jwt_failed", error=str(exc))
        return None


async def _request_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    token: str,
) -> httpx.Response | None:
    """Execute HTTP GET with retry and exponential backoff.

    Retries only on network errors and server errors (5xx).
    Client errors (4xx) fail immediately.
    """
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _NON_RETRYABLE_STATUS:
                logger.warning(
                    "pharmadb_client_error",
                    status_code=e.response.status_code,
                    url=url,
                )
                return None
            if attempt == MAX_RETRIES - 1:
                logger.warning(
                    "pharmadb_unavailable",
                    error=str(e),
                    attempts=MAX_RETRIES,
                )
                return None
            await asyncio.sleep(1.0 * (attempt + 1))
        except httpx.RequestError as e:
            if attempt == MAX_RETRIES - 1:
                logger.warning(
                    "pharmadb_unavailable",
                    error=str(e),
                    attempts=MAX_RETRIES,
                )
                return None
            await asyncio.sleep(1.0 * (attempt + 1))
    return None


def _clean_text(text: str) -> str:
    """Remove paywall placeholder text from API responses."""
    if not text or _PAYWALL_PATTERN.search(text):
        return ""
    return text


def _format_interactions(interactions: list[dict]) -> str:
    """Format structured interaction data from /v1/bulas/{id}/interacoes."""
    if not interactions:
        return ""

    parts = ["\n**Interações Medicamentosas:**"]
    all_refs: list[dict] = []

    for inter in interactions[:5]:
        pa_b = inter.get("pa_b", {})
        gravidade = inter.get("gravidade", "")
        efeito = inter.get("efeito_clinico", "")
        manejo = inter.get("manejo_clinico", "")

        name = pa_b.get("nome_dcb", "") if isinstance(pa_b, dict) else ""
        if not name:
            continue

        severity_icon = {"grave": "🔴", "moderada": "🟡", "leve": "🟢"}.get(
            gravidade, "⚪"
        )
        line = f"- {severity_icon} **{name}** ({gravidade})"
        if efeito:
            line += f": {efeito}"
        if manejo:
            line += f" → Manejo: {manejo}"
        parts.append(line)

        for ref in inter.get("referencias", []):
            if ref.get("url") and ref not in all_refs:
                all_refs.append(ref)

    if len(parts) == 1:
        return ""

    if all_refs:
        parts.append("\n**Referências científicas:**")
        for ref in all_refs[:5]:
            url = ref.get("url", "")
            text = ref.get("text", "")
            parts.append(f"  - {text} ({url})" if text else f"  - {url}")

    return "\n".join(parts)


def _format_bula(
    data: dict, drug_name: str, *, interactions: list[dict] | None = None
) -> str:
    """Format PharmaDB bula response for LLM consumption."""
    produto = data.get("produto", {})
    name = produto.get("nome", drug_name)
    lab = produto.get("laboratorio", "")
    pas = produto.get("principios_ativos", [])

    parts = [f"💊 **{name}**"]

    if pas:
        parts.append(f"Princípios ativos: {', '.join(pas)}")
    if lab:
        parts.append(f"Laboratório: {lab}")

    if indicacoes := _clean_text(data.get("texto_indicacoes", "")):
        parts.append(f"\n**Indicações:** {indicacoes}")

    if posologia := _clean_text(data.get("texto_posologia", "")):
        parts.append(f"\n**Posologia:** {posologia}")

    if contra := _clean_text(data.get("texto_contraindicacoes", "")):
        parts.append(f"\n**Contraindicações:** {contra}")

    # Prefer structured interactions with references over raw text
    if interactions:
        interactions_text = _format_interactions(interactions)
        if interactions_text:
            parts.append(interactions_text)
    elif interacoes_text := _clean_text(data.get("texto_interacoes", "")):
        parts.append(f"\n**Interações Medicamentosas:** {interacoes_text}")

    if adversos := _clean_text(data.get("texto_reacoes_adversas", "")):
        parts.append(f"\n**Reações Adversas:** {adversos}")

    parts.append(f"\n📋 Fonte: Bula ANVISA — {name}")

    logger.info("drug_lookup_executed", provider="pharmadb", drug_name=drug_name)
    return "\n".join(parts)


def _format_product_summary(data: dict, drug_name: str) -> str:
    """Format PharmaDB product search result (when no bula is available)."""
    name = data.get("nome", drug_name)
    parts = [f"💊 **{name}**"]

    if pas := data.get("principios_ativos", []):
        parts.append(f"Princípios ativos: {', '.join(pas)}")
    if lab := data.get("laboratorio", ""):
        parts.append(f"Laboratório: {lab}")
    if tarja := data.get("tarja", ""):
        parts.append(f"Tarja: {tarja}")
    if classe := data.get("classe_terapeutica", ""):
        parts.append(f"Classe terapêutica: {classe}")

    parts.append(f"\n📋 Fonte: ANVISA — {name} (via PharmaDB)")
    parts.append("\n⚠️ Bula completa não disponível. Dados resumidos do registro ANVISA.")

    logger.info("drug_lookup_executed", provider="pharmadb_summary", drug_name=drug_name)
    return "\n".join(parts)


async def _drug_lookup_impl(drug_name: str) -> str:
    """Core implementation with PharmaDB JWT auth."""
    api_key = getattr(settings, "PHARMADB_API_KEY", None)
    if not api_key:
        return (
            "Consulta de bulas não disponível (provedor não configurado). "
            "Responda com base no seu conhecimento geral."
        )

    async with httpx.AsyncClient(timeout=PHARMADB_TIMEOUT) as client:
        # Step 1: Get JWT token
        token = await _get_jwt_token(client)
        if not token:
            return (
                "Consulta de bulas temporariamente indisponível (falha na autenticação). "
                "Responda com base no seu conhecimento geral."
            )

        # Step 2: Search bulas by drug name (request more to find extracted ones)
        response = await _request_with_retry(
            client,
            f"{PHARMADB_BASE_URL}/v1/bulas/busca",
            params={"q": drug_name, "per_page": 10},
            token=token,
        )

        if response:
            data = response.json()
            items = data.get("items", [])

            # Prefer bulas with extracted text (extraido=True)
            extracted = [i for i in items if i.get("extraido")]
            target = extracted[0] if extracted else (items[0] if items else None)

            if target:
                bula_id = target.get("id")
                if bula_id:
                    # Fetch bula detail and interactions in parallel
                    bula_task = _request_with_retry(
                        client,
                        f"{PHARMADB_BASE_URL}/v1/bulas/{bula_id}",
                        params={},
                        token=token,
                    )
                    inter_task = _request_with_retry(
                        client,
                        f"{PHARMADB_BASE_URL}/v1/bulas/{bula_id}/interacoes",
                        params={"per_page": 10},
                        token=token,
                    )
                    bula_response, inter_response = await asyncio.gather(
                        bula_task, inter_task
                    )

                    if bula_response:
                        interactions = None
                        if inter_response:
                            inter_data = inter_response.json()
                            interactions = inter_data.get("items", [])
                        return _format_bula(
                            bula_response.json(),
                            drug_name,
                            interactions=interactions,
                        )

        # Fallback: try product search (less detail, but still useful)
        logger.info("pharmadb_bula_not_found_trying_products", drug_name=drug_name)
        response = await _request_with_retry(
            client,
            f"{PHARMADB_BASE_URL}/v1/produtos/busca",
            params={"q": drug_name, "per_page": 1},
            token=token,
        )
        if response:
            data = response.json()
            items = data.get("items", [])
            if items:
                return _format_product_summary(items[0], drug_name)

    logger.info("drug_not_found", drug_name=drug_name)
    return (
        f"Medicamento '{drug_name}' não encontrado na base PharmaDB. "
        "Verifique o nome comercial ou genérico e tente novamente."
    )


@tool
async def drug_lookup(drug_name: str) -> str:
    """Consulta bula ANVISA com dados farmacológicos GERAIS de um medicamento.

    **QUANDO USAR:**
    - Contraindicações absolutas de uma droga (ex: "contraindicações de losartana")
    - Efeitos adversos gerais (ex: "efeitos colaterais de metformina")
    - Posologia GERAL sem contexto clínico específico (ex: "dose usual de dipirona")
    - Interações medicamentosas conhecidas (ex: "varfarina interage com quê")
    - Classe terapêutica, princípio ativo, laboratório

    **QUANDO NÃO USAR:**
    - Droga + contexto clínico (ex: "dose de amoxicilina para otite") → use rag_medical_search
    - Protocolos de tratamento de doenças → use rag_medical_search
    - Cálculo de dose por peso/idade → use medical_calculator
    - Verificar artigo sobre a droga → use verify_medical_paper

    **EXEMPLO:** "Quais as contraindicações de enalapril?" ✅ (info geral de bula)
    **CONTRA-EXEMPLO:** "Qual a dose de enalapril para hipertensão?" ❌ (contexto → RAG)

    Args:
        drug_name: Nome comercial ou genérico do medicamento.
    """
    if not drug_name or not drug_name.strip():
        return "Por favor, informe o nome do medicamento que deseja consultar."

    drug_name = drug_name.strip()

    # Check cache first (7 days TTL)
    cached_output = await cache_service.get("drug_lookup", drug_name.lower())
    if cached_output is not None:
        logger.info("drug_lookup_cache_hit", drug_name=drug_name)
        return cached_output

    tool_timeout = await _get_bulas_timeout()

    try:
        output = await asyncio.wait_for(_drug_lookup_impl(drug_name), timeout=tool_timeout)

        # Cache successful results (7 days TTL)
        # Don't cache "not found" or error messages
        if not any(phrase in output.lower() for phrase in ["não encontrado", "não disponível", "indisponível"]):
            await cache_service.set("drug_lookup", drug_name.lower(), output, ttl_seconds=DRUG_CACHE_TTL)

        return output
    except TimeoutError:
        logger.warning(
            "drug_lookup_timeout",
            tool_name="drug_lookup",
            service="pharmadb",
            drug_name=drug_name,
            timeout=tool_timeout,
        )
        return (
            f"A consulta de '{drug_name}' excedeu o tempo limite. "
            "Tente novamente em alguns instantes."
        )
