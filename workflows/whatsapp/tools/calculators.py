"""Calculadoras médicas — tool LangChain para scores e fórmulas clínicas."""

from collections.abc import Callable

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Funções internas de cálculo (puras, sem I/O)
# ---------------------------------------------------------------------------


def _calculate_cha2ds2_vasc(
    idade: int,
    sexo: str,
    icc: bool = False,
    has: bool = False,
    avc_ait: bool = False,
    doenca_vascular: bool = False,
    diabetes: bool = False,
) -> str:
    """CHA₂DS₂-VASc — risco de AVC em fibrilação atrial."""
    sexo = sexo.upper()
    if sexo not in ("M", "F"):
        return "Erro: 'sexo' deve ser 'M' ou 'F'."

    score = 0
    score += 1 if icc else 0
    score += 1 if has else 0
    score += 2 if idade >= 75 else (1 if idade >= 65 else 0)
    score += 1 if diabetes else 0
    score += 2 if avc_ait else 0
    score += 1 if doenca_vascular else 0
    score += 1 if sexo == "F" else 0

    if sexo == "M":
        if score == 0:
            risco = "Baixo risco"
            conduta = "Nenhuma terapia antitrombótica recomendada."
        elif score == 1:
            risco = "Risco intermediário"
            conduta = "Considerar anticoagulação oral."
        else:
            risco = "Alto risco"
            conduta = "Anticoagulação oral recomendada (DOACs preferenciais)."
    else:
        if score <= 1:
            risco = "Baixo risco"
            conduta = "Nenhuma terapia antitrombótica recomendada."
        elif score == 2:
            risco = "Risco intermediário"
            conduta = "Considerar anticoagulação oral."
        else:
            risco = "Alto risco"
            conduta = "Anticoagulação oral recomendada (DOACs preferenciais)."

    return (
        f"CHA₂DS₂-VASc: {score}/9\n"
        f"Interpretação: {risco}\n"
        f"Conduta: {conduta}\n"
        f"Referência: ESC Guidelines 2020 — Atrial Fibrillation"
    )


def _calculate_cockcroft_gault(
    idade: int,
    peso_kg: float,
    creatinina_serica: float,
    sexo: str,
) -> str:
    """Cockcroft-Gault — clearance de creatinina estimado."""
    sexo = sexo.upper()
    if sexo not in ("M", "F"):
        return "Erro: 'sexo' deve ser 'M' ou 'F'."
    if creatinina_serica <= 0:
        return "Erro: 'creatinina_serica' deve ser maior que zero."

    crcl = ((140 - idade) * peso_kg) / (72 * creatinina_serica)
    if sexo == "F":
        crcl *= 0.85

    if crcl > 90:
        classificacao = "Função renal normal"
    elif crcl >= 60:
        classificacao = "Insuficiência renal leve"
    elif crcl >= 30:
        classificacao = "Insuficiência renal moderada"
    elif crcl >= 15:
        classificacao = "Insuficiência renal grave"
    else:
        classificacao = "Falência renal"

    return (
        f"Clearance de Creatinina: {crcl:.1f} mL/min\n"
        f"Classificação: {classificacao}\n"
        f"Conduta: Ajustar doses de medicamentos conforme clearance.\n"
        f"Referência: Cockcroft & Gault, 1976 — Nephron"
    )


