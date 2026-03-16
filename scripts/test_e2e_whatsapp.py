#!/usr/bin/env python
"""Teste E2E real: simula mensagem WhatsApp → processamento → resposta.

Mede custo total e tempo total da operação completa.
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import django

# Setup Django
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from langchain_core.messages import AIMessage

from workflows.whatsapp.graph import get_graph
from workflows.whatsapp.state import WhatsAppState


class Colors:
    """ANSI colors."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_success(text: str):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_warning(text: str):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text: str):
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


async def test_e2e(query: str, phone: str = None):
    """Teste E2E completo: mensagem in → processamento → mensagem out.

    Simula o fluxo real:
    1. Usuário envia mensagem via WhatsApp
    2. Webhook recebe e processa
    3. Graph executa (identify → rate_limit → process_media → load_context →
       orchestrate_llm → tools → collect_sources → format → send → persist)
    4. Resposta enviada via WhatsApp
    5. Métricas coletadas
    """
    if not phone:
        phone = f"5511{int(datetime.now().timestamp())}"

    print_header("🧪 TESTE E2E - WhatsApp Real")
    print(f"📝 Query: {Colors.BOLD}{query}{Colors.ENDC}")
    print(f"📞 Phone: {Colors.BOLD}{phone}{Colors.ENDC}")
    print("-" * 80)

    # Simula estado inicial como se webhook tivesse recebido mensagem
    state: WhatsAppState = {
        "phone_number": phone,
        "user_message": query,
        "message_type": "text",
        "media_url": None,
        "wamid": f"wamid.test_{int(datetime.now().timestamp())}",
        "user_id": "",  # será preenchido por identify_user
        "subscription_tier": "",
        "is_new_user": False,
        "messages": [],
        "formatted_response": "",
        "additional_responses": [],
        "response_sent": False,
        "trace_id": f"trace-e2e-{int(datetime.now().timestamp())}",
        "cost_usd": 0.0,
        "provider_used": "unknown",
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "transcribed_text": "",
        "image_message": None,
        "rate_limit_exceeded": False,
        "remaining_daily": 0,
        "rate_limit_warning": "",
    }

    config = {"configurable": {"thread_id": phone}}

    print_info("Carregando graph com checkpointer (histórico persistido)...")
    graph = await get_graph()

    print_info("Executando pipeline completo...")
    print()

    start_time = time.time()

    try:
        final_state = await graph.ainvoke(state, config=config)
    except Exception as e:
        elapsed = time.time() - start_time
        print_error(f"Erro após {elapsed:.2f}s: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return None

    elapsed_time = time.time() - start_time

    # Análise de resultados
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}📊 RESULTADOS E2E{Colors.ENDC}")
    print("=" * 80)

    # Métricas principais
    cost = final_state.get("cost_usd", 0.0)
    provider = final_state.get("provider_used", "unknown")
    response_sent = final_state.get("response_sent", False)
    rate_limited = final_state.get("rate_limit_exceeded", False)

    print(f"⏱️  Tempo total: {Colors.BOLD}{elapsed_time:.2f}s{Colors.ENDC}")
    print(f"💰 Custo total: {Colors.BOLD}${cost:.4f}{Colors.ENDC}")
    print(f"🔧 Provider: {Colors.BOLD}{provider}{Colors.ENDC}")
    print(f"📤 Resposta enviada: {Colors.BOLD}{response_sent}{Colors.ENDC}")

    if rate_limited:
        print_warning(f"Rate limit aplicado! Restante: {final_state.get('remaining_daily', 0)}")

    # Extrai tool calls
    tool_calls_list = []
    for msg in final_state["messages"]:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_calls_list.append(tool_name)

    unique_tools = list(dict.fromkeys(tool_calls_list))
    total_calls = len(tool_calls_list)

    print(f"🛠️  Tools chamadas: {Colors.BOLD}{total_calls}{Colors.ENDC}")
    if tool_calls_list:
        print(f"   Sequência: {' → '.join(tool_calls_list)}")
        print(f"   Únicas: {', '.join(unique_tools)}")

    # Resposta
    response = final_state.get("formatted_response", "")
    if response:
        print("\n" + "-" * 80)
        print(f"{Colors.BOLD}📄 RESPOSTA ENVIADA:{Colors.ENDC}")
        print("-" * 80)
        # Mostra primeiros 500 caracteres
        preview = response[:500]
        print(preview + ("..." if len(response) > 500 else ""))
        print()
        print(f"Tamanho total: {len(response)} caracteres")

    # Fontes
    sources = final_state.get("retrieved_sources", [])
    web_sources = final_state.get("web_sources", [])
    if sources or web_sources:
        print("\n" + "-" * 80)
        print(f"{Colors.BOLD}📚 FONTES UTILIZADAS:{Colors.ENDC}")
        print("-" * 80)
        if sources:
            print(f"RAG: {len(sources)} documentos")
        if web_sources:
            print(f"Web: {len(web_sources)} resultados")

    # Análise vs baseline
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}📈 COMPARAÇÃO COM BASELINE{Colors.ENDC}")
    print("=" * 80)

    baseline_cost = 0.075
    baseline_time = 24.0
    baseline_tools = 5

    cost_diff = ((baseline_cost - cost) / baseline_cost) * 100
    time_diff = ((baseline_time - elapsed_time) / baseline_time) * 100
    tools_diff = ((baseline_tools - total_calls) / baseline_tools) * 100

    print(f"Baseline: ${baseline_cost:.4f}, {baseline_time:.1f}s, {baseline_tools} tools")
    print(f"Atual:    ${cost:.4f}, {elapsed_time:.2f}s, {total_calls} tools")
    print()

    if cost_diff > 40:
        print_success(f"Custo: {cost_diff:.1f}% menor (economia de ${baseline_cost - cost:.4f})")
    elif cost_diff > 0:
        print_warning(f"Custo: {cost_diff:.1f}% menor (meta: >40%)")
    else:
        print_error(f"Custo AUMENTOU: {abs(cost_diff):.1f}%")

    if time_diff > 20:
        print_success(f"Tempo: {time_diff:.1f}% mais rápido ({baseline_time - elapsed_time:.2f}s economizado)")
    elif time_diff > 0:
        print_warning(f"Tempo: {time_diff:.1f}% mais rápido (meta: >20%)")
    else:
        print_error(f"Tempo AUMENTOU: {abs(time_diff):.1f}%")

    if tools_diff > 50:
        print_success(f"Tools: {tools_diff:.1f}% menos chamadas")
    elif tools_diff > 0:
        print_warning(f"Tools: {tools_diff:.1f}% menos chamadas (meta: >50%)")
    else:
        print_error(f"Tools AUMENTARAM: {abs(tools_diff):.1f}%")

    return {
        "query": query,
        "cost": cost,
        "time": elapsed_time,
        "tools_count": total_calls,
        "tools_list": unique_tools,
        "response_sent": response_sent,
        "success": response_sent and cost < baseline_cost * 0.8,
    }


