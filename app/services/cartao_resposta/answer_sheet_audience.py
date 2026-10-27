# -*- coding: utf-8 -*-
"""Público do cartão-resposta: turma inteira ou subturma ADAP 1, 2 ou 3.

O nível vem do gabarito: a série dele é "Suporte N" (etapa Educação Especial),
exibida como "ADAP N", e equivale a ``subturma.support_level = N``. Gabarito com
séries regulares gera para turmas inteiras; gabarito ADAP gera só para subturmas.

O recorte fica no scope_snapshot de cada geração (answer_sheet_generations):
chave ``subturma_ids`` e ``subturma_id`` em cada item de ``class_ids``.
Snapshot sem ``subturma_ids`` vale a turma inteira, como sempre foi.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

ADAP_CARTAO_LEVELS = (1, 2, 3)
PUBLICO_ADAP = "adap"
PUBLICO_REGULAR = "regular"
PUBLICO_MISTO = "misto"


class GenerationAudienceError(ValueError):
    """Recorte de geração inválido. ``code`` vai na resposta da API."""

    def __init__(self, message: str, code: str, details: Optional[list] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or []


def cartao_adap_label(grade_name: Any, class_name: Any, level: Any) -> str:
    """Ex.: 5º Ano A – ADAP 1."""
    base = " ".join(
        text for text in (str(grade_name or "").strip(), str(class_name or "").strip()) if text
    )
    tag = f"ADAP {int(level)}"
    return f"{base} – {tag}" if base else tag


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _as_uuid(value: Any) -> Optional[uuid.UUID]:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Série ADAP do gabarito
# ---------------------------------------------------------------------------

def adap_series_label(level: Any) -> str:
    """Nome exibido da série Suporte N."""
    return f"ADAP {int(level)}"


def adap_level_of_grade(grade: Any) -> Optional[int]:
    """
    Nível ADAP de uma série {id, name} do gabarito: "Suporte N" / "ADAP N".
    Série da etapa Educação Especial sem nível no nome não é aceita como ADAP.
    """
    from app.services.special_education import support_level_from_exact_grade_name

    if isinstance(grade, dict):
        name = grade.get("name")
    else:
        name = getattr(grade, "name", grade)
    return support_level_from_exact_grade_name(name)


def _grade_is_special(grade: Dict[str, Any]) -> bool:
    if adap_level_of_grade(grade) is not None:
        return True
    gid = grade.get("id") if isinstance(grade, dict) else None
    if not gid:
        return False
    try:
        from app.models.grades import Grade
        from app.services.special_education import is_adap_education_stage

        row = Grade.query.get(_as_uuid(gid) or gid)
        return bool(row is not None and is_adap_education_stage(row.education_stage_id))
    except Exception:
        return False


def validate_gabarito_grades(grades: Sequence[Dict[str, Any]]) -> Optional[int]:
    """
    Séries do cadastro. Educação Especial: uma única série ADAP, sem séries regulares.
    Devolve o nível ADAP ou None (gabarito regular).
    """
    rows = list(grades or [])
    special = [g for g in rows if _grade_is_special(g)]
    if not special:
        return None
    if len(rows) > 1:
        raise GenerationAudienceError(
            "Cartão de Educação Especial tem uma única série ADAP e não pode ter outras séries.",
            "gabarito_series_adap_invalida",
        )
    level = adap_level_of_grade(special[0])
    if level not in ADAP_CARTAO_LEVELS:
        raise GenerationAudienceError(
            "Série de Educação Especial sem nível ADAP. Use ADAP 1, ADAP 2 ou ADAP 3.",
            "gabarito_series_adap_invalida",
        )
    return level


def gabarito_adap_level(gabarito: Any) -> Optional[int]:
    """Nível ADAP do gabarito (série Suporte N única). Gabarito regular: None."""
    if gabarito is None:
        return None
    from app.services.cartao_resposta.gabarito_grades import get_gabarito_grades

    grades = get_gabarito_grades(gabarito)
    if len(grades) != 1:
        return None
    level = adap_level_of_grade(grades[0])
    return level if level in ADAP_CARTAO_LEVELS else None


# ---------------------------------------------------------------------------
# Opções do seletor
# ---------------------------------------------------------------------------

def adap_option_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    sub, class_obj, grade, school = row["subturma"], row["class"], row["grade"], row["school"]
    label = cartao_adap_label(grade.name, class_obj.name, sub.support_level)
    return {
        "id": str(sub.id),
        "subturma_id": str(sub.id),
        "class_id": str(class_obj.id),
        "name": label,
        "nome": label,
        "support_level": int(sub.support_level),
        "students_count": int(row["students_count"]),
        "shift": (class_obj.shift or "") if getattr(class_obj, "shift", None) else "",
        "serie_id": str(grade.id),
        "serie_nome": grade.name,
        "escola_id": str(class_obj.school_id) if class_obj.school_id else None,
        "escola_nome": school.name if school else None,
    }


def list_cartao_adap_options(
    *,
    school_ids: Optional[Sequence[Any]] = None,
    grade_ids: Optional[Sequence[Any]] = None,
    levels: Optional[Iterable[int]] = None,
    allowed_class_ids: Optional[Sequence[Any]] = None,
) -> List[Dict[str, Any]]:
    """Subturmas ADAP com aluno, em turma-mãe regular. levels None = 1, 2 e 3."""
    from app.services.subturma_options import list_subturma_rows

    wanted = [int(level) for level in (levels or ADAP_CARTAO_LEVELS) if int(level) in ADAP_CARTAO_LEVELS]
    if not wanted:
        return []
    rows = list_subturma_rows(
        grade_ids=grade_ids,
        school_ids=school_ids,
        allowed_class_ids=allowed_class_ids,
        levels=wanted,
        only_with_students=True,
        exclude_special_parent=True,
    )
    return [adap_option_payload(row) for row in rows]


# ---------------------------------------------------------------------------
# Geração
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdapSlice:
    """Uma subturma na geração: turma-mãe + subturma."""

    class_obj: Any
    subturma: Any
    grade_name: str
    students_count: int

    @property
    def class_id(self) -> str:
        return str(self.class_obj.id)

    @property
    def subturma_id(self) -> str:
        return str(self.subturma.id)

    @property
    def level(self) -> int:
        return int(self.subturma.support_level)

    @property
    def label(self) -> str:
        return cartao_adap_label(self.grade_name, self.class_obj.name, self.level)


def check_generation_subturmas(
    rows: Sequence[Dict[str, Any]],
    *,
    city_id: Any,
    expected_level: Optional[int] = None,
) -> int:
    """
    Regras puras sobre as linhas já carregadas. Devolve o nível único.

    Cada linha: subturma_id, level, school_city_id, parent_is_special, students_count, label.
    expected_level: nível da série ADAP do gabarito.
    """
    if not rows:
        raise GenerationAudienceError("Selecione ao menos uma subturma ADAP.", "subturma_required")
    outside = [row["label"] for row in rows if _norm(row.get("school_city_id")) != _norm(city_id)]
    if outside:
        raise GenerationAudienceError(
            "Uma ou mais subturmas ADAP não pertencem ao município.", "subturma_out_of_city", outside
        )
    invalid = [row["label"] for row in rows if row.get("level") not in ADAP_CARTAO_LEVELS]
    if invalid:
        raise GenerationAudienceError(
            "Nível ADAP inválido. Use ADAP 1, ADAP 2 ou ADAP 3.",
            "subturma_level_not_allowed",
            invalid,
        )
    if expected_level is not None:
        other = [row["label"] for row in rows if int(row["level"]) != int(expected_level)]
        if other:
            raise GenerationAudienceError(
                f"Este cartão é do ADAP {int(expected_level)}. Selecione só subturmas ADAP {int(expected_level)}.",
                "subturma_level_mismatch",
                other,
            )
    special = [row["label"] for row in rows if row.get("parent_is_special")]
    if special:
        raise GenerationAudienceError(
            "Turmas de série Suporte não entram no cartão. Use a subturma ADAP da turma regular.",
            "subturma_parent_special",
            special,
        )
    levels = sorted({int(row["level"]) for row in rows})
    if len(levels) > 1:
        raise GenerationAudienceError(
            "Cada nível ADAP é uma prova diferente. Gere cada nível separadamente.",
            "subturma_mixed_levels",
        )
    empty = [row["label"] for row in rows if int(row.get("students_count") or 0) == 0]
    if empty:
        raise GenerationAudienceError(
            "Uma ou mais subturmas ADAP não têm alunos.", "subturma_empty", empty
        )
    return levels[0]


def resolve_generation_subturmas(
    subturma_ids: Sequence[Any],
    *,
    city_id: Any,
    class_ids: Sequence[Any] = (),
    school_ids: Sequence[Any] = (),
    grade_ids: Sequence[Any] = (),
    expected_level: Optional[int] = None,
) -> List[AdapSlice]:
    """
    Valida o pedido de geração ADAP e devolve as fatias ordenadas por série e turma.
    grade_ids: só séries regulares (filtro das turmas-mãe); séries ADAP são ignoradas.
    """
    from sqlalchemy import func

    from app import db
    from app.models.grades import Grade
    from app.models.school import School
    from app.models.student import Student
    from app.models.studentClass import Class
    from app.models.subturma import Subturma
    from app.services.special_education import (
        is_adap_education_stage,
        support_level_from_exact_grade_name,
    )

    if class_ids:
        raise GenerationAudienceError(
            "Cartão de Educação Especial vai só para subturmas ADAP. Não envie turmas regulares.",
            "subturma_mixed_with_classes",
        )
    raw = [str(item).strip() for item in (subturma_ids or []) if str(item or "").strip()]
    uuids = [_as_uuid(item) for item in raw]
    if any(item is None for item in uuids) or len(set(raw)) != len(raw):
        raise GenerationAudienceError("Uma ou mais subturmas ADAP não foram encontradas.", "subturma_not_found")
    if not uuids:
        raise GenerationAudienceError("Selecione ao menos uma subturma ADAP.", "subturma_required")

    found = (
        db.session.query(Subturma, Class, Grade, School)
        .join(Class, Class.id == Subturma.class_id)
        .outerjoin(Grade, Grade.id == Class.grade_id)
        .outerjoin(School, School.id == Class.school_id)
        .filter(Subturma.id.in_(uuids))
        .all()
    )
    if len(found) != len(uuids):
        raise GenerationAudienceError("Uma ou mais subturmas ADAP não foram encontradas.", "subturma_not_found")

    counts = {
        str(sub_id): int(total)
        for sub_id, total in (
            db.session.query(Student.subturma_id, func.count(Student.id))
            .filter(Student.subturma_id.in_(uuids))
            .group_by(Student.subturma_id)
            .all()
        )
    }
    checks = []
    for sub, class_obj, grade, school in found:
        grade_name = (grade.name if grade else "") or ""
        checks.append({
            "subturma_id": str(sub.id),
            "level": int(sub.support_level),
            "school_city_id": getattr(school, "city_id", None),
            "parent_is_special": bool(
                grade is not None and (
                    is_adap_education_stage(getattr(grade, "education_stage_id", None))
                    or support_level_from_exact_grade_name(grade.name) is not None
                )
            ),
            "students_count": counts.get(str(sub.id), 0),
            "label": cartao_adap_label(grade_name, class_obj.name, sub.support_level),
        })
    check_generation_subturmas(checks, city_id=city_id, expected_level=expected_level)

    school_filter = {_norm(item) for item in school_ids or [] if item}
    grade_filter = {
        _norm(item) for item in grade_ids or []
        if item and not _grade_is_special({"id": item})
    }
    outside_filters = [
        check["label"]
        for check, (_, class_obj, _, _) in zip(checks, found)
        if (school_filter and _norm(class_obj.school_id) not in school_filter)
        or (grade_filter and _norm(class_obj.grade_id) not in grade_filter)
    ]
    if outside_filters:
        raise GenerationAudienceError(
            "Uma ou mais subturmas ADAP estão fora das escolas ou séries selecionadas.",
            "subturma_outside_filters",
            outside_filters,
        )

    slices = [
        AdapSlice(
            class_obj=class_obj,
            subturma=sub,
            grade_name=(grade.name if grade else "") or "",
            students_count=counts.get(str(sub.id), 0),
        )
        for sub, class_obj, grade, _ in found
    ]
    slices.sort(key=lambda item: (item.grade_name.upper(), (item.class_obj.name or "").upper(), item.class_id))
    return slices


def slice_students_query(class_id: Any, subturma_id: Any = None):
    """Alunos de uma turma; com subturma_id, só os daquela subturma."""
    from app.models.student import Student

    query = Student.query.filter(Student.class_id == class_id)
    if subturma_id:
        query = query.filter(Student.subturma_id == _as_uuid(subturma_id))
    return query


# ---------------------------------------------------------------------------
# Público do gabarito (a partir das gerações)
# ---------------------------------------------------------------------------

@dataclass
class GabaritoAudience:
    """
    restricted: turma -> subturmas permitidas. Turma fora de restricted vale inteira,
    exceto em gabarito só ADAP, em que o público é só quem está nas subturmas.
    """

    restricted: Dict[str, Set[str]] = field(default_factory=dict)
    whole: Set[str] = field(default_factory=set)
    levels: Set[int] = field(default_factory=set)

    @property
    def has_restrictions(self) -> bool:
        return bool(self.restricted)

    @property
    def publico(self) -> str:
        if not self.restricted:
            return PUBLICO_REGULAR
        if not self.whole:
            return PUBLICO_ADAP
        return PUBLICO_MISTO

    @property
    def subturma_ids(self) -> Set[str]:
        out: Set[str] = set()
        for subs in self.restricted.values():
            out |= subs
        return out

    def allows(self, class_id: Any, subturma_id: Any) -> bool:
        if not self.restricted:
            return True
        sub = _norm(subturma_id)
        if self.publico == PUBLICO_ADAP:
            return bool(sub) and sub in self.subturma_ids
        cid = _norm(class_id)
        if cid not in self.restricted:
            return True
        return bool(sub) and sub in self.restricted[cid]

    def student_criterion(self):
        """Filtro SQL sobre Student. None quando o gabarito não tem recorte ADAP."""
        if not self.restricted:
            return None
        from sqlalchemy import false, or_

        from app.models.student import Student

        subs = [item for item in (_as_uuid(s) for s in self.subturma_ids) if item]
        in_subs = Student.subturma_id.in_(subs) if subs else false()
        if self.publico == PUBLICO_ADAP:
            return in_subs
        restricted_classes = [item for item in (_as_uuid(c) for c in self.restricted) if item]
        return or_(~Student.class_id.in_(restricted_classes), in_subs)

    def apply(self, query):
        criterion = self.student_criterion()
        return query if criterion is None else query.filter(criterion)

    def filter_students(self, students: Iterable[Any]) -> List[Any]:
        """Mantém a ordem. Sem recorte devolve a lista como veio."""
        rows = [item for item in students if item is not None]
        if not self.restricted:
            return rows
        sub_by_student = _subturma_ids_of(rows)
        return [
            item for item in rows
            if self.allows(getattr(item, "class_id", None), sub_by_student.get(str(getattr(item, "id", ""))))
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "publico": self.publico,
            "adap_niveis": sorted(self.levels),
            "subturma_ids": sorted(self.subturma_ids),
        }


def _subturma_ids_of(students: Sequence[Any]) -> Dict[str, Optional[str]]:
    """subturma_id por aluno, sem disparar um lazy load por linha."""
    from app.models.student import Student

    out: Dict[str, Optional[str]] = {}
    pending = []
    for item in students:
        key = str(getattr(item, "id", "") or "")
        state = getattr(item, "_sa_instance_state", None)
        if state is None:
            out[key] = getattr(item, "subturma_id", None)
        elif "subturma_id" in state.dict:
            out[key] = state.dict.get("subturma_id")
        else:
            pending.append(item.id)
    if pending:
        for sid, sub in (
            Student.query.with_entities(Student.id, Student.subturma_id)
            .filter(Student.id.in_(pending))
            .all()
        ):
            out[str(sid)] = sub
    return {key: (str(value) if value else None) for key, value in out.items()}


def audience_from_snapshots(snapshots: Iterable[Any]) -> GabaritoAudience:
    """Regra pura: snapshot sem subturma_ids marca as turmas como inteiras."""
    audience = GabaritoAudience()
    for snap in snapshots or []:
        if not isinstance(snap, dict):
            continue
        entries = snap.get("class_ids") or []
        adap = bool(snap.get("subturma_ids"))
        for item in entries:
            if isinstance(item, dict):
                cid = _norm(item.get("class_id"))
                sub = _norm(item.get("subturma_id")) if adap else ""
                level = item.get("support_level")
            else:
                cid, sub, level = _norm(item), "", None
            if not cid:
                continue
            if sub:
                audience.restricted.setdefault(cid, set()).add(sub)
                try:
                    audience.levels.add(int(level))
                except (TypeError, ValueError):
                    pass
            else:
                audience.whole.add(cid)
    for cid in list(audience.restricted):
        if cid in audience.whole:
            del audience.restricted[cid]
    if not audience.restricted:
        audience.levels.clear()
    return audience


def gabarito_audience(gabarito_or_id: Any) -> GabaritoAudience:
    """Público do gabarito pelas gerações registradas. Sem geração: sem recorte."""
    gid = str(getattr(gabarito_or_id, "id", gabarito_or_id) or "").strip()
    if not gid:
        return GabaritoAudience()
    try:
        from app.services.cartao_resposta.answer_sheet_gabarito_generation import (
            AnswerSheetGabaritoGeneration,
        )

        rows = (
            AnswerSheetGabaritoGeneration.query.with_entities(AnswerSheetGabaritoGeneration.scope_snapshot)
            .filter_by(gabarito_id=gid)
            .all()
        )
    except Exception as exc:
        logger.warning("Público do gabarito %s: falha ao ler gerações: %s", gid, exc)
        return GabaritoAudience()
    return audience_from_snapshots(row[0] for row in rows)


def gabarito_audience_cached(gabarito_or_id: Any) -> GabaritoAudience:
    """gabarito_audience com cache por requisição (vários relatórios pedem o mesmo gabarito)."""
    gid = str(getattr(gabarito_or_id, "id", gabarito_or_id) or "").strip()
    if not gid:
        return GabaritoAudience()
    try:
        from flask import g, has_app_context

        if not has_app_context():
            return gabarito_audience(gid)
        cache = getattr(g, "_cartao_audience_cache", None)
        if cache is None:
            cache = {}
            g._cartao_audience_cache = cache
        if gid not in cache:
            cache[gid] = gabarito_audience(gid)
        return cache[gid]
    except Exception:
        return gabarito_audience(gid)


def apply_gabarito_audience(query, gabarito_or_id: Any):
    """Recorta uma query de Student pelo público do gabarito. Gabarito regular: query igual."""
    if not gabarito_or_id:
        return query
    return gabarito_audience_cached(gabarito_or_id).apply(query)


def filter_students_for_gabarito(students: Iterable[Any], gabarito_or_id: Any) -> List[Any]:
    """Mesma regra em lista já carregada. Gabarito regular: lista igual."""
    rows = list(students or [])
    if not gabarito_or_id:
        return rows
    audience = gabarito_audience_cached(gabarito_or_id)
    if not audience.has_restrictions:
        return rows
    return audience.filter_students(rows)


def check_generation_request(
    gabarito_level: Optional[int],
    *,
    subturma_ids: Sequence[Any] = (),
    class_ids: Sequence[Any] = (),
) -> None:
    """Gabarito ADAP N gera só para subturmas; gabarito regular nunca recebe subturmas."""
    if gabarito_level is None:
        if subturma_ids:
            raise GenerationAudienceError(
                "Este cartão é de séries regulares e não gera para subturmas ADAP. "
                "Cadastre um cartão de Educação Especial com a série ADAP.",
                "gabarito_regular_sem_subturmas",
            )
        return
    if class_ids:
        raise GenerationAudienceError(
            f"Este cartão é do ADAP {int(gabarito_level)}: vai só para as subturmas ADAP {int(gabarito_level)}, "
            "não para turmas regulares.",
            "gabarito_adap_sem_turmas",
        )
    if not subturma_ids:
        raise GenerationAudienceError(
            f"Selecione ao menos uma subturma ADAP {int(gabarito_level)}.", "subturma_required"
        )


def warn_if_student_outside_audience(gabarito: Any, student: Any, origem: str) -> None:
    """Só log. Não bloqueia a correção."""
    if gabarito is None or student is None:
        return
    try:
        from app.services.cartao_resposta.answer_sheet_gabarito_generation import (
            class_ids_union_all_generations,
        )

        target = {_norm(item) for item in class_ids_union_all_generations(str(gabarito.id))}
        if not target:
            return
        audience = gabarito_audience(gabarito)
        class_id = getattr(student, "class_id", None)
        sub = _subturma_ids_of([student]).get(str(getattr(student, "id", "")))
        dentro = audience.allows(class_id, sub) and (
            audience.publico == PUBLICO_ADAP or _norm(class_id) in target
        )
        if not dentro:
            logger.warning(
                "[CARTAO-PUBLICO] %s: aluno %s fora do público do gabarito %s (publico=%s, turma=%s, subturma=%s)",
                origem,
                getattr(student, "id", None),
                gabarito.id,
                audience.publico,
                class_id,
                sub,
            )
    except Exception as exc:
        logger.debug("Aviso de público do cartão não verificado: %s", exc)