def _calculate_imc(peso_kg: float, altura_m: float) -> str:
    """IMC — Índice de Massa Corporal."""
    if altura_m <= 0:
        return "Erro: 'altura_m' deve ser maior que zero."
    if peso_kg <= 0:
        return "Erro: 'peso_kg' deve ser maior que zero."

    imc = peso_kg / (altura_m**2)

    if imc < 18.5:
        classificacao = "Baixo peso"
        conduta = "Investigar causas nutricionais e orgânicas."
    elif imc < 25:
        classificacao = "Peso normal"
        conduta = "Manter hábitos saudáveis."
    elif imc < 30:
        classificacao = "Sobrepeso"
        conduta = "Orientar reeducação alimentar e atividade física."
    elif imc < 35:
        classificacao = "Obesidade grau I"
        conduta = "Avaliação nutricional e programa de exercícios."
    elif imc < 40:
        classificacao = "Obesidade grau II"
        conduta = "Acompanhamento multidisciplinar. Considerar farmacoterapia."
    else:
        classificacao = "Obesidade grau III (mórbida)"
        conduta = "Acompanhamento multidisciplinar. Considerar cirurgia bariátrica."

    return (
        f"IMC: {imc:.1f} kg/m²\n"
        f"Classificação: {classificacao}\n"
        f"Conduta: {conduta}\n"
        f"Referência: OMS — Classificação de Obesidade"
    )


def _calculate_glasgow(
    abertura_ocular: int,
    resposta_verbal: int,
    resposta_motora: int,
) -> str:
    """Escala de Coma de Glasgow."""
    if not (1 <= abertura_ocular <= 4):
        return "Erro: 'abertura_ocular' deve estar entre 1 e 4."
    if not (1 <= resposta_verbal <= 5):
        return "Erro: 'resposta_verbal' deve estar entre 1 e 5."
    if not (1 <= resposta_motora <= 6):
        return "Erro: 'resposta_motora' deve estar entre 1 e 6."

    total = abertura_ocular + resposta_verbal + resposta_motora

    if total >= 13:
        gravidade = "Traumatismo craniano leve"
        conduta = "Observação clínica. TC de crânio se indicado."
    elif total >= 9:
        gravidade = "Traumatismo craniano moderado"
        conduta = "TC de crânio urgente. Internação para observação."
    else:
        gravidade = "Traumatismo craniano grave"
        conduta = "Intubação orotraqueal. TC de crânio. UTI."

    return (
        f"Glasgow: {total}/15 "
        f"(O:{abertura_ocular} V:{resposta_verbal} M:{resposta_motora})\n"
        f"Interpretação: {gravidade}\n"
        f"Conduta: {conduta}\n"
        f"Referência: Teasdale & Jennett, 1974 — The Lancet"
    )


def _calculate_curb65(
    confusao: bool,
    ureia: float,
    freq_resp: int,
    pa_sistolica: int,
    pa_diastolica: int,
    idade: int,
) -> str:
    """CURB-65 — gravidade de pneumonia adquirida na comunidade."""
    score = 0
    score += 1 if confusao else 0
    score += 1 if ureia > 42 else 0
    score += 1 if freq_resp >= 30 else 0
    score += 1 if (pa_sistolica < 90 or pa_diastolica <= 60) else 0
    score += 1 if idade >= 65 else 0

    if score <= 1:
        conduta = "Tratamento ambulatorial."
        mortalidade = "Baixa (<3%)"
    elif score == 2:
        conduta = "Considerar internação hospitalar."
        mortalidade = "Intermediária (~9%)"
    elif score == 3:
        conduta = "Internação hospitalar."
        mortalidade = "Alta (~17%)"
    else:
        conduta = "Internação em UTI."
        mortalidade = "Muito alta (>40%)"

    return (
        f"CURB-65: {score}/5\n"
        f"Mortalidade estimada: {mortalidade}\n"
        f"Conduta: {conduta}\n"
        f"Referência: British Thoracic Society, 2009"
    )


