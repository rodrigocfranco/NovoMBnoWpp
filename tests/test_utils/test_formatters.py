"""Tests for Markdown -> WhatsApp formatters (AC1, AC7)."""

from workflows.utils.formatters import (
    add_medical_disclaimer,
    detect_content_type,
    markdown_to_whatsapp,
    should_add_disclaimer,
)


class TestMarkdownToWhatsApp:
    """Tests for markdown_to_whatsapp conversion (AC1)."""

    def test_bold_conversion(self):
        """AC1: **bold** -> *bold*."""
        assert markdown_to_whatsapp("**texto**") == "*texto*"

    def test_italic_underscore_preserved(self):
        """AC1: _italic_ mantém."""
        assert markdown_to_whatsapp("_italic_") == "_italic_"

    def test_strikethrough_conversion(self):
        """AC1: ~~strike~~ -> ~strike~."""
        assert markdown_to_whatsapp("~~strike~~") == "~strike~"

    def test_header_h1_to_bold(self):
        """AC1: # Header -> *Header*."""
        assert markdown_to_whatsapp("# Header") == "*Header*"

    def test_header_h2_to_bold(self):
        """AC1: ## Header -> *Header*."""
        assert markdown_to_whatsapp("## Sub Header") == "*Sub Header*"

    def test_header_h3_to_bold(self):
        """AC1: ### Header -> *Header*."""
        assert markdown_to_whatsapp("### H3") == "*H3*"

    def test_unordered_list_dash(self):
        """AC1: - item -> bullet item."""
        result = markdown_to_whatsapp("- item 1\n- item 2")
        assert "\u2022 item 1" in result
        assert "\u2022 item 2" in result

    def test_unordered_list_asterisk(self):
        """AC1: * item -> bullet item."""
        result = markdown_to_whatsapp("* item 1")
        assert "\u2022 item 1" in result

    def test_ordered_list_preserved(self):
        """AC1: 1. item mantém."""
        assert "1. item" in markdown_to_whatsapp("1. item")

    def test_inline_code_preserved(self):
        """AC1: `code` mantém."""
        assert "`code`" in markdown_to_whatsapp("`code`")

    def test_code_block_preserved(self):
        """AC1: ```block``` mantém."""
        text = "```\ncode block\n```"
        result = markdown_to_whatsapp(text)
        assert "```" in result

    def test_code_block_content_not_transformed(self):
        """M1: Conteúdo dentro de code blocks NÃO é transformado."""
        text = "Veja:\n```\n# This is a comment\n**not bold**\n- not a list\n```"
        result = markdown_to_whatsapp(text)
        # Headers inside code blocks must NOT be converted to bold
        assert "# This is a comment" in result
        # Bold inside code blocks must NOT be converted
        assert "**not bold**" in result
        # Lists inside code blocks must NOT be converted
        assert "- not a list" in result

    def test_inline_code_content_not_transformed(self):
        """M1: Conteúdo dentro de inline code NÃO é transformado."""
        text = "Use `**bold syntax**` para negrito."
        result = markdown_to_whatsapp(text)
        assert "`**bold syntax**`" in result

    def test_link_conversion(self):
        """AC1: [text](url) -> text (url)."""
        result = markdown_to_whatsapp("[Clique aqui](https://example.com)")
        assert result == "Clique aqui (https://example.com)"

    def test_combined_formatting(self):
        """AC1: Múltiplas formatações combinadas."""
        text = "# Título\n\n**Importante:** _nota_\n\n- item 1\n- item 2"
        result = markdown_to_whatsapp(text)
        assert "*Título*" in result
        assert "*Importante:*" in result
        assert "_nota_" in result
        assert "\u2022 item 1" in result


class TestShouldAddDisclaimer:
    """Tests for should_add_disclaimer heuristic (AC7)."""

    def test_medical_content_returns_true(self):
        """AC7: Conteúdo médico retorna True."""
        assert should_add_disclaimer("O diagnóstico diferencial inclui pneumonia e tuberculose.")

    def test_treatment_content_returns_true(self):
        """AC7: Conteúdo sobre tratamento retorna True."""
        assert should_add_disclaimer("O tratamento recomendado é amoxicilina 500mg.")

    def test_drug_content_returns_true(self):
        """AC7: Conteúdo sobre medicamentos retorna True."""
        assert should_add_disclaimer("A posologia do ibuprofeno é 400mg a cada 8h.")

    def test_greeting_returns_false(self):
        """AC7: Saudação retorna False."""
        assert not should_add_disclaimer("Olá! Como posso ajudar?")

    def test_casual_conversation_returns_false(self):
        """AC7: Conversa casual retorna False."""
        assert not should_add_disclaimer("Tudo bem! Estou aqui para ajudar com seus estudos.")

    def test_symptom_content_returns_true(self):
        """AC7: Conteúdo sobre sintomas retorna True."""
        assert should_add_disclaimer("Os sintomas incluem febre, tosse e dispneia.")

    def test_mg_word_boundary_no_false_positive(self):
        """L1: 'mg' como abreviatura de estado NÃO dispara disclaimer."""
        assert not should_add_disclaimer("A prevalência em MG é alta comparada a SP.")

    def test_mg_dosage_triggers_disclaimer(self):
        """L1: 'mg' como dosagem dispara disclaimer."""
        assert should_add_disclaimer("Administrar 500 mg por via oral.")


class TestAddMedicalDisclaimer:
    """Tests for add_medical_disclaimer (AC7)."""

    def test_adds_disclaimer_at_end(self):
        """AC7: Disclaimer adicionado ao final."""
        result = add_medical_disclaimer("Resposta médica aqui.")
        assert result.endswith(
            "\n\n⚕️ _Sou uma ferramenta de apoio ao estudo. "
            "Sempre consulte um profissional de saúde para decisões clínicas._"
        )

    def test_preserves_original_text(self):
        """AC7: Texto original é preservado."""
        original = "Conteúdo médico original."
        result = add_medical_disclaimer(original)
        assert result.startswith(original)


class TestDetectContentType:
    """Tests for detect_content_type (AC1)."""

    def test_greeting_detection(self):
        """AC1: Detecta saudação."""
        assert detect_content_type("Olá! Tudo bem?") == "greeting"

    def test_list_detection(self):
        """AC1: Detecta lista."""
        assert detect_content_type("Aqui estão os itens:\n- item 1\n- item 2\n- item 3") == "list"

    def test_calculation_detection(self):
        """AC1: Detecta cálculo."""
        text = "O cálculo do IMC é: peso / altura² = 25.3 kg/m²"
        assert detect_content_type(text) == "calculation"

    def test_comparison_detection(self):
        """AC1: Detecta comparação."""
        text = "Comparando A versus B: por outro lado, enquanto A faz X, B faz Y"
        assert detect_content_type(text) == "comparison"

    def test_explanation_as_default(self):
        """AC1: Explicação como default."""
        text = "A fisiopatologia da hipertensão envolve múltiplos fatores."
        assert detect_content_type(text) == "explanation"
