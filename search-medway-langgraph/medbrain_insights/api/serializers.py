from rest_framework import serializers


class QuestoesSerializer(serializers.Serializer):
    semana_anterior_qtd = serializers.IntegerField(min_value=0)
    mes_acumulado_qtd = serializers.IntegerField(min_value=0)
    semana_anterior_desempenho_percent = serializers.FloatField(min_value=0, max_value=1)
    mes_acumulado_desempenho_percent = serializers.FloatField(min_value=0, max_value=1)


class ProvasSimuladosSerializer(serializers.Serializer):
    semana_anterior_qtd = serializers.IntegerField(min_value=0)
    mes_acumulado_qtd = serializers.IntegerField(min_value=0)
    total_acumulado_qtd = serializers.IntegerField(min_value=0)
    semana_anterior_desempenho_percent = serializers.FloatField(min_value=0)
    mes_acumulado_desempenho_percent = serializers.FloatField(min_value=0)


class HorasEstudoSerializer(serializers.Serializer):
    semana_anterior_horas = serializers.FloatField(min_value=0)
    mes_acumulado_horas = serializers.FloatField(min_value=0)


class DiasEstudoSerializer(serializers.Serializer):
    semana_anterior_dias = serializers.IntegerField(min_value=0)
    mes_acumulado_dias = serializers.IntegerField(min_value=0)


class MedbrainInsightsInputSerializer(serializers.Serializer):
    curso = serializers.ListField(
        child=serializers.CharField(),
        min_length=1
    )
    residency_degrees = serializers.ListField(
        child=serializers.CharField(),
        min_length=1
    )

    id_aluno = serializers.IntegerField()
    aluno_email = serializers.EmailField()
    aluno_nome = serializers.CharField(allow_blank=True, required=False)

    data_referencia = serializers.DateField()

    questoes = QuestoesSerializer()
    provas_simulados = ProvasSimuladosSerializer()
    horas_estudo = HorasEstudoSerializer()
    dias_estudo = DiasEstudoSerializer()