def _calculate_wells_tep(
    sinais_tvp: bool = False,
    diagnostico_alternativo_improvavel: bool = False,
    fc_maior_100: bool = False,
    imobilizacao_cirurgia: bool = False,
    tep_tvp_previo: bool = False,
    hemoptise: bool = False,
    cancer_ativo: bool = False,
) -> str:
    """Wells TEP — probabilidade de tromboembolismo pulmonar."""
    score = 0.0
    score += 3.0 if sinais_tvp else 0
    score += 3.0 if diagnostico_alternativo_improvavel else 0
    score += 1.5 if fc_maior_100 else 0
    score += 1.5 if imobilizacao_cirurgia else 0
    score += 1.5 if tep_tvp_previo else 0
    score += 1.0 if hemoptise else 0
    score += 1.0 if cancer_ativo else 0

    if score < 2:
        probabilidade = "Baixa probabilidade"
        conduta = "D-dímero para exclusão. Se negativo, TEP improvável."
    elif score <= 6:
        probabilidade = "Probabilidade moderada"
        conduta = "Angiotomografia de tórax recomendada."
    else:
        probabilidade = "Alta probabilidade"
        conduta = "Angiotomografia de tórax. Considerar anticoagulação empírica."

    score_display = f"{score:.1f}" if score != int(score) else str(int(score))

    return (
        f"Wells (TEP): {score_display}/12.5\n"
        f"Interpretação: {probabilidade}\n"
        f"Conduta: {conduta}\n"
        f"Referência: Wells et al., 2001 — Thrombosis and Haemostasis"
    )


def _calculate_heart_score(
    historia: int,
    ecg: int,
    idade: int,
    fatores_risco: int,
    troponina: int,
) -> str:
    """HEART Score — risco de síndrome coronariana aguda."""
    for nome, valor, minimo, maximo in [
        ("historia", historia, 0, 2),
        ("ecg", ecg, 0, 2),
        ("fatores_risco", fatores_risco, 0, 2),
        ("troponina", troponina, 0, 2),
    ]:
        if not (minimo <= valor <= maximo):
            return f"Erro: '{nome}' deve estar entre {minimo} e {maximo}."

    # Componente idade
    if idade < 45:
        idade_score = 0
    elif idade <= 64:
        idade_score = 1
    else:
        idade_score = 2

    score = historia + ecg + idade_score + fatores_risco + troponina

    if score <= 3:
        risco = "Baixo risco (MACE 0.9-1.7%)"
        conduta = "Considerar alta precoce com acompanhamento ambulatorial."
    elif score <= 6:
        risco = "Risco moderado (MACE 12-16.6%)"
        conduta = "Internação para observação e investigação complementar."
    else:
        risco = "Alto risco (MACE 50-65%)"
        conduta = "Internação e intervenção precoce."

    return (
        f"HEART Score: {score}/10\n"
        f"Interpretação: {risco}\n"
        f"Conduta: {conduta}\n"
        f"Referência: Backus et al., 2010 — Netherlands Heart Journal"
    )


def _calculate_child_pugh(
    bilirrubina: float,
    albumina: float,
    inr: float,
    ascite: str,
    encefalopatia: str,
) -> str:
    """Child-Pugh — classificação de cirrose hepática."""
    ascite = ascite.lower()
    encefalopatia = encefalopatia.lower()

    ascite_validos = ("ausente", "leve", "moderada_grave")
    encefalopatia_validos = ("ausente", "grau1_2", "grau3_4")

    if ascite not in ascite_validos:
        return f"Erro: 'ascite' deve ser um de: {', '.join(ascite_validos)}."
    if encefalopatia not in encefalopatia_validos:
        return f"Erro: 'encefalopatia' deve ser um de: {', '.join(encefalopatia_validos)}."

    score = 0

    # Bilirrubina (mg/dL)
    if bilirrubina < 2:
        score += 1
    elif bilirrubina <= 3:
        score += 2
    else:
        score += 3

    # Albumina (g/dL)
    if albumina > 3.5:
        score += 1
    elif albumina >= 2.8:
        score += 2
    else:
        score += 3

    # INR
    if inr < 1.7:
        score += 1
    elif inr <= 2.3:
        score += 2
    else:
        score += 3

    # Ascite
    if ascite == "ausente":
        score += 1
    elif ascite == "leve":
        score += 2
    else:
        score += 3

    # Encefalopatia
    if encefalopatia == "ausente":
        score += 1
    elif encefalopatia == "grau1_2":
        score += 2
    else:
        score += 3

    if score <= 6:
        classe = "A"
        sobrevida = "Sobrevida em 1 ano: ~100%"
        conduta = "Cirrose compensada. Seguimento ambulatorial."
    elif score <= 9:
        classe = "B"
        sobrevida = "Sobrevida em 1 ano: ~80%"
        conduta = "Cirrose moderada. Considerar avaliação para transplante."
    else:
        classe = "C"
        sobrevida = "Sobrevida em 1 ano: ~45%"
        conduta = "Cirrose grave. Encaminhar para avaliação de transplante hepático."

    return (
        f"Child-Pugh: {score}/15 — Classe {classe}\n"
        f"Prognóstico: {sobrevida}\n"
        f"Conduta: {conduta}\n"
        f"Referência: Pugh et al., 1973 — British Journal of Surgery"
    )


