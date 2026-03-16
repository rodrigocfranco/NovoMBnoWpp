"""Tests for medical_calculator tool (AC1, AC2 — Story 2.5)."""

from workflows.whatsapp.tools.calculators import medical_calculator


class TestMedicalCalculatorDispatch:
    """Testes de despacho e erro da tool principal."""

    async def test_calculator_not_found_fallback_with_available_list(self):
        """Calculadora inexistente retorna instrução de fallback + lista de disponíveis."""
        result = await medical_calculator.ainvoke(
            {"calculator_name": "apache_ii", "parameters": {}}
        )
        assert "não disponível" in result
        assert "cha2ds2_vasc" in result
        assert "imc" in result
        assert "conhecimento" in result.lower()
        assert "assistente" in result.lower()

    async def test_missing_params_returns_helpful_message(self):
        """AC2: Parâmetros faltantes retorna mensagem clara."""
        result = await medical_calculator.ainvoke({"calculator_name": "imc", "parameters": {}})
        assert "insuficientes" in result.lower() or "missing" in result.lower()
        assert "peso_kg" in result
        assert "altura_m" in result

    def test_tool_has_comprehensive_docstring(self):
        """Tool tem docstring com todas as calculadoras listadas."""
        assert medical_calculator.description
        assert "cha2ds2_vasc" in medical_calculator.description
        assert "cockcroft_gault" in medical_calculator.description
        assert "imc" in medical_calculator.description
        assert "glasgow" in medical_calculator.description
        assert "curb65" in medical_calculator.description
        assert "wells_tep" in medical_calculator.description
        assert "heart_score" in medical_calculator.description
        assert "child_pugh" in medical_calculator.description
        assert "correcao_sodio" in medical_calculator.description
        assert "correcao_calcio" in medical_calculator.description


class TestCHA2DS2VASc:
    """Testes para calculadora CHA₂DS₂-VASc."""

    async def test_happy_path_high_risk_male(self):
        """AC1: Homem 72a, HAS, DM, sem AVC → score 3 → anticoagulação."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 72,
                    "sexo": "M",
                    "icc": False,
                    "has": True,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": True,
                },
            }
        )
        assert "3/9" in result
        assert "Alto risco" in result
        assert "anticoagulação" in result.lower()
        assert "ESC Guidelines 2020" in result

    async def test_low_risk_young_male(self):
        """Homem jovem sem fatores → score 0 → baixo risco."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 40,
                    "sexo": "M",
                    "icc": False,
                    "has": False,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            }
        )
        assert "0/9" in result
        assert "Baixo risco" in result

    async def test_female_score_1_is_low_risk(self):
        """Mulher com score 1 (só sexo) → baixo risco."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 40,
                    "sexo": "F",
                    "icc": False,
                    "has": False,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            }
        )
        assert "1/9" in result
        assert "Baixo risco" in result

    async def test_male_score_1_is_intermediate(self):
        """Homem com score 1 → risco intermediário."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 40,
                    "sexo": "M",
                    "icc": False,
                    "has": True,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            }
        )
        assert "1/9" in result
        assert "intermediário" in result.lower()

    async def test_age_75_gives_2_points(self):
        """Idade >= 75 dá 2 pontos."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 75,
                    "sexo": "M",
                    "icc": False,
                    "has": False,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            }
        )
        assert "2/9" in result

    async def test_age_65_gives_1_point(self):
        """Idade 65-74 dá 1 ponto."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 65,
                    "sexo": "M",
                    "icc": False,
                    "has": False,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            }
        )
        assert "1/9" in result

    async def test_avc_gives_2_points(self):
        """AVC/AIT dá 2 pontos."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 40,
                    "sexo": "M",
                    "icc": False,
                    "has": False,
                    "avc_ait": True,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            }
        )
        assert "2/9" in result

    async def test_invalid_sexo(self):
        """Sexo inválido retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 40,
                    "sexo": "X",
                    "icc": False,
                    "has": False,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            }
        )
        assert "Erro" in result
        assert "'M' ou 'F'" in result


