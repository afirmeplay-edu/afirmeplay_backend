# -*- coding: utf-8 -*-
"""
Filtros e cálculo de participação para cartão-resposta
(report_entity_type=answer_sheet).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import joinedload

from app.answer_sheets.models.answerSheetGabarito import AnswerSheetGabarito
from app.answer_sheets.models.answerSheetResult import AnswerSheetResult
from app.models.city import City
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.permissions import get_user_permission_scope
from app.participation_report.services.filters import obter_estados, obter_municipios, parse_id_list
from app.utils.class_label_helpers import format_grade_class_label, normalize_shift
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path
from app.utils.uuid_helpers import ensure_uuid_list


def _ensure_tenant_schema(municipio_id: str) -> None:
    set_search_path(city_id_to_schema_name(str(municipio_id).strip()))


def _normalize_serie_item(item: Dict[str, Any]) -> Dict[str, Any]:
    nome = item.get("nome") or item.get("name") or ""
    return {"id": str(item["id"]), "nome": nome, "name": nome}


def _normalize_turma_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Garante id/nome no mesmo formato do digital."""
    out = dict(item)
    if "id" in out:
        out["id"] = str(out["id"])
    if "nome" not in out and out.get("name"):
        out["nome"] = out["name"]
    if "name" not in out and out.get("nome"):
        out["name"] = out["nome"]
    return out


def _percentual(avaliados: int, matriculados: int) -> float:
    if matriculados <= 0:
        return 0.0
    return round(100.0 * avaliados / matriculados, 2)


def _merge_unique_options(items: List[Dict[str, Any]], id_key: str = "id") -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        iid = str(item.get(id_key) or "")
        if not iid or iid in seen:
            continue
        seen.add(iid)
        out.append(item)
    return out


