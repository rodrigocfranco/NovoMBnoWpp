import calendar
from enum import Enum

META_PARAMETERS_MATRIX_R1 = {
    1: [2, 12, 460, 3, 13],
    2: [2, 14, 680, 4, 15],
    3: [3, 18, 850, 4, 18],
    4: [3, 20, 950, 4, 18],
    5: [3, 22, 960, 4, 18],
    6: [4, 26, 1000, 4, 18],
    7: [4, 28, 1240, 4, 19],
    8: [4, 30, 1360, 4, 20],
    9: [6, 31, 1390, 5, 19],
    10: [6, 32, 1460, 5, 20],
    11: [6, 31, 1280, 4, 18],
    12: [3, 14, 460, 2, 8],
}
META_PARAMETERS_MATRIX_RPLUS = {
    1: [0, 6, 112, 3, 13],
    2: [0, 9, 246, 4, 15],
    3: [0, 13, 284, 4, 18],
    4: [0, 13, 324, 4, 18],
    5: [0, 15, 384, 4, 18],
    6: [0, 12, 362, 4, 18],
    7: [1, 15, 566, 5, 19],
    8: [2, 16, 583, 5, 20],
    9: [2, 14, 634, 4, 19],
    10: [4, 19, 806, 5, 20],
    11: [7, 22, 1040, 5, 18],
    12: [2, 6, 300, 2, 8],
}


class StatusEnum(Enum):
    SUPER_GOAL = "Estudo Padrão Ouro"
    GOAL = "Ritmo de Aprovação"
    ALMOST = "Quase lá"
    ATTENTION = "Ajustar"
    CRITICAL = "Recuperar"


