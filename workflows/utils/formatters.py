"""Markdown -> WhatsApp formatting utilities."""

import re

MEDICAL_DISCLAIMER = (
    "\n\n⚕️ _Sou uma ferramenta de apoio ao estudo. "
    "Sempre consulte um profissional de saúde para decisões clínicas._"
)

# Keywords that indicate medical content — short keywords use word boundary
_MEDICAL_KEYWORDS_EXACT = [
    "diagnóstico",
    "diagnostico",
    "tratamento",
    "medicamento",
    "medicação",
    "medicacao",
    "posologia",
    "dose",
    "sintoma",
    "patologia",
    "fisiopatologia",
    "etiologia",
    "prognóstico",
    "prognostico",
    "cirurgia",
    "terapia",
    "farmacologia",
    "contraindicação",
    "contraindicacao",
    "exame",
    "laboratorial",
    "hemograma",
    "radiografia",
    "tomografia",
    "ressonância",
    "ressonancia",
    "biópsia",
    "biopsia",
    "prescrição",
    "prescricao",
    "anamnese",
    "semiologia",
    "propedêutica",
    "propedeutica",
    "diferencial",
    "clínico",
    "clinico",
    "clínica",
    "clinica",
    "infecção",
    "infeccao",
    "pneumonia",
    "diabetes",
    "hipertensão",
    "hipertensao",
    "neoplasia",
    "tumor",
    "câncer",
    "cancer",
    "antibiótico",
    "antibiotico",
    "anti-inflamatório",
    "anti-inflamatorio",
    "analgésico",
    "analgesico",
    "febre",
    "dispneia",
    "dispnéia",
]

# Short unit keywords require preceding number to avoid false positives
# e.g. "500mg" or "10 ml" match, but "MG" (state abbreviation) does not
_MEDICAL_KEYWORDS_BOUNDARY = [
    re.compile(r"\d+\s*mg/kg\b"),
    re.compile(r"\d+\s*mg\b"),
    re.compile(r"\d+\s*ml\b"),
    re.compile(r"\d+\s*mcg\b"),
]

_GREETING_PATTERNS = [
    r"^(olá|oi|ei|hey|hello|hi|bom dia|boa tarde|boa noite)",
    r"como posso (te )?ajudar",
    r"tudo bem",
    r"estou aqui para",
    r"prazer",
]

# Placeholder for code block protection
_CODE_PLACEHOLDER = "\x00CB"


def markdown_to_whatsapp(text: str) -> str:
    """Convert Markdown formatting to WhatsApp-compatible formatting.

    Conversions:
        - ``**bold**`` -> ``*bold*``
        - ``_italic_`` -> ``_italic_`` (kept)
        - ``~~strike~~`` -> ``~strike~``
        - ``# Header`` -> ``*Header*``
        - ``- item`` -> ``• item``
        - ``[text](url)`` -> ``text (url)``
        - Code blocks and inline code are preserved (protected from transformations).
    """
    # Protect code blocks and inline code from transformations
    code_blocks: list[str] = []

    def _save_code_block(match: re.Match) -> str:
        code_blocks.append(match.group(0))
        return f"{_CODE_PLACEHOLDER}{len(code_blocks) - 1}{_CODE_PLACEHOLDER}"

    # Fenced code blocks first (```...```)
    text = re.sub(r"```[\s\S]*?```", _save_code_block, text)
    # Inline code (`...`)
    text = re.sub(r"`[^`]+`", _save_code_block, text)

    # Apply formatting transformations
    # Headers -> bold
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Bold **text** -> *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Strikethrough ~~text~~ -> ~text~
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)
    # Unordered lists - item or * item -> • item
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)
    # Links [text](url) -> text (url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        text = text.replace(f"{_CODE_PLACEHOLDER}{i}{_CODE_PLACEHOLDER}", block)

    return text


def should_add_disclaimer(text: str) -> bool:
    """Determine if text contains medical content that needs a disclaimer.

    Returns True if text contains medical keywords, False for greetings
    and casual conversation.
    """
    text_lower = text.lower()

    # Check if it's a greeting/casual first
    for pattern in _GREETING_PATTERNS:
        if re.search(pattern, text_lower):
            return False

    # Check for exact-match medical keywords (substring)
    for keyword in _MEDICAL_KEYWORDS_EXACT:
        if keyword in text_lower:
            return True

    # Check for short keywords with word boundary
    for pattern in _MEDICAL_KEYWORDS_BOUNDARY:
        if pattern.search(text_lower):
            return True

    return False


def add_medical_disclaimer(text: str) -> str:
    """Append medical disclaimer to text."""
    return text + MEDICAL_DISCLAIMER


def detect_content_type(text: str) -> str:
    """Detect the type of content for format adaptation.

    Returns one of: "greeting", "calculation", "list", "comparison", "explanation".
    """
    text_lower = text.lower()

    # Greeting
    for pattern in _GREETING_PATTERNS:
        if re.search(pattern, text_lower):
            return "greeting"

    # Calculation
    calc_patterns = [
        r"cálculo",
        r"calculo",
        r"resultado",
        r"=\s*\d",
        r"\d+\s*[/×÷+\-*]\s*\d+",
        r"kg/m²",
        r"mg/dl",
    ]
    for pattern in calc_patterns:
        if re.search(pattern, text_lower):
            return "calculation"

    # List (3+ bullet items)
    list_count = len(re.findall(r"^[-•*]\s+", text, flags=re.MULTILINE))
    if list_count >= 3:
        return "list"

    # Comparison
    comparison_keywords = [
        "versus",
        "vs",
        "comparando",
        "por outro lado",
        "enquanto",
        "diferença entre",
        "diferenca entre",
    ]
    comp_count = sum(1 for kw in comparison_keywords if kw in text_lower)
    if comp_count >= 2:
        return "comparison"

    return "explanation"
