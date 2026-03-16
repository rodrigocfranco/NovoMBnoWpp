"""Tests for medical_calculator tool (AC #4 — Story 2.6)."""

from workflows.whatsapp.tools.calculators import medical_calculator


class TestCHA2DS2VASc:
    """Tests for CHA₂DS₂-VASc calculator."""

    async def test_high_risk_male(self):
        """Homem 72a, HAS, DM, sem AVC → score 3 → anticoagulação."""
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
        assert "ESC Guidelines" in result

    async def test_low_risk_male(self):
        """Homem jovem sem fatores → score 0 → sem anticoagulação."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 50,
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

    async def test_female_adds_one_point(self):
        """Mulher jovem sem fatores → score 1 → baixo risco."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 50,
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

    async def test_age_75_plus_adds_two(self):
        """Idade ≥ 75 adiciona 2 pontos."""
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

    async def test_stroke_adds_two(self):
        """AVC/AIT adiciona 2 pontos."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 50,
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


class TestCockcroftGault:
    """Tests for Cockcroft-Gault calculator."""

    async def test_normal_function(self):
        """Homem jovem com função renal normal."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cockcroft_gault",
                "parameters": {
                    "idade": 30,
                    "peso_kg": 70.0,
                    "creatinina_serica": 0.8,
                    "sexo": "M",
                },
            }
        )

        assert "mL/min" in result
        assert "normal" in result.lower()
        assert "Cockcroft" in result

    async def test_female_correction(self):
        """Mulher 65a, 60kg, Cr 1.2 → insuf. moderada."""
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

    async def test_zero_creatinine_error(self):
        """Creatinina = 0 retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "cockcroft_gault",
                "parameters": {
                    "idade": 50,
                    "peso_kg": 70.0,
                    "creatinina_serica": 0,
                    "sexo": "M",
                },
            }
        )

        assert "erro" in result.lower()


class TestIMC:
    """Tests for IMC/BMI calculator."""

    async def test_normal_weight(self):
        """70kg, 1.75m → 22.9 → normal."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 70.0, "altura_m": 1.75},
            }
        )

        assert "22.9" in result
        assert "normal" in result.lower()
        assert "OMS" in result

    async def test_obesity_grade_3(self):
        """120kg, 1.60m → 46.9 → obesidade III."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 120.0, "altura_m": 1.60},
            }
        )

        assert "grau III" in result

    async def test_zero_height_error(self):
        """Altura = 0 retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 70.0, "altura_m": 0},
            }
        )

        assert "erro" in result.lower()


class TestGlasgow:
    """Tests for Glasgow Coma Scale calculator."""

    async def test_normal_score(self):
        """4+5+6 = 15 → TCE leve."""
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

        assert "15" in result
        assert "leve" in result.lower()
        assert "Teasdale" in result

    async def test_severe(self):
        """1+1+1 = 3 → TCE grave."""
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

        assert "3" in result
        assert "grave" in result.lower()

    async def test_invalid_range(self):
        """Valor fora do range retorna erro."""
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

        assert "erro" in result.lower()


class TestCURB65:
    """Tests for CURB-65 calculator."""

    async def test_high_risk(self):
        """Confuso, ureia 50, FR 32, PAS 85, 70a → score 5 → UTI."""
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

    async def test_low_risk(self):
        """Sem fatores, jovem → score 0 → ambulatorial."""
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


class TestWellsTEP:
    """Tests for Wells TEP calculator."""

    async def test_moderate_probability(self):
        """Sinais TVP + sem alt. diagnóstico → score 6.0 → moderada."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "wells_tep",
                "parameters": {
                    "sinais_tvp": True,
                    "diagnostico_alternativo_improvavel": True,
                },
            }
        )

        assert "6" in result
        assert "moderada" in result.lower()

    async def test_low_probability(self):
        """Sem fatores → score 0 → baixa."""
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
        assert "baixa" in result.lower()


class TestHEARTScore:
    """Tests for HEART Score calculator."""

    async def test_high_risk(self):
        """Historia 2, ECG 2, idade 70, FR 2, troponina 2 → alto risco."""
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
        assert "alto risco" in result.lower()

    async def test_invalid_param(self):
        """Valor fora do range retorna erro."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "heart_score",
                "parameters": {
                    "historia": 5,
                    "ecg": 0,
                    "idade": 50,
                    "fatores_risco": 0,
                    "troponina": 0,
                },
            }
        )

        assert "erro" in result.lower()


class TestChildPugh:
    """Tests for Child-Pugh calculator."""

    async def test_class_a(self):
        """Valores normais → Classe A."""
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

        assert "Classe A" in result
        assert "100%" in result

    async def test_class_c(self):
        """Valores graves → Classe C."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "child_pugh",
                "parameters": {
                    "bilirrubina": 5.0,
                    "albumina": 2.0,
                    "inr": 3.0,
                    "ascite": "moderada_grave",
                    "encefalopatia": "grau3_4",
                },
            }
        )

        assert "Classe C" in result
        assert "45%" in result


class TestCorrecaoSodio:
    """Tests for sodium correction calculator."""

    async def test_hyperglycemia_correction(self):
        """Na 130, glicemia 400 → Na corrigido ~134.8."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "correcao_sodio",
                "parameters": {"sodio_medido": 130.0, "glicemia": 400.0},
            }
        )

        assert "134.8" in result
        assert "Katz" in result


class TestCorrecaoCalcio:
    """Tests for calcium correction calculator."""

    async def test_low_albumin_correction(self):
        """Ca 8.0, albumina 2.0 → Ca corrigido 9.6."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "correcao_calcio",
                "parameters": {"calcio_total": 8.0, "albumina": 2.0},
            }
        )

        assert "9.6" in result
        assert "Payne" in result


class TestMedicalCalculatorTool:
    """Tests for the medical_calculator tool itself."""

    def test_tool_has_descriptive_docstring(self):
        """AC#4: Tool has comprehensive docstring."""
        assert medical_calculator.description
        assert len(medical_calculator.description) > 100
        assert "cha2ds2_vasc" in medical_calculator.description

    async def test_unknown_calculator_fallback(self):
        """AC#4: Unknown calculator returns fallback instruction + available list."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "apache_ii",
                "parameters": {},
            }
        )

        assert "não disponível" in result.lower()
        assert "cha2ds2_vasc" in result
        assert "conhecimento" in result.lower()

    async def test_missing_parameters(self):
        """AC#4: Missing params returns message about what's needed."""
        result = await medical_calculator.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {},
            }
        )

        assert "insuficientes" in result.lower() or "parâmetros" in result.lower()
