"""Tests for quiz_generate tool (AC1, AC2, AC3 — Story 9.1)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestQuizGenerate:
    """Tests for quiz_generate LangChain tool."""

    @patch("workflows.whatsapp.tools.quiz_generator._get_quiz_model")
    async def test_generates_quiz_with_default_level(self, mock_get_quiz_model):
        """AC1: Gera questão com nível intermediate por padrão."""
        mock_response = MagicMock()
        mock_response.content = (
            "**Questão:** Paciente de 65 anos com dispneia...\n\n"
            "A) Furosemida\nB) Carvedilol\nC) Amiodarona\n"
            "D) Digoxina\nE) Espironolactona\n\n"
            "**Gabarito:** B\n\n"
            "**Comentário:** O carvedilol é um betabloqueador..."
        )
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_quiz_model.return_value = mock_model

        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        result = await quiz_generate.ainvoke({"topic": "insuficiência cardíaca"})

        assert "Questão" in result
        assert "A)" in result
        assert "B)" in result
        assert "Gabarito" in result

    @patch("workflows.whatsapp.tools.quiz_generator._get_quiz_model")
    async def test_generates_quiz_with_easy_level(self, mock_get_quiz_model):
        """AC1: Gera questão com nível easy."""
        mock_response = MagicMock()
        mock_response.content = (
            "**Questão:** Qual das alternativas define insuficiência cardíaca?\n\n"
            "A) Opção A\nB) Opção B\nC) Opção C\nD) Opção D\nE) Opção E\n\n"
            "**Gabarito:** A\n\n**Comentário:** A IC é definida como..."
        )
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_quiz_model.return_value = mock_model

        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        result = await quiz_generate.ainvoke({"topic": "insuficiência cardíaca", "level": "easy"})

        assert "Questão" in result
        # Verify the prompt used "básico" level description
        call_args = mock_model.ainvoke.call_args[0][0]
        assert "básico" in call_args[0].content

    @patch("workflows.whatsapp.tools.quiz_generator._get_quiz_model")
    async def test_generates_quiz_with_hard_level(self, mock_get_quiz_model):
        """AC1: Gera questão com nível hard."""
        mock_response = MagicMock()
        mock_response.content = (
            "**Questão:** Caso complexo...\n\nA) A\nB) B\nC) C\nD) D\nE) E\n\n"
            "**Gabarito:** C\n\n**Comentário:** Explicação avançada..."
        )
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_quiz_model.return_value = mock_model

        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        result = await quiz_generate.ainvoke({"topic": "farmacologia", "level": "hard"})

        assert "Questão" in result
        call_args = mock_model.ainvoke.call_args[0][0]
        assert "avançado" in call_args[0].content

    @patch("workflows.whatsapp.tools.quiz_generator._get_quiz_model")
    async def test_invalid_level_defaults_to_intermediate(self, mock_get_quiz_model):
        """AC1: Nível inválido usa intermediate como fallback."""
        mock_response = MagicMock()
        mock_response.content = (
            "**Questão:** Teste...\n\nA) A\nB) B\nC) C\nD) D\nE) E\n\n"
            "**Gabarito:** A\n\n**Comentário:** ..."
        )
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_quiz_model.return_value = mock_model

        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        await quiz_generate.ainvoke({"topic": "cardiologia", "level": "invalid_level"})

        call_args = mock_model.ainvoke.call_args[0][0]
        assert "intermediário" in call_args[0].content

    async def test_empty_topic_returns_error_message(self):
        """AC1: Topic vazio retorna mensagem de erro."""
        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        result = await quiz_generate.ainvoke({"topic": ""})
        assert "informe o tema" in result.lower()

    async def test_whitespace_topic_returns_error_message(self):
        """AC1: Topic com apenas espaços retorna mensagem de erro."""
        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        result = await quiz_generate.ainvoke({"topic": "   "})
        assert "informe o tema" in result.lower()

    @patch("workflows.whatsapp.tools.quiz_generator._get_quiz_model")
    async def test_llm_error_returns_error_message(self, mock_get_quiz_model):
        """H1: Erro do LLM retorna mensagem amigável (consistente com outras tools)."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(side_effect=Exception("LLM connection failed"))
        mock_get_quiz_model.return_value = mock_model

        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        result = await quiz_generate.ainvoke({"topic": "cardiologia"})
        assert "indisponível" in result.lower()

    @patch("workflows.whatsapp.tools.quiz_generator._get_quiz_model")
    async def test_timeout_returns_error_message(self, mock_get_quiz_model):
        """M1: Timeout retorna mensagem amigável em vez de travar."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(side_effect=TimeoutError("timed out"))
        mock_get_quiz_model.return_value = mock_model

        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        result = await quiz_generate.ainvoke({"topic": "cardiologia"})
        assert "tempo limite" in result.lower()

    @patch("workflows.whatsapp.tools.quiz_generator._get_quiz_model")
    async def test_cost_tracking_callback_is_used(self, mock_get_quiz_model):
        """AC1: CostTrackingCallback é passado na invocação do LLM."""
        mock_response = MagicMock()
        mock_response.content = (
            "**Questão:** ...\n\nA) A\nB) B\nC) C\nD) D\nE) E\n\n"
            "**Gabarito:** A\n\n**Comentário:** ..."
        )
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_quiz_model.return_value = mock_model

        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        await quiz_generate.ainvoke({"topic": "neurologia"})

        # Verify ainvoke was called with callbacks config
        call_kwargs = mock_model.ainvoke.call_args
        config = call_kwargs[1].get("config")
        if config is None and len(call_kwargs[0]) > 1:
            config = call_kwargs[0][1]
        assert config is not None
        assert "callbacks" in config
        assert len(config["callbacks"]) == 1

        from workflows.services.cost_tracker import CostTrackingCallback

        assert isinstance(config["callbacks"][0], CostTrackingCallback)

    def test_tool_has_docstring(self):
        """AC1: Tool tem docstring (LLM usa para decisão de uso)."""
        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        assert quiz_generate.description
        assert len(quiz_generate.description) > 20
        assert "quiz" in quiz_generate.description.lower()

    def test_tool_has_correct_name(self):
        """AC1: Tool tem nome correto para registro."""
        from workflows.whatsapp.tools.quiz_generator import quiz_generate

        assert quiz_generate.name == "quiz_generate"

    @patch("workflows.whatsapp.tools.quiz_generator._get_quiz_model")
    async def test_long_topic_is_truncated(self, mock_get_quiz_model):
        """L1: Topic com mais de MAX_TOPIC_LENGTH é truncado."""
        mock_response = MagicMock()
        mock_response.content = "Questão sobre tema truncado..."
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_quiz_model.return_value = mock_model

        from workflows.whatsapp.tools.quiz_generator import (
            MAX_TOPIC_LENGTH,
            quiz_generate,
        )

        long_topic = "x" * (MAX_TOPIC_LENGTH + 500)
        await quiz_generate.ainvoke({"topic": long_topic})

        # Verify the prompt uses truncated topic
        call_args = mock_model.ainvoke.call_args[0][0]
        prompt_content = call_args[0].content
        assert "x" * MAX_TOPIC_LENGTH in prompt_content
        assert "x" * (MAX_TOPIC_LENGTH + 1) not in prompt_content


class TestQuizGenerateRegistration:
    """Tests for quiz_generate registration in get_tools()."""

    def test_quiz_generate_in_get_tools(self):
        """AC1: quiz_generate está registrada em get_tools()."""
        from workflows.whatsapp.tools import get_tools

        tools = get_tools()
        tool_names = [t.name for t in tools]
        assert "quiz_generate" in tool_names

    def test_get_tools_returns_six_tools(self):
        """AC1: get_tools() agora retorna 6 tools (incluindo quiz)."""
        from workflows.whatsapp.tools import get_tools

        tools = get_tools()
        assert len(tools) == 6


class TestQuizModelCaching:
    """Tests for quiz LLM model caching (M2 fix)."""

    @patch("workflows.whatsapp.tools.quiz_generator.get_model")
    def test_quiz_model_is_cached(self, mock_get_model):
        """M2: _get_quiz_model retorna instância cached (criada uma vez)."""
        mock_get_model.return_value = MagicMock()

        import workflows.whatsapp.tools.quiz_generator as mod

        original = mod._quiz_model
        mod._quiz_model = None  # Reset cache

        try:
            model1 = mod._get_quiz_model()
            model2 = mod._get_quiz_model()

            assert model1 is model2
            mock_get_model.assert_called_once_with(tools=None, max_tokens=512)
        finally:
            mod._quiz_model = original


class TestSystemPromptQuizInstructions:
    """Tests for quiz instructions in system prompt."""

    def test_system_prompt_contains_quiz_section(self):
        """AC3: System prompt contém seção 'Quiz e Prática Ativa'."""
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert "Quiz e Prática Ativa" in SYSTEM_PROMPT

    def test_system_prompt_contains_quiz_generate_tool(self):
        """AC1: System prompt referencia tool quiz_generate."""
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert "quiz_generate" in SYSTEM_PROMPT

    def test_system_prompt_contains_contextual_suggestion(self):
        """AC3: System prompt contém instruções de sugestão contextual (FR26)."""
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert "SUGESTÃO CONTEXTUAL" in SYSTEM_PROMPT
        assert "5 interações" in SYSTEM_PROMPT

    def test_system_prompt_contains_feedback_instructions(self):
        """AC2: System prompt contém instruções de feedback após resposta."""
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert "QUANDO O ALUNO RESPONDER" in SYSTEM_PROMPT
        assert "Acertou" in SYSTEM_PROMPT
        assert "Errou" in SYSTEM_PROMPT

    def test_system_prompt_hides_gabarito(self):
        """AC1: System prompt instrui a NÃO revelar gabarito antes da resposta."""
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert "NÃO revele o gabarito" in SYSTEM_PROMPT

    def test_system_prompt_updated_tool_count(self):
        """AC1: System prompt atualizado para 6 ferramentas."""
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert "6 FERRAMENTAS" in SYSTEM_PROMPT


@pytest.mark.django_db
class TestQuizGenerateWithDB:
    """Tests with real DB to avoid over-mocking (lesson from Sprint 6)."""

    async def test_quiz_prompt_version_seeded_by_migration(self):
        """M3: Verify migration 0020 seeded SystemPromptVersion with quiz instructions."""
        from workflows.models import SystemPromptVersion

        version = await SystemPromptVersion.objects.filter(author="migration-9.1-quiz").afirst()
        assert version is not None, "Migration 0020 should seed quiz prompt version"
        assert "quiz_generate" in version.content
        assert "Quiz e Prática Ativa" in version.content
        assert version.is_active is True
