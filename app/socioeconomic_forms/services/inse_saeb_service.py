# -*- coding: utf-8 -*-
"""
Serviço para o relatório INSE x SAEB: cruza respostas do formulário socioeconômico
com resultados da avaliação (proficiência por disciplina e média).
"""

from app import db
from app.socioeconomic_forms.models import Form
from app.socioeconomic_forms.services.results_service import ResultsService
from app.socioeconomic_forms.constants.inse_normalizer import normalizar_respostas
from app.socioeconomic_forms.constants.inse_scoring import (
    calcular_pontos_inse_canonico,
    pontuacao_para_nivel_inse,
    NIVEIS_INSE_LABELS,
)
from app.models.evaluationResult import EvaluationResult
from app.models.test import Test
from collections import defaultdict
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _calcular_inse_de_respostas(responses: Dict[str, Any]) -> Tuple[int, bool, Optional[int], str]:
    """
    Normaliza respostas e calcula INSE (pontos e nível).
    Retorna (pontos, ok, nivel_num, nivel_label).
    nivel_num pode ser None quando pontos < 10 (não calculado).
    """
    normalized = normalizar_respostas(responses or {})
    pontos, ok = calcular_pontos_inse_canonico(normalized)
    nivel_num, nivel_label = pontuacao_para_nivel_inse(pontos)
    return pontos, ok, nivel_num, nivel_label


def _format_decimal(val: Optional[float]) -> float:
    if val is None:
        return 0.0
    return round(float(val), 2)