async def main():
    """Roda testes E2E com queries reais."""
    print_header("🚀 TESTE E2E COMPLETO - WHATSAPP REAL")
    print_info("Simulando fluxo completo: webhook → processamento → envio")
    print_info("TODAS as etapas do graph serão executadas")
    print()

    # Queries de teste
    test_queries = [
        "Qual a dose de amoxicilina para otite média?",  # DROGA + CONTEXTO → RAG
        # "Quais as contraindicações de losartana?",  # DROGA SEM CONTEXTO → drug_lookup
        # "Calcule o CHA2DS2-VASc para paciente de 75 anos com HAS e DM",  # CÁLCULO
    ]

    results = []
    for i, query in enumerate(test_queries, 1):
        print_info(f"Teste {i}/{len(test_queries)}")
        result = await test_e2e(query)
        if result:
            results.append(result)

        if i < len(test_queries):
            print("\n" + "~" * 80)
            print_info("Aguardando 3s antes do próximo teste...")
            await asyncio.sleep(3)

    # Resumo final
    if results:
        print_header("📊 RESUMO GERAL")

        avg_cost = sum(r["cost"] for r in results) / len(results)
        avg_time = sum(r["time"] for r in results) / len(results)
        avg_tools = sum(r["tools_count"] for r in results) / len(results)
        success_rate = sum(1 for r in results if r["success"]) / len(results) * 100

        print(f"Testes executados: {Colors.BOLD}{len(results)}{Colors.ENDC}")
        print(f"Taxa de sucesso: {Colors.BOLD}{success_rate:.0f}%{Colors.ENDC}")
        print()
        print(f"Custo médio: {Colors.BOLD}${avg_cost:.4f}{Colors.ENDC} (baseline: $0.075)")
        print(f"Tempo médio: {Colors.BOLD}{avg_time:.2f}s{Colors.ENDC} (baseline: ~24s)")
        print(f"Tools médias: {Colors.BOLD}{avg_tools:.1f}{Colors.ENDC} (baseline: 5)")
        print()

        if success_rate == 100:
            print_success("TODOS OS TESTES PASSARAM! 🎉")
        elif success_rate >= 80:
            print_warning(f"{100 - success_rate:.0f}% dos testes falharam")
        else:
            print_error(f"{100 - success_rate:.0f}% dos testes falharam")


if __name__ == "__main__":
    asyncio.run(main())
