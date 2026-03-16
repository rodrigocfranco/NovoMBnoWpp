"""RAG medical search tool for knowledge base queries."""

import time

import structlog
from langchain_core.tools import tool

from workflows.providers.pinecone import get_pinecone
from workflows.services import cache_service

logger = structlog.get_logger(__name__)

# Cache TTL: 24h (respostas médicas mudam raramente)
RAG_CACHE_TTL = 24 * 3600  # 86400 seconds


@tool
async def rag_medical_search(query: str) -> str:
    """Busca protocolos clínicos, guidelines e condutas na base Medway validada.

    **QUANDO USAR:**
    - Protocolos de tratamento (ex: "manejo de pneumonia", "protocolo TEV")
    - Droga + contexto clínico (ex: "amoxicilina para otite média", "dose de heparina em gestante")
    - Diagnóstico diferencial, fisiopatologia, condutas médicas
    - Guidelines atualizadas (SBP, AHA, ESC)

    **QUANDO NÃO USAR:**
    - Dose geral de droga SEM contexto clínico → use drug_lookup
    - Cálculos numéricos (IMC, clearance) → use medical_calculator
    - Verificar artigo específico citado pelo usuário → use verify_medical_paper
    - Informação muito recente (<7 dias) → use web_search

    **EXEMPLO:** "Qual a dose de amoxicilina para otite média?" ✅ (contexto clínico)
    **CONTRA-EXEMPLO:** "Qual a dose de amoxicilina?" ❌ (sem contexto → drug_lookup)

    Args:
        query: Pergunta médica com contexto clínico ou protocolo.
    """
    start = time.perf_counter()

    # Check cache first (24h TTL)
    cached_output = await cache_service.get("rag", query)
    if cached_output is not None:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "rag_cache_hit",
            query=query[:80],
            latency_ms=round(latency_ms, 1),
        )
        return cached_output

    try:
        provider = await get_pinecone()
        results = await provider.query_similar(query=query, top_k=5)
    except Exception as exc:
        logger.error(
            "rag_search_failed",
            tool_name="rag_medical_search",
            service="pinecone",
            error_type=type(exc).__name__,
            error_message=str(exc),
            query=query[:80],
        )
        return (
            "Erro ao buscar na base de conhecimento. O serviço está temporariamente indisponível."
        )

    latency_ms = (time.perf_counter() - start) * 1000

    if not results:
        logger.info("rag_search_zero_coverage", query=query[:80], latency_ms=round(latency_ms, 1))
        return (
            "Não encontrei conteúdo curado sobre este tema na base de conhecimento. "
            "Posso buscar informações atualizadas na web se necessário."
        )

    formatted_parts = []
    for i, result in enumerate(results, start=1):
        part = (
            f"[{i}] {result['title']}, {result['section']}\n"
            f'   "{result["text"]}"\n'
            f"   Fonte: {result['source']}"
        )
        formatted_parts.append(part)

    output = "\n\n".join(formatted_parts)

    logger.info(
        "tool_executed",
        tool="rag_medical_search",
        query=query[:80],
        results_count=len(results),
        latency_ms=round(latency_ms, 1),
    )

    # Cache successful results (24h TTL)
    if results:  # Only cache non-empty results
        await cache_service.set("rag", query, output, ttl_seconds=RAG_CACHE_TTL)

    return output