class InseSaebService:
    """Serviço do relatório INSE x SAEB."""

    @staticmethod
    def gerar_relatorio(
        form_id: str,
        filters: Dict[str, Any],
        avaliacao_id: str,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Gera o relatório completo INSE x SAEB.

        Args:
            form_id: ID do formulário
            filters: state, municipio, escola, serie, turma
            avaliacao_id: ID da avaliação (test_id)
            page: Página da lista de alunos
            limit: Limite por página

        Returns:
            dict com resumo, distribuição INSE, distribuição proficiência e lista de alunos
        """
        form = Form.query.get(form_id)
        if not form:
            raise ValueError("Formulário não encontrado")

        test = Test.query.get(avaliacao_id)
        if not test:
            raise ValueError("Avaliação não encontrada")

        # 1) Alunos do escopo (responderam ao formulário e passaram nos filtros)
        query = ResultsService._build_base_query(form_id, filters)
        results = query.all()
        total_alunos_questionario = len(results)

        if total_alunos_questionario == 0:
            return InseSaebService._empty_report(form, test, filters)

        # 2) Calcular INSE por aluno e agregados
        student_ids = []
        inse_por_aluno = {}
        distribuicao_inse = {i: {"quantidade": 0, "porcentagem": 0.0} for i in range(1, 7)}
        soma_inse = 0
        count_inse_valido = 0

        for row in results:
            response, user, student, school, grade, class_, city = row
            student_ids.append(student.id)
            responses_data = (response.responses or {})
            pontos, ok, nivel_num, nivel_label = _calcular_inse_de_respostas(responses_data)
            inse_por_aluno[student.id] = {
                "pontos": pontos,
                "nivel": nivel_num,
                "nivel_label": nivel_label,
            }
            if nivel_num is not None:
                distribuicao_inse[nivel_num]["quantidade"] += 1
            if ok and nivel_num is not None:
                soma_inse += pontos
                count_inse_valido += 1

        for i in range(1, 7):
            qtd = distribuicao_inse[i]["quantidade"]
            distribuicao_inse[i]["porcentagem"] = round(
                (qtd / total_alunos_questionario * 100), 2
            ) if total_alunos_questionario else 0

        inse_medio = (soma_inse / count_inse_valido) if count_inse_valido else 0.0

        # 3) Resultados da avaliação (uma disciplina por test_id; suportar vários no futuro)
        resultados_avaliacao = EvaluationResult.query.filter(
            EvaluationResult.test_id == avaliacao_id,
            EvaluationResult.student_id.in_(student_ids),
        ).all()
        er_por_aluno = {r.student_id: r for r in resultados_avaliacao}

        # Proficiência média do escopo (entre quem tem resultado)
        proficiencias = [r.proficiency for r in resultados_avaliacao]
        media_proficiencia_escopo = (
            sum(proficiencias) / len(proficiencias) if proficiencias else 0.0
        )

        # Distribuição por nível de proficiência
        classificacoes = defaultdict(int)
        for r in resultados_avaliacao:
            c = (r.classification or "").strip()
            if not c:
                continue
            if "Abaixo" in c or "básico" in c.lower():
                classificacoes["abaixo_do_basico"] += 1
            elif "Básico" in c or "basico" in c:
                classificacoes["basico"] += 1
            elif "Adequado" in c:
                classificacoes["adequado"] += 1
            elif "Avançado" in c or "avancado" in c:
                classificacoes["avancado"] += 1
        total_class = sum(classificacoes.values())
        distribuicao_proficiencia = {
            "abaixo_do_basico": classificacoes["abaixo_do_basico"],
            "basico": classificacoes["basico"],
            "adequado": classificacoes["adequado"],
            "avancado": classificacoes["avancado"],
            "abaixo_do_basico_porcentagem": round(
                (classificacoes["abaixo_do_basico"] / total_class * 100), 2
            ) if total_class else 0,
            "basico_porcentagem": round(
                (classificacoes["basico"] / total_class * 100), 2
            ) if total_class else 0,
            "adequado_porcentagem": round(
                (classificacoes["adequado"] / total_class * 100), 2
            ) if total_class else 0,
            "avancado_porcentagem": round(
                (classificacoes["avancado"] / total_class * 100), 2
            ) if total_class else 0,
        }

        # 4) Disciplina da avaliação (um Test = um subject)
        disciplina_nome = (
            test.subject_rel.name if test.subject_rel else (test.title or "Avaliação")
        )
        disciplinas_info = [{"id": str(test.id), "nome": disciplina_nome}]

        # 5) Lista de alunos (paginada)
        start = (page - 1) * limit
        end = start + limit
        rows_paginados = results[start:end]
        alunos_lista = []

        for row in rows_paginados:
            response, user, student, school, grade, class_, city = row
            er = er_por_aluno.get(student.id)
            inse_data = inse_por_aluno.get(student.id, {})

            proficiencia_val = _format_decimal(er.proficiency) if er else 0.0
            nota_val = _format_decimal(er.grade) if er else 0.0
            classificacao_val = er.classification if er else None

            disciplinas_aluno = [
                {
                    "id": str(test.id),
                    "nome": disciplina_nome,
                    "proficiencia": proficiencia_val,
                    "nota": nota_val,
                    "nivel_proficiencia": classificacao_val,
                }
            ]
            proficiencia_media_aluno = proficiencia_val  # um teste = uma disciplina

            alunos_lista.append({
                "nome_completo": (user.name or student.name or "").strip() or "—",
                "disciplinas": disciplinas_aluno,
                "proficiencia_media": _format_decimal(proficiencia_media_aluno),
                "nota": nota_val,
                "nivel_proficiencia": classificacao_val,
                "inse_pontos": inse_data.get("pontos", 0),
                "inse_nivel": inse_data.get("nivel"),
                "inse_nivel_label": inse_data.get("nivel_label", ""),
            })

        return {
            "formId": form.id,
            "formTitle": form.title,
            "avaliacaoId": avaliacao_id,
            "avaliacaoTitulo": test.title,
            "filtros": filters,
            "resumo": {
                "total_alunos_questionario": total_alunos_questionario,
                "media_proficiencia_escopo": _format_decimal(media_proficiencia_escopo),
                "inse_medio": _format_decimal(inse_medio),
            },
            "distribuicao_inse": {
                str(i): {
                    "nivel": i,
                    "label": NIVEIS_INSE_LABELS.get(i, ""),
                    "quantidade": distribuicao_inse[i]["quantidade"],
                    "porcentagem": distribuicao_inse[i]["porcentagem"],
                }
                for i in range(1, 7)
            },
            "distribuicao_proficiencia": distribuicao_proficiencia,
            "disciplinas_avaliacao": disciplinas_info,
            "alunos": {
                "data": alunos_lista,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_alunos_questionario,
                    "totalPages": (total_alunos_questionario + limit - 1) // limit if limit > 0 else 0,
                },
            },
        }

    @staticmethod
    def _empty_report(form: Form, test: Test, filters: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "formId": form.id,
            "formTitle": form.title,
            "avaliacaoId": test.id,
            "avaliacaoTitulo": test.title,
            "filtros": filters,
            "resumo": {
                "total_alunos_questionario": 0,
                "media_proficiencia_escopo": 0.0,
                "inse_medio": 0.0,
            },
            "distribuicao_inse": {
                str(i): {"nivel": i, "label": NIVEIS_INSE_LABELS.get(i, ""), "quantidade": 0, "porcentagem": 0.0}
                for i in range(1, 7)
            },
            "distribuicao_proficiencia": {
                "abaixo_do_basico": 0, "basico": 0, "adequado": 0, "avancado": 0,
                "abaixo_do_basico_porcentagem": 0, "basico_porcentagem": 0,
                "adequado_porcentagem": 0, "avancado_porcentagem": 0,
            },
            "disciplinas_avaliacao": [],
            "alunos": {"data": [], "pagination": {"page": 1, "limit": 50, "total": 0, "totalPages": 0}},
        }
