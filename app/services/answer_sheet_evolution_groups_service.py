# -*- coding: utf-8 -*-
"""
Evolução por grupos (turma / série / escola) entre gabaritos de cartão-resposta.

Mesmo contrato de POST /test/compare-groups. Cada ponto é calculado por
``_calcular_estatisticas_grupo_cartao`` (base de GET /answer-sheets/resultados-agregados):
mesmas turmas-alvo, público ADAP, filtro ``alunos``, média hierárquica e nível.

Visão escola com mais de uma série: mesmo critério da tela Resultados — o ponto
da escola sai só com participação (média e nível ``None`` e
``requer_filtro_serie=True``) e cada série vai separada em ``by_serie``.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from app.services.evolution_groups_service import (
    LEVEL_ORDER,
    _build_grade_by_recorte,
    _group_key,
    _pp_delta,
    _valid_view_by,
)

logger = logging.getLogger(__name__)

ORIGEM_CARTAO = "cartao_resposta"
SEM_SERIE = "_sem_serie"
PERFIS_ESCOLA = ("diretor", "coordenador")


class PermissaoGruposCartaoError(Exception):
    """Perfil sem vínculo ou filtro fora do que o usuário pode ver."""

    def __init__(self, message: str, status: int = 403):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# Permissão por perfil
# ---------------------------------------------------------------------------

def _manager_school_id(user_id: Any) -> Optional[str]:
    from app.models.manager import Manager

    manager = Manager.query.filter_by(user_id=user_id).first()
    if manager and manager.school_id:
        return str(manager.school_id)
    return None


def _teacher_class_ids(user_id: Any) -> Optional[Set[str]]:
    from app.models.teacher import Teacher
    from app.models.teacherClass import TeacherClass

    teacher = Teacher.query.filter_by(user_id=user_id).first()
    if not teacher:
        return None
    return {
        str(tc.class_id)
        for tc in TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        if tc.class_id
    }


def restricao_por_perfil(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Diretor/coordenador: só a escola do Manager. Professor: só as turmas vinculadas."""
    role = str((user or {}).get("role") or "").strip().lower()
    if role in PERFIS_ESCOLA:
        school_id = _manager_school_id(user.get("id"))
        if not school_id:
            raise PermissaoGruposCartaoError("Usuário sem escola vinculada")
        return {"tipo": "escola", "school_id": school_id}
    if role == "professor":
        class_ids = _teacher_class_ids(user.get("id"))
        if class_ids is None:
            raise PermissaoGruposCartaoError("Professor não encontrado")
        return {"tipo": "turmas", "class_ids": class_ids}
    return {"tipo": "livre"}


def validar_filtros_do_perfil(restricao: Dict[str, Any], scope_info: Dict[str, Any]) -> None:
    escola = (scope_info or {}).get("escola")
    turma = (scope_info or {}).get("turma")
    if restricao.get("tipo") == "escola" and escola and str(escola) != restricao["school_id"]:
        raise PermissaoGruposCartaoError("Acesso negado à escola informada")
    if restricao.get("tipo") == "turmas" and turma and str(turma) not in restricao["class_ids"]:
        raise PermissaoGruposCartaoError("Acesso negado à turma informada")


def turma_permitida(classe: Any, restricao: Dict[str, Any]) -> bool:
    tipo = restricao.get("tipo")
    if tipo == "escola":
        return str(getattr(classe, "school_id", "") or "") == restricao["school_id"]
    if tipo == "turmas":
        return str(getattr(classe, "id", "")) in restricao["class_ids"]
    return True


# ---------------------------------------------------------------------------
# Acesso a dados (isolado para teste)
# ---------------------------------------------------------------------------

def _turmas_alvo(gabarito_id: str, scope_info: Dict[str, Any], nivel: str, user: Any) -> List[Any]:
    from app.routes.answer_sheet_routes import _class_ids_alunos_previstos_cartao

    return list(_class_ids_alunos_previstos_cartao(gabarito_id, scope_info, nivel, user) or [])


def _load_classes(class_ids: Iterable[Any]) -> Dict[str, Any]:
    from app.models.studentClass import Class

    ids = list({c for c in class_ids})
    if not ids:
        return {}
    return {str(c.id): c for c in Class.query.filter(Class.id.in_(ids)).all()}


def _load_names(classes: Sequence[Any]) -> Tuple[Dict[str, str], Dict[str, str]]:
    from app.models.grades import Grade
    from app.models.school import School

    school_ids = list({str(c.school_id) for c in classes if getattr(c, "school_id", None)})
    grade_ids = list({c.grade_id for c in classes if getattr(c, "grade_id", None)})
    schools = (
        {str(s.id): s.name or "" for s in School.query.filter(School.id.in_(school_ids)).all()}
        if school_ids
        else {}
    )
    grades = (
        {str(g.id): g.name or "" for g in Grade.query.filter(Grade.id.in_(grade_ids)).all()}
        if grade_ids
        else {}
    )
    return schools, grades