def build_filter_options_answer_sheet(user: dict, args) -> Dict[str, Any]:
    """
    Mesma hierarquia do digital, com gabaritos na chave ``avaliacoes``
    (contrato compatível com a aba do frontend).
    """
    from app.answer_sheets.routes.answer_sheet_evaluation_listing import (
        obter_escolas_por_gabarito,
        obter_gabaritos_por_municipio,
        obter_series_por_gabarito_escola,
        obter_series_por_gabarito_municipio,
        obter_turmas_por_gabarito_escola_serie,
        obter_turmas_por_gabarito_serie_municipio,
    )

    permissao = get_user_permission_scope(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")

    estado = (args.get("estado") or "").strip() or None
    municipio = (args.get("municipio") or "").strip() or None

    def _multi(*keys: str) -> List[str]:
        values = []
        for key in keys:
            values.append(args.get(key))
            getlist = getattr(args, "getlist", None)
            if callable(getlist):
                values.extend(getlist(key))
        return parse_id_list(*values)

    # Frontend reutiliza ``avaliacoes``; aceita também ``gabaritos``
    gabarito_ids = _multi("avaliacoes", "avaliacao", "gabaritos", "gabarito")
    escola_ids = _multi("escolas", "escola")
    serie_ids = _multi("series", "serie")

    response: Dict[str, Any] = {
        "estados": obter_estados(user, permissao),
    }

    if not estado:
        return response

    response["municipios"] = obter_municipios(estado, user, permissao)

    if not municipio:
        return response

    _ensure_tenant_schema(municipio)

    escola_param = escola_ids[0] if len(escola_ids) == 1 else "all"
    serie_filtro = serie_ids[0] if len(serie_ids) == 1 else None
    response["avaliacoes"] = obter_gabaritos_por_municipio(
        municipio,
        user,
        permissao,
        escola_param=escola_param,
        serie_id=serie_filtro,
    )

    if not gabarito_ids:
        return response

    escolas: List[Dict[str, Any]] = []
    series: List[Dict[str, Any]] = []
    for gid in gabarito_ids:
        escolas.extend(obter_escolas_por_gabarito(gid, municipio, user, permissao))
        if escola_ids:
            for eid in escola_ids:
                series.extend(
                    obter_series_por_gabarito_escola(
                        gid, eid, municipio, user, permissao
                    )
                )
        else:
            series.extend(
                obter_series_por_gabarito_municipio(gid, municipio, user, permissao)
            )

    response["escolas"] = _merge_unique_options(escolas)
    response["series"] = [
        _normalize_serie_item(s) for s in _merge_unique_options(series)
    ]

    if serie_ids or escola_ids:
        turmas: List[Dict[str, Any]] = []
        for gid in gabarito_ids:
            if escola_ids and serie_ids:
                for eid in escola_ids:
                    for sid in serie_ids:
                        turmas.extend(
                            obter_turmas_por_gabarito_escola_serie(
                                gid, eid, sid, municipio, user, permissao
                            )
                        )
            elif serie_ids:
                for sid in serie_ids:
                    turmas.extend(
                        obter_turmas_por_gabarito_serie_municipio(
                            gid, sid, municipio, user, permissao
                        )
                    )
            elif escola_ids:
                # Sem série: turmas de todas as séries das escolas selecionadas
                for eid in escola_ids:
                    series_escola = obter_series_por_gabarito_escola(
                        gid, eid, municipio, user, permissao
                    )
                    for s in series_escola:
                        turmas.extend(
                            obter_turmas_por_gabarito_escola_serie(
                                gid, eid, str(s["id"]), municipio, user, permissao
                            )
                        )
        response["turmas"] = [
            _normalize_turma_item(t) for t in _merge_unique_options(turmas)
        ]

    return response


def _filter_classes(
    classes: List[Class],
    escola_ids: Optional[List[str]],
    serie_ids: Optional[List[str]],
    turma_ids: Optional[List[str]],
) -> List[Class]:
    escola_set = {str(x) for x in (escola_ids or [])}
    serie_set = {str(x) for x in (serie_ids or [])}
    turma_set = {str(x) for x in (turma_ids or [])}
    out: List[Class] = []
    for c in classes:
        if turma_set and str(c.id) not in turma_set:
            continue
        if escola_set and str(c.school_id) not in escola_set:
            continue
        if serie_set and str(c.grade_id) not in serie_set:
            continue
        out.append(c)
    return out


def _placement_for_student(
    student: Student,
    result: Optional[AnswerSheetResult],
):
    if result is not None:
        has_snap = bool(
            getattr(result, "school_id_snapshot", None)
            or getattr(result, "class_id_snapshot", None)
        )
        if has_snap:
            school_id = (
                str(result.school_id_snapshot) if result.school_id_snapshot else None
            )
            class_id = result.class_id_snapshot
            grade_id = result.grade_id_snapshot
            if class_id is not None and grade_id is None:
                cls_obj = Class.query.get(class_id)
                if cls_obj is not None:
                    grade_id = getattr(cls_obj, "grade_id", None)
                    if school_id is None and getattr(cls_obj, "school_id", None):
                        school_id = str(cls_obj.school_id)
            return school_id, class_id, grade_id

    school_id = str(student.school_id) if getattr(student, "school_id", None) else None
    class_id = getattr(student, "class_id", None)
    grade_id = getattr(student, "grade_id", None)
    if class_id and (school_id is None or grade_id is None):
        cls_obj = getattr(student, "class_", None) or Class.query.get(class_id)
        if cls_obj is not None:
            if school_id is None and getattr(cls_obj, "school_id", None):
                school_id = str(cls_obj.school_id)
            if grade_id is None:
                grade_id = getattr(cls_obj, "grade_id", None)
    return school_id, class_id, grade_id


def build_participation_report_answer_sheet(
    user: dict,
    estado: str,
    municipio_id: str,
    gabarito_ids: Optional[List[str]] = None,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Participação em cartão-resposta: alunos únicos, AnswerSheetResult + turmas-alvo.
    """
    from app.answer_sheets.routes.answer_sheet_evaluation_listing import (
        answer_sheet_target_classes_visible_for_user,
        obter_gabaritos_por_municipio,
    )
    from app.answer_sheets.routes.answer_sheet_routes import _load_cartao_roster_and_results

    permissao = get_user_permission_scope(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")

    city = City.query.get(municipio_id)
    if not city:
        raise ValueError("Município não encontrado")
    if permissao.get("scope") != "all":
        user_city = str(user.get("city_id") or user.get("tenant_id") or "")
        if user_city != str(city.id):
            raise PermissionError("Sem permissão para este município")

    _ensure_tenant_schema(municipio_id)

    gabarito_ids = list(gabarito_ids or [])
    if not gabarito_ids:
        opts = obter_gabaritos_por_municipio(municipio_id, user, permissao)
        gabarito_ids = [str(g["id"]) for g in opts]

    # Normalizar UUIDs de série/turma
    serie_ids_norm = [str(x) for x in (serie_ids or [])]
    turma_ids_norm = [str(x) for x in (ensure_uuid_list(turma_ids) or turma_ids or [])]
    if turma_ids and not turma_ids_norm:
        turma_ids_norm = [str(x) for x in turma_ids]
    escola_ids_norm = [str(x) for x in (escola_ids or [])]

    escopo = {
        "estado": estado,
        "municipio_id": str(municipio_id),
        "avaliacoes": list(gabarito_ids),
        "gabaritos": list(gabarito_ids),
        "escolas": list(escola_ids_norm),
        "series": list(serie_ids_norm),
        "turmas": list(turma_ids_norm),
        "report_entity_type": "answer_sheet",
    }

    empty = {
        "escopo": escopo,
        "metricas": {
            "matriculados": 0,
            "avaliados": 0,
            "total_turmas": 0,
            "percentual_participacao": 0.0,
        },
        "por_escola": [],
        "por_turma": [],
    }

    if not gabarito_ids:
        return empty

    class_meta: Dict[Any, Dict[str, Any]] = {}
    school_class_ids: Dict[str, Set[Any]] = defaultdict(set)
    school_ids_needed: Set[str] = set()
    all_class_ids: Set[Any] = set()
    classes_by_gabarito: Dict[str, List[Any]] = {}

    for gid in gabarito_ids:
        gab = AnswerSheetGabarito.query.get(gid)
        if not gab:
            continue
        classes = answer_sheet_target_classes_visible_for_user(
            gab, user, permissao, municipio_id
        )
        classes = _filter_classes(
            classes, escola_ids_norm or None, serie_ids_norm or None, turma_ids_norm or None
        )
        cids = [c.id for c in classes]
        classes_by_gabarito[str(gid)] = cids
        for c in classes:
            all_class_ids.add(c.id)
            school_id = str(c.school_id) if c.school_id else None
            class_meta[c.id] = {
                "escola_id": school_id,
                "serie_id": c.grade_id,
                "turma_nome": c.name or "",
                "shift": normalize_shift(getattr(c, "shift", None)) or "",
                "serie_nome": (c.grade.name if c.grade else "") or "",
            }
            if school_id:
                school_class_ids[school_id].add(c.id)
                school_ids_needed.add(school_id)

    if not all_class_ids:
        return empty

    schools_by_id: Dict[str, School] = {}
    if school_ids_needed:
        for sch in School.query.filter(School.id.in_(list(school_ids_needed))).all():
            schools_by_id[str(sch.id)] = sch
    for meta in class_meta.values():
        sid = meta.get("escola_id")
        meta["escola_nome"] = (
            schools_by_id[sid].name if sid and sid in schools_by_id else ""
        )

    students_by_id: Dict[Any, Student] = {}
    best_result_by_student: Dict[Any, AnswerSheetResult] = {}
    matriculados_ids: Set[Any] = set()
    avaliados_ids: Set[Any] = set()

    for gid, cids in classes_by_gabarito.items():
        if not cids:
            continue
        results, students = _load_cartao_roster_and_results(str(gid), cids)
        for s in students:
            students_by_id[s.id] = s
            matriculados_ids.add(s.id)
        for r in results:
            if not r.student_id:
                continue
            avaliados_ids.add(r.student_id)
            prev = best_result_by_student.get(r.student_id)
            if prev is None:
                best_result_by_student[r.student_id] = r
                continue
            prev_ts = getattr(prev, "corrected_at", None)
            cur_ts = getattr(r, "corrected_at", None)
            if cur_ts and (not prev_ts or cur_ts > prev_ts):
                best_result_by_student[r.student_id] = r

    missing = (matriculados_ids | avaliados_ids) - set(students_by_id.keys())
    if missing:
        for s in (
            Student.query.filter(Student.id.in_(list(missing)))
            .options(joinedload(Student.class_).joinedload(Class.grade))
            .all()
        ):
            students_by_id[s.id] = s
    matriculados_ids = set(students_by_id.keys()) | matriculados_ids | avaliados_ids
    still_missing = matriculados_ids - set(students_by_id.keys())
    if still_missing:
        for s in Student.query.filter(Student.id.in_(list(still_missing))).all():
            students_by_id[s.id] = s
    matriculados_ids = set(students_by_id.keys())

    matriculados = len(matriculados_ids)
    avaliados = len(avaliados_ids)
    total_turmas = len(all_class_ids)

    mat_by_school: Dict[str, Set[Any]] = defaultdict(set)
    av_by_school: Dict[str, Set[Any]] = defaultdict(set)
    mat_by_class: Dict[Any, Set[Any]] = defaultdict(set)
    av_by_class: Dict[Any, Set[Any]] = defaultdict(set)
    school_names: Dict[str, str] = {}
    class_labels: Dict[Any, Dict[str, Any]] = {}

    for sid in matriculados_ids:
        student = students_by_id.get(sid)
        if not student:
            continue
        result = best_result_by_student.get(sid)
        school_id, class_id, grade_id = _placement_for_student(student, result)

        if class_id not in class_meta and student.class_id in class_meta:
            class_id = student.class_id
            meta = class_meta[class_id]
            school_id = meta.get("escola_id") or school_id
            grade_id = meta.get("serie_id") or grade_id

        if school_id:
            mat_by_school[school_id].add(sid)
            if sid in avaliados_ids:
                av_by_school[school_id].add(sid)
            if school_id not in school_names:
                name = ""
                for meta in class_meta.values():
                    if meta.get("escola_id") == school_id and meta.get("escola_nome"):
                        name = meta["escola_nome"]
                        break
                if not name:
                    sch = schools_by_id.get(school_id) or School.query.get(school_id)
                    name = sch.name if sch else school_id
                school_names[school_id] = name

        if class_id is not None:
            mat_by_class[class_id].add(sid)
            if sid in avaliados_ids:
                av_by_class[class_id].add(sid)
            if class_id not in class_labels:
                meta = class_meta.get(class_id) or {}
                turma_nome = meta.get("turma_nome")
                serie_nome = meta.get("serie_nome")
                shift = meta.get("shift") or ""
                if not turma_nome:
                    cls_obj = Class.query.get(class_id)
                    if cls_obj:
                        turma_nome = cls_obj.name or ""
                        serie_nome = cls_obj.grade.name if cls_obj.grade else ""
                        shift = normalize_shift(getattr(cls_obj, "shift", None)) or ""
                        grade_id = grade_id or cls_obj.grade_id
                        school_id = school_id or (
                            str(cls_obj.school_id) if cls_obj.school_id else None
                        )
                class_labels[class_id] = {
                    "turma_id": str(class_id),
                    "turma_nome": format_grade_class_label(
                        serie_nome, turma_nome, shift, include_shift=bool(shift)
                    )
                    if serie_nome or turma_nome
                    else (turma_nome or str(class_id)),
                    "escola_id": school_id,
                    "serie_id": str(grade_id)
                    if grade_id is not None
                    else (
                        str(meta.get("serie_id"))
                        if meta.get("serie_id") is not None
                        else None
                    ),
                }

    for cid, meta in class_meta.items():
        if cid not in class_labels:
            class_labels[cid] = {
                "turma_id": str(cid),
                "turma_nome": format_grade_class_label(
                    meta.get("serie_nome"),
                    meta.get("turma_nome"),
                    meta.get("shift"),
                    include_shift=bool(meta.get("shift")),
                ),
                "escola_id": meta.get("escola_id"),
                "serie_id": str(meta["serie_id"])
                if meta.get("serie_id") is not None
                else None,
            }
        sid_school = meta.get("escola_id")
        if sid_school and sid_school not in school_names:
            school_names[sid_school] = meta.get("escola_nome") or sid_school

    por_escola = []
    for school_id in sorted(school_names.keys(), key=lambda x: school_names.get(x, x)):
        m = len(mat_by_school.get(school_id, set()))
        a = len(av_by_school.get(school_id, set()))
        por_escola.append(
            {
                "escola_id": school_id,
                "escola_nome": school_names.get(school_id) or school_id,
                "matriculados": m,
                "avaliados": a,
                "total_turmas": len(school_class_ids.get(school_id, set())),
                "percentual_participacao": _percentual(a, m),
            }
        )

    por_turma = []
    for class_id, label in sorted(
        class_labels.items(),
        key=lambda item: (item[1].get("escola_id") or "", item[1].get("turma_nome") or ""),
    ):
        m = len(mat_by_class.get(class_id, set()))
        a = len(av_by_class.get(class_id, set()))
        por_turma.append(
            {
                "turma_id": label["turma_id"],
                "turma_nome": label["turma_nome"],
                "escola_id": label.get("escola_id"),
                "serie_id": label.get("serie_id"),
                "matriculados": m,
                "avaliados": a,
                "percentual_participacao": _percentual(a, m),
            }
        )

    logging.info(
        "participation_report answer_sheet municipio=%s gabaritos=%s classes=%s "
        "matriculados=%s avaliados=%s",
        municipio_id,
        len(gabarito_ids),
        total_turmas,
        matriculados,
        avaliados,
    )

    return {
        "escopo": escopo,
        "metricas": {
            "matriculados": matriculados,
            "avaliados": avaliados,
            "total_turmas": total_turmas,
            "percentual_participacao": _percentual(avaliados, matriculados),
        },
        "por_escola": por_escola,
        "por_turma": por_turma,
    }
