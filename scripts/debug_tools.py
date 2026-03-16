#!/usr/bin/env python
"""Debug: verificar se tools estão sendo bound corretamente."""

import asyncio
import os
import sys
from pathlib import Path

import django

# Setup Django
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from langchain_core.messages import HumanMessage, SystemMessage

from workflows.providers.llm import get_model
from workflows.whatsapp.tools import get_tools


async def test_tools_binding():
    """Test if tools are properly bound to the model."""
    print("=" * 80)
    print("DEBUG: Verificando binding de tools")
    print("=" * 80)

    tools = get_tools()
    print(f"\n✅ Tools carregadas: {len(tools)}")
    for tool in tools:
        print(f"   - {tool.name}: {tool.description[:80]}...")

    print("\n" + "-" * 80)
    print("Testando model COM tools e parallel_tool_calls=False")
    print("-" * 80)

    model = get_model(tools=tools, parallel_tool_calls=False)

    # Check if tools are bound
    print(f"\nModel type: {type(model)}")
    print(f"Model: {model}")

    # Try a simple invocation
    messages = [
        SystemMessage(content="Você é um assistente médico. Use ferramentas quando necessário."),
        HumanMessage(content="Qual a dose de amoxicilina para otite média?"),
    ]

    print("\n" + "-" * 80)
    print("Invocando model com query que DEVE usar rag_medical_search...")
    print("-" * 80)

    try:
        response = await model.ainvoke(messages)
        print(f"\n✅ Response type: {type(response)}")
        print(f"✅ Response content: {response.content[:200]}...")

        if hasattr(response, "tool_calls"):
            print(f"\n🛠️  Tool calls: {len(response.tool_calls)}")
            for tc in response.tool_calls:
                print(f"   - {tc}")
        else:
            print("\n❌ Response NÃO tem tool_calls!")

        if hasattr(response, "response_metadata"):
            print(f"\n📊 Response metadata: {response.response_metadata}")

    except Exception as e:
        print(f"\n❌ Erro: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_tools_binding())