def _data_aplicacao(gabarito: Any) -> Optional[datetime]:
    """Primeira correção do gabarito; sem correção, data de criação."""
    from sqlalchemy import func

    from app import db
    from app.models.answerSheetResult import AnswerSheetResult

    first = (
        db.session.query(func.min(AnswerSheetResult.corrected_at))
        .filter(AnswerSheetResult.gabarito_id == str(gabarito.id))
        .scalar()
    )
    return first or getattr(gabarito, "created_at", None)


def _series_do_gabarito(gabarito: Any) -> List[Dict[str, str]]:
    from app.services.cartao_resposta.gabarito_grades import get_gabarito_grades

    return get_gabarito_grades(gabarito)


def _course_name_serie(gabarito: Any, serie_id: Optional[str]) -> str:
    from app.services.cartao_resposta.gabarito_grades import course_meta_for_gabarito_serie

    return course_meta_for_gabarito_serie(gabarito, serie_id)[0] or ""


def _estatisticas_grupo(
    class_ids: List[Any],
    gabarito_id: str,
    aggregation_level: str,
    alunos_filtro: str,
    serie_id_curso: Optional[str],
) -> Dict[str, Any]:
    from app.routes.answer_sheet_routes import _calcular_estatisticas_grupo_cartao
    from app.services.skills_map_service import _participating_answer_sheet_result

    return _calcular_estatisticas_grupo_cartao(
        class_ids,
        gabarito_id,
        None,
        aggregation_level=aggregation_level,
        alunos_filtro=alunos_filtro,
        serie_id_curso=serie_id_curso,
        filtro_resultados=_participating_answer_sheet_result,
    )


def _nivel(media_proficiencia: float, gabarito: Any, serie_id: Optional[str]) -> Optional[str]:
    from app.routes.answer_sheet_routes import _nivel_escola_por_media_proficiencia_cartao

    return _nivel_escola_por_media_proficiencia_cartao(
        float(media_proficiencia or 0), gabarito, serie_id=serie_id
    )


# ---------------------------------------------------------------------------
# Pontos e transições
# ---------------------------------------------------------------------------

def _ponto_vazio(gabarito: Any, order: int) -> Dict[str, Any]:
    return {
        "evaluation_id": str(gabarito.id),
        "evaluation_title": gabarito.title,
        "order": order,
        "average_grade": None,
        "average_proficiency": None,
        "level": None,
        "total_students": 0,
        "total_alunos": 0,
        "alunos_participantes": 0,
        "alunos_ausentes": 0,
        "percentual_comparecimento": 0.0,
    }


def _montar_ponto(
    gabarito: Any,
    order: int,
    stats: Dict[str, Any],
    level: Optional[str],
    *,
    com_media: bool,
) -> Dict[str, Any]:
    ponto = _ponto_vazio(gabarito, order)
    participantes = int(stats.get("alunos_participantes") or 0)
    ponto.update(
        {
            "total_students": participantes,
            "total_alunos": int(stats.get("total_alunos") or 0),
            "alunos_participantes": participantes,
            "alunos_ausentes": int(stats.get("alunos_ausentes") or 0),
            "percentual_comparecimento": float(stats.get("percentual_comparecimento") or 0.0),
        }
    )
    if participantes and com_media:
        ponto["average_grade"] = round(float(stats.get("media_nota") or 0), 2)
        ponto["average_proficiency"] = round(float(stats.get("media_proficiencia") or 0), 2)
        ponto["level"] = level
    return ponto


def _ponto_calculado(
    gabarito: Any,
    order: int,
    turmas: List[Any],
    aggregation_level: str,
    alunos_filtro: str,
    serie_id: Optional[str],
) -> Dict[str, Any]:
    course_name = _course_name_serie(gabarito, serie_id)
    stats = _estatisticas_grupo(
        [t.id for t in turmas], str(gabarito.id), aggregation_level, alunos_filtro, serie_id
    )
    level = None
    if course_name and stats.get("alunos_participantes"):
        level = _nivel(stats.get("media_proficiencia"), gabarito, serie_id)
    return _montar_ponto(gabarito, order, stats, level, com_media=bool(course_name))


def _serie_de(turma: Any) -> str:
    return str(turma.grade_id) if getattr(turma, "grade_id", None) else SEM_SERIE