def _calculate_correcao_sodio(sodio_medido: float, glicemia: float) -> str:
    """Correção de sódio para hiperglicemia."""
    if glicemia <= 0:
        return "Erro: 'glicemia' deve ser maior que zero."
    if sodio_medido <= 0:
        return "Erro: 'sodio_medido' deve ser maior que zero."
    na_corrigido = sodio_medido + 1.6 * ((glicemia - 100) / 100)

    return (
        f"Sódio corrigido: {na_corrigido:.1f} mEq/L\n"
        f"Sódio medido: {sodio_medido} mEq/L | Glicemia: {glicemia} mg/dL\n"
        f"Fórmula: Na corrigido = Na medido + 1.6 × ((glicemia - 100) / 100)\n"
        f"Conduta: Corrigir hiperglicemia e reavaliar sódio sérico.\n"
        f"Referência: Katz, 1973 — New England Journal of Medicine"
    )


def _calculate_correcao_calcio(calcio_total: float, albumina: float) -> str:
    """Correção de cálcio pela albumina."""
    if calcio_total <= 0:
        return "Erro: 'calcio_total' deve ser maior que zero."
    if albumina <= 0:
        return "Erro: 'albumina' deve ser maior que zero."
    ca_corrigido = calcio_total + 0.8 * (4.0 - albumina)

    return (
        f"Cálcio corrigido: {ca_corrigido:.1f} mg/dL\n"
        f"Cálcio total: {calcio_total} mg/dL | Albumina: {albumina} g/dL\n"
        f"Fórmula: Ca corrigido = Ca total + 0.8 × (4.0 - albumina)\n"
        f"Conduta: Interpretar cálcio corrigido para decisão clínica.\n"
        f"Referência: Payne et al., 1973 — British Medical Journal"
    )


# ---------------------------------------------------------------------------
# Registro de calculadoras e formatação de erros
# ---------------------------------------------------------------------------

CALCULATORS: dict[str, Callable] = {
    "cha2ds2_vasc": _calculate_cha2ds2_vasc,
    "cockcroft_gault": _calculate_cockcroft_gault,
    "imc": _calculate_imc,
    "glasgow": _calculate_glasgow,
    "curb65": _calculate_curb65,
    "wells_tep": _calculate_wells_tep,
    "heart_score": _calculate_heart_score,
    "child_pugh": _calculate_child_pugh,
    "correcao_sodio": _calculate_correcao_sodio,
    "correcao_calcio": _calculate_correcao_calcio,
}

