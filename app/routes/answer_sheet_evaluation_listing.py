# -*- coding: utf-8 -*-
"""
Listagem e filtros de cartão-resposta em evaluation-results (Acertos e níveis / fluxos de relatório).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from flask import jsonify, request
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.test import Test
from app.models.city import City
from app.models.manager import Manager
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.teacher import Teacher
from app.models.teacherClass import TeacherClass
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path
from app.report_analysis.answer_sheet_report_builder import (
    _question_skills_map_from_gabarito,
    answer_sheet_total_question_count,
    get_answer_sheet_target_classes_for_report,
    ordered_question_numbers_for_gabarito,
    question_skills_map_for_answer_sheet,
)

REPORT_ENTITY_ANSWER_SHEET = "answer_sheet"


def is_answer_sheet_report_entity() -> bool:
    return (request.args.get("report_entity_type") or "").strip().lower() == REPORT_ENTITY_ANSWER_SHEET


def obter_gabaritos_por_municipio(
    municipio_id: str, user: dict, permissao: dict, escola_param: str = "all"
) -> List[Dict[str, Any]]:
    """
    Cartões-resposta do município com ou sem resultado (não exige AnswerSheetResult).
    Liga escola/turma do gabarito ou resultados já existentes ao city_id.
    """
    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    school_ids_city = [s[0] for s in db.session.query(School.id).filter(School.city_id == city.id).all()]
    if not school_ids_city:
        return []

    class_ids_in_city = db.session.query(Class.id).filter(Class._school_id.in_(school_ids_city))
    gab_ids_from_results = (
        db.session.query(AnswerSheetGabarito.id)
        .join(AnswerSheetResult, AnswerSheetResult.gabarito_id == AnswerSheetGabarito.id)
        .join(Student, AnswerSheetResult.student_id == Student.id)
        .join(Class, Student.class_id == Class.id)
        .join(School, Class._school_id == School.id)
        .filter(School.city_id == city.id)
        .distinct()
    )

    conds = [
        AnswerSheetGabarito.school_id.in_(school_ids_city),
        AnswerSheetGabarito.class_id.in_(class_ids_in_city),
        AnswerSheetGabarito.id.in_(gab_ids_from_results),
    ]
    q = AnswerSheetGabarito.query.filter(or_(*conds))
    q = q.outerjoin(Test, AnswerSheetGabarito.test_id == Test.id).filter(
        or_(
            AnswerSheetGabarito.test_id.is_(None),
            Test.evaluation_mode == "physical",
        )
    )

    if escola_param and escola_param.lower() != "all":
        eid = escola_param
        class_ids_escola = db.session.query(Class.id).filter(Class._school_id == eid)
        q = q.filter(
            or_(
                AnswerSheetGabarito.school_id == eid,
                AnswerSheetGabarito.class_id.in_(class_ids_escola),
                AnswerSheetGabarito.id.in_(
                    db.session.query(AnswerSheetGabarito.id)
                    .join(AnswerSheetResult, AnswerSheetResult.gabarito_id == AnswerSheetGabarito.id)
                    .join(Student, AnswerSheetResult.student_id == Student.id)
                    .join(Class, Student.class_id == Class.id)
                    .filter(Class._school_id == eid)
                    .distinct()
                ),
            )
        )

    if permissao["scope"] == "escola":
        if user.get("role") in ("diretor", "coordenador"):
            manager = Manager.query.filter_by(user_id=user["id"]).first()
            if manager and manager.school_id:
                mid = manager.school_id
                class_ids_mgr = db.session.query(Class.id).filter(Class._school_id == mid)
                q = q.filter(
                    or_(
                        AnswerSheetGabarito.school_id == mid,
                        AnswerSheetGabarito.class_id.in_(class_ids_mgr),
                        AnswerSheetGabarito.id.in_(
                            db.session.query(AnswerSheetGabarito.id)
                            .join(AnswerSheetResult, AnswerSheetResult.gabarito_id == AnswerSheetGabarito.id)
                            .join(Student, AnswerSheetResult.student_id == Student.id)
                            .join(Class, Student.class_id == Class.id)
                            .filter(Class._school_id == mid)
                            .distinct()
                        ),
                    )
                )
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
            school_ids_prof = [
                r[0]
                for r in db.session.query(Class._school_id)
                .filter(Class.id.in_(cids))
                .distinct()
                .all()
                if r[0]
            ]
            gab_ids_prof = (
                db.session.query(AnswerSheetGabarito.id)
                .join(AnswerSheetResult, AnswerSheetResult.gabarito_id == AnswerSheetGabarito.id)
                .join(Student, AnswerSheetResult.student_id == Student.id)
                .filter(Student.class_id.in_(cids))
                .distinct()
            )
            prof_parts = [
                AnswerSheetGabarito.created_by == str(user.get("id") or ""),
                AnswerSheetGabarito.class_id.in_(cids),
                AnswerSheetGabarito.id.in_(gab_ids_prof),
            ]
            if school_ids_prof:
                prof_parts.append(AnswerSheetGabarito.school_id.in_(school_ids_prof))
            q = q.filter(or_(*prof_parts))
        else:
            return []

    # DISTINCT só em id: PostgreSQL não permite DISTINCT na linha inteira se há colunas json.
    gab_ids = [r[0] for r in q.with_entities(AnswerSheetGabarito.id).distinct().all()]
    if not gab_ids:
        return []
    rows = (
        AnswerSheetGabarito.query.filter(AnswerSheetGabarito.id.in_(gab_ids))
        .order_by(AnswerSheetGabarito.created_at.desc())
        .all()
    )
    return [{"id": str(r.id), "titulo": r.title or "Cartão resposta"} for r in rows]


def obter_escolas_por_gabarito(
    gabarito_id: str, municipio_id: str, user: dict, permissao: dict
) -> List[Dict[str, Any]]:
    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    gab = AnswerSheetGabarito.query.get(gabarito_id)
    if not gab:
        return []

    classes = answer_sheet_target_classes_visible_for_user(gab, user, permissao, municipio_id)
    school_ids = {c.school_id for c in classes if getattr(c, "school_id", None)}
    if not school_ids:
        return []
    escolas = (
        School.query.filter(School.id.in_(school_ids))
        .filter(School.city_id == city.id)
        .order_by(School.name)
        .all()
    )
    return [{"id": str(e.id), "nome": e.name} for e in escolas]


def obter_series_por_gabarito_escola(
    gabarito_id: str, escola_id: str, municipio_id: str, user: dict, permissao: dict
) -> List[Dict[str, Any]]:
    from app.models.grades import Grade

    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    gab = AnswerSheetGabarito.query.get(gabarito_id)
    if not gab:
        return []

    classes = answer_sheet_target_classes_visible_for_user(gab, user, permissao, municipio_id)
    classes = [c for c in classes if str(c.school_id) == str(escola_id)]
    grade_ids = {c.grade_id for c in classes if getattr(c, "grade_id", None)}
    if not grade_ids:
        return []
    rows = Grade.query.filter(Grade.id.in_(grade_ids)).order_by(Grade.name).all()
    return [{"id": str(s.id), "name": s.name} for s in rows]


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
    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    gab = AnswerSheetGabarito.query.get(gabarito_id)
    if not gab:
        return []

    classes = answer_sheet_target_classes_visible_for_user(gab, user, permissao, municipio_id)
    turmas = [
        c
        for c in classes
        if str(c.school_id) == str(escola_id) and str(c.grade_id) == str(serie_id)
    ]
    turmas.sort(key=lambda c: (c.name or "") or str(c.id))
    return [{"id": str(t.id), "name": t.name or f"Turma {t.id}"} for t in turmas]


def obter_series_por_gabarito_municipio(
    gabarito_id: str, municipio_id: str, user: dict, permissao: dict
) -> List[Dict[str, Any]]:
    """Séries distintas entre todas as escolas do município onde o gabarito tem turmas visíveis ao usuário."""
    from app.models.grades import Grade

    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    gab = AnswerSheetGabarito.query.get(gabarito_id)
    if not gab:
        return []

    classes = answer_sheet_target_classes_visible_for_user(gab, user, permissao, municipio_id)
    grade_ids = {c.grade_id for c in classes if getattr(c, "grade_id", None)}
    if not grade_ids:
        return []
    rows = Grade.query.filter(Grade.id.in_(grade_ids)).order_by(Grade.name).all()
    return [{"id": str(s.id), "name": s.name} for s in rows]


def obter_turmas_por_gabarito_serie_municipio(
    gabarito_id: str,
    serie_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
) -> List[Dict[str, Any]]:
    """Turmas (todas as escolas do escopo) com o gabarito aplicado e a série informada."""
    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    gab = AnswerSheetGabarito.query.get(gabarito_id)
    if not gab:
        return []

    classes = answer_sheet_target_classes_visible_for_user(gab, user, permissao, municipio_id)
    turmas = [c for c in classes if str(c.grade_id) == str(serie_id)]
    turmas.sort(key=lambda c: (c.name or "") or str(c.id))
    return [{"id": str(t.id), "name": t.name or f"Turma {t.id}"} for t in turmas]


def results_for_listing_filters(
    gabarito_id: str,
    municipio_id: str,
    escola: Optional[str],
    serie: Optional[str],
    turma: Optional[str],
    allowed_class_ids: Optional[Set[str]] = None,
) -> List[AnswerSheetResult]:
    q = (
        AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
        .join(Student, AnswerSheetResult.student_id == Student.id)
        .join(Class, Student.class_id == Class.id)
        .join(School, Class._school_id == School.id)
        .options(joinedload(AnswerSheetResult.student))
    )
    q = q.filter(School.city_id == municipio_id)
    if allowed_class_ids is not None:
        if not allowed_class_ids:
            return []
        from uuid import UUID

        uuids = []
        for x in allowed_class_ids:
            try:
                uuids.append(UUID(str(x)))
            except ValueError:
                continue
        if not uuids:
            return []
        q = q.filter(Class.id.in_(uuids))
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

    scope_classes = get_answer_sheet_target_classes_for_report(gab, "city", municipio)
    allowed_scope = {str(c.id) for c in scope_classes}
    results = results_for_listing_filters(
        avaliacao, municipio, escola, serie, turma, allowed_class_ids=allowed_scope
    )
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


def user_can_access_gabarito(
    user: dict, permissao: dict, gab: AnswerSheetGabarito, city_id: Optional[str] = None
) -> bool:
    from app.permissions.roles import Roles

    role = Roles.normalize(user.get("role", ""))
    if permissao.get("scope") == "all":
        return True
    if permissao.get("scope") == "municipio":
        return True

    if not city_id:
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

    classes = get_answer_sheet_target_classes_for_report(gab, "city", city_id)

    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        manager = Manager.query.filter_by(user_id=user["id"]).first()
        if not manager or not manager.school_id:
            return False
        return any(str(c.school_id) == str(manager.school_id) for c in classes)

    if role == Roles.PROFESSOR:
        if str(gab.created_by or "") == str(user.get("id") or ""):
            return True
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            return False
        tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        allowed = {str(tc.class_id) for tc in tcs}
        return any(str(c.id) in allowed for c in classes)

    return False


def answer_sheet_target_classes_visible_for_user(
    gab: AnswerSheetGabarito, user: dict, permissao: dict, city_id: str
) -> List[Class]:
    """Turmas do cartão no município, respeitando escopo diretor/professor."""
    from app.permissions.roles import Roles

    classes = get_answer_sheet_target_classes_for_report(gab, "city", city_id)
    role = Roles.normalize(user.get("role", ""))
    if permissao.get("scope") in ("all", "municipio"):
        return classes
    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        manager = Manager.query.filter_by(user_id=user["id"]).first()
        if not manager or not manager.school_id:
            return []
        return [c for c in classes if str(c.school_id) == str(manager.school_id)]
    if role == Roles.PROFESSOR:
        if str(gab.created_by or "") == str(user.get("id") or ""):
            return classes
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            return []
        tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        allowed = {str(tc.class_id) for tc in tcs}
        return [c for c in classes if str(c.id) in allowed]
    return classes


def answer_sheet_results_for_detail(
    user: dict, permissao: dict, gab: AnswerSheetGabarito
) -> List[AnswerSheetResult]:
    from app.permissions.roles import Roles

    role = Roles.normalize(user.get("role", ""))

    def _by_class_ids(class_ids: List[Any]) -> List[AnswerSheetResult]:
        if not class_ids:
            return []
        return (
            AnswerSheetResult.query.filter_by(gabarito_id=gab.id)
            .options(joinedload(AnswerSheetResult.student))
            .join(Student, AnswerSheetResult.student_id == Student.id)
            .filter(Student.class_id.in_(class_ids))
            .all()
        )

    if permissao.get("scope") in ("all", "municipio"):
        target = get_answer_sheet_target_classes_for_report(gab, "overall", None)
        return _by_class_ids([c.id for c in target])

    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        manager = Manager.query.filter_by(user_id=user["id"]).first()
        if not manager or not manager.school_id:
            return []
        target = get_answer_sheet_target_classes_for_report(
            gab, "school", str(manager.school_id)
        )
        return _by_class_ids([c.id for c in target])

    if role == Roles.PROFESSOR:
        if str(gab.created_by or "") == str(user.get("id") or ""):
            target = get_answer_sheet_target_classes_for_report(gab, "overall", None)
            return _by_class_ids([c.id for c in target])
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            return []
        target = get_answer_sheet_target_classes_for_report(
            gab, "teacher", str(teacher.id)
        )
        return _by_class_ids([c.id for c in target])

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
) -> Tuple[
    Optional[AnswerSheetGabarito],
    Optional[List[AnswerSheetResult]],
    Optional[Tuple[Any, int]],
    Optional[str],
]:
    """
    Resolve city/schema, carrega gabarito e verifica acesso.
    Retorna (gabarito, results, erro_ou_None, city_id) em sucesso city_id preenchido.
    """
    if not permissao.get("permitted"):
        return None, None, (
            jsonify({"error": permissao.get("error", "Acesso negado")}),
            403,
        ), None

    city_id, err = resolve_city_id_for_answer_sheet_detail(user, permissao)
    if err:
        return None, None, err, None

    set_search_path(city_id_to_schema_name(city_id))
    gab = AnswerSheetGabarito.query.get(gabarito_id)
    if not gab:
        return None, None, (jsonify({"error": "Gabarito não encontrado"}), 404), None

    if not user_can_access_gabarito(user, permissao, gab, city_id):
        return None, None, (jsonify({"error": "Acesso negado"}), 403), None

    results = answer_sheet_results_for_detail(user, permissao, gab)
    return gab, results, None, city_id


def build_answer_sheet_evaluation_by_id_json(
    gab: AnswerSheetGabarito, results: List[AnswerSheetResult]
) -> Dict[str, Any]:
    from app.models.test import Test

    stats = stats_from_answer_sheet_results(results)
    nq = answer_sheet_total_question_count(gab)
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
        "total_questoes": nq,
        **stats,
    }


def build_answer_sheet_relatorio_detalhado_json(
    gab: AnswerSheetGabarito,
    results: List[AnswerSheetResult],
    target_classes: Optional[List[Class]] = None,
) -> Dict[str, Any]:
    """
    Mesmo formato de GET /relatorio-detalhado (Test), para cartão-resposta (gabarito).
    Com target_classes, inclui todos os alunos matriculados nessas turmas (sem resultado = nao_respondida).
    """
    from uuid import UUID

    from app.models.skill import Skill
    from app.models.test import Test

    q_skills = question_skills_map_for_answer_sheet(gab)
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

    question_nums = ordered_question_numbers_for_gabarito(gab)
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

    def row_concluida(res: AnswerSheetResult) -> Optional[Dict[str, Any]]:
        student = res.student
        if not student:
            return None
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
        return {
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

    def row_nao_respondida(student: Student) -> Dict[str, Any]:
        turma_nome = student.class_.name if student.class_ else "N/A"
        respostas: List[Dict[str, Any]] = []
        nq = len(question_nums)
        for qn in question_nums:
            qid = f"{gab.id}-q{qn}"
            respostas.append(
                {
                    "questao_id": qid,
                    "questao_numero": qn,
                    "resposta_correta": False,
                    "resposta_em_branco": True,
                    "tempo_gasto": 0,
                }
            )
        return {
            "id": student.id,
            "nome": student.name or (student.user.name if student.user else "N/A"),
            "turma": turma_nome,
            "respostas": respostas,
            "total_acertos": 0,
            "total_erros": 0,
            "total_em_branco": nq,
            "nota_final": 0.0,
            "proficiencia": 0.0,
            "classificacao": None,
            "status": "nao_respondida",
        }

    alunos_data: List[Dict[str, Any]] = []
    if target_classes:
        by_sid = {str(r.student_id): r for r in results if r.student_id}
        class_ids = [c.id for c in target_classes]
        enrolled = (
            Student.query.options(joinedload(Student.class_), joinedload(Student.user))
            .filter(Student.class_id.in_(class_ids))
            .order_by(Student.class_id, Student.name)
            .all()
        )
        listed: set = set()
        for student in enrolled:
            sid = str(student.id)
            listed.add(sid)
            res = by_sid.get(sid)
            if res:
                row = row_concluida(res)
                if row:
                    alunos_data.append(row)
            else:
                alunos_data.append(row_nao_respondida(student))
        for res in results:
            sid = str(res.student_id) if res.student_id else ""
            if sid and sid not in listed:
                row = row_concluida(res)
                if row:
                    alunos_data.append(row)
    else:
        for res in results:
            row = row_concluida(res)
            if row:
                alunos_data.append(row)

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


def collect_skill_ids_for_answer_sheet_gabarito(gab: AnswerSheetGabarito) -> List[str]:
    """
    IDs de habilidade (UUID) para o gabarito: topologia + fallback pela prova (test_id),
    alinhado ao mapa usado em relatórios.
    """
    m = question_skills_map_for_answer_sheet(gab)
    ids: Set[str] = set()
    for lst in m.values():
        for sid in lst or []:
            if sid:
                ids.add(str(sid).strip())
    return sorted(ids)
