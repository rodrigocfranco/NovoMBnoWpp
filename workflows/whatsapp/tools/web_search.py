"""Tool: web search via Tavily with competitor domain blocking."""

import httpx
import structlog
from django.conf import settings
from langchain_core.tools import tool
from tavily import AsyncTavilyClient

from workflows.services.config_service import ConfigService

logger = structlog.get_logger(__name__)

FALLBACK_COMPETITOR_DOMAINS = [
    "medgrupo.com.br",
    "grupomedcof.com.br",
    "med.estrategia.com",
    "estrategia.com",
    "medcel.com.br",
    "sanarmed.com",
    "sanarflix.com.br",
    "sanar.com.br",
    "aristo.com.br",
    "eumedicoresidente.com.br",
    "revisamed.com.br",
    "medprovas.com.br",
    "vrmed.com.br",
    "medmentoria.com",
    "oresidente.org",
    "afya.com.br",
]

MAX_CONTENT_LENGTH = 400
FALLBACK_TAVILY_TIMEOUT = 10


async def _get_tavily_timeout() -> int:
    """Load Tavily timeout from ConfigService with hardcoded fallback."""
    try:
        return await ConfigService.get("timeout:tavily")
    except Exception:
        logger.warning("tavily_timeout_config_not_found", fallback=FALLBACK_TAVILY_TIMEOUT)
        return FALLBACK_TAVILY_TIMEOUT


async def _get_blocked_domains() -> list[str]:
    """Load blocked competitor domains from Config model with hardcoded fallback."""
    try:
        config_value = await ConfigService.get("blocked_competitors")
        if isinstance(config_value, dict):
            return config_value.get("domains", FALLBACK_COMPETITOR_DOMAINS)
        if isinstance(config_value, list):
            return config_value
    except Exception:
        logger.warning("blocked_competitors_config_not_found", fallback="hardcoded")
    return FALLBACK_COMPETITOR_DOMAINS


@tool
async def web_search(query: str) -> str:
    """Busca web APENAS quando RAG/drug_lookup falharam ou info muito recente.

    **QUANDO USAR (RESTRIÇÕES RÍGIDAS):**
    - rag_medical_search retornou 0-1 documentos insuficientes
    - Informação sobre evento/diretriz MUITO recente (últimos 7 dias)
    - Tópico fora do escopo médico da base Medway
    - drug_lookup não encontrou o medicamento

    **QUANDO NÃO USAR (CRÍTICO):**
    - rag_medical_search JÁ retornou ≥2 documentos relevantes → **NÃO CHAME WEB**
    - drug_lookup JÁ respondeu a pergunta → **NÃO CHAME WEB**
    - Pergunta sobre protocolo clínico comum → **SEMPRE tente RAG primeiro**
    - Cálculos ou verificação de artigos → use ferramentas específicas

    **REGRA DE OURO:** Web search é ÚLTIMO RECURSO após RAG/drug_lookup falharem.
    Evita redundância e prioriza fontes médicas confiáveis sobre resultados genéricos.

    **CONTRA-EXEMPLO:** "protocolo de hipertensão" ❌ (RAG tem isso, não chame web!)

    Args:
        query: Consulta médica quando outras fontes falharam.
    """
    blocked_domains = await _get_blocked_domains()
    timeout = await _get_tavily_timeout()

    try:
        client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
        response = await client.search(
            query=query,
            search_depth="basic",
            topic="general",
            max_results=4,
            include_raw_content=False,
            exclude_domains=blocked_domains,
            timeout=timeout,
        )
    except (TimeoutError, httpx.TimeoutException):
        logger.warning(
            "web_search_timeout",
            tool_name="web_search",
            service="tavily",
            query=query,
        )
        return "Busca web excedeu o tempo limite. Responda com base no seu conhecimento geral."
    except Exception as exc:
        logger.error(
            "web_search_failed",
            tool_name="web_search",
            service="tavily",
            error_type=type(exc).__name__,
            error_message=str(exc),
            query=query,
        )
        return "Erro ao buscar na web. Responda com base no seu conhecimento geral."

    results = response.get("results", [])

    if not results:
        logger.info("web_search_no_results", query=query)
        return (
            "Não foram encontradas fontes web confiáveis para esta consulta. "
            "Responda com base no seu conhecimento geral, sem citar fontes web."
        )

    formatted_parts = []
    for i, result in enumerate(results, start=1):
        title = result.get("title", "Sem título")
        url = result.get("url", "")
        content = result.get("content", "")
        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH] + "..."

        formatted_parts.append(f"[W-{i}] {title}\nURL: {url}\n{content}")

    logger.info(
        "web_search_completed",
        query=query,
        results_count=len(results),
    )

    return "\n\n".join(formatted_parts)
