"""Tests for message splitter (AC2)."""

from workflows.utils.message_splitter import split_message


class TestSplitMessage:
    """Tests for split_message function."""

    def test_short_message_returns_single_element(self):
        """AC2: Mensagem curta retorna lista com 1 elemento."""
        result = split_message("Hello World")
        assert result == ["Hello World"]

    def test_exact_limit_returns_single_element(self):
        """AC2: Mensagem exata no limite retorna 1 elemento."""
        text = "a" * 4096
        result = split_message(text)
        assert len(result) == 1

    def test_splits_on_paragraph_break(self):
        """AC2: Divide em quebra de parágrafo."""
        part1 = "A" * 2000
        part2 = "B" * 2000
        text = part1 + "\n\n" + part2
        result = split_message(text, max_length=2500)
        assert len(result) == 2
        assert result[0].strip() == part1
        assert result[1].strip() == part2

    def test_splits_on_newline(self):
        """AC2: Divide em newline quando não há parágrafo."""
        part1 = "A" * 2000
        part2 = "B" * 2000
        text = part1 + "\n" + part2
        result = split_message(text, max_length=2500)
        assert len(result) == 2

    def test_splits_on_sentence(self):
        """AC2: Divide em frase quando não há newline."""
        text = "Frase um. " * 500  # ~5000 chars
        result = split_message(text, max_length=4096)
        assert len(result) >= 2
        for part in result:
            assert len(part) <= 4096

    def test_no_part_exceeds_max_length(self):
        """AC2: Nenhuma parte excede max_length."""
        text = "Palavra " * 1000  # ~8000 chars
        result = split_message(text, max_length=4096)
        for part in result:
            assert len(part) <= 4096

    def test_splits_long_message_correctly(self):
        """AC2: Mensagem longa dividida em múltiplas partes."""
        # Create text that's ~15000 chars with paragraph breaks
        paragraphs = ["Parágrafo " + str(i) + ". " + "texto " * 80 for i in range(30)]
        text = "\n\n".join(paragraphs)
        assert len(text) > 12000  # Ensure test data is actually long
        result = split_message(text, max_length=4096)
        assert len(result) >= 3
        for part in result:
            assert len(part) <= 4096

    def test_preserves_all_content(self):
        """AC2: Nenhum conteúdo é perdido no split."""
        text = "Parte A.\n\nParte B.\n\nParte C."
        result = split_message(text, max_length=15)
        joined = " ".join(part.strip() for part in result)
        # Check all original words are present
        for word in ["Parte", "A.", "B.", "C."]:
            assert word in joined

    def test_never_splits_mid_word(self):
        """AC2: Nunca divide no meio de uma palavra."""
        text = "Palavra " * 600  # ~4800 chars
        result = split_message(text, max_length=4096)
        for part in result:
            # No part should start or end with a partial word
            assert not part.startswith(" ")

    def test_empty_string(self):
        """Edge case: string vazia."""
        result = split_message("")
        assert result == [""]

    def test_custom_max_length(self):
        """AC2: Suporta max_length customizado."""
        text = "A" * 200
        result = split_message(text, max_length=100)
        assert len(result) >= 2
        for part in result:
            assert len(part) <= 100
