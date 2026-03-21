# -*- coding: utf-8 -*-
"""
Listagem e filtros de cartão-resposta em evaluation-results (Acertos e níveis / fluxos de relatório).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from flask import jsonify, request
from sqlalchemy import cast, String

from sqlalchemy.orm import joinedload

from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.city import City
from app.models.manager import Manager
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.teacher import Teacher
from app.models.teacherClass import TeacherClass
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path
from app.report_analysis.answer_sheet_report_builder import _question_skills_map_from_gabarito

REPORT_ENTITY_ANSWER_SHEET = "answer_sheet"


def is_answer_sheet_report_entity() -> bool:
    return (request.args.get("report_entity_type") or "").strip().lower() == REPORT_ENTITY_ANSWER_SHEET


def base_gabarito_results_query():
    return (
        db.session.query(AnswerSheetGabarito.id, AnswerSheetGabarito.title)
        .join(AnswerSheetResult, AnswerSheetResult.gabarito_id == AnswerSheetGabarito.id)
        .join(Student, AnswerSheetResult.student_id == Student.id)
        .join(Class, Student.class_id == Class.id)
        .join(School, Class._school_id == School.id)
    )


def obter_gabaritos_por_municipio(
    municipio_id: str, user: dict, permissao: dict, escola_param: str = "all"
) -> List[Dict[str, Any]]:
    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    q = base_gabarito_results_query().filter(School.city_id == city.id)

    if escola_param and escola_param.lower() != "all":
        q = q.filter(School.id == escola_param)

    if permissao["scope"] == "escola":
        if user.get("role") in ("diretor", "coordenador"):
            manager = Manager.query.filter_by(user_id=user["id"]).first()
            if manager and manager.school_id:
                q = q.filter(School.id == manager.school_id)
            else:
                return []
        elif user.get("role") == "professor":
            teacher = Teacher.query.filter_by(user_id=user["id"]).first()
            if not teacher:
                return []
            tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            cids = [tc.class_id for tc in tcs]
            if not cids:
                return []
            q = q.filter(Student.class_id.in_(cids))
        else:
            return []
    rows = q.distinct().all()
    return [{"id": str(r[0]), "titulo": r[1] or "Cartão resposta"} for r in rows]


def obter_escolas_por_gabarito(
    gabarito_id: str, municipio_id: str, user: dict, permissao: dict
) -> List[Dict[str, Any]]:
    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    q = (
        School.query.with_entities(School.id, School.name)
        .join(Class, School.id == cast(Class.school_id, String))
        .join(Student, Class.id == Student.class_id)
        .join(AnswerSheetResult, Student.id == AnswerSheetResult.student_id)
        .filter(AnswerSheetResult.gabarito_id == gabarito_id)
        .filter(School.city_id == city.id)
    )
    if permissao["scope"] == "escola":
        if user.get("role") in ("diretor", "coordenador"):
            manager = Manager.query.filter_by(user_id=user["id"]).first()
            if manager and manager.school_id:
                q = q.filter(School.id == manager.school_id)
            else:
                return []
        elif user.get("role") == "professor":
            teacher = Teacher.query.filter_by(user_id=user["id"]).first()
            if not teacher:
                return []
            tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            cids = [tc.class_id for tc in tcs]
            if not cids:
                return []
            q = q.filter(Class.id.in_(cids))
    escolas = q.distinct().all()
    return [{"id": str(e[0]), "nome": e[1]} for e in escolas]


def obter_series_por_gabarito_escola(
    gabarito_id: str, escola_id: str, municipio_id: str, user: dict, permissao: dict
) -> List[Dict[str, Any]]:
    from app.models.grades import Grade

    city = City.query.get(municipio_id)
    if not city:
        return []
    q = (
        Grade.query.with_entities(Grade.id, Grade.name)
        .join(Class, Grade.id == Class.grade_id)
        .join(Student, Class.id == Student.class_id)
        .join(AnswerSheetResult, Student.id == AnswerSheetResult.student_id)
        .join(School, Class._school_id == School.id)
        .filter(AnswerSheetResult.gabarito_id == gabarito_id)
        .filter(School.id == escola_id)
        .filter(School.city_id == city.id)
    )
    if permissao["scope"] == "escola" and user.get("role") == "professor":
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            return []
        tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        cids = [tc.class_id for tc in tcs]
        if not cids:
            return []
        q = q.filter(Class.id.in_(cids))
    series = q.distinct().all()
    return [{"id": str(s[0]), "name": s[1]} for s in series]


def obter_turmas_por_gabarito_escola_serie(
    gabarito_id: str,
    escola_id: str,
    serie_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
) -> List[Dict[str, Any]]:
    city = City.query.get(municipio_id)
    if not city:
        return []
    q = (
        Class.query.with_entities(Class.id, Class.name)
        .join(Student, Class.id == Student.class_id)
        .join(AnswerSheetResult, Student.id == AnswerSheetResult.student_id)
        .join(School, Class._school_id == School.id)
        .filter(AnswerSheetResult.gabarito_id == gabarito_id)
        .filter(School.id == escola_id)
        .filter(Class.grade_id == serie_id)
        .filter(School.city_id == city.id)
    )
    if permissao["scope"] == "escola" and user.get("role") == "professor":
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            return []
        tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        cids = [tc.class_id for tc in tcs]
        if not cids:
            return []
        q = q.filter(Class.id.in_(cids))
    turmas = q.distinct().all()
    return [{"id": str(t[0]), "name": t[1] or f"Turma {t[0]}"} for t in turmas]


def results_for_listing_filters(
    gabarito_id: str,
    municipio_id: str,
    escola: Optional[str],
    serie: Optional[str],
    turma: Optional[str],
) -> List[AnswerSheetResult]:
    q = (
        AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
        .join(Student, AnswerSheetResult.student_id == Student.id)
        .join(Class, Student.class_id == Class.id)
        .join(School, Class._school_id == School.id)
        .options(joinedload(AnswerSheetResult.student))
    )
    q = q.filter(School.city_id == municipio_id)
    if escola and escola.lower() != "all":
        q = q.filter(School.id == escola)
    if serie and serie.lower() != "all":
        q = q.filter(Class.grade_id == serie)
    if turma and turma.lower() != "all":
        q = q.filter(Class.id == turma)
    return q.all()


def listar_avaliacoes_answer_sheet_response(
    *,
    estado: str,
    municipio: str,
    escola: str,
    serie: str,
    turma: str,
    avaliacao: str,
    page: int,
    per_page: int,
    user: dict,
    permissao: dict,
    scope_info: dict,
    city_data,
) -> Any:
    """Resposta JSON para GET /evaluation-results/avaliacoes com report_entity_type=answer_sheet."""
    nivel = scope_info.get("nivel_granularidade") or "municipio"
    escola_param = request.args.get("escola", "all")

    opcoes: Dict[str, Any] = {"avaliacoes": [], "escolas": [], "series": [], "turmas": []}
    if nivel in ("estado", "municipio", "escola"):
        opcoes["avaliacoes"] = obter_gabaritos_por_municipio(municipio, user, permissao, escola_param)
    if nivel in ("estado", "municipio", "avaliacao", "escola") and avaliacao and avaliacao.lower() != "all":
        opcoes["escolas"] = obter_escolas_por_gabarito(avaliacao, municipio, user, permissao)
    if (
        nivel in ("estado", "municipio", "avaliacao", "escola")
        and avaliacao
        and avaliacao.lower() != "all"
        and escola
        and escola.lower() != "all"
    ):
        opcoes["series"] = obter_series_por_gabarito_escola(avaliacao, escola, municipio, user, permissao)
    if (
        avaliacao
        and avaliacao.lower() != "all"
        and escola
        and escola.lower() != "all"
        and serie
        and serie.lower() != "all"
    ):
        opcoes["turmas"] = obter_turmas_por_gabarito_escola_serie(
            avaliacao, escola, serie, municipio, user, permissao
        )

    if not avaliacao or avaliacao.lower() == "all":
        return jsonify(
            {
                "nivel_granularidade": nivel,
                "filtros_aplicados": {
                    "estado": estado,
                    "municipio": municipio,
                    "escola": escola,
                    "serie": serie,
                    "turma": turma,
                    "avaliacao": avaliacao,
                    "report_entity_type": REPORT_ENTITY_ANSWER_SHEET,
                },
                "estatisticas_gerais": {
                    "tipo": nivel,
                    "nome": city_data.name if city_data else "",
                    "total_avaliacoes": len(opcoes["avaliacoes"]),
                    "report_entity_type": REPORT_ENTITY_ANSWER_SHEET,
                },
                "resultados_por_disciplina": [],
                "resultados_detalhados": {
                    "avaliacoes": [],
                    "paginacao": {
                        "page": page,
                        "per_page": per_page,
                        "total": 0,
                        "total_pages": 0,
                    },
                },
                "tabela_detalhada": {},
                "ranking": [],
                "opcoes_proximos_filtros": opcoes,
            }
        ), 200

    gab = AnswerSheetGabarito.query.get(avaliacao)
    if not gab:
        return jsonify({"error": "Gabarito não encontrado"}), 404

    results = results_for_listing_filters(avaliacao, municipio, escola, serie, turma)
    if permissao["scope"] == "escola" and user.get("role") == "professor":
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if teacher:
            tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            cids = {tc.class_id for tc in tcs}
            results = [r for r in results if r.student and r.student.class_id in cids]

    n = len(results)
    grades = [float(r.grade or 0) for r in results]
    profs = [float(r.proficiency) for r in results if r.proficiency is not None]
    dist = defaultdict(int)
    for r in results:
        cl = (r.classification or "—").strip()
        dist[cl] += 1

    estatisticas = {
        "tipo": nivel,
        "nome": city_data.name if city_data else "",
        "municipio": city_data.name if city_data else "",
        "total_alunos": n,
        "alunos_participantes": n,
        "media_nota_geral": round_to_two_decimals(sum(grades) / len(grades)) if grades else 0.0,
        "media_proficiencia_geral": round_to_two_decimals(sum(profs) / len(profs)) if profs else 0.0,
        "distribuicao_classificacao_geral": dict(dist),
        "report_entity_type": REPORT_ENTITY_ANSWER_SHEET,
    }

    tabela = {
        "disciplinas": [
            {
                "nome": "GERAL",
                "alunos": [
                    {
                        "aluno_id": r.student_id,
                        "nome": r.student.name if r.student else "",
                        "nota": r.grade,
                        "proficiencia": r.proficiency,
                        "classificacao": r.classification,
                    }
                    for r in results
                ],
            }
        ]
    }
    ranking = sorted(
        [
            {
                "aluno_id": r.student_id,
                "nome": r.student.name if r.student else "",
                "nota": r.grade,
                "proficiencia": r.proficiency,
            }
            for r in results
        ],
        key=lambda x: (x["nota"] or 0),
        reverse=True,
    )

    detalhe_row = {
        "id": str(gab.id),
        "titulo": gab.title or "Cartão resposta",
        "total_alunos": n,
        "media_nota": estatisticas["media_nota_geral"],
        "report_entity_type": REPORT_ENTITY_ANSWER_SHEET,
    }

    return jsonify(
        {
            "nivel_granularidade": nivel,
            "filtros_aplicados": {
                "estado": estado,
                "municipio": municipio,
                "escola": escola,
                "serie": serie,
                "turma": turma,
                "avaliacao": avaliacao,
                "report_entity_type": REPORT_ENTITY_ANSWER_SHEET,
            },
            "estatisticas_gerais": estatisticas,
            "resultados_por_disciplina": [],
            "resultados_detalhados": {
                "avaliacoes": [detalhe_row],
                "paginacao": {"page": page, "per_page": per_page, "total": 1, "total_pages": 1},
            },
            "tabela_detalhada": tabela,
            "ranking": ranking,
            "opcoes_proximos_filtros": opcoes,
        }
    ), 200


def resolve_city_id_for_answer_sheet_detail(user: dict, permissao: dict) -> Tuple[Optional[str], Optional[Tuple[Any, int]]]:
    """
    city_id efetivo para definir search_path em endpoints de detalhe (gabarito).
    Retorna (city_id, None) ou (None, (jsonify(...), status_code)).
    """
    raw = request.args.get("city_id") or request.args.get("municipio")
    raw = str(raw).strip() if raw else None
    user_city = str(user.get("city_id") or user.get("tenant_id") or "").strip() or None

    if permissao.get("scope") == "all":
        if not raw:
            return None, (
                jsonify(
                    {
                        "error": "Para cartão-resposta neste endpoint, informe city_id ou municipio na URL.",
                    }
                ),
                400,
            )
        return raw, None

    if permissao.get("scope") == "municipio":
        if not user_city:
            return None, (jsonify({"error": "Tecadm sem município vinculado"}), 403)
        if raw and raw != user_city:
            return None, (jsonify({"error": "Acesso negado a este município"}), 403)
        return user_city, None

    if not user_city:
        return None, (jsonify({"error": "Usuário sem município vinculado"}), 400)
    if raw and raw != user_city:
        return None, (jsonify({"error": "Acesso negado a este município"}), 403)
    return user_city, None


def user_can_access_gabarito(user: dict, permissao: dict, gab: AnswerSheetGabarito) -> bool:
    from app.permissions.roles import Roles

    role = Roles.normalize(user.get("role", ""))
    if permissao.get("scope") == "all":
        return True
    if permissao.get("scope") == "municipio":
        return True

    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        manager = Manager.query.filter_by(user_id=user["id"]).first()
        if not manager or not manager.school_id:
            return False
        return (
            AnswerSheetResult.query.filter_by(gabarito_id=gab.id)
            .join(Student, AnswerSheetResult.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .filter(Class._school_id == manager.school_id)
            .first()
            is not None
        )

    if role == Roles.PROFESSOR:
        if str(gab.created_by or "") == str(user.get("id") or ""):
            return True
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            return False
        tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        cids = [tc.class_id for tc in tcs]
        if not cids:
            return False
        return (
            AnswerSheetResult.query.filter_by(gabarito_id=gab.id)
            .join(Student, AnswerSheetResult.student_id == Student.id)
            .filter(Student.class_id.in_(cids))
            .first()
            is not None
        )

    return False


def answer_sheet_results_for_detail(
    user: dict, permissao: dict, gab: AnswerSheetGabarito
) -> List[AnswerSheetResult]:
    from app.permissions.roles import Roles

    role = Roles.normalize(user.get("role", ""))
    q = AnswerSheetResult.query.filter_by(gabarito_id=gab.id).options(
        joinedload(AnswerSheetResult.student)
    )

    if permissao.get("scope") in ("all", "municipio"):
        return q.all()

    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        manager = Manager.query.filter_by(user_id=user["id"]).first()
        if not manager or not manager.school_id:
            return []
        return (
            q.join(Student, AnswerSheetResult.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .filter(Class._school_id == manager.school_id)
            .all()
        )

    if role == Roles.PROFESSOR:
        if str(gab.created_by or "") == str(user.get("id") or ""):
            return q.all()
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            return []
        tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        cids = [tc.class_id for tc in tcs]
        if not cids:
            return []
        return (
            q.join(Student, AnswerSheetResult.student_id == Student.id)
            .filter(Student.class_id.in_(cids))
            .all()
        )

    return []


def stats_from_answer_sheet_results(results: List[AnswerSheetResult]) -> Dict[str, Any]:
    empty_dist = {
        "abaixo_do_basico": 0,
        "basico": 0,
        "adequado": 0,
        "avancado": 0,
    }
    if not results:
        return {
            "total_alunos": 0,
            "alunos_participantes": 0,
            "alunos_pendentes": 0,
            "alunos_ausentes": 0,
            "media_nota": 0.0,
            "media_proficiencia": 0.0,
            "distribuicao_classificacao": empty_dist.copy(),
        }

    n = len(results)
    media_nota = sum(float(r.grade or 0) for r in results) / n
    profs = [float(r.proficiency) for r in results if r.proficiency is not None]
    media_prof = sum(profs) / len(profs) if profs else 0.0

    dist = empty_dist.copy()
    for r in results:
        cl = (r.classification or "").lower()
        if "abaixo" in cl:
            dist["abaixo_do_basico"] += 1
        elif "básico" in cl or "basico" in cl:
            dist["basico"] += 1
        elif "adequado" in cl:
            dist["adequado"] += 1
        elif "avançado" in cl or "avancado" in cl:
            dist["avancado"] += 1

    return {
        "total_alunos": n,
        "alunos_participantes": n,
        "alunos_pendentes": 0,
        "alunos_ausentes": 0,
        "media_nota": round(media_nota, 2),
        "media_proficiencia": round(media_prof, 2),
        "distribuicao_classificacao": dist,
    }


def fetch_answer_sheet_gabarito_for_detail(
    user: dict, permissao: dict, gabarito_id: str
) -> Tuple[Optional[AnswerSheetGabarito], Optional[List[AnswerSheetResult]], Optional[Tuple[Any, int]]]:
    """
    Resolve city/schema, carrega gabarito e verifica acesso.
    Retorna (gabarito, results, None) ou (None, None, (Response Flask, status)).
    """
    if not permissao.get("permitted"):
        return None, None, (
            jsonify({"error": permissao.get("error", "Acesso negado")}),
            403,
        )

    city_id, err = resolve_city_id_for_answer_sheet_detail(user, permissao)
    if err:
        return None, None, err

    set_search_path(city_id_to_schema_name(city_id))
    gab = AnswerSheetGabarito.query.get(gabarito_id)
    if not gab:
        return None, None, (jsonify({"error": "Gabarito não encontrado"}), 404)

    if not user_can_access_gabarito(user, permissao, gab):
        return None, None, (jsonify({"error": "Acesso negado"}), 403)

    results = answer_sheet_results_for_detail(user, permissao, gab)
    return gab, results, None


def build_answer_sheet_evaluation_by_id_json(
    gab: AnswerSheetGabarito, results: List[AnswerSheetResult]
) -> Dict[str, Any]:
    from app.models.test import Test

    stats = stats_from_answer_sheet_results(results)
    disciplina = "N/A"
    if gab.test_id:
        t = (
            Test.query.options(joinedload(Test.subject_rel))
            .filter(Test.id == gab.test_id)
            .first()
        )
        if t and t.subject_rel:
            disciplina = t.subject_rel.name
        elif t:
            disciplina = t.title or "N/A"

    return {
        "id": gab.id,
        "titulo": gab.title or "Cartão resposta",
        "disciplina": disciplina,
        "curso": gab.institution or gab.grade_name or "N/A",
        "serie": gab.grade_name or "N/A",
        "escola": gab.school_name or "N/A",
        "municipio": gab.municipality or "N/A",
        "data_aplicacao": gab.created_at.isoformat() if gab.created_at else None,
        "data_correcao": gab.template_generated_at.isoformat()
        if gab.template_generated_at
        else None,
        "status": "concluida",
        "report_entity_type": REPORT_ENTITY_ANSWER_SHEET,
        **stats,
    }


def _ordered_question_numbers_from_gabarito(gab: AnswerSheetGabarito) -> List[int]:
    cfg = gab.blocks_config or {}
    topo = cfg.get("topology") or {}
    blocks = topo.get("blocks") or []
    nums: List[int] = []
    seen: set = set()
    for block in blocks:
        for q in block.get("questions") or []:
            qn = q.get("q") or q.get("numero")
            if qn is None:
                continue
            try:
                n = int(qn)
            except (TypeError, ValueError):
                continue
            if n not in seen:
                seen.add(n)
                nums.append(n)
    if nums:
        return nums
    correct_json = gab.correct_answers or {}
    if isinstance(correct_json, str):
        import json

        correct_json = json.loads(correct_json) or {}
    keys: List[int] = []
    for k in (correct_json or {}).keys():
        try:
            keys.append(int(k))
        except (TypeError, ValueError):
            continue
    keys.sort()
    if keys:
        return keys
    nq = gab.num_questions or 0
    return list(range(1, nq + 1)) if nq > 0 else []


def build_answer_sheet_relatorio_detalhado_json(
    gab: AnswerSheetGabarito, results: List[AnswerSheetResult]
) -> Dict[str, Any]:
    """
    Mesmo formato de GET /relatorio-detalhado (Test), para cartão-resposta (gabarito).
    """
    from uuid import UUID

    from app.models.skill import Skill
    from app.models.test import Test

    q_skills = _question_skills_map_from_gabarito(gab)
    correct_json = gab.correct_answers or {}
    if isinstance(correct_json, str):
        import json

        correct_json = json.loads(correct_json) or {}
    gab_map: Dict[int, str] = {}
    for k, v in (correct_json or {}).items():
        try:
            gab_map[int(k)] = str(v).upper() if v else ""
        except (TypeError, ValueError):
            continue

    question_nums = _ordered_question_numbers_from_gabarito(gab)
    if not question_nums:
        question_nums = sorted(gab_map.keys())

    disciplina = "N/A"
    if gab.test_id:
        t = (
            Test.query.options(joinedload(Test.subject_rel))
            .filter(Test.id == gab.test_id)
            .first()
        )
        if t and t.subject_rel:
            disciplina = t.subject_rel.name
        elif t:
            disciplina = t.title or "N/A"

    skill_ids: List[str] = []
    for qn in question_nums:
        for sid in q_skills.get(qn) or []:
            if sid:
                skill_ids.append(str(sid).strip())
    unique_skill_ids = list(dict.fromkeys(skill_ids))
    code_by_id: Dict[str, str] = {}
    if unique_skill_ids:
        uuids = []
        for raw in unique_skill_ids:
            try:
                uuids.append(UUID(str(raw)))
            except ValueError:
                continue
        if uuids:
            rows = Skill.query.filter(Skill.id.in_(uuids)).all()
            code_by_id = {str(sk.id): (sk.code or "N/A") for sk in rows}

    questoes_data: List[Dict[str, Any]] = []
    for i, qn in enumerate(question_nums, 1):
        ca = gab_map.get(qn)
        total_respostas = len(results)
        acertos = 0
        if ca is not None and total_respostas > 0:
            for res in results:
                det = res.detected_answers or {}
                st = det.get(str(qn), det.get(qn))
                st = str(st).upper() if st else ""
                if st and st == ca:
                    acertos += 1
        porcentagem_acertos = (acertos / total_respostas * 100) if total_respostas > 0 else 0.0

        sids = q_skills.get(qn) or []
        first_code = "N/A"
        if sids:
            first_code = code_by_id.get(str(sids[0]).strip(), "N/A")

        qid = f"{gab.id}-q{qn}"
        questoes_data.append(
            {
                "id": qid,
                "numero": i,
                "texto": f"Questão {qn}",
                "habilidade": first_code,
                "codigo_habilidade": first_code,
                "tipo": "multiple_choice",
                "dificuldade": "Médio",
                "porcentagem_acertos": round_to_two_decimals(porcentagem_acertos),
                "porcentagem_erros": round_to_two_decimals(100 - porcentagem_acertos),
            }
        )

    alunos_data: List[Dict[str, Any]] = []
    for res in results:
        student = res.student
        if not student:
            continue
        turma_nome = student.class_.name if student.class_ else "N/A"

        respostas: List[Dict[str, Any]] = []
        for qn in question_nums:
            ca = gab_map.get(qn)
            det = res.detected_answers or {}
            raw = det.get(str(qn), det.get(qn))
            resposta_em_branco = raw is None or (
                isinstance(raw, str) and raw.strip() == ""
            )
            st = "" if resposta_em_branco else str(raw).strip().upper()
            is_correct = bool(st) and ca is not None and st == ca
            qid = f"{gab.id}-q{qn}"
            respostas.append(
                {
                    "questao_id": qid,
                    "questao_numero": qn,
                    "resposta_correta": is_correct,
                    "resposta_em_branco": resposta_em_branco,
                    "tempo_gasto": 120,
                }
            )

        prof = res.proficiency
        alunos_data.append(
            {
                "id": student.id,
                "nome": student.name or (student.user.name if student.user else "N/A"),
                "turma": turma_nome,
                "respostas": respostas,
                "total_acertos": res.correct_answers,
                "total_erros": res.incorrect_answers,
                "total_em_branco": res.unanswered_questions,
                "nota_final": float(res.grade or 0),
                "proficiencia": round_to_two_decimals(float(prof)) if prof is not None else 0.0,
                "classificacao": res.classification,
                "status": "concluida",
            }
        )

    avaliacao_data = {
        "id": gab.id,
        "titulo": gab.title or "Cartão resposta",
        "disciplina": disciplina,
        "total_questoes": len(question_nums),
        "report_entity_type": REPORT_ENTITY_ANSWER_SHEET,
    }

    return {
        "avaliacao": avaliacao_data,
        "questoes": questoes_data,
        "alunos": alunos_data,
    }


def collect_skill_ids_from_gabarito_topology(gab: AnswerSheetGabarito) -> List[str]:
    m = _question_skills_map_from_gabarito(gab)
    ids: set = set()
    for lst in m.values():
        for sid in lst:
            if sid:
                ids.add(str(sid).strip())
    return sorted(ids)
