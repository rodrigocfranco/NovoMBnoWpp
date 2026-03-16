#!/usr/bin/env python
"""Profile timing detalhado de cada nó do grafo WhatsApp.

Mede latência de:
- identify_user
- check_rate_limit
- load_context
- orchestrate_llm (separando: LLM call vs tool execution)
- tools (cada tool individual)
- format_response
- send_whatsapp

Usage:
    python scripts/profile_timing.py
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

from workflows.whatsapp.graph import build_whatsapp_graph
from workflows.whatsapp.state import WhatsAppState


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


def print_timing(label: str, duration_ms: float, indent: int = 0):
    """Print timing line with color coding."""
    prefix = "  " * indent
    if duration_ms < 100:
        color = Colors.OKGREEN
    elif duration_ms < 500:
        color = Colors.OKCYAN
    elif duration_ms < 2000:
        color = Colors.WARNING
    else:
        color = Colors.FAIL

    print(f"{prefix}{color}{label:<50} {duration_ms:>8.0f}ms{Colors.ENDC}")


async def profile_query(query: str, description: str):
    """Profile a single query with detailed timing breakdown."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}📊 PROFILE: {description}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"Query: {Colors.BOLD}{query}{Colors.ENDC}\n")

    # Build graph
    graph = build_whatsapp_graph(checkpointer=None)

    # Create state
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

    # Timing storage
    timings = {}
    node_order = []

    total_start = time.perf_counter()

    try:
        # Stream through graph and capture timing per node
        async for chunk in graph.astream(state, config=config):
            for node_name, state_update in chunk.items():
                # Track timing (astream doesn't give us per-node timing, so we approximate)
                node_order.append(node_name)
    except Exception as e:
        if "whatsapp" in str(e).lower():
            pass  # Expected error (token expired)
        else:
            print(f"{Colors.FAIL}Erro: {e}{Colors.ENDC}")
            import traceback
            traceback.print_exc()
            return None

    total_duration = (time.perf_counter() - total_start) * 1000

    # Print results
    print(f"{Colors.BOLD}NÓDOS EXECUTADOS:{Colors.ENDC}")
    print(f"  Ordem: {' → '.join(node_order)}\n")

    print(f"{Colors.BOLD}TEMPO TOTAL:{Colors.ENDC}")
    print_timing("Total end-to-end", total_duration, 0)

    print(f"\n{Colors.WARNING}⚠️  Breakdown detalhado não disponível via astream(){Colors.ENDC}")
    print(f"{Colors.WARNING}   astream() não expõe timing individual de nós.{Colors.ENDC}")
    print(f"{Colors.WARNING}   Recomendação: usar invoke() com hooks ou adicionar timing nos nós.{Colors.ENDC}")

    return {
        "query": query,
        "description": description,
        "total_ms": total_duration,
        "nodes": node_order,
    }


async def profile_with_instrumentation(query: str, description: str):
    """Profile usando invoke() para capturar timing detalhado."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}🔬 PROFILE DETALHADO: {description}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"Query: {Colors.BOLD}{query}{Colors.ENDC}\n")

    # Build graph
    graph = build_whatsapp_graph(checkpointer=None)

    # Create state
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

    # Timing per node
    node_timings = []

    total_start = time.perf_counter()

    # Hook to capture node execution timing
    def on_node_start(node_name: str):
        node_timings.append({"node": node_name, "start": time.perf_counter()})

    def on_node_end(node_name: str):
        for t in reversed(node_timings):
            if t["node"] == node_name and "end" not in t:
                t["end"] = time.perf_counter()
                t["duration_ms"] = (t["end"] - t["start"]) * 1000
                break

    # PROBLEMA: LangGraph não expõe hooks simples para capturar timing
    # Vamos usar uma abordagem diferente: stream e medir intervalo entre chunks

    prev_time = total_start
    chunk_timings = []

    try:
        async for chunk in graph.astream(state, config=config):
            current_time = time.perf_counter()
            chunk_duration = (current_time - prev_time) * 1000

            for node_name in chunk.keys():
                chunk_timings.append({
                    "node": node_name,
                    "duration_ms": chunk_duration,
                })

            prev_time = current_time

    except Exception as e:
        if "whatsapp" in str(e).lower():
            pass  # Expected
        else:
            print(f"{Colors.FAIL}Erro: {e}{Colors.ENDC}")
            return None

    total_duration = (time.perf_counter() - total_start) * 1000

    # Aggregate timing by node (handle multiple calls to same node)
    node_totals = {}
    for t in chunk_timings:
        node = t["node"]
        if node not in node_totals:
            node_totals[node] = {"count": 0, "total_ms": 0, "durations": []}
        node_totals[node]["count"] += 1
        node_totals[node]["total_ms"] += t["duration_ms"]
        node_totals[node]["durations"].append(t["duration_ms"])

    # Print breakdown
    print(f"{Colors.BOLD}BREAKDOWN POR NÓ:{Colors.ENDC}\n")

    for node, data in node_totals.items():
        count = data["count"]
        total = data["total_ms"]
        avg = total / count if count > 0 else 0

        if count == 1:
            print_timing(f"{node}", total, 1)
        else:
            print_timing(f"{node} (total {count}x calls)", total, 1)
            for i, dur in enumerate(data["durations"], 1):
                print_timing(f"  ↳ call #{i}", dur, 2)

    print(f"\n{Colors.BOLD}TEMPO TOTAL:{Colors.ENDC}")
    print_timing("Total end-to-end", total_duration, 0)

    # Calculate overhead (nodes not accounted for)
    accounted = sum(d["total_ms"] for d in node_totals.values())
    overhead = total_duration - accounted
    if overhead > 50:  # >50ms overhead worth noting
        print_timing("⚙️ Overhead (graph/networking)", overhead, 1)

    return {
        "query": query,
        "description": description,
        "total_ms": total_duration,
        "node_timings": node_totals,
        "overhead_ms": overhead,
    }


async def main():
    """Run profiling for different query types."""
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}⏱️  PROFILING DE LATÊNCIA - WhatsApp Graph{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")

    queries = [
        ("Qual a dose de amoxicilina para otite média?", "DROGA + CONTEXTO → RAG"),
        ("Quais as contraindicações de losartana?", "DROGA SEM CONTEXTO → drug_lookup"),
        ("Calcule o CHA2DS2-VASc para HAS + 75 anos", "CÁLCULO → calculator"),
    ]

    results = []
    for query, desc in queries:
        result = await profile_with_instrumentation(query, desc)
        if result:
            results.append(result)
        await asyncio.sleep(2)  # Evitar rate limit

    # Summary
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}📈 RESUMO DE LATÊNCIA{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")

    for r in results:
        print(f"{Colors.BOLD}{r['description']}{Colors.ENDC}")
        print(f"  Total: {r['total_ms']:.0f}ms")
        print("  Top nodes:")

        # Sort by total_ms
        sorted_nodes = sorted(
            r["node_timings"].items(),
            key=lambda x: x[1]["total_ms"],
            reverse=True
        )

        for node, data in sorted_nodes[:3]:
            print(f"    - {node}: {data['total_ms']:.0f}ms ({data['count']}x)")
        print()


if __name__ == "__main__":
    asyncio.run(main())
