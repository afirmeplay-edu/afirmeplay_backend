# -*- coding: utf-8 -*-
"""
Mapa de questões — cartão-resposta (AnswerSheetGabarito + AnswerSheetResult).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Set

from app.mapa_questoes.helpers import (
    build_question_row,
    empty_payload,
    letters_for_answer_sheet,
    media_acertos_percentual,
)
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.city import City
from app.models.subject import Subject
from app.permissions import get_user_permission_scope
from app.participation_report.answer_sheet import _filter_classes
from app.report_analysis.answer_sheet_report_builder import question_skills_map_for_answer_sheet
from app.services.skills_map_service import (
    _disciplinas_config_from_gabarito_blocks,
    _fetch_skills_batch,
    _gabarito_answer_map,
    _habilidade_codigo_e_descricao,
    _parse_detected,
    _question_num_to_subject_id,
    resolve_participating_students_answer_sheet,
)
from app.utils.uuid_helpers import ensure_uuid_list

logger = logging.getLogger(__name__)


def _ensure_tenant_schema(municipio_id: str) -> None:
    set_search_path(city_id_to_schema_name(str(municipio_id).strip()))


def _skill_code_for_question(skill_ids: Sequence[str], skills_db: Dict[str, Any]) -> str:
    codes: List[str] = []
    seen: Set[str] = set()
    for sid in skill_ids:
        obj = skills_db.get(str(sid))
        codigo, _ = _habilidade_codigo_e_descricao(str(sid), obj)
        if codigo and codigo not in seen:
            codes.append(codigo)
            seen.add(codigo)
    return ", ".join(codes) if codes else "N/A"


def _resolve_subject_name(subject_id: str, fallback: str) -> str:
    if fallback and fallback.strip() and fallback.strip().lower() not in ("outras", "geral"):
        return fallback.strip()
    if not subject_id or subject_id in ("geral", "sem_disciplina"):
        return fallback or "Geral"
    obj = Subject.query.get(str(subject_id))
    if obj and getattr(obj, "name", None):
        return obj.name
    return fallback or "Geral"


def build_mapa_questoes_answer_sheet(
    user: dict,
    estado: str,
    municipio_id: str,
    gabarito_id: str,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    from app.routes.answer_sheet_evaluation_listing import (
        answer_sheet_target_classes_visible_for_user,
    )

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

    payload = empty_payload(
        estado, municipio_id, gabarito_id, escola_ids, serie_ids, turma_ids
    )
    payload["escopo"]["report_entity_type"] = "answer_sheet"

    gab = AnswerSheetGabarito.query.get(str(gabarito_id))
    if not gab:
        raise LookupError("Gabarito não encontrado")

    payload["avaliacao"]["nome"] = gab.title or ""

    serie_ids_norm = [str(x) for x in (serie_ids or [])]
    turma_ids_norm = [str(x) for x in (ensure_uuid_list(turma_ids) or turma_ids or [])]
    if turma_ids and not turma_ids_norm:
        turma_ids_norm = [str(x) for x in turma_ids]
    escola_ids_norm = [str(x) for x in (escola_ids or [])]

    classes = answer_sheet_target_classes_visible_for_user(gab, user, permissao, municipio_id)
    classes = _filter_classes(
        classes,
        escola_ids_norm or None,
        serie_ids_norm or None,
        turma_ids_norm or None,
    )
    class_ids = [c.id for c in classes]

    gab_map = _gabarito_answer_map(gab)
    question_numbers = sorted(gab_map.keys())
    blocks_config = getattr(gab, "blocks_config", None) or {}
    disciplinas_config = _disciplinas_config_from_gabarito_blocks(blocks_config)
    if not disciplinas_config:
        disciplinas_config = [
            {"id": "geral", "nome": "Geral", "question_numbers": question_numbers}
        ]
    q_to_subject = _question_num_to_subject_id(disciplinas_config, gab_map)
    nome_por_disciplina = {
        str(b["id"]): (b.get("nome") or "Outras") for b in disciplinas_config
    }

    q_skills = question_skills_map_for_answer_sheet(gab)
    skill_ids: Set[str] = set()
    for sids in q_skills.values():
        for sid in sids or []:
            skill_ids.add(str(sid))
    skills_db = _fetch_skills_batch(skill_ids)

    disciplinas_header: List[Dict[str, str]] = []
    seen_subj: Set[str] = set()
    for b in disciplinas_config:
        sid = str(b["id"])
        if sid in seen_subj:
            continue
        seen_subj.add(sid)
        disciplinas_header.append(
            {
                "id": sid,
                "nome": _resolve_subject_name(sid, nome_por_disciplina.get(sid, "Outras")),
            }
        )
    payload["avaliacao"]["disciplinas"] = disciplinas_header
    payload["metricas"]["total_questoes"] = len(question_numbers)

    if not question_numbers:
        return payload

    students = []
    result_by_student: Dict[Any, Any] = {}
    if class_ids:
        students, result_by_student, _ = resolve_participating_students_answer_sheet(
            gab, class_ids
        )
    n_alunos = len(students)
    payload["metricas"]["total_alunos_realizaram"] = n_alunos

    detected_by_student: Dict[Any, Dict[int, str]] = {}
    marked_letters: List[str] = []
    for st in students:
        r = result_by_student.get(st.id)
        det = _parse_detected(r.detected_answers if r else None)
        detected_by_student[st.id] = det
        marked_letters.extend([v for v in det.values() if v])

    letters = letters_for_answer_sheet(list(gab_map.values()), marked_letters)

    total_acertos = 0
    por_disciplina_map: Dict[str, Dict[str, Any]] = {}
    disciplina_ordem: List[str] = []

    for qn in question_numbers:
        gabarito = (gab_map.get(qn) or "").strip().upper() or None
        mark_counts: Dict[str, int] = {L: 0 for L in letters}
        mark_counts["sem_resposta"] = 0
        acertaram = 0

        for st in students:
            marked = (detected_by_student.get(st.id, {}).get(qn) or "").strip().upper()
            if not marked:
                mark_counts["sem_resposta"] += 1
            elif marked in mark_counts:
                mark_counts[marked] += 1
            else:
                mark_counts[marked] = mark_counts.get(marked, 0) + 1
            if gabarito and marked == gabarito:
                acertaram += 1
                total_acertos += 1

        disciplina_id = str(q_to_subject.get(qn) or "geral")
        disciplina_nome = _resolve_subject_name(
            disciplina_id, nome_por_disciplina.get(disciplina_id, "Geral")
        )
        if disciplina_id not in por_disciplina_map:
            disciplina_ordem.append(disciplina_id)
            por_disciplina_map[disciplina_id] = {
                "disciplina_id": disciplina_id,
                "disciplina": disciplina_nome,
                "questoes": [],
            }

        por_disciplina_map[disciplina_id]["questoes"].append(
            build_question_row(
                numero=qn,
                disciplina=disciplina_nome,
                disciplina_id=disciplina_id,
                habilidade=_skill_code_for_question(q_skills.get(qn) or [], skills_db),
                gabarito=gabarito,
                letters=letters,
                mark_counts=mark_counts,
                acertaram=acertaram,
                n_alunos=n_alunos,
            )
        )

    payload["metricas"]["media_acertos_percentual"] = media_acertos_percentual(
        total_acertos, n_alunos, len(question_numbers)
    )
    payload["por_disciplina"] = [por_disciplina_map[k] for k in disciplina_ordem]
    logger.info(
        "mapa_questoes answer_sheet gabarito=%s alunos=%s questoes=%s media=%s",
        gabarito_id,
        n_alunos,
        len(question_numbers),
        payload["metricas"]["media_acertos_percentual"],
    )
    return payload
