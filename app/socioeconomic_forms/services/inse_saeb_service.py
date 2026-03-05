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
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.subject import Subject
from app.models.studentAnswer import StudentAnswer
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.evaluation_result_service import EvaluationResultService
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


def _course_name_for_test(test: Test) -> str:
    """Retorna o nome do curso (ex.: Anos Iniciais) a partir de test.course."""
    if not getattr(test, "course", None):
        return "Anos Iniciais"
    try:
        from app.models.educationStage import EducationStage
        import uuid as _uuid
        course_uuid = _uuid.UUID(test.course)
        stage = EducationStage.query.get(course_uuid)
        return stage.name if stage else "Anos Iniciais"
    except (ValueError, TypeError, Exception):
        return "Anos Iniciais"


def _nivel_proficiencia_geral(proficiencia_media: float, course_name: str) -> Optional[str]:
    """
    Classificação geral do aluno a partir da média das proficiências (por disciplina).
    Mesma lógica de evaluation_results_routes._calcular_dados_gerais_alunos.
    """
    if proficiencia_media is None:
        return None
    cn = (course_name or "").lower()
    if "finais" in cn or "médio" in cn or "medio" in cn:
        # Anos Finais / Ensino Médio
        if proficiencia_media >= 340:
            return "Avançado"
        if proficiencia_media >= 290:
            return "Adequado"
        if proficiencia_media >= 212.50:
            return "Básico"
        return "Abaixo do Básico"
    # Anos Iniciais / EJA / Infantil
    if proficiencia_media >= 263:
        return "Avançado"
    if proficiencia_media >= 213:
        return "Adequado"
    if proficiencia_media >= 163:
        return "Básico"
    return "Abaixo do Básico"


