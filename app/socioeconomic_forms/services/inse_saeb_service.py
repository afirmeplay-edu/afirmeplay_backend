# -*- coding: utf-8 -*-
"""
Serviço para o relatório INSE x Avaliação: cruza respostas do formulário socioeconômico
com resultados da avaliação (proficiência por disciplina e média).
"""

from app import db
from app.socioeconomic_forms.models import Form
from app.socioeconomic_forms.services.results_service import ResultsService
from app.socioeconomic_forms.constants.inse_normalizer import normalizar_respostas
from app.socioeconomic_forms.constants.inse_scoring import (
    calcular_inse_canonico,
    pontuacao_para_nivel_inse,
    NIVEIS_INSE_DESCRICOES,
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
import unicodedata

logger = logging.getLogger(__name__)


def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _race_group(value: Optional[str]) -> str:
    """
    Agrupamento racial para filtros/visões consolidadas.
    """
    v = (_normalize_str(value) or "").lower()
    if v == "branca":
        return "Branca"
    if v in ("preta", "parda"):
        return "PretaParda"
    if v in ("não quero declarar", "nao quero declarar", "não declarar", "nao declarar"):
        return "NaoDeclarada"
    if v:
        return "Outras"
    return "NaoInformada"


def _normalize_text_key(value: Any) -> str:
    s = str(value or "").strip().lower()
    if not s:
        return ""
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
    return " ".join(s.split())


def _resolver_question_id_raca(form: Form) -> str:
    """
    Resolve dinamicamente o question_id de raça/cor no formulário.
    Fallback para q5 (templates atuais) e q4 (templates legados).
    """
    try:
        for question in getattr(form, "questions", []) or []:
            text_norm = _normalize_text_key(getattr(question, "text", ""))
            if ("cor" in text_norm and "raca" in text_norm) or ("cor ou raca" in text_norm):
                qid = getattr(question, "question_id", None)
                if qid:
                    return str(qid)
    except Exception:
        pass
    return "q5"


def _extrair_raca_resposta(responses_data: Dict[str, Any], race_question_id: str) -> Optional[str]:
    raw = _normalize_str((responses_data or {}).get(race_question_id))
    if raw:
        return raw
    # Fallback para variações conhecidas de templates.
    for k in ("q5", "q4"):
        raw_fallback = _normalize_str((responses_data or {}).get(k))
        if raw_fallback:
            return raw_fallback
    return None


def _calcular_inse_de_respostas(
    responses: Dict[str, Any],
) -> Tuple[float, bool, Optional[int], str]:
    """
    Normaliza respostas e calcula INSE (pontos e nível).
    Retorna (inse, ok, nivel_num, nivel_label).
    """
    normalized = normalizar_respostas(responses or {})
    inse, ok, _theta = calcular_inse_canonico(normalized)
    nivel_num, nivel_label = pontuacao_para_nivel_inse(inse)
    return inse, ok, nivel_num, nivel_label


def _format_decimal(val: Optional[float]) -> float:
    if val is None:
        return 0.0
    return round(float(val), 2)


def _empty_comparativos() -> Dict[str, Any]:
    return {
        "comparativo_por_raca_cor": [],
        "comparativo_por_inse": [
            {
                "inse_nivel": i,
                "label": NIVEIS_INSE_LABELS.get(i, f"Nível {i}"),
                "quantidade": 0,
                "quantidade_com_resultado": 0,
                "media_proficiencia": None,
                "media_nota": None,
            }
            for i in range(1, 9)
        ],
        "comparativo_raca_x_inse": [],
        "destaques": {
            "maior_media": None,
            "menor_media": None,
            "maior_gap": None,
        },
    }


def _build_comparativos(metricas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Agrega médias de desempenho por raça/cor, por nível INSE e no cruzamento.
    Cálculo exclusivo do backend — o frontend só exibe.
    Alunos sem resultado de avaliação entram em `quantidade`, mas não na média.
    """
    by_raca: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "quantidade": 0,
            "quantidade_com_resultado": 0,
            "soma_prof": 0.0,
            "soma_nota": 0.0,
        }
    )
    by_inse: Dict[int, Dict[str, Any]] = {
        i: {
            "quantidade": 0,
            "quantidade_com_resultado": 0,
            "soma_prof": 0.0,
            "soma_nota": 0.0,
        }
        for i in range(1, 9)
    }
    by_cruz: Dict[Tuple[str, int], Dict[str, Any]] = defaultdict(
        lambda: {
            "quantidade": 0,
            "quantidade_com_resultado": 0,
            "soma_prof": 0.0,
            "soma_nota": 0.0,
        }
    )

    for m in metricas:
        raca = m.get("raca_cor") or "NaoInformada"
        inse_nivel = m.get("inse_nivel")
        media_prof = m.get("media_proficiencia")
        media_nota = m.get("media_nota")
        tem_resultado = media_prof is not None

        by_raca[raca]["quantidade"] += 1
        if tem_resultado:
            by_raca[raca]["quantidade_com_resultado"] += 1
            by_raca[raca]["soma_prof"] += float(media_prof)
            if media_nota is not None:
                by_raca[raca]["soma_nota"] += float(media_nota)

        if inse_nivel is not None and 1 <= int(inse_nivel) <= 8:
            nivel = int(inse_nivel)
            by_inse[nivel]["quantidade"] += 1
            if tem_resultado:
                by_inse[nivel]["quantidade_com_resultado"] += 1
                by_inse[nivel]["soma_prof"] += float(media_prof)
                if media_nota is not None:
                    by_inse[nivel]["soma_nota"] += float(media_nota)

            cruz_key = (raca, nivel)
            by_cruz[cruz_key]["quantidade"] += 1
            if tem_resultado:
                by_cruz[cruz_key]["quantidade_com_resultado"] += 1
                by_cruz[cruz_key]["soma_prof"] += float(media_prof)
                if media_nota is not None:
                    by_cruz[cruz_key]["soma_nota"] += float(media_nota)

    def _medias(bucket: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        n = bucket["quantidade_com_resultado"]
        if n <= 0:
            return None, None
        media_p = _format_decimal(bucket["soma_prof"] / n)
        media_n = _format_decimal(bucket["soma_nota"] / n) if n else None
        return media_p, media_n

    comparativo_por_raca_cor = []
    for raca, bucket in sorted(by_raca.items(), key=lambda x: x[0].lower()):
        media_p, media_n = _medias(bucket)
        comparativo_por_raca_cor.append({
            "raca_cor": raca,
            "raca_cor_grupo": _race_group(None if raca == "NaoInformada" else raca),
            "quantidade": bucket["quantidade"],
            "quantidade_com_resultado": bucket["quantidade_com_resultado"],
            "media_proficiencia": media_p,
            "media_nota": media_n,
        })

    comparativo_por_inse = []
    for i in range(1, 9):
        bucket = by_inse[i]
        media_p, media_n = _medias(bucket)
        comparativo_por_inse.append({
            "inse_nivel": i,
            "label": NIVEIS_INSE_LABELS.get(i, f"Nível {i}"),
            "quantidade": bucket["quantidade"],
            "quantidade_com_resultado": bucket["quantidade_com_resultado"],
            "media_proficiencia": media_p,
            "media_nota": media_n,
        })

    comparativo_raca_x_inse = []
    for (raca, nivel), bucket in sorted(by_cruz.items(), key=lambda x: (x[0][0].lower(), x[0][1])):
        media_p, media_n = _medias(bucket)
        comparativo_raca_x_inse.append({
            "raca_cor": raca,
            "raca_cor_grupo": _race_group(None if raca == "NaoInformada" else raca),
            "inse_nivel": nivel,
            "inse_nivel_label": NIVEIS_INSE_LABELS.get(nivel, f"Nível {nivel}"),
            "quantidade": bucket["quantidade"],
            "quantidade_com_resultado": bucket["quantidade_com_resultado"],
            "media_proficiencia": media_p,
            "media_nota": media_n,
        })

    # Destaques: grupos de raça/cor com ao menos 1 resultado
    candidatos = [
        item for item in comparativo_por_raca_cor
        if item["media_proficiencia"] is not None and item["quantidade_com_resultado"] > 0
    ]
    maior = max(candidatos, key=lambda x: x["media_proficiencia"]) if candidatos else None
    menor = min(candidatos, key=lambda x: x["media_proficiencia"]) if candidatos else None
    maior_gap = None
    if maior and menor and maior is not menor:
        maior_gap = _format_decimal(maior["media_proficiencia"] - menor["media_proficiencia"])

    destaques = {
        "maior_media": (
            {
                "dimensao": "raca_cor",
                "grupo": maior["raca_cor"],
                "valor": maior["media_proficiencia"],
                "quantidade_com_resultado": maior["quantidade_com_resultado"],
            }
            if maior else None
        ),
        "menor_media": (
            {
                "dimensao": "raca_cor",
                "grupo": menor["raca_cor"],
                "valor": menor["media_proficiencia"],
                "quantidade_com_resultado": menor["quantidade_com_resultado"],
            }
            if menor else None
        ),
        "maior_gap": maior_gap,
    }

    return {
        "comparativo_por_raca_cor": comparativo_por_raca_cor,
        "comparativo_por_inse": comparativo_por_inse,
        "comparativo_raca_x_inse": comparativo_raca_x_inse,
        "destaques": destaques,
    }


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


class InseAvaliacaoService:
    """Serviço do relatório INSE x Avaliação."""

    @staticmethod
    def gerar_relatorio(
        form_id: str,
        filters: Dict[str, Any],
        avaliacao_id: str,
        page: int = 1,
        limit: int = 50,
        raca_cor: Optional[str] = None,
        raca_cor_grupo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gera o relatório completo INSE x Avaliação.

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
        race_question_id = _resolver_question_id_raca(form)

        test = Test.query.get(avaliacao_id)
        if not test:
            raise ValueError("Avaliação não encontrada")

        # 0) Total que receberam o formulário no escopo (form_recipients + mesmo escopo dos filtros)
        total_receberam_formulario = ResultsService.count_recipients_in_scope(form_id, filters)

        # 1) Alunos do escopo (responderam ao formulário e passaram nos filtros)
        query = ResultsService._build_base_query(form_id, filters)
        results_raw = query.all()

        # Opções de filtro por raça/cor com base no escopo antes do filtro de raça.
        opcoes_raca_cor = defaultdict(int)
        opcoes_raca_cor_grupo = defaultdict(int)
        raca_por_student = {}
        for row in results_raw:
            response, user, student, school, grade, class_, city = row
            responses_data = response.responses or {}
            race_raw = _extrair_raca_resposta(responses_data, race_question_id)
            raca_por_student[student.id] = race_raw
            opcoes_raca_cor[race_raw or "NaoInformada"] += 1
            opcoes_raca_cor_grupo[_race_group(race_raw)] += 1

        # Filtro por raça/cor (backend), aplicado antes de qualquer cálculo/paginação.
        target_raca = _normalize_str(raca_cor)
        target_raca_grupo = _normalize_str(raca_cor_grupo)
        if target_raca or target_raca_grupo:
            results = []
            for row in results_raw:
                response, user, student, school, grade, class_, city = row
                race_raw = raca_por_student.get(student.id)
                group = _race_group(race_raw)
                if target_raca and (race_raw or "") != target_raca:
                    continue
                if target_raca_grupo and group != target_raca_grupo:
                    continue
                results.append(row)
        else:
            results = results_raw

        total_alunos_questionario = len(results)

        total_nao_responderam = max(0, total_receberam_formulario - total_alunos_questionario)
        porcentagem_participacao = round(
            (total_alunos_questionario / total_receberam_formulario * 100), 2
        ) if total_receberam_formulario else 0
        porcentagem_nao_responderam = round(
            (total_nao_responderam / total_receberam_formulario * 100), 2
        ) if total_receberam_formulario else 0

        if total_alunos_questionario == 0:
            empty = InseAvaliacaoService._empty_report(
                form, test, avaliacao_id, filters,
                total_receberam_formulario=total_receberam_formulario,
                total_nao_responderam=total_nao_responderam,
                porcentagem_participacao=porcentagem_participacao,
                porcentagem_nao_responderam=porcentagem_nao_responderam,
                raca_cor=target_raca,
                raca_cor_grupo=target_raca_grupo,
            )
            # Comparativos no escopo completo (antes do filtro de raça), mesmo sem linhas filtradas.
            if results_raw:
                student_ids_full = [row[2].id for row in results_raw]
                inse_full = {}
                for row in results_raw:
                    response, _user, student, *_rest = row
                    inse, ok, nivel_num, nivel_label = _calcular_inse_de_respostas(response.responses or {})
                    inse_full[student.id] = {"valor": inse, "nivel": nivel_num, "nivel_label": nivel_label, "ok": ok}
                disciplinas_info_full, resultado_full = _disciplinas_e_proficiencia_por_aluno(
                    avaliacao_id, test, student_ids_full
                )
                metricas_full = []
                for row in results_raw:
                    _response, _user, student, *_rest = row
                    disc_data = resultado_full.get(student.id, {})
                    media_prof = None
                    media_nota = None
                    if disc_data:
                        profs = [d["proficiency"] for d in disc_data.values()]
                        grades = [d["grade"] for d in disc_data.values()]
                        media_prof = sum(profs) / len(profs) if profs else None
                        media_nota = sum(grades) / len(grades) if grades else None
                    race_raw = raca_por_student.get(student.id)
                    inse_data = inse_full.get(student.id, {})
                    metricas_full.append({
                        "raca_cor": race_raw or "NaoInformada",
                        "inse_nivel": inse_data.get("nivel"),
                        "media_proficiencia": media_prof,
                        "media_nota": media_nota,
                    })
                empty["disciplinas_avaliacao"] = disciplinas_info_full
                empty.update(_build_comparativos(metricas_full))
            return empty

        # 2) INSE + proficiência no escopo COMPLETO (antes do filtro de raça)
        #    → base dos comparativos. O filtro de raça afeta só resumo/distribuições/tabela.
        student_ids_full = [row[2].id for row in results_raw]
        inse_por_aluno = {}
        for row in results_raw:
            response, _user, student, *_rest = row
            inse, ok, nivel_num, nivel_label = _calcular_inse_de_respostas(response.responses or {})
            inse_por_aluno[student.id] = {
                "valor": inse,
                "nivel": nivel_num,
                "nivel_label": nivel_label,
                "ok": ok,
            }

        disciplinas_info, resultado_por_aluno_por_disciplina = _disciplinas_e_proficiencia_por_aluno(
            avaliacao_id, test, student_ids_full
        )
        course_name = _course_name_for_test(test)

        metricas_full = []
        for row in results_raw:
            _response, _user, student, *_rest = row
            disc_data = resultado_por_aluno_por_disciplina.get(student.id, {})
            media_prof = None
            media_nota = None
            if disc_data:
                profs = [d["proficiency"] for d in disc_data.values()]
                grades = [d["grade"] for d in disc_data.values()]
                media_prof = sum(profs) / len(profs) if profs else None
                media_nota = sum(grades) / len(grades) if grades else None
            race_raw = raca_por_student.get(student.id)
            inse_data = inse_por_aluno.get(student.id, {})
            metricas_full.append({
                "raca_cor": race_raw or "NaoInformada",
                "inse_nivel": inse_data.get("nivel"),
                "media_proficiencia": media_prof,
                "media_nota": media_nota,
            })

        comparativos = _build_comparativos(metricas_full)

        # 3) Agregados do escopo FILTRADO (raça/cor) — resumo + distribuições
        student_ids = [row[2].id for row in results]
        distribuicao_inse = {i: {"quantidade": 0, "porcentagem": 0.0} for i in range(1, 9)}
        soma_inse = 0.0
        count_inse_valido = 0

        for sid in student_ids:
            inse_data = inse_por_aluno.get(sid, {})
            nivel_num = inse_data.get("nivel")
            if nivel_num is not None:
                distribuicao_inse[nivel_num]["quantidade"] += 1
            if inse_data.get("ok") and nivel_num is not None:
                soma_inse += float(inse_data.get("valor") or 0)
                count_inse_valido += 1

        for i in range(1, 9):
            qtd = distribuicao_inse[i]["quantidade"]
            distribuicao_inse[i]["porcentagem"] = round(
                (qtd / total_alunos_questionario * 100), 2
            ) if total_alunos_questionario else 0

        inse_medio = (soma_inse / count_inse_valido) if count_inse_valido else 0.0

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

        # 4) Lista de alunos (paginada) — escopo filtrado
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
                "inse_valor": _format_decimal(inse_data.get("valor", 0)),
                "inse_nivel": inse_data.get("nivel"),
                "inse_nivel_label": inse_data.get("nivel_label", ""),
                "raca_cor": raca_por_student.get(student.id),
                "raca_cor_grupo": _race_group(raca_por_student.get(student.id)),
            })

        return {
            "formId": form.id,
            "formTitle": form.title,
            "avaliacaoId": avaliacao_id,
            "avaliacaoTitulo": test.title,
            "filtros": {
                **filters,
                **({"raca_cor": target_raca} if target_raca else {}),
                **({"raca_cor_grupo": target_raca_grupo} if target_raca_grupo else {}),
            },
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
                    "descricao": NIVEIS_INSE_DESCRICOES.get(i, ""),
                    "quantidade": distribuicao_inse[i]["quantidade"],
                    "porcentagem": distribuicao_inse[i]["porcentagem"],
                }
                for i in range(1, 9)
            },
            "distribuicao_proficiencia": distribuicao_proficiencia,
            "opcoes_raca_cor": {
                "categorias": [{"valor": k, "quantidade": v} for k, v in sorted(opcoes_raca_cor.items(), key=lambda x: x[0])],
                "grupos": [{"valor": k, "quantidade": v} for k, v in sorted(opcoes_raca_cor_grupo.items(), key=lambda x: x[0])],
            },
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
            **comparativos,
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
        raca_cor: Optional[str] = None,
        raca_cor_grupo: Optional[str] = None,
    ) -> Dict[str, Any]:
        disciplinas_info, _ = _disciplinas_e_proficiencia_por_aluno(avaliacao_id, test, [])
        return {
            "formId": form.id,
            "formTitle": form.title,
            "avaliacaoId": test.id,
            "avaliacaoTitulo": test.title,
            "filtros": {
                **(filters or {}),
                **({"raca_cor": raca_cor} if raca_cor else {}),
                **({"raca_cor_grupo": raca_cor_grupo} if raca_cor_grupo else {}),
            },
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
                str(i): {
                    "nivel": i,
                    "label": NIVEIS_INSE_LABELS.get(i, ""),
                    "descricao": NIVEIS_INSE_DESCRICOES.get(i, ""),
                    "quantidade": 0,
                    "porcentagem": 0.0,
                }
                for i in range(1, 9)
            },
            "distribuicao_proficiencia": {
                "abaixo_do_basico": 0, "basico": 0, "adequado": 0, "avancado": 0,
                "abaixo_do_basico_porcentagem": 0, "basico_porcentagem": 0,
                "adequado_porcentagem": 0, "avancado_porcentagem": 0,
            },
            "opcoes_raca_cor": {"categorias": [], "grupos": []},
            "disciplinas_avaliacao": disciplinas_info,
            "alunos": {"data": [], "pagination": {"page": 1, "limit": 50, "total": 0, "totalPages": 0}},
            **_empty_comparativos(),
        }


# Compatibilidade com imports antigos
InseSaebService = InseAvaliacaoService