class TestCockcroftGault:
    """Testes para calculadora Cockcroft-Gault."""

    async def test_happy_path_moderate_insufficiency(self):
        """AC1: Mulher 65a, 60kg, Cr 1.2 → ~42 mL/min → moderada."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cockcroft_gault",
                "parameters": {
                    "idade": 65,
                    "peso_kg": 60.0,
                    "creatinina_serica": 1.2,
                    "sexo": "F",
                },
            }
        )
        assert "mL/min" in result
        assert "moderada" in result.lower()
        assert "Cockcroft" in result

    async def test_normal_function(self):
        """Homem jovem com Cr normal → função normal."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cockcroft_gault",
                "parameters": {
                    "idade": 30,
                    "peso_kg": 80.0,
                    "creatinina_serica": 0.9,
                    "sexo": "M",
                },
            }
        )
        assert "normal" in result.lower()

    async def test_zero_creatinine_returns_error(self):
        """Creatinina zero retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cockcroft_gault",
                "parameters": {
                    "idade": 40,
                    "peso_kg": 70.0,
                    "creatinina_serica": 0,
                    "sexo": "M",
                },
            }
        )
        assert "Erro" in result

    async def test_invalid_sexo(self):
        """Sexo inválido retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cockcroft_gault",
                "parameters": {
                    "idade": 40,
                    "peso_kg": 70.0,
                    "creatinina_serica": 1.0,
                    "sexo": "Z",
                },
            }
        )
        assert "Erro" in result


class TestIMC:
    """Testes para calculadora IMC."""

    async def test_happy_path_normal(self):
        """AC1: 70kg, 1.75m → 22.9 → normal."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 70.0, "altura_m": 1.75},
            }
        )
        assert "22.9" in result
        assert "normal" in result.lower()
        assert "OMS" in result

    async def test_underweight(self):
        """Baixo peso."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 45.0, "altura_m": 1.70},
            }
        )
        assert "Baixo peso" in result

    async def test_overweight(self):
        """Sobrepeso."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 82.0, "altura_m": 1.75},
            }
        )
        assert "Sobrepeso" in result

    async def test_obesity_grade_3(self):
        """Obesidade grau III."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 130.0, "altura_m": 1.70},
            }
        )
        assert "grau III" in result

    async def test_zero_height_returns_error(self):
        """Altura zero retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 70.0, "altura_m": 0},
            }
        )
        assert "Erro" in result

    async def test_zero_weight_returns_error(self):
        """Peso zero retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 0, "altura_m": 1.75},
            }
        )
        assert "Erro" in result