class EvaluationInsightService:
    def __init__(self, residency_degrees: str, reference_date):
        self.reference_date = reference_date
        self.meta_parameters = self._get_meta_parameters(residency_degrees)

    def _get_meta_parameters(self, residency_degrees):
        if 'R1' in residency_degrees:
            meta_parameters_matrix = META_PARAMETERS_MATRIX_R1
        else:
            meta_parameters_matrix = META_PARAMETERS_MATRIX_RPLUS

        meta_parameters = meta_parameters_matrix[self.reference_date.month]
        return {
            'monthly_exam': meta_parameters[0],
            'weekly_hours': meta_parameters[1],
            'monthly_questions': meta_parameters[2],
            'weekly_study_days': meta_parameters[3],
            'monthly_study_days': meta_parameters[4]
        }

    def evaluate_exams(self, exams_data):
        """
        input:
        {
            "semana_anterior_qtd": 1,
            "mes_acumulado_qtd": 1,
            "total_acumulado_qtd": 5,
            "semana_anterior_desempenho_percent": 40.58,
            "mes_acumulado_desempenho_percent": 40.58
        }

        output:
        {
            "mes": 1,
            "realizado_mes_qtd": 1,
            "meta_mes_qtd": 2,
            "desempenho_mes_percent": 40.58,
            "status_mes": "Ajustar",
            "resumo_tecnico": "
                Janeiro: 1/1 atividades (~50%, Ajustar), desempenho 40,58% (Ajustar).
                Mês: 1/2 (~50%, Ajustar), desempenho 40,58% (Ajustar).
            "
        }
        """

        meta_mes = self.meta_parameters.get('monthly_exam')
        month_elapsed_ratio = self.compute_month_elapsed_ratio(self.reference_date)

        if meta_mes == 0:
            ratio_mes = 1
        else:
            ratio_mes = exams_data["mes_acumulado_qtd"] / (meta_mes * month_elapsed_ratio)

        status_qtd_mes = self.compute_status(ratio_mes)

        output_qtd_mes = {
            "realizado_mes_qtd": exams_data["mes_acumulado_qtd"],
            "meta_mes_qtd": meta_mes
        }

        # 2. Performance nas questões mês
        if meta_mes == 0:
            status_perf_mes = StatusEnum.GOAL.value
        else:
            status_perf_mes = self.compute_status_performance(exams_data["mes_acumulado_desempenho_percent"] / 100)

        output_perf_mes = {
            "desempenho_mes_percent": exams_data["mes_acumulado_desempenho_percent"]
        }

        # 3. Numero de atividades semana, só considerar quando meta mês > 4
        considerar_meta_qtd_semana = meta_mes >= 4
        output_qtd_semana = {}
        if considerar_meta_qtd_semana:
            meta_semana = round(meta_mes / 4)
            ratio_semana = exams_data["semana_anterior_qtd"] / meta_semana
            status_qtd_semana = self.compute_status(ratio_semana)
            output_qtd_semana = {
                "realizado_semana_qtd": exams_data["semana_anterior_qtd"],
                "meta_semana_qtd": meta_semana
            }

        # 4. Performance nas questões semana
        status_perf_semana = self.compute_status_performance(exams_data["semana_anterior_desempenho_percent"] / 100)
        output_perf_semana = {
            "desempenho_semana_percent": exams_data["semana_anterior_desempenho_percent"]
        }

        # 5. Final status
        status_mes = self.combine_status(status_qtd_mes, status_perf_mes)
        if considerar_meta_qtd_semana:
            status_semana = self.combine_status(status_qtd_semana, status_perf_semana)
        else:
            status_semana = status_perf_semana

        output_status = {
            "status_semana": status_semana,
            "status_mes": status_mes
        }

        # 6. Resumo tecnico:
        if considerar_meta_qtd_semana:
            resumo_semana = (
                f"Semana: {exams_data['semana_anterior_qtd']} atividades realizadas da meta semanal de {meta_semana} "
                f"com desempenho de {exams_data['semana_anterior_desempenho_percent']}% - "
                f"Número de atividades ficou com status'{status_qtd_semana}' e desempenho ficou com status '{status_perf_semana}', "  # noqa
                f"combinando os dois, o status final da semana = '{status_semana}'. "
            )
        else:
            resumo_semana = (
                f"Semana: {exams_data['semana_anterior_qtd']} atividades realizadas com desempenho de "
                f"{exams_data['semana_anterior_desempenho_percent']}% - "
                f"Pelo desempenho a semana ficou com status = '{status_semana}'. "
            )

        resumo_mes = (
            f"Mês: {exams_data['mes_acumulado_qtd']} atividades realizadas da meta do mês de {meta_mes} "
            f"com desempenho de {exams_data['mes_acumulado_desempenho_percent']}% - "
            f"Número de atividades ficou com status '{status_qtd_mes}' e desempenho ficou com status '{status_perf_mes}', "  # noqa
            f"combinando os dois, o status final do mês ficou com '{status_mes}', considerando que a data ainda é {self.reference_date}."  # noqa
        )

        return {
            "mes": self.reference_date.month,
            **output_qtd_mes,
            **output_perf_mes,
            **output_qtd_semana,
            **output_perf_semana,
            **output_status,
            "resumo_tecnico": resumo_semana + resumo_mes
        }

    def evaluate_hours(self, hours_data):
        """
        input:
        {
            "semana_anterior_horas": 12.59,
            "mes_acumulado_horas": 21.56
        }

        output:
        {
            "mes": 1,
            "realizado_semana_horas": 12.59,
            "meta_semana_horas": 12,
            "status_semana": "Estudo Padrão Ouro",
            "realizado_mes_horas": 21.56,
            "meta_mes_horas": 48,
            "status_mes": "Ajustar",
            "resumo_tecnico": "Janeiro: 12.6/12h (~105%, Estudo Padrão Ouro). Mês: 21.6/48h (~45%, Recuperar)."
        }
        """
        meta_semana = self.meta_parameters.get('weekly_hours')

        semana_ratio = hours_data["semana_anterior_horas"] / meta_semana
        status_semana = self.compute_status(semana_ratio)

        # Meta mes
        meta_mes = 4 * meta_semana

        month_elapsed_ratio = self.compute_month_elapsed_ratio(self.reference_date)

        mes_ratio = hours_data["mes_acumulado_horas"] / (meta_mes * month_elapsed_ratio)
        status_mes = self.compute_status(mes_ratio)

        return {
            "mes": self.reference_date.month,
            "status_semana": status_semana,
            "realizado_semana_horas": hours_data["semana_anterior_horas"],
            "meta_semana_horas": meta_semana,
            "status_mes": status_mes,
            "realizado_mes_horas": hours_data["mes_acumulado_horas"],
            "meta_mes_horas": meta_mes,
            "resumo_tecnico": (
                f"Semana: {hours_data['semana_anterior_horas']} horas realizadas da meta de {meta_semana} horas na semana - status da semana = '{status_semana}'. "  # noqa
                f"Mês: {hours_data['mes_acumulado_horas']} horas realizadas da meta de {meta_mes} horas no mês - status do mês = '{status_mes}', "  # noqa
                f"considerando que a data ainda é {self.reference_date}."
            )
        }

    def evaluate_questions(self, questions_data):
        """
        input:
        {
            "semana_anterior_qtd": 255,
            "mes_acumulado_qtd": 507,
            "semana_anterior_desempenho_percent": 0.6,
            "mes_acumulado_desempenho_percent": 0.62
        }

        output:
        {
            "mes": 1,
            "realizado_semana_qtd": 255,
            "meta_semana_qtd": 115,
            "realizado_mes_qtd": 507,
            "meta_mes_qtd": 460,
            "desempenho_semana_percent": 60,
            "desempenho_mes_percent": 62,
            "status_semana": "Estudo Padrão Ouro",
            "status_mes": "Estudo Padrão Ouro",
            "resumo_tecnico": "
                Semana: 255/115 questões com desempenho de 60% (Estudo Padrão Ouro, ótimo volume com bom desempenho).
                Mês: 507/460 questões com desempenho de 62% (Estudo Padrão Ouro, desempenho e quantidade acima da meta).
            "
        }
        """
        meta_mes = self.meta_parameters.get('monthly_questions')

        month_elapsed_ratio = self.compute_month_elapsed_ratio(self.reference_date)
        ratio_mes = questions_data["mes_acumulado_qtd"] / (meta_mes * month_elapsed_ratio)
        status_qtd_mes = self.compute_status(ratio_mes)

        meta_semana = round(meta_mes / 4)
        ratio_semana = questions_data["semana_anterior_qtd"] / meta_semana
        status_qtd_semana = self.compute_status(ratio_semana)

        # Performance nas questões
        status_perf_mes = self.compute_status_performance(questions_data["mes_acumulado_desempenho_percent"])
        status_perf_semana = self.compute_status_performance(questions_data["semana_anterior_desempenho_percent"])

        # Final status
        status_semana = self.combine_status(status_qtd_semana, status_perf_semana)
        status_mes = self.combine_status(status_qtd_mes, status_perf_mes)

        return {
            "mes": self.reference_date.month,
            "realizado_semana_qtd": questions_data["semana_anterior_qtd"],
            "meta_semana_qtd": meta_semana,
            "realizado_mes_qtd": questions_data["mes_acumulado_qtd"],
            "meta_mes_qtd": meta_mes,
            "desempenho_semana_percent": 100 * questions_data["semana_anterior_desempenho_percent"],
            "desempenho_mes_percent": 100 * questions_data["mes_acumulado_desempenho_percent"],
            "status_semana": status_semana,
            "status_mes": status_mes,
            "resumo_tecnico": (
                f"Semana: {questions_data['semana_anterior_qtd']} questões realizadas da meta semanal de {meta_semana} "
                f"com desempenho de {100 * questions_data['semana_anterior_desempenho_percent']}% - "
                f"Volume de questões ficou com status '{status_qtd_semana}' e desempenho ficou com status '{status_perf_semana}', "  # noqa
                f"combinando os dois, o status final da semana = '{status_semana}'. "
                f"Mês: {questions_data['mes_acumulado_qtd']} questões realizadas da meta mensal de {meta_mes} "
                f"com desempenho de {100 * questions_data['mes_acumulado_desempenho_percent']}% - "
                f"Volume de questões ficou com status '{status_qtd_mes}' e desempenho ficou com status '{status_perf_mes}', "  # noqa
                f"combinando os dois, o status final do mês ficou com '{status_mes}', considerando que a data ainda é {self.reference_date}."  # noqa
            )
        }

    def evaluate_study_days(self, study_days_data):
        """
        input:
        {
            "semana_anterior_dias": 6,
            "mes_acumulado_dias": 16
        }

        output:
        {
            "mes": 1,
            "status_semana": "Estudo Padrão Ouro",
            "realizado_semana": 6,
            "meta_semana": 3,
            "status_mes": "Ritmo de Aprovação",
            "realizado_mes": 16,
            "meta_mes": 13,
            "resumo_tecnico": "
                Semana: 6/3 dias ativos (Estudo Padrão Ouro).
                Mês: 16/13 dias ativos (Ritmo de Aprovação).
            "
        }
        """
        meta_semana = self.meta_parameters.get('weekly_study_days')
        meta_mes = self.meta_parameters.get('monthly_study_days')

        # Status semana
        semana_ratio = study_days_data["semana_anterior_dias"] / meta_semana
        status_semana = self.compute_status(semana_ratio)

        month_elapsed_ratio = self.compute_month_elapsed_ratio(self.reference_date)
        mes_ratio = study_days_data["mes_acumulado_dias"] / (meta_mes * month_elapsed_ratio)
        status_mes = self.compute_status(mes_ratio)

        return {
            "mes": self.reference_date.month,
            "status_semana": status_semana,
            "realizado_semana": study_days_data["semana_anterior_dias"],
            "meta_semana": meta_semana,
            "status_mes": status_mes,
            "realizado_mes": study_days_data["mes_acumulado_dias"],
            "meta_mes": meta_mes,
            "resumo_tecnico": (
                f"Semana: {study_days_data['semana_anterior_dias']} dias ativos da meta semanal de {meta_semana} - status da semana = '{status_semana}'. "  # noqa
                f"Mês: {study_days_data['mes_acumulado_dias']} dias ativos da meta de {meta_mes} dias ativos no mês - status do mês = '{status_mes}', "  # noqa
                f"considerando que a data ainda é {self.reference_date}."
            )
        }

    def compute_status(self, ratio):
        reference_month = self.reference_date.month

        if 1.1 < ratio:
            return StatusEnum.SUPER_GOAL.value
        elif 0.9 <= ratio:
            return StatusEnum.GOAL.value
        elif 0.75 <= ratio:
            return StatusEnum.ALMOST.value
        elif 0.5 <= ratio or reference_month <= 5:
            return StatusEnum.ATTENTION.value
        else:
            return StatusEnum.CRITICAL.value

    def compute_status_performance(self, performance):
        reference_month = self.reference_date.month
        if 0.75 < performance:
            return StatusEnum.SUPER_GOAL.value
        elif 0.65 <= performance:
            return StatusEnum.GOAL.value
        elif 0.55 <= performance:
            return StatusEnum.ALMOST.value
        elif 0.4 <= performance or reference_month <= 5:
            return StatusEnum.ATTENTION.value
        else:
            return StatusEnum.CRITICAL.value

    @staticmethod
    def combine_status(status1, status2):
        if StatusEnum.CRITICAL.value in [status1, status2]:
            return StatusEnum.CRITICAL.value
        elif StatusEnum.ATTENTION.value in [status1, status2]:
            return StatusEnum.ATTENTION.value
        elif StatusEnum.ALMOST.value in [status1, status2]:
            return StatusEnum.ALMOST.value
        elif StatusEnum.GOAL.value in [status1, status2]:
            return StatusEnum.GOAL.value

        return StatusEnum.SUPER_GOAL.value

    @staticmethod
    def compute_month_elapsed_ratio(date):
        """
        Compute the proportion of the month elapsed on the given date.
        Example, date January 12th -> 12 days elapsed of 31 -> proportion 12/31.
        """
        return date.day / calendar.monthrange(date.year, date.month)[1]