def _ponto_do_grupo(
    gabarito: Any,
    order: int,
    turmas: List[Any],
    view_by: str,
    alunos_filtro: str,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """Ponto do grupo e, na visão escola com várias séries, um ponto por série."""
    if not turmas:
        return _ponto_vazio(gabarito, order), {}
    series = sorted({_serie_de(t) for t in turmas})
    if view_by != "escola" or len(series) == 1:
        serie_id = series[0] if series[0] != SEM_SERIE else None
        ponto = _ponto_calculado(gabarito, order, turmas, view_by, alunos_filtro, serie_id)
        if view_by == "escola":
            ponto["requer_filtro_serie"] = False
        return ponto, {}

    por_serie: Dict[str, Dict[str, Any]] = {}
    for sid in series:
        turmas_serie = [t for t in turmas if _serie_de(t) == sid]
        por_serie[sid] = _ponto_calculado(
            gabarito,
            order,
            turmas_serie,
            "serie",
            alunos_filtro,
            sid if sid != SEM_SERIE else None,
        )

    # Mesmo critério da tela Resultados: escola com mais de uma série sai sem média única
    # (apenas participação) e cada série vai separada em by_serie.
    stats = _estatisticas_grupo(
        [t.id for t in turmas], str(gabarito.id), "escola", alunos_filtro, None
    )
    ponto = _montar_ponto(gabarito, order, stats, None, com_media=False)
    ponto["requer_filtro_serie"] = True
    return ponto, por_serie


def _transicoes(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mesma regra de /test/compare-groups: só entre pontos consecutivos com nível."""
    transitions: List[Dict[str, Any]] = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        if not (a.get("level") and b.get("level")):
            continue
        prof_delta = None
        grade_delta = None
        if a.get("average_proficiency") is not None and b.get("average_proficiency") is not None:
            prof_delta = _pp_delta(a["average_proficiency"], b["average_proficiency"])
        if a.get("average_grade") is not None and b.get("average_grade") is not None:
            grade_delta = round((b["average_grade"] - a["average_grade"]) * 10, 1)
        transitions.append(
            {
                "from_order": a["order"],
                "to_order": b["order"],
                "from_level": a["level"],
                "to_level": b["level"],
                "level_changed": a["level"] != b["level"],
                "proficiency_delta": prof_delta,
                "grade_pp_delta": grade_delta,
            }
        )
    return transitions


def _nivel_atual(points: List[Dict[str, Any]]) -> Optional[str]:
    for p in reversed(points):
        if p.get("level"):
            return p["level"]
    return None


def _tem_participante(points: List[Dict[str, Any]]) -> bool:
    return any(int(p.get("alunos_participantes") or 0) > 0 for p in points)


# ---------------------------------------------------------------------------
# Grupos
# ---------------------------------------------------------------------------

def _group_meta(
    view_by: str,
    key: str,
    turma: Any,
    school_names: Dict[str, str],
    grade_names: Dict[str, str],
) -> Dict[str, Any]:
    school_id = str(turma.school_id)
    sname = school_names.get(school_id) or "Escola"
    grade_id = _serie_de(turma)
    gname = grade_names.get(grade_id) or "Série"
    if view_by == "escola":
        return {
            "id": key,
            "name": sname,
            "school_id": school_id,
            "school_name": sname,
            "grade_id": None,
            "grade_name": None,
            "class_id": None,
            "class_name": None,
        }
    if view_by == "serie":
        return {
            "id": key,
            "name": f"{gname} — {sname}",
            "school_id": school_id,
            "school_name": sname,
            "grade_id": grade_id if grade_id != SEM_SERIE else None,
            "grade_name": gname,
            "class_id": None,
            "class_name": None,
        }
    cname = getattr(turma, "name", None) or "Turma"
    return {
        "id": key,
        "name": cname,
        "school_id": school_id,
        "school_name": sname,
        "grade_id": grade_id if grade_id != SEM_SERIE else None,
        "grade_name": gname,
        "class_id": str(turma.id),
        "class_name": cname,
    }


def _by_serie_payload(
    gabaritos: List[Any],
    por_serie_por_gab: List[Dict[str, Dict[str, Any]]],
    grade_names: Dict[str, str],
) -> List[Dict[str, Any]]:
    series = sorted(
        {sid for por_serie in por_serie_por_gab for sid in por_serie},
        key=lambda sid: ((grade_names.get(sid) or "").lower(), sid),
    )
    out: List[Dict[str, Any]] = []
    for sid in series:
        points = []
        course_name = ""
        for order, (gab, por_serie) in enumerate(zip(gabaritos, por_serie_por_gab), start=1):
            ponto = por_serie.get(sid)
            if ponto is None:
                points.append(_ponto_vazio(gab, order))
                continue
            points.append(ponto)
            if not course_name and sid != SEM_SERIE:
                course_name = _course_name_serie(gab, sid)
        if not _tem_participante(points):
            continue
        out.append(
            {
                "serie_id": sid if sid != SEM_SERIE else None,
                "serie_name": grade_names.get(sid) or "Série",
                "course_name": course_name or None,
                "current_level": _nivel_atual(points),
                "points": points,
                "transitions": _transicoes(points),
                "grade_by_recorte": _build_grade_by_recorte(points),
            }
        )
    return out


def _evaluations_payload(gabaritos: List[Any]) -> List[Dict[str, Any]]:
    out = []
    for order, gab in enumerate(gabaritos, start=1):
        data = _data_aplicacao(gab)
        out.append(
            {
                "order": order,
                "id": str(gab.id),
                "title": gab.title or f"Cartão-resposta {order}",
                "application_date": data.isoformat() if isinstance(data, datetime) else (
                    str(data) if data else None
                ),
                "series": _series_do_gabarito(gab),
                "origem": ORIGEM_CARTAO,
            }
        )
    return out


def compare_gabaritos_by_groups(
    gabaritos: List[Any],
    *,
    view_by: str = "turma",
    scope_info: Dict[str, Any],
    nivel_granularidade: str,
    user: Optional[Dict[str, Any]] = None,
    alunos_filtro: str = "todos",
    filtros_aplicados: Optional[Dict[str, Any]] = None,
    restricao: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """``gabaritos`` já na ordem da linha do tempo (a do pedido)."""
    view_by = _valid_view_by(view_by)
    restricao = restricao or {"tipo": "livre"}

    turmas_por_gab: Dict[str, List[Any]] = {
        str(gab.id): _turmas_alvo(str(gab.id), scope_info, nivel_granularidade, user)
        for gab in gabaritos
    }
    classes = _load_classes(c for ids in turmas_por_gab.values() for c in ids)
    classes = {
        cid: c
        for cid, c in classes.items()
        if getattr(c, "school_id", None) and turma_permitida(c, restricao)
    }
    school_names, grade_names = _load_names(list(classes.values()))

    membros: Dict[str, Dict[str, List[Any]]] = defaultdict(lambda: defaultdict(list))
    metas: Dict[str, Dict[str, Any]] = {}
    for gid, ids in turmas_por_gab.items():
        for cid in ids:
            turma = classes.get(str(cid))
            if turma is None:
                continue
            key = _group_key(view_by, str(turma.school_id), _serie_de(turma), str(turma.id))
            if turma not in membros[key][gid]:
                membros[key][gid].append(turma)
            if key not in metas:
                metas[key] = _group_meta(view_by, key, turma, school_names, grade_names)

    groups_out: List[Dict[str, Any]] = []
    summary_counts = {lvl: 0 for lvl in LEVEL_ORDER}
    algum_requer_serie = False

    for key, meta in metas.items():
        points: List[Dict[str, Any]] = []
        por_serie_por_gab: List[Dict[str, Dict[str, Any]]] = []
        for order, gab in enumerate(gabaritos, start=1):
            ponto, por_serie = _ponto_do_grupo(
                gab, order, membros[key].get(str(gab.id), []), view_by, alunos_filtro
            )
            points.append(ponto)
            por_serie_por_gab.append(por_serie)

        by_serie = (
            _by_serie_payload(gabaritos, por_serie_por_gab, grade_names)
            if any(por_serie_por_gab)
            else []
        )
        if not _tem_participante(points) and not by_serie:
            continue

        current_level = _nivel_atual(points)
        if current_level in summary_counts:
            summary_counts[current_level] += 1

        group = {
            **meta,
            "current_level": current_level,
            "points": points,
            "transitions": _transicoes(points),
            "grade_by_recorte": _build_grade_by_recorte(points),
        }
        if view_by == "escola":
            requer = any(p.get("requer_filtro_serie") for p in points)
            algum_requer_serie = algum_requer_serie or requer
            group["requer_filtro_serie"] = requer
            group["by_serie"] = by_serie
        groups_out.append(group)

    groups_out.sort(
        key=lambda g: ((g.get("name") or "").lower(), (g.get("school_name") or "").lower())
    )

    return {
        "view_by": view_by,
        "origem": ORIGEM_CARTAO,
        "filtros_aplicados": filtros_aplicados,
        "evaluations": _evaluations_payload(gabaritos),
        "total_evaluations": len(gabaritos),
        "total_groups": len(groups_out),
        "summary_by_level": summary_counts,
        "requer_filtro_serie": algum_requer_serie,
        "groups": groups_out,
    }