class TestGlasgow:
    """Testes para Escala de Coma de Glasgow."""

    async def test_happy_path_normal(self):
        """AC1: 4+5+6 → 15 → leve."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "glasgow",
                "parameters": {
                    "abertura_ocular": 4,
                    "resposta_verbal": 5,
                    "resposta_motora": 6,
                },
            }
        )
        assert "15/15" in result
        assert "leve" in result.lower()
        assert "Teasdale" in result

    async def test_moderate(self):
        """Score 9-12 → moderado."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "glasgow",
                "parameters": {
                    "abertura_ocular": 3,
                    "resposta_verbal": 3,
                    "resposta_motora": 5,
                },
            }
        )
        assert "11/15" in result
        assert "moderado" in result.lower()

    async def test_severe(self):
        """Score 3-8 → grave."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "glasgow",
                "parameters": {
                    "abertura_ocular": 1,
                    "resposta_verbal": 1,
                    "resposta_motora": 1,
                },
            }
        )
        assert "3/15" in result
        assert "grave" in result.lower()

    async def test_invalid_ocular_returns_error(self):
        """Abertura ocular fora de range retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "glasgow",
                "parameters": {
                    "abertura_ocular": 5,
                    "resposta_verbal": 5,
                    "resposta_motora": 6,
                },
            }
        )
        assert "Erro" in result
        assert "abertura_ocular" in result

    async def test_invalid_verbal_returns_error(self):
        """Resposta verbal fora de range retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "glasgow",
                "parameters": {
                    "abertura_ocular": 4,
                    "resposta_verbal": 0,
                    "resposta_motora": 6,
                },
            }
        )
        assert "Erro" in result
        assert "resposta_verbal" in result

    async def test_invalid_motor_returns_error(self):
        """Resposta motora fora de range retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "glasgow",
                "parameters": {
                    "abertura_ocular": 4,
                    "resposta_verbal": 5,
                    "resposta_motora": 7,
                },
            }
        )
        assert "Erro" in result
        assert "resposta_motora" in result

    async def test_shows_component_breakdown(self):
        """Resultado mostra breakdown O:V:M."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "glasgow",
                "parameters": {
                    "abertura_ocular": 3,
                    "resposta_verbal": 4,
                    "resposta_motora": 5,
                },
            }
        )
        assert "O:3" in result
        assert "V:4" in result
        assert "M:5" in result


class TestCURB65:
    """Testes para CURB-65."""

    async def test_happy_path_high_score(self):
        """AC1: Confuso, ureia 50, FR 32, PAS 85, 70a → score 5 → UTI."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "curb65",
                "parameters": {
                    "confusao": True,
                    "ureia": 50.0,
                    "freq_resp": 32,
                    "pa_sistolica": 85,
                    "pa_diastolica": 50,
                    "idade": 70,
                },
            }
        )
        assert "5/5" in result
        assert "UTI" in result
        assert "British Thoracic Society" in result

    async def test_low_score_ambulatory(self):
        """Score 0 → ambulatorial."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "curb65",
                "parameters": {
                    "confusao": False,
                    "ureia": 30.0,
                    "freq_resp": 18,
                    "pa_sistolica": 120,
                    "pa_diastolica": 80,
                    "idade": 40,
                },
            }
        )
        assert "0/5" in result
        assert "ambulatorial" in result.lower()

    async def test_score_2_consider_hospitalization(self):
        """Score 2 → considerar internação."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "curb65",
                "parameters": {
                    "confusao": True,
                    "ureia": 30.0,
                    "freq_resp": 18,
                    "pa_sistolica": 120,
                    "pa_diastolica": 80,
                    "idade": 70,
                },
            }
        )
        assert "2/5" in result
        assert "internação" in result.lower()

    async def test_score_3_hospitalization(self):
        """Score 3 → internação hospitalar."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "curb65",
                "parameters": {
                    "confusao": True,
                    "ureia": 50.0,
                    "freq_resp": 18,
                    "pa_sistolica": 120,
                    "pa_diastolica": 80,
                    "idade": 70,
                },
            }
        )
        assert "3/5" in result
        assert "internação" in result.lower()

    async def test_diastolic_threshold(self):
        """PAD ≤ 60 conta como ponto."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "curb65",
                "parameters": {
                    "confusao": False,
                    "ureia": 30.0,
                    "freq_resp": 18,
                    "pa_sistolica": 120,
                    "pa_diastolica": 60,
                    "idade": 40,
                },
            }
        )
        assert "1/5" in result


