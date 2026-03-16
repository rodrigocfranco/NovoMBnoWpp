#!/usr/bin/env python
"""Script interativo para testar o pipeline LangGraph sem enviar mensagens pelo WhatsApp.

Usa LLM real (Vertex AI), Redis real e PostgreSQL real.
Mocka APENAS o envio ao WhatsApp — captura a resposta localmente.

Uso:
    uv run python scripts/test_pipeline.py
    uv run python scripts/test_pipeline.py "Qual a dose de amoxicilina para otite média?"
    uv run python scripts/test_pipeline.py --phone 5511999999999 "Explique síndrome nefrótica"
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add project root to sys.path so Django can find the config module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Django setup MUST happen before any app import
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from workflows.providers.checkpointer import get_checkpointer, setup_checkpointer
from workflows.whatsapp.graph import build_whatsapp_graph

# Default test phone (will be used as thread_id for checkpointer)
DEFAULT_PHONE = "5500000000000"


def make_initial_state(user_message: str, phone: str = DEFAULT_PHONE) -> dict:
    """Build initial state dict identical to views._process_message."""
    return {
        "phone_number": phone,
        "user_message": user_message,
        "message_type": "text",
        "media_url": None,
        "media_id": None,
        "mime_type": None,
        "wamid": f"wamid.test.{int(time.time())}",
        "messages": [],
        "user_id": "",
        "subscription_tier": "",
        "is_new_user": False,
        "formatted_response": "",
        "additional_responses": [],
        "response_sent": False,
        "trace_id": "",
        "cost_usd": 0.0,
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "rate_limit_exceeded": False,
        "remaining_daily": 0,
        "rate_limit_warning": "",
        "transcribed_text": "",
        "image_message": None,
        "provider_used": "",
    }


async def run_pipeline(user_message: str, phone: str = DEFAULT_PHONE) -> dict:
    """Execute the full LangGraph pipeline, mocking only WhatsApp send."""
    # Setup checkpointer (creates tables if needed)
    await setup_checkpointer()
    checkpointer = await get_checkpointer()
    graph = build_whatsapp_graph(checkpointer=checkpointer)

    initial_state = make_initial_state(user_message, phone)

    # Mock ONLY the WhatsApp API calls — everything else is real
    with (
        patch(
            "workflows.whatsapp.nodes.send_whatsapp.send_text_message",
            new_callable=AsyncMock,
        ) as mock_send,
        patch(
            "workflows.whatsapp.nodes.send_whatsapp.mark_as_read",
            new_callable=AsyncMock,
        ),
    ):
        start = time.perf_counter()
        result = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": phone}},
        )
        elapsed = time.perf_counter() - start

    # Display results
    print("\n" + "=" * 70)
    print("  RESULTADO DO PIPELINE")
    print("=" * 70)

    print(f"\n📥 Pergunta: {user_message}")
    print(f"📱 Telefone: {phone}")
    print(f"👤 user_id: {result.get('user_id', 'N/A')}")
    print(f"🏷️  Tier: {result.get('subscription_tier', 'N/A')}")
    print(f"🆕 Novo usuário: {result.get('is_new_user', False)}")
    print(f"🤖 Provider: {result.get('provider_used', 'N/A')}")
    print(f"💰 Custo: ${result.get('cost_usd', 0):.6f}")
    print(f"⏱️  Tempo: {elapsed:.2f}s")
    print(f"📊 Rate limit restante: {result.get('remaining_daily', 'N/A')}")

    if result.get("rate_limit_exceeded"):
        print("\n⚠️  RATE LIMIT EXCEEDED — pipeline parou antes do LLM")
        return result

    if result.get("rate_limit_warning"):
        print(f"⚠️  Warning: {result['rate_limit_warning']}")

    # Show formatted response
    print(f"\n{'─' * 70}")
    print("  RESPOSTA FORMATADA (seria enviada ao WhatsApp)")
    print(f"{'─' * 70}\n")
    print(result.get("formatted_response", "(vazio)"))

    additional = result.get("additional_responses", [])
    if additional:
        for i, part in enumerate(additional, 1):
            print(f"\n{'─' * 40} Parte {i + 1} {'─' * 40}\n")
            print(part)

    # Show tool usage from messages
    messages = result.get("messages", [])
    tool_calls = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_calls.extend(msg.tool_calls)

    if tool_calls:
        print(f"\n{'─' * 70}")
        print(f"  TOOLS USADAS ({len(tool_calls)})")
        print(f"{'─' * 70}")
        for tc in tool_calls:
            print(f"\n  🔧 {tc['name']}")
            args = tc.get("args", {})
            for k, v in args.items():
                val_str = str(v)
                if len(val_str) > 100:
                    val_str = val_str[:100] + "..."
                print(f"     {k}: {val_str}")

    # Show tool results
    tool_messages = [m for m in messages if hasattr(m, "name") and m.name]
    if tool_messages:
        print(f"\n{'─' * 70}")
        print(f"  RESULTADOS DAS TOOLS ({len(tool_messages)})")
        print(f"{'─' * 70}")
        for tm in tool_messages:
            content_str = str(tm.content)
            if len(content_str) > 300:
                content_str = content_str[:300] + "..."
            print(f"\n  📋 {tm.name}: {content_str}")

    # Show citations
    sources = result.get("retrieved_sources", [])
    web_sources = result.get("web_sources", [])
    if sources or web_sources:
        print(f"\n{'─' * 70}")
        print("  FONTES CITADAS")
        print(f"{'─' * 70}")
        for s in sources:
            print(f"  📚 {s.get('title', s)}")
        for s in web_sources:
            print(f"  🌐 {s.get('title', s.get('url', s))}")

    # Show send_text_message mock calls
    print(f"\n{'─' * 70}")
    print(f"  CHAMADAS AO WHATSAPP (mockadas) — {mock_send.call_count} chamada(s)")
    print(f"{'─' * 70}")
    for i, call in enumerate(mock_send.call_args_list):
        args, kwargs = call
        recipient = args[0] if args else kwargs.get("phone_number", "?")
        text = args[1] if len(args) > 1 else kwargs.get("text", "?")
        preview = text[:200] + "..." if len(text) > 200 else text
        print(f"\n  [{i + 1}] Para: {recipient}")
        print(f"      Texto: {preview}")

    print(f"\n{'=' * 70}\n")
    return result


async def interactive_mode(phone: str = DEFAULT_PHONE) -> None:
    """Run interactive chat loop — each message keeps conversation context."""
    print("\n" + "=" * 70)
    print("  MEDBRAIN PIPELINE TESTER (modo interativo)")
    print("=" * 70)
    print(f"\n  Thread: {phone} (conversação mantida pelo checkpointer)")
    print("  Digite 'sair' ou Ctrl+C para encerrar.\n")

    while True:
        try:
            user_input = input("Você: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando...")
            break

        if not user_input or user_input.lower() in ("sair", "exit", "quit"):
            print("Encerrando...")
            break

        await run_pipeline(user_input, phone)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Testa o pipeline LangGraph sem enviar WhatsApp."
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="Mensagem para enviar. Se omitida, entra em modo interativo.",
    )
    parser.add_argument(
        "--phone",
        default=DEFAULT_PHONE,
        help=f"Telefone/thread_id (default: {DEFAULT_PHONE})",
    )
    args = parser.parse_args()

    if args.message:
        asyncio.run(run_pipeline(args.message, args.phone))
    else:
        asyncio.run(interactive_mode(args.phone))


if __name__ == "__main__":
    main()