def _disciplinas_e_proficiencia_por_aluno(
    avaliacao_id: str,
    test: Test,
    student_ids: List[str],
) -> Tuple[
    List[Dict[str, Any]],
    Dict[str, Dict[str, Dict[str, Any]]],
]:
    """
    Obtém disciplinas da avaliação (subjects_info ou subject_rel) e calcula
    proficiência por (aluno, disciplina) a partir das respostas, igual a
    evaluation_results_routes / EvaluationResultService.

    Returns:
        (disciplinas_info, resultado_por_aluno_por_disciplina)
        disciplinas_info: [{"id": subject_id, "nome": "Matemática"}, ...]
        resultado_por_aluno_por_disciplina: student_id -> subject_id -> {proficiency, grade, classification}
    """
    course_name = _course_name_for_test(test)
    resultado_por_aluno = defaultdict(dict)  # student_id -> subject_id -> {}

    # 1) Definir disciplinas: subjects_info ou fallback subject_rel
    subject_ids = []
    subjects_list = []  # Subject objects
    if test.subjects_info and isinstance(test.subjects_info, list) and len(test.subjects_info) > 0:
        for item in test.subjects_info:
            if isinstance(item, dict) and "id" in item:
                subject_ids.append(str(item["id"]))
            elif isinstance(item, str):
                subject_ids.append(str(item))
        if subject_ids:
            subjects_list = Subject.query.filter(Subject.id.in_(subject_ids)).all()
            subject_ids = [str(s.id) for s in subjects_list]
    if not subjects_list and test.subject_rel:
        subjects_list = [test.subject_rel]
        subject_ids = [str(test.subject_rel.id)]

    if not subjects_list:
        return [], dict(resultado_por_aluno)

    # 2) Questões do teste agrupadas por disciplina
    tq_list = TestQuestion.query.filter_by(test_id=avaliacao_id).order_by(TestQuestion.order).all()
    question_ids = [tq.question_id for tq in tq_list]
    questions = Question.query.filter(Question.id.in_(question_ids)).all() if question_ids else []
    questions_by_id = {q.id: q for q in questions}

    questions_by_subject = defaultdict(list)
    for tq in tq_list:
        q = questions_by_id.get(tq.question_id)
        if not q:
            continue
        if subjects_list and len(subjects_list) == 1 and not getattr(q, "subject_id", None):
            sid = str(subjects_list[0].id)
            questions_by_subject[sid].append(q)
        elif q.subject_id and str(q.subject_id) in subject_ids:
            questions_by_subject[str(q.subject_id)].append(q)

    # 3) Respostas de todos os alunos (uma query)
    all_answers = []
    if student_ids:
        all_answers = StudentAnswer.query.filter(
            StudentAnswer.test_id == avaliacao_id,
            StudentAnswer.student_id.in_(student_ids),
        ).all()
    respostas_por_aluno = defaultdict(dict)  # student_id -> question_id -> StudentAnswer
    for a in all_answers:
        respostas_por_aluno[a.student_id][a.question_id] = a

    # 4) Por disciplina e por aluno: acertos, total respondidas, calcular proficiência
    for subject in subjects_list:
        sid = str(subject.id)
        subject_questions = questions_by_subject.get(sid)
        if not subject_questions:
            continue
        questions_with_answer = [q for q in subject_questions if getattr(q, "correct_answer", None)]
        if not questions_with_answer:
            continue
        subject_question_ids = {q.id for q in questions_with_answer}
        subject_name = subject.name

        for student_id in student_ids:
            answers = respostas_por_aluno.get(student_id, {})
            subject_answers = [(qid, answers[qid]) for qid in subject_question_ids if qid in answers]
            total_respondidas = len(subject_answers)
            if total_respondidas == 0:
                continue
            correct = 0
            for qid, answer in subject_answers:
                q = questions_by_id.get(qid)
                if not q:
                    continue
                if getattr(q, "question_type", None) == "multiple_choice":
                    if EvaluationResultService.check_multiple_choice_answer(answer.answer, q.correct_answer):
                        correct += 1
                elif q.correct_answer and str(getattr(answer, "answer", "") or "").strip().lower() == str(q.correct_answer).strip().lower():
                    correct += 1
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=correct,
                total_questions=total_respondidas,
                course_name=course_name,
                subject_name=subject_name,
            )
            resultado_por_aluno[student_id][sid] = {
                "proficiency": result["proficiency"],
                "grade": result["grade"],
                "classification": result["classification"],
            }

    disciplinas_info = [{"id": str(s.id), "nome": s.name} for s in subjects_list]
    return disciplinas_info, dict(resultado_por_aluno)


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

        # 0) Total que receberam o formulário no escopo (form_recipients + mesmo escopo dos filtros)
        total_receberam_formulario = ResultsService.count_recipients_in_scope(form_id, filters)

        # 1) Alunos do escopo (responderam ao formulário e passaram nos filtros)
        query = ResultsService._build_base_query(form_id, filters)
        results = query.all()
        total_alunos_questionario = len(results)

        total_nao_responderam = max(0, total_receberam_formulario - total_alunos_questionario)
        porcentagem_participacao = round(
            (total_alunos_questionario / total_receberam_formulario * 100), 2
        ) if total_receberam_formulario else 0
        porcentagem_nao_responderam = round(
            (total_nao_responderam / total_receberam_formulario * 100), 2
        ) if total_receberam_formulario else 0

        if total_alunos_questionario == 0:
            return InseSaebService._empty_report(
                form, test, avaliacao_id, filters,
                total_receberam_formulario=total_receberam_formulario,
                total_nao_responderam=total_nao_responderam,
                porcentagem_participacao=porcentagem_participacao,
                porcentagem_nao_responderam=porcentagem_nao_responderam,
            )

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

        # 3) Proficiência por disciplina (subjects_info + respostas, igual evaluation_results_routes)
        disciplinas_info, resultado_por_aluno_por_disciplina = _disciplinas_e_proficiencia_por_aluno(
            avaliacao_id, test, student_ids
        )

        # Média de proficiência do escopo e distribuição por nível (1 aluno = 1 classificação, igual evaluation_results_routes)
        course_name = _course_name_for_test(test)
        soma_media_alunos = 0.0
        count_alunos_com_proficiencia = 0
        classificacoes = defaultdict(int)
        for student_id in student_ids:
            disc_data = resultado_por_aluno_por_disciplina.get(student_id, {})
            if not disc_data:
                continue
            profs = [d["proficiency"] for d in disc_data.values()]
            media_aluno = sum(profs) / len(profs) if profs else 0.0
            soma_media_alunos += media_aluno
            count_alunos_com_proficiencia += 1
            # Um aluno = um nível (derivado da proficiência média)
            nivel = _nivel_proficiencia_geral(media_aluno, course_name)
            if nivel:
                if nivel == "Abaixo do Básico":
                    classificacoes["abaixo_do_basico"] += 1
                elif nivel == "Básico":
                    classificacoes["basico"] += 1
                elif nivel == "Adequado":
                    classificacoes["adequado"] += 1
                elif nivel == "Avançado":
                    classificacoes["avancado"] += 1
        media_proficiencia_escopo = (
            soma_media_alunos / count_alunos_com_proficiencia
            if count_alunos_com_proficiencia else 0.0
        )
        total_class = sum(classificacoes.values())  # total = quantidade de alunos com resultado
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

        # 4) Lista de alunos (paginada)
        start = (page - 1) * limit
        end = start + limit
        rows_paginados = results[start:end]
        alunos_lista = []

        for row in rows_paginados:
            response, user, student, school, grade, class_, city = row
            resultado_aluno = resultado_por_aluno_por_disciplina.get(student.id, {})
            inse_data = inse_por_aluno.get(student.id, {})

            disciplinas_aluno = []
            for disc in disciplinas_info:
                sid = disc["id"]
                nome = disc["nome"]
                d = resultado_aluno.get(sid, {})
                proficiencia_val = _format_decimal(d.get("proficiency")) if d else 0.0
                nota_val = _format_decimal(d.get("grade")) if d else 0.0
                classificacao_val = d.get("classification") if d else None
                disciplinas_aluno.append({
                    "id": sid,
                    "nome": nome,
                    "proficiencia": proficiencia_val,
                    "nota": nota_val,
                    "nivel_proficiencia": classificacao_val,
                })
            if disciplinas_aluno:
                proficiencia_media_aluno = sum(d["proficiencia"] for d in disciplinas_aluno) / len(disciplinas_aluno)
                nota_media = sum(d["nota"] for d in disciplinas_aluno) / len(disciplinas_aluno)
                classificacao_principal = _nivel_proficiencia_geral(proficiencia_media_aluno, course_name)
            else:
                proficiencia_media_aluno = 0.0
                nota_media = 0.0
                classificacao_principal = None

            alunos_lista.append({
                "id": str(user.id),
                "nome_completo": (user.name or student.name or "").strip() or "—",
                "disciplinas": disciplinas_aluno,
                "proficiencia_media": _format_decimal(proficiencia_media_aluno),
                "nota": _format_decimal(nota_media),
                "nivel_proficiencia": classificacao_principal,
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
                "total_receberam_formulario": total_receberam_formulario,
                "total_alunos_questionario": total_alunos_questionario,
                "total_nao_responderam": total_nao_responderam,
                "porcentagem_participacao": porcentagem_participacao,
                "porcentagem_nao_responderam": porcentagem_nao_responderam,
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
    def _empty_report(
        form: Form,
        test: Test,
        avaliacao_id: str,
        filters: Dict[str, Any],
        total_receberam_formulario: int = 0,
        total_nao_responderam: int = 0,
        porcentagem_participacao: float = 0.0,
        porcentagem_nao_responderam: float = 0.0,
    ) -> Dict[str, Any]:
        disciplinas_info, _ = _disciplinas_e_proficiencia_por_aluno(avaliacao_id, test, [])
        return {
            "formId": form.id,
            "formTitle": form.title,
            "avaliacaoId": test.id,
            "avaliacaoTitulo": test.title,
            "filtros": filters,
            "resumo": {
                "total_receberam_formulario": total_receberam_formulario,
                "total_alunos_questionario": 0,
                "total_nao_responderam": total_nao_responderam,
                "porcentagem_participacao": porcentagem_participacao,
                "porcentagem_nao_responderam": porcentagem_nao_responderam,
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
            "disciplinas_avaliacao": disciplinas_info,
            "alunos": {"data": [], "pagination": {"page": 1, "limit": 50, "total": 0, "totalPages": 0}},
        }