class TestWellsTEP:
    """Testes para Wells TEP."""

    async def test_happy_path_moderate(self):
        """AC1: Sinais TVP + sem alt. diagnóstico → score 6 → moderada."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "wells_tep",
                "parameters": {
                    "sinais_tvp": True,
                    "diagnostico_alternativo_improvavel": True,
                    "fc_maior_100": False,
                    "imobilizacao_cirurgia": False,
                    "tep_tvp_previo": False,
                    "hemoptise": False,
                    "cancer_ativo": False,
                },
            }
        )
        assert "6" in result
        assert "moderada" in result.lower()
        assert "Wells" in result

    async def test_low_probability(self):
        """Nenhum fator → score 0 → baixa."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "wells_tep",
                "parameters": {
                    "sinais_tvp": False,
                    "diagnostico_alternativo_improvavel": False,
                    "fc_maior_100": False,
                    "imobilizacao_cirurgia": False,
                    "tep_tvp_previo": False,
                    "hemoptise": False,
                    "cancer_ativo": False,
                },
            }
        )
        assert "0" in result
        assert "Baixa" in result
        assert "D-dímero" in result

    async def test_high_probability(self):
        """Múltiplos fatores → alta probabilidade."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "wells_tep",
                "parameters": {
                    "sinais_tvp": True,
                    "diagnostico_alternativo_improvavel": True,
                    "fc_maior_100": True,
                    "imobilizacao_cirurgia": False,
                    "tep_tvp_previo": False,
                    "hemoptise": False,
                    "cancer_ativo": False,
                },
            }
        )
        assert "7.5" in result
        assert "Alta" in result


class TestHEARTScore:
    """Testes para HEART Score."""

    async def test_happy_path_low_risk(self):
        """Score baixo → baixo risco."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "heart_score",
                "parameters": {
                    "historia": 0,
                    "ecg": 0,
                    "idade": 40,
                    "fatores_risco": 0,
                    "troponina": 0,
                },
            }
        )
        assert "0/10" in result
        assert "Baixo risco" in result
        assert "Backus" in result

    async def test_moderate_risk(self):
        """Score 4-6 → risco moderado."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "heart_score",
                "parameters": {
                    "historia": 1,
                    "ecg": 1,
                    "idade": 55,
                    "fatores_risco": 1,
                    "troponina": 1,
                },
            }
        )
        assert "5/10" in result
        assert "moderado" in result.lower()

    async def test_high_risk(self):
        """Score 7+ → alto risco."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "heart_score",
                "parameters": {
                    "historia": 2,
                    "ecg": 2,
                    "idade": 70,
                    "fatores_risco": 2,
                    "troponina": 2,
                },
            }
        )
        assert "10/10" in result
        assert "Alto risco" in result

    async def test_age_under_45_gives_0_points(self):
        """Idade < 45 → 0 pontos de idade."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "heart_score",
                "parameters": {
                    "historia": 0,
                    "ecg": 0,
                    "idade": 44,
                    "fatores_risco": 0,
                    "troponina": 0,
                },
            }
        )
        assert "0/10" in result

    async def test_age_45_64_gives_1_point(self):
        """Idade 45-64 → 1 ponto."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "heart_score",
                "parameters": {
                    "historia": 0,
                    "ecg": 0,
                    "idade": 50,
                    "fatores_risco": 0,
                    "troponina": 0,
                },
            }
        )
        assert "1/10" in result

    async def test_age_65_plus_gives_2_points(self):
        """Idade ≥ 65 → 2 pontos."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "heart_score",
                "parameters": {
                    "historia": 0,
                    "ecg": 0,
                    "idade": 65,
                    "fatores_risco": 0,
                    "troponina": 0,
                },
            }
        )
        assert "2/10" in result

    async def test_invalid_historia_returns_error(self):
        """Historia fora de range retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "heart_score",
                "parameters": {
                    "historia": 3,
                    "ecg": 0,
                    "idade": 50,
                    "fatores_risco": 0,
                    "troponina": 0,
                },
            }
        )
        assert "Erro" in result
        assert "historia" in result

    async def test_invalid_troponina_returns_error(self):
        """Troponina fora de range retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "heart_score",
                "parameters": {
                    "historia": 0,
                    "ecg": 0,
                    "idade": 50,
                    "fatores_risco": 0,
                    "troponina": 5,
                },
            }
        )
        assert "Erro" in result
        assert "troponina" in result


class TestChildPugh:
    """Testes para Child-Pugh."""

    async def test_happy_path_class_a(self):
        """Classe A — cirrose compensada."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "child_pugh",
                "parameters": {
                    "bilirrubina": 1.5,
                    "albumina": 4.0,
                    "inr": 1.2,
                    "ascite": "ausente",
                    "encefalopatia": "ausente",
                },
            }
        )
        assert "5/15" in result
        assert "Classe A" in result
        assert "100%" in result
        assert "Pugh" in result

    async def test_class_b(self):
        """Classe B — cirrose moderada (score 7-9)."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "child_pugh",
                "parameters": {
                    "bilirrubina": 2.5,
                    "albumina": 3.0,
                    "inr": 1.5,
                    "ascite": "leve",
                    "encefalopatia": "ausente",
                },
            }
        )
        # bil=2(2pts) + alb=3.0(2pts) + inr=1.5(1pt) + ascite=leve(2pts) + encef=ausente(1pt) = 8
        assert "Classe B" in result
        assert "80%" in result

    async def test_class_c(self):
        """Classe C — cirrose grave."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "child_pugh",
                "parameters": {
                    "bilirrubina": 4.0,
                    "albumina": 2.0,
                    "inr": 2.5,
                    "ascite": "moderada_grave",
                    "encefalopatia": "grau3_4",
                },
            }
        )
        assert "Classe C" in result
        assert "45%" in result

    async def test_invalid_ascite_returns_error(self):
        """Ascite inválida retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "child_pugh",
                "parameters": {
                    "bilirrubina": 1.5,
                    "albumina": 4.0,
                    "inr": 1.2,
                    "ascite": "invalida",
                    "encefalopatia": "ausente",
                },
            }
        )
        assert "Erro" in result
        assert "ascite" in result

    async def test_invalid_encefalopatia_returns_error(self):
        """Encefalopatia inválida retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "child_pugh",
                "parameters": {
                    "bilirrubina": 1.5,
                    "albumina": 4.0,
                    "inr": 1.2,
                    "ascite": "ausente",
                    "encefalopatia": "invalida",
                },
            }
        )
        assert "Erro" in result
        assert "encefalopatia" in result


