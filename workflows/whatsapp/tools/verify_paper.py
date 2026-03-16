"""Tool: verify_medical_paper — verifica artigos no PubMed E-utilities."""

import asyncio

import httpx
import structlog
from django.conf import settings
from langchain_core.tools import tool

from workflows.services.config_service import ConfigService

logger = structlog.get_logger(__name__)

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
FALLBACK_PUBMED_TIMEOUT = 5.0


async def _get_pubmed_timeout() -> float:
    """Load PubMed timeout from ConfigService with hardcoded fallback."""
    try:
        return float(await ConfigService.get("timeout:pubmed"))
    except Exception:
        logger.warning("pubmed_timeout_config_not_found", fallback=FALLBACK_PUBMED_TIMEOUT)
        return FALLBACK_PUBMED_TIMEOUT


@tool
async def verify_medical_paper(title: str, authors: str = "") -> str:
    """Verifica existência e valida artigos científicos citados pelo usuário no PubMed.

    **QUANDO USAR:**
    - Usuário menciona artigo específico (título, DOI, PMID)
    - Precisa validar se estudo citado existe realmente
    - Extrair detalhes de um paper mencionado (autores, journal, ano)
    - Verificar se citação do aluno está correta

    **QUANDO NÃO USAR:**
    - Buscar artigos sobre um tópico → use rag_medical_search ou web_search
    - Pergunta genérica sobre tratamento → use rag_medical_search
    - Verificar apenas autor sem título → insuficiente, use web_search

    **EXEMPLO:** "verifique o artigo 'SPRINT Trial hypertension'" ✅
    **CONTRA-EXEMPLO:** "busque artigos sobre hipertensão" ❌ (busca → use RAG/web)

    Args:
        title: Título completo ou parcial do artigo citado.
        authors: Nome dos autores (opcional, aumenta precisão).
    """
    query = title if not authors else f"{title} {authors}"

    params: dict[str, str | int] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": 3,
    }
    if api_key := getattr(settings, "NCBI_API_KEY", None):
        params["api_key"] = api_key
    if email := getattr(settings, "NCBI_EMAIL", None):
        params["email"] = email
        params["tool"] = "mb-wpp"

    timeout = await _get_pubmed_timeout()

    async with httpx.AsyncClient(timeout=timeout) as client:
        # ── esearch: buscar PMIDs ──
        for attempt in range(3):
            try:
                response = await client.get(PUBMED_ESEARCH_URL, params=params)
                response.raise_for_status()
                break
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == 2:
                    logger.warning(
                        "pubmed_api_unavailable",
                        tool_name="verify_medical_paper",
                        service="pubmed",
                        error_type=type(e).__name__,
                        error=str(e),
                        phase="esearch",
                    )
                    return "⚠️ Verificação de artigo indisponível no momento. Cite com ressalva."
                await asyncio.sleep(1.0 * (attempt + 1))

        data = response.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])

        if not id_list:
            logger.info("pubmed_paper_not_found", query=query)
            return (
                "⚠️ ARTIGO NÃO ENCONTRADO no PubMed. "
                "NÃO cite este estudo — pode ser alucinação do LLM."
            )

        # ── esummary: metadados ──
        pmids = ",".join(id_list)
        summary_params: dict[str, str] = {
            "db": "pubmed",
            "id": pmids,
            "retmode": "json",
        }
        if api_key:
            summary_params["api_key"] = api_key
        if email:
            summary_params["email"] = email
            summary_params["tool"] = "mb-wpp"

        for attempt in range(3):
            try:
                response = await client.get(PUBMED_ESUMMARY_URL, params=summary_params)
                response.raise_for_status()
                break
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == 2:
                    logger.warning(
                        "pubmed_api_unavailable",
                        tool_name="verify_medical_paper",
                        service="pubmed",
                        error_type=type(e).__name__,
                        error=str(e),
                        phase="esummary",
                    )
                    return "⚠️ Verificação de artigo indisponível no momento. Cite com ressalva."
                await asyncio.sleep(1.0 * (attempt + 1))

        summary_data = response.json()
        result_parts: list[str] = ["✅ ARTIGO VERIFICADO no PubMed:\n"]

        for pmid in id_list:
            article = summary_data.get("result", {}).get(pmid, {})
            if not article:
                continue

            article_title = article.get("title", "N/A")
            journal = article.get("source", "N/A")
            pub_date = article.get("pubdate", "N/A")
            doi = article.get("elocationid", "N/A").removeprefix("doi: ")
            author_list = article.get("authors", [])
            authors_str = ", ".join(a.get("name", "") for a in author_list[:5])
            if len(author_list) > 5:
                authors_str += " et al."

            result_parts.append(
                f"- **PMID:** {pmid}\n"
                f"  **Título:** {article_title}\n"
                f"  **Autores:** {authors_str}\n"
                f"  **Journal:** {journal}\n"
                f"  **Data:** {pub_date}\n"
                f"  **DOI:** {doi}\n"
                f"  **URL:** https://pubmed.ncbi.nlm.nih.gov/{pmid}/\n"
            )

        logger.info("pubmed_paper_verified", pmids=pmids, query=query)
        return "\n".join(result_parts)
