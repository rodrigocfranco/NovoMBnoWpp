#!/usr/bin/env python
"""Script de teste local para validar otimizações de tool calling.

Usage:
    python scripts/test_tool_calling.py
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import django

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from langchain_core.messages import AIMessage

from workflows.whatsapp.graph import build_whatsapp_graph
from workflows.whatsapp.state import WhatsAppState


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print colored header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


async def test_query(graph, query: str, expected_tools: list[str], scenario: str):
    """Test a single query and validate tool calling behavior.

    Args:
        graph: Compiled LangGraph instance
        query: User query to test
        expected_tools: List of expected tool names to be called
        scenario: Description of test scenario
    """
    print_header(f"TESTE: {scenario}")
    print(f"📝 Query: {Colors.BOLD}{query}{Colors.ENDC}")
    print(f"🎯 Esperado: {', '.join(expected_tools)} ({len(expected_tools)} tool{'s' if len(expected_tools) > 1 else ''})")
    print("-" * 80)

    # Create unique phone for this test
    phone = f"5511{int(datetime.now().timestamp())}"

    state: WhatsAppState = {
        "phone_number": phone,
        "user_message": query,
        "message_type": "text",
        "media_url": None,
        "wamid": f"wamid.test_{int(datetime.now().timestamp())}",
        "user_id": "test-user",
        "subscription_tier": "premium",
        "is_new_user": False,
        "messages": [],
        "formatted_response": "",
        "additional_responses": [],
        "response_sent": False,
        "trace_id": f"trace-test-{int(datetime.now().timestamp())}",
        "cost_usd": 0.0,
        "provider_used": "unknown",
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "transcribed_text": "",
        "image_message": None,
        "rate_limit_exceeded": False,
        "remaining_daily": 100,
        "rate_limit_warning": "",
    }

    config = {"configurable": {"thread_id": phone}}

    start_time = time.time()
    final_state = None

    try:
        # Usar astream para capturar estados intermediários
        async for chunk in graph.astream(state, config=config):
            # chunk é um dict com {node_name: state_update}
            # Pegar o último valor (state update do último nó executado)
            if chunk:
                # Atualizar final_state com o chunk mais recente
                for node_name, state_update in chunk.items():
                    # state_update pode ser None ou dict parcial
                    if state_update is not None and isinstance(state_update, dict):
                        if final_state is None:
                            final_state = state_update.copy()
                        else:
                            # Merge state update - special handling for messages list
                            for key, value in state_update.items():
                                if key == "messages" and isinstance(value, list):
                                    # Concatenate messages instead of replacing
                                    if key in final_state:
                                        final_state[key] = final_state[key] + value
                                    else:
                                        final_state[key] = value
                                else:
                                    # Regular update for other keys
                                    final_state[key] = value
    except Exception as e:
        # Se falhar no send_whatsapp (token expirado), ainda temos as métricas!
        # O processamento completo (LLM + tools) já aconteceu antes do envio
        if "whatsapp" in str(e).lower():
            print_warning("WhatsApp send falhou (esperado sem token válido)")
            print_info("Continuando análise... processamento LLM foi concluído!")
            # final_state já tem o último estado válido antes do erro
            if final_state is None:
                print_error("Nenhum estado capturado antes do erro")
                return None
        else:
            print_error(f"Erro ao executar graph: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            return None

    elapsed_time = time.time() - start_time

    if final_state is None:
        print_error("Erro: nenhum estado final capturado")
        return None

    # Extract tool calls from messages
    tool_calls_list = []
    for msg in final_state["messages"]:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_calls_list.append(tool_name)

    # Count unique tools
    unique_tools = list(dict.fromkeys(tool_calls_list))  # preserves order
    total_calls = len(tool_calls_list)

    # Print results
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}📊 RESULTADOS{Colors.ENDC}")
    print("=" * 80)
    print(f"⏱️  Tempo: {Colors.BOLD}{elapsed_time:.2f}s{Colors.ENDC}")
    print(f"💰 Custo: {Colors.BOLD}${final_state['cost_usd']:.4f}{Colors.ENDC}")
    print(f"🔧 Provider: {Colors.BOLD}{final_state['provider_used']}{Colors.ENDC}")
    print(f"🛠️  Tools chamadas: {Colors.BOLD}{total_calls}{Colors.ENDC}")

    if tool_calls_list:
        print(f"   Sequência: {' → '.join(tool_calls_list)}")
        print(f"   Únicas: {', '.join(unique_tools)}")
    else:
        print_warning("   Nenhuma tool foi chamada (resposta direta)")

    # Validation
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}🔍 VALIDAÇÃO{Colors.ENDC}")
    print("=" * 80)

    success = True

    # Check if expected tools were called
    if len(expected_tools) == 0 and len(unique_tools) == 0:
        print_success("Correto: Nenhuma tool chamada (resposta direta)")
    elif set(unique_tools) == set(expected_tools):
        print_success(f"Correto: Tools esperadas foram chamadas ({', '.join(expected_tools)})")
    else:
        print_error(
            f"ERRO: Tools incorretas! Esperado: {expected_tools}, Obtido: {unique_tools}"
        )
        success = False

    # Check for redundant calls
    if total_calls > len(expected_tools) + 1:  # +1 margem para retry legítimo
        print_warning(
            f"Chamadas redundantes detectadas: {total_calls} calls para {len(expected_tools)} tools esperadas"
        )
        success = False
    else:
        print_success(f"Sem redundância excessiva ({total_calls} calls)")

    # Check cost (NEW baseline: $0.0512 from Haiku without cache)
    baseline_cost = 0.0512
    if final_state["cost_usd"] < baseline_cost * 0.6:  # <60% do baseline = sucesso
        reduction = ((baseline_cost - final_state["cost_usd"]) / baseline_cost) * 100
        print_success(f"Custo reduzido: {reduction:.1f}% menor que baseline (${baseline_cost})")
    elif final_state["cost_usd"] < baseline_cost * 0.8:  # 60-80% = ok
        reduction = ((baseline_cost - final_state["cost_usd"]) / baseline_cost) * 100
        print_warning(f"Custo moderado: {reduction:.1f}% menor que baseline (${baseline_cost})")
    else:
        print_warning(f"Custo alto: ${final_state['cost_usd']:.4f} (baseline: ${baseline_cost})")

    # Check time (NEW baseline: 18.81s from Haiku tests)
    baseline_time = 18.81
    if elapsed_time < baseline_time * 0.7:  # <70% do baseline = sucesso
        reduction = ((baseline_time - elapsed_time) / baseline_time) * 100
        print_success(f"Tempo reduzido: {reduction:.1f}% mais rápido que baseline ({baseline_time}s)")
    elif elapsed_time < baseline_time * 0.9:
        reduction = ((baseline_time - elapsed_time) / baseline_time) * 100
        print_warning(
            f"Tempo moderado: {reduction:.1f}% mais rápido que baseline ({baseline_time}s)"
        )
    else:
        print_warning(f"Tempo alto: {elapsed_time:.2f}s (baseline: {baseline_time}s)")

    # Show response preview
    response = final_state.get("formatted_response", "")
    if response:
        print("\n" + "-" * 80)
        print(f"{Colors.BOLD}📄 RESPOSTA (preview):{Colors.ENDC}")
        print("-" * 80)
        preview = response[:300]
        print(preview + ("..." if len(response) > 300 else ""))

    print("\n")
    return {
        "scenario": scenario,
        "query": query,
        "success": success,
        "tools_called": unique_tools,
        "expected_tools": expected_tools,
        "total_calls": total_calls,
        "cost": final_state["cost_usd"],
        "time": elapsed_time,
        "provider": final_state["provider_used"],
    }


async def main():
    """Run all test scenarios."""
    print_header("🧪 TESTE DE TOOL CALLING - Haiku + Cache")
    print_info("Testando otimizações: Haiku 4.5 + cache_control + parallel_tool_calls=False")
    print_info("Baseline: $0.0512, ~18.81s, 1.8 tools (Haiku sem cache)")
    print()

    # Build graph without checkpointer (avoid DB dependency)
    graph = build_whatsapp_graph(checkpointer=None)

    # Test scenarios
    test_cases = [
        # CENÁRIO 1: Droga + contexto clínico → RAG APENAS
        {
            "query": "Qual a dose de amoxicilina para otite média?",
            "expected_tools": ["rag_medical_search"],
            "scenario": "DROGA + CONTEXTO CLÍNICO → RAG",
        },
        # CENÁRIO 2: Droga SEM contexto → drug_lookup APENAS
        {
            "query": "Quais as contraindicações de losartana?",
            "expected_tools": ["drug_lookup"],
            "scenario": "DROGA SEM CONTEXTO → drug_lookup",
        },
        # CENÁRIO 3: Protocolo médico → RAG
        {
            "query": "Qual o protocolo de manejo de pneumonia comunitária?",
            "expected_tools": ["rag_medical_search"],
            "scenario": "PROTOCOLO MÉDICO → RAG",
        },
        # CENÁRIO 4: Cálculo médico → calculator APENAS
        {
            "query": "Calcule o CHA2DS2-VASc para paciente de 75 anos com HAS e DM",
            "expected_tools": ["medical_calculator"],
            "scenario": "CÁLCULO MÉDICO → calculator",
        },
        # CENÁRIO 5: Pergunta conceitual simples → SEM tools (resposta direta)
        {
            "query": "O que é hipertensão arterial?",
            "expected_tools": [],  # pode responder direto OU usar RAG
            "scenario": "PERGUNTA CONCEITUAL → resposta direta ou RAG",
        },
    ]

    results = []
    for i, test_case in enumerate(test_cases, 1):
        print_info(f"Executando teste {i}/{len(test_cases)}...")
        result = await test_query(
            graph,
            test_case["query"],
            test_case["expected_tools"],
            test_case["scenario"],
        )
        if result:
            results.append(result)
        await asyncio.sleep(2)  # Pausa entre testes para evitar rate limit

    # Summary
    print_header("📈 RESUMO GERAL")

    total_tests = len(results)
    successful_tests = sum(1 for r in results if r["success"])

    if total_tests == 0:
        print_error("Nenhum teste foi concluído. Verifique logs acima.")
        return

    print(f"Total de testes: {Colors.BOLD}{total_tests}{Colors.ENDC}")
    print(f"Sucessos: {Colors.BOLD}{successful_tests}{Colors.ENDC}")
    print(f"Falhas: {Colors.BOLD}{total_tests - successful_tests}{Colors.ENDC}")
    print(f"Taxa de sucesso: {Colors.BOLD}{(successful_tests/total_tests)*100:.1f}%{Colors.ENDC}")
    print()

    avg_cost = sum(r["cost"] for r in results) / len(results)
    avg_time = sum(r["time"] for r in results) / len(results)
    avg_tools = sum(r["total_calls"] for r in results) / len(results)

    print(f"Custo médio: {Colors.BOLD}${avg_cost:.4f}{Colors.ENDC} (baseline: $0.0512)")
    print(f"Tempo médio: {Colors.BOLD}{avg_time:.2f}s{Colors.ENDC} (baseline: ~18.81s)")
    print(f"Tools médias: {Colors.BOLD}{avg_tools:.1f}{Colors.ENDC} (baseline: 1.8)")
    print()

    # Cost reduction
    baseline_cost = 0.0512
    cost_reduction = ((baseline_cost - avg_cost) / baseline_cost) * 100
    if cost_reduction > 40:
        print_success(f"Redução de custo: {cost_reduction:.1f}% ✅")
    else:
        print_warning(f"Redução de custo: {cost_reduction:.1f}% (meta: >40%)")

    # Detailed results table
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}DETALHAMENTO POR CENÁRIO{Colors.ENDC}")
    print("=" * 80)
    print(
        f"{'Cenário':<50} {'Tools':<15} {'Custo':<10} {'Tempo':<10} {'Status':<10}"
    )
    print("-" * 80)
    for r in results:
        status = "✅ OK" if r["success"] else "❌ FAIL"
        tools_str = f"{r['total_calls']} ({', '.join(r['tools_called'][:2])}{'...' if len(r['tools_called']) > 2 else ''})"
        print(
            f"{r['scenario']:<50} {tools_str:<15} ${r['cost']:<9.4f} {r['time']:<9.2f}s {status:<10}"
        )

    print()
    if successful_tests == total_tests:
        print_success("TODOS OS TESTES PASSARAM! 🎉")
    else:
        print_warning(f"{total_tests - successful_tests} teste(s) falharam. Revisar logs acima.")


if __name__ == "__main__":
    asyncio.run(main())