class TestCorrecaoSodio:
    """Testes para correção de sódio."""

    async def test_happy_path(self):
        """Correção com hiperglicemia."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "correcao_sodio",
                "parameters": {"sodio_medido": 130.0, "glicemia": 400.0},
            }
        )
        # Na corrigido = 130 + 1.6 * ((400-100)/100) = 130 + 4.8 = 134.8
        assert "134.8" in result
        assert "mEq/L" in result
        assert "Katz" in result

    async def test_normal_glucose_no_correction(self):
        """Glicemia 100 → sem correção."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "correcao_sodio",
                "parameters": {"sodio_medido": 140.0, "glicemia": 100.0},
            }
        )
        assert "140.0" in result


class TestCorrecaoCalcio:
    """Testes para correção de cálcio pela albumina."""

    async def test_happy_path(self):
        """Correção com albumina baixa."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "correcao_calcio",
                "parameters": {"calcio_total": 8.0, "albumina": 2.0},
            }
        )
        # Ca corrigido = 8.0 + 0.8 * (4.0 - 2.0) = 8.0 + 1.6 = 9.6
        assert "9.6" in result
        assert "mg/dL" in result
        assert "Payne" in result

    async def test_normal_albumin_no_correction(self):
        """Albumina 4.0 → sem correção."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "correcao_calcio",
                "parameters": {"calcio_total": 9.5, "albumina": 4.0},
            }
        )
        assert "9.5" in result