def prompt_priority(month):
    if month in [1, 2, 3]:
        return "Jan–Mar:\n1) constancia\n2) horas\n3) questoes\n4) provas_simulados\n"
    elif month in [4, 5]:
        return "Abr–Mai:\n1) constancia\n2) questoes\n3) horas\n4) provas_simulados\n"
    elif month == 6:
        return "Jun:\n1) questoes\n2) constancia\n3) provas_simulados\n4) horas\n"
    elif month in [7, 8]:
        return "Jul–Ago (transição para intensivo):\n1) provas_simulados\n2) questoes\n3) constancia\n4) horas\n"
    else:
        return "Set–Dez (fase de provas):\n1) provas_simulados\n2) questoes\n3) constancia\n4) horas\n"


def prompt_educational_rules(month):
    if month in [1, 2, 3]:
        return (
            "Jan–Mar:\n"
            "- constância estar ativos e cumprir o cronograma da Minha Semana.\n"
            "- se constância ou horas ruins → focar em 4 dias/semana, fazendo revisões.\n"
            "- se questões ruins → reforçar trilha pré/pós e blocos guiados.\n"
        )
    elif month in [4, 5]:
        return (
            "Abr–Mai:\n"
            "- rotina mais pesada, priorizar fazer questão, ao invés de assistir aulas longas para não perder o ritmo.\n"  # noqa
            "- se constância baixa → incentivar blocos curtos (aula Flash, trilha curta).\n"
            "- se questões ruins → blocos de 15–30 questões com revisão.\n"
        )
    elif month == 6:
        return (
            "Jun:\n"
            "- consolidar 6 meses: revisão de gaps + prova do mês.\n"
            "- se provas ruins → agendar prova 100 e revisão dos erros.\n"
            "- se questões ruins → priorizar questões dos focos mais importantes.\n"
        )
    elif month in [7, 8]:
        return (
            "Jul–Ago:\n"
            "- transição extensivo → intensivo.\n"
            "- se provas ruins → aumentar frequência de provas na íntegra.\n"
            "- se conteúdo acumulado → sugerir focar nas aulas do intensivo e IEs de interesse.\n"
        )
    else:
        return (
            "Set–Dez:\n"
            "- foco total em provas e IEs-alvo.\n"
            "- se provas ruins → pelo menos 1 prova/semana e revisar erros.\n"
            "- se constância ruim → garantir presença mínima nos dias de estudo e usar blocos rápidos (Flash, trilhas curtas) para não quebrar o ritmo.\n"  # noqa
        )
