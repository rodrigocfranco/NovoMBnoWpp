#!/usr/bin/env python
"""Teste de performance do cache Redis para ferramentas.

Compara latência:
- COLD: primeira chamada (sem cache)
- WARM: segunda chamada (com cache)

Usage:
    python scripts/test_cache_performance.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

import django

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from workflows.services import cache_service
from workflows.whatsapp.tools.bulas_med import drug_lookup
from workflows.whatsapp.tools.rag_medical import rag_medical_search


class Colors:
    """ANSI color codes."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


async def test_cache_hit(tool_name: str, tool_func, query: str):
    """Test cache performance for a tool.

    Args:
        tool_name: Name of the tool (for display)
        tool_func: LangChain tool (StructuredTool)
        query: Query string
    """
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}🔬 TESTE: {tool_name}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"Query: {Colors.BOLD}{query}{Colors.ENDC}\n")

    # COLD: primeira chamada (sem cache)
    print(f"{Colors.WARNING}❄️  COLD (sem cache):{Colors.ENDC}")
    start = time.perf_counter()
    result_cold = await tool_func.ainvoke(query)
    cold_time = (time.perf_counter() - start) * 1000
    print(f"   Latência: {Colors.BOLD}{cold_time:.0f}ms{Colors.ENDC}")
    print(f"   Tamanho: {len(result_cold)} bytes")

    # WARM: segunda chamada (com cache)
    print(f"\n{Colors.OKGREEN}🔥 WARM (com cache):{Colors.ENDC}")
    start = time.perf_counter()
    result_warm = await tool_func.ainvoke(query)
    warm_time = (time.perf_counter() - start) * 1000
    print(f"   Latência: {Colors.BOLD}{warm_time:.0f}ms{Colors.ENDC}")

    # Validar que resultados são idênticos
    if result_cold != result_warm:
        print(f"{Colors.FAIL}❌ ERRO: Resultados diferentes!{Colors.ENDC}")
        return None

    # Calcular ganho
    speedup = ((cold_time - warm_time) / cold_time) * 100
    saved_ms = cold_time - warm_time

    print(f"\n{Colors.BOLD}📊 GANHO:{Colors.ENDC}")
    if speedup > 90:
        color = Colors.OKGREEN
        icon = "🚀"
    elif speedup > 50:
        color = Colors.OKCYAN
        icon = "⚡"
    else:
        color = Colors.WARNING
        icon = "📈"

    print(f"   {color}{icon} Speedup: {speedup:.1f}%{Colors.ENDC}")
    print(f"   {color}⏱️  Tempo economizado: {saved_ms:.0f}ms{Colors.ENDC}")

    return {
        "tool": tool_name,
        "query": query,
        "cold_ms": cold_time,
        "warm_ms": warm_time,
        "speedup_pct": speedup,
        "saved_ms": saved_ms,
    }


async def main():
    """Run cache performance tests."""
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}⚡ TESTE DE PERFORMANCE - Redis Cache{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")

    # Clear cache before tests
    print(f"\n{Colors.WARNING}🧹 Limpando cache...{Colors.ENDC}")
    await cache_service.clear_namespace("rag")
    await cache_service.clear_namespace("drug_lookup")

    # Test cases
    tests = [
        ("RAG Medical Search", rag_medical_search, "Qual a dose de amoxicilina para otite média?"),
        ("RAG Medical Search #2", rag_medical_search, "Qual o protocolo de manejo de pneumonia comunitária?"),
        ("Drug Lookup", drug_lookup, "Quais as contraindicações de losartana?"),
        ("Drug Lookup #2", drug_lookup, "Quais os efeitos colaterais de metformina?"),
    ]

    results = []
    for tool_name, tool_func, query in tests:
        result = await test_cache_hit(tool_name, tool_func, query)
        if result:
            results.append(result)
        await asyncio.sleep(1)  # Pausa entre testes

    # Summary
    if not results:
        print(f"\n{Colors.FAIL}❌ Nenhum teste concluído.{Colors.ENDC}")
        return

    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}📊 RESUMO GERAL{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")

    avg_cold = sum(r["cold_ms"] for r in results) / len(results)
    avg_warm = sum(r["warm_ms"] for r in results) / len(results)
    avg_speedup = sum(r["speedup_pct"] for r in results) / len(results)
    avg_saved = sum(r["saved_ms"] for r in results) / len(results)

    print(f"{Colors.BOLD}Latência média:{Colors.ENDC}")
    print(f"  COLD (sem cache): {avg_cold:.0f}ms")
    print(f"  WARM (com cache): {avg_warm:.0f}ms")
    print()
    print(f"{Colors.BOLD}Ganho médio:{Colors.ENDC}")
    print(f"  {Colors.OKGREEN}Speedup: {avg_speedup:.1f}%{Colors.ENDC}")
    print(f"  {Colors.OKGREEN}Tempo economizado: {avg_saved:.0f}ms{Colors.ENDC}")
    print()

    # Detailed table
    print(f"{Colors.BOLD}DETALHAMENTO:{Colors.ENDC}")
    print(f"{'Tool':<30} {'COLD':<10} {'WARM':<10} {'Speedup':<10}")
    print("-" * 80)
    for r in results:
        print(
            f"{r['tool']:<30} {r['cold_ms']:<10.0f} {r['warm_ms']:<10.0f} {r['speedup_pct']:<10.1f}%"
        )

    print()
    if avg_speedup > 90:
        print(f"{Colors.OKGREEN}✅ Cache funcionando perfeitamente! (>90% speedup){Colors.ENDC}")
    elif avg_speedup > 50:
        print(f"{Colors.OKCYAN}✅ Cache funcionando bem! (>50% speedup){Colors.ENDC}")
    else:
        print(f"{Colors.WARNING}⚠️  Cache com ganho moderado (<50% speedup){Colors.ENDC}")


if __name__ == "__main__":
    asyncio.run(main())