class TestResultFormat:
    """Testes de formatação do resultado (AC1)."""

    async def test_all_calculators_return_reference(self):
        """AC1: Toda calculadora retorna referência bibliográfica."""
        test_cases = [
            (
                "cha2ds2_vasc",
                {
                    "idade": 50,
                    "sexo": "M",
                    "icc": False,
                    "has": False,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            ),
            (
                "cockcroft_gault",
                {
                    "idade": 50,
                    "peso_kg": 70.0,
                    "creatinina_serica": 1.0,
                    "sexo": "M",
                },
            ),
            ("imc", {"peso_kg": 70.0, "altura_m": 1.75}),
            (
                "glasgow",
                {
                    "abertura_ocular": 4,
                    "resposta_verbal": 5,
                    "resposta_motora": 6,
                },
            ),
            (
                "curb65",
                {
                    "confusao": False,
                    "ureia": 30.0,
                    "freq_resp": 18,
                    "pa_sistolica": 120,
                    "pa_diastolica": 80,
                    "idade": 40,
                },
            ),
            (
                "wells_tep",
                {
                    "sinais_tvp": False,
                    "diagnostico_alternativo_improvavel": False,
                    "fc_maior_100": False,
                    "imobilizacao_cirurgia": False,
                    "tep_tvp_previo": False,
                    "hemoptise": False,
                    "cancer_ativo": False,
                },
            ),
            (
                "heart_score",
                {
                    "historia": 0,
                    "ecg": 0,
                    "idade": 50,
                    "fatores_risco": 0,
                    "troponina": 0,
                },
            ),
            (
                "child_pugh",
                {
                    "bilirrubina": 1.5,
                    "albumina": 4.0,
                    "inr": 1.2,
                    "ascite": "ausente",
                    "encefalopatia": "ausente",
                },
            ),
            (
                "correcao_sodio",
                {
                    "sodio_medido": 140.0,
                    "glicemia": 100.0,
                },
            ),
            (
                "correcao_calcio",
                {
                    "calcio_total": 9.5,
                    "albumina": 4.0,
                },
            ),
        ]
        for calc_name, params in test_cases:
            result = await medical_calculator.ainvoke(
                {
                    "calculator_name": calc_name,
                    "parameters": params,
                }
            )
            assert "Referência:" in result or "Fórmula:" in result, (
                f"Calculadora '{calc_name}' não retornou referência"
            )

    async def test_all_calculators_return_conduta(self):
        """AC1: Toda calculadora retorna conduta recomendada."""
        test_cases = [
            (
                "cha2ds2_vasc",
                {
                    "idade": 50,
                    "sexo": "M",
                    "icc": False,
                    "has": False,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            ),
            (
                "cockcroft_gault",
                {
                    "idade": 50,
                    "peso_kg": 70.0,
                    "creatinina_serica": 1.0,
                    "sexo": "M",
                },
            ),
            ("imc", {"peso_kg": 70.0, "altura_m": 1.75}),
            (
                "glasgow",
                {
                    "abertura_ocular": 4,
                    "resposta_verbal": 5,
                    "resposta_motora": 6,
                },
            ),
            (
                "curb65",
                {
                    "confusao": False,
                    "ureia": 30.0,
                    "freq_resp": 18,
                    "pa_sistolica": 120,
                    "pa_diastolica": 80,
                    "idade": 40,
                },
            ),
            (
                "wells_tep",
                {
                    "sinais_tvp": False,
                    "diagnostico_alternativo_improvavel": False,
                    "fc_maior_100": False,
                    "imobilizacao_cirurgia": False,
                    "tep_tvp_previo": False,
                    "hemoptise": False,
                    "cancer_ativo": False,
                },
            ),
            (
                "heart_score",
                {
                    "historia": 0,
                    "ecg": 0,
                    "idade": 50,
                    "fatores_risco": 0,
                    "troponina": 0,
                },
            ),
            (
                "child_pugh",
                {
                    "bilirrubina": 1.5,
                    "albumina": 4.0,
                    "inr": 1.2,
                    "ascite": "ausente",
                    "encefalopatia": "ausente",
                },
            ),
            (
                "correcao_sodio",
                {
                    "sodio_medido": 140.0,
                    "glicemia": 100.0,
                },
            ),
            (
                "correcao_calcio",
                {
                    "calcio_total": 9.5,
                    "albumina": 4.0,
                },
            ),
        ]
        for calc_name, params in test_cases:
            result = await medical_calculator.ainvoke(
                {
                    "calculator_name": calc_name,
                    "parameters": params,
                }
            )
            assert "Conduta:" in result, (
                f"Calculadora '{calc_name}' não retornou conduta recomendada"
            )

    async def test_all_calculators_return_string(self):
        """AC1: Toda calculadora retorna string."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 70.0, "altura_m": 1.75},
            }
        )
        assert isinstance(result, str)


class TestTypeCoercion:
    """Testes de type coercion — tipos errados devem retornar erro, não crash."""

    async def test_sexo_as_int_returns_error(self):
        """sexo=1 (int) não deve causar crash."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 50,
                    "sexo": 1,
                    "icc": False,
                    "has": False,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": False,
                },
            }
        )
        assert "erro" in result.lower()

    async def test_sexo_as_int_cockcroft_returns_error(self):
        """sexo=1 (int) em Cockcroft-Gault não deve causar crash."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cockcroft_gault",
                "parameters": {
                    "idade": 50,
                    "peso_kg": 70.0,
                    "creatinina_serica": 1.0,
                    "sexo": 1,
                },
            }
        )
        assert "erro" in result.lower()

    async def test_ascite_as_bool_returns_error(self):
        """ascite=True (bool) em Child-Pugh não deve causar crash."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "child_pugh",
                "parameters": {
                    "bilirrubina": 1.5,
                    "albumina": 4.0,
                    "inr": 1.2,
                    "ascite": True,
                    "encefalopatia": "ausente",
                },
            }
        )
        assert "erro" in result.lower()

    async def test_encefalopatia_as_none_returns_error(self):
        """encefalopatia=None em Child-Pugh não deve causar crash."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "child_pugh",
                "parameters": {
                    "bilirrubina": 1.5,
                    "albumina": 4.0,
                    "inr": 1.2,
                    "ascite": "ausente",
                    "encefalopatia": None,
                },
            }
        )
        assert "erro" in result.lower()

    async def test_wells_tep_empty_params_defaults_to_zero(self):
        """Wells TEP com params vazios usa defaults (todos False) → score 0."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "wells_tep",
                "parameters": {},
            }
        )
        assert "0" in result
        assert "Baixa" in result