_CALCULATOR_PARAMS: dict[str, list[str]] = {
    "cha2ds2_vasc": ["idade", "sexo", "icc", "has", "avc_ait", "doenca_vascular", "diabetes"],
    "cockcroft_gault": ["idade", "peso_kg", "creatinina_serica", "sexo"],
    "imc": ["peso_kg", "altura_m"],
    "glasgow": ["abertura_ocular", "resposta_verbal", "resposta_motora"],
    "curb65": ["confusao", "ureia", "freq_resp", "pa_sistolica", "pa_diastolica", "idade"],
    "wells_tep": [
        "sinais_tvp",
        "diagnostico_alternativo_improvavel",
        "fc_maior_100",
        "imobilizacao_cirurgia",
        "tep_tvp_previo",
        "hemoptise",
        "cancer_ativo",
    ],
    "heart_score": ["historia", "ecg", "idade", "fatores_risco", "troponina"],
    "child_pugh": ["bilirrubina", "albumina", "inr", "ascite", "encefalopatia"],
    "correcao_sodio": ["sodio_medido", "glicemia"],
    "correcao_calcio": ["calcio_total", "albumina"],
}


def _format_missing_params(calculator_name: str, error: TypeError) -> str:
    """Formata mensagem quando parâmetros obrigatórios estão faltando."""
    expected = _CALCULATOR_PARAMS.get(calculator_name, [])
    return (
        f"Dados insuficientes para '{calculator_name}'. "
        f"Parâmetros necessários: {', '.join(expected)}.\n"
        f"Detalhe: {error}"
    )


# ---------------------------------------------------------------------------
# Tool LangChain
# ---------------------------------------------------------------------------


@tool
async def medical_calculator(calculator_name: str, parameters: dict) -> str:
    """Executa cálculos médicos e scores clínicos (CHA₂DS₂-VASc, Cockcroft-Gault, etc).

    **QUANDO USAR:**
    - Calcular scores de risco (CHA₂DS₂-VASc, CURB-65, Wells, HEART, Child-Pugh)
    - Clearance de creatinina (Cockcroft-Gault)
    - IMC, Glasgow, correções de sódio/cálcio
    - Qualquer cálculo numérico médico

    **QUANDO NÃO USAR:**
    - Buscar informações sobre o score → use rag_medical_search
    - Perguntar "o que é CHA₂DS₂-VASc" → use rag_medical_search
    - Obter protocolo de anticoagulação → use rag_medical_search

    **CALCULADORAS DISPONÍVEIS:** cha2ds2_vasc, cockcroft_gault, imc, glasgow,
    curb65, wells_tep, heart_score, child_pugh, correcao_sodio, correcao_calcio.

    **EXEMPLO:** "calcule CHA₂DS₂-VASc para HAS + 75 anos + DM" ✅
    **CONTRA-EXEMPLO:** "o que é o score CURB-65?" ❌ (busca → use RAG)

    Args:
        calculator_name: Nome da calculadora (ex: "cha2ds2_vasc").
        parameters: Dicionário com parâmetros (ex: {"age": 75, "hypertension": True}).
    """
    calc_fn = CALCULATORS.get(calculator_name)
    if not calc_fn:
        available = ", ".join(sorted(CALCULATORS.keys()))
        logger.info(
            "calculator_not_found",
            calculator=calculator_name,
            params=parameters,
        )
        return (
            f"Calculadora '{calculator_name}' não disponível como função dedicada. "
            f"Calculadoras disponíveis: {available}.\n"
            f"INSTRUÇÃO: Calcule usando seu conhecimento médico. "
            f"Inclua na resposta: resultado, interpretação, conduta e referência. "
            f"Avise que o cálculo foi feito pelo assistente"
            f" (sem validação por calculadora dedicada)."
        )

    is_error = False
    try:
        result = calc_fn(**parameters)
    except TypeError as e:
        is_error = True
        result = _format_missing_params(calculator_name, e)
    except Exception as e:
        is_error = True
        logger.error(
            "calculator_error",
            tool_name="medical_calculator",
            calculator=calculator_name,
            error_type=type(e).__name__,
            error=str(e),
        )
        result = f"Erro ao calcular '{calculator_name}': {e}"

    if not is_error:
        logger.info(
            "calculator_executed",
            calculator=calculator_name,
            params=parameters,
            result=result[:100],
        )

    return result
