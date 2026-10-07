# -*- coding: utf-8 -*-
"""Pareamento ADAP ↔ regular e escolha do resultado válido (menu Resultados).

Ativado só quando o cliente envia o parâmetro ``alunos``. Sem o parâmetro,
ou sem vínculos ``paired_regular_test_id``, o comportamento permanece o de sempre.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from app.services.special_education import (
    SpecialEducationStatus,
    is_special_education_many,
)

logger = logging.getLogger(__name__)

# Ranking: ADAP 1/2 ficam de fora. Troque para True para incluí-los no ranking.
ADAP_INCLUDED_IN_RANKING = False

_ADAP_LEVELS = (1, 2)

_ADAP_TITLE_RE = re.compile(
    r"^adap\s*(i{1,3}|[123])\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AdapValidResult:
    """Resultado válido de um aluno ADAP 1/2 para uma prova regular."""

    student_id: str
    level: int
    source_test_id: Optional[str]
    source_test_title: Optional[str]
    result: Any  # EvaluationResult ou None
    situation: str  # "participou" | "pendente"
    from_adap_test: bool


def fold_title(value: Any) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").strip().lower()


def is_adap_test_title(title: Any) -> bool:
    return bool(_ADAP_TITLE_RE.match(fold_title(title)))


def parse_adap_level_from_title(title: Any) -> Optional[int]:
    text = fold_title(title)
    match = _ADAP_TITLE_RE.match(text)
    if not match:
        return None
    token = match.group(1).lower()
    if token.isdigit():
        level = int(token)
        return level if level in (1, 2, 3) else None
    roman = {"i": 1, "ii": 2, "iii": 3}
    return roman.get(token)


def strip_adap_prefix(title: Any) -> str:
    """Remove o prefixo ADAP I/II/III do título para casar com a regular."""
    text = str(title or "").strip()
    folded = fold_title(text)
    match = _ADAP_TITLE_RE.match(folded)
    if not match:
        return text
    # Corta o prefixo no original pela mesma extensão aproximada
    raw = re.sub(
        r"^\s*adap\s*(i{1,3}|[123])\s*[-–—:]?\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    return raw.strip(" -–—:\t")


def extract_pairing_key(title: Any) -> Optional[Tuple[Optional[int], Optional[str], Optional[int], str]]:
    """
    Chave de pareamento: (ano, disciplina LP/MAT/None, nº avaliação, título normalizado sem ADAP).

    Disciplina None = prova única (várias matérias no mesmo título).
    """
    base = strip_adap_prefix(title) if is_adap_test_title(title) else str(title or "").strip()
    folded = fold_title(base)
    if not folded:
        return None

    ano = None
    ano_m = re.search(r"(\d+)\s*[ºo°]?\s*ano", folded)
    if ano_m:
        ano = int(ano_m.group(1))

    disc = None
    if re.search(r"\b(lp|lingua\s*portuguesa|portugues)\b", folded):
        disc = "LP"
    elif re.search(r"\b(mat|matematica)\b", folded):
        disc = "MAT"

    avaliacao = None
    av_m = re.search(r"(\d+)\s*[ºo°]?\s*avalia", folded)
    if av_m:
        avaliacao = int(av_m.group(1))

    # Normaliza espaços e hífens para comparação
    norm = re.sub(r"[\s\-–—:/]+", " ", folded).strip()
    return (ano, disc, avaliacao, norm)


def choose_valid_evaluation_result(
    regular_result: Any,
    adap_results: Sequence[Any],
) -> Any:
    """
    Regra do gestor: maior nota; empate → maior proficiência; empate → prova ADAP.

    Recebe objetos com ``grade``, ``proficiency`` e opcionalmente ``test_id``.
    Não recalcula nota.
    """
    candidates: List[Tuple[Any, bool]] = []
    if regular_result is not None:
        candidates.append((regular_result, False))
    for item in adap_results or []:
        if item is not None:
            candidates.append((item, True))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0][0]

    def sort_key(pair: Tuple[Any, bool]):
        result, from_adap = pair
        grade = float(getattr(result, "grade", None) or 0.0)
        prof = float(getattr(result, "proficiency", None) or 0.0)
        # Maior nota/prof; em empate total, ADAP vence (from_adap=True → 1)
        return (grade, prof, 1 if from_adap else 0)

    return max(candidates, key=sort_key)[0]


def adap_students_level_12(students: Sequence[Any]) -> Dict[str, SpecialEducationStatus]:
    """Alunos ADAP nível 1 ou 2 no universo (subturma ou série)."""
    rows = [s for s in students if s is not None]
    if not rows:
        return {}
    statuses = is_special_education_many(rows)
    out: Dict[str, SpecialEducationStatus] = {}
    for student in rows:
        key = str(getattr(student, "id", "") or "")
        if not key:
            continue
        status = statuses.get(key) or SpecialEducationStatus(False, None, None)
        if status.is_special and status.level in _ADAP_LEVELS:
            out[key] = status
    return out


def find_paired_adap_tests(regular_test_id: str) -> List[Any]:
    """Provas ADAP com ``paired_regular_test_id`` apontando para a regular."""
    if not regular_test_id:
        return []
    try:
        from app.models.test import Test

        if not hasattr(Test, "paired_regular_test_id"):
            return []
        return (
            Test.query.filter(Test.paired_regular_test_id == str(regular_test_id)).all()
        )
    except Exception as exc:
        logger.warning(
            "Pareamento ADAP: falha ao buscar provas pareadas de %s: %s",
            regular_test_id,
            exc,
        )
        return []


def resolve_adap_valid_results(
    regular_test_id: str,
    students: Sequence[Any],
    *,
    regular_results_by_student: Optional[Dict[str, Any]] = None,
) -> Dict[str, AdapValidResult]:
    """
    Para cada aluno ADAP 1/2 do universo, devolve o resultado válido
    (regular vs provas ADAP pareadas) e a origem.
    """
    adap_map = adap_students_level_12(students)
    if not adap_map:
        return {}

    paired_tests = find_paired_adap_tests(regular_test_id)
    paired_by_id = {str(t.id): t for t in paired_tests}
    paired_ids = list(paired_by_id.keys())

    regular_by = {
        str(k): v for k, v in (regular_results_by_student or {}).items() if k is not None
    }
    student_ids = list(adap_map.keys())

    adap_results_by_student: Dict[str, List[Any]] = {sid: [] for sid in student_ids}
    if paired_ids and student_ids:
        try:
            from app.models.evaluationResult import EvaluationResult

            rows = (
                EvaluationResult.query.filter(
                    EvaluationResult.test_id.in_(paired_ids),
                    EvaluationResult.student_id.in_(student_ids),
                ).all()
            )
            for row in rows:
                sid = str(row.student_id)
                if sid in adap_results_by_student:
                    adap_results_by_student[sid].append(row)
        except Exception as exc:
            logger.warning(
                "Pareamento ADAP: falha ao carregar evaluation_results pareados: %s",
                exc,
            )

    out: Dict[str, AdapValidResult] = {}
    for sid, status in adap_map.items():
        regular_er = regular_by.get(sid)
        adap_ers = adap_results_by_student.get(sid) or []
        chosen = choose_valid_evaluation_result(regular_er, adap_ers)
        if chosen is None:
            out[sid] = AdapValidResult(
                student_id=sid,
                level=int(status.level or 0),
                source_test_id=None,
                source_test_title=None,
                result=None,
                situation="pendente",
                from_adap_test=False,
            )
            continue
        chosen_tid = str(getattr(chosen, "test_id", "") or "")
        from_adap = chosen_tid in paired_by_id
        title = None
        if from_adap:
            title = getattr(paired_by_id.get(chosen_tid), "title", None)
        else:
            try:
                from app.models.test import Test

                reg = Test.query.get(regular_test_id)
                title = getattr(reg, "title", None) if reg else None
            except Exception:
                title = None
        out[sid] = AdapValidResult(
            student_id=sid,
            level=int(status.level or 0),
            source_test_id=chosen_tid or None,
            source_test_title=title,
            result=chosen,
            situation="participou",
            from_adap_test=from_adap,
        )
    return out


def merge_results_with_adap_valid(
    results: Sequence[Any],
    adap_valid: Dict[str, AdapValidResult],
) -> List[Any]:
    """
    Substitui/insere o resultado válido ADAP no conjunto usado pelas estatísticas.

    Aluno regular com resultado em prova ADAP não é afetado (só chaves em adap_valid).
    """
    by_sid: Dict[str, Any] = {}
    for row in results or []:
        sid = str(getattr(row, "student_id", "") or "")
        if not sid:
            continue
        prev = by_sid.get(sid)
        if prev is None:
            by_sid[sid] = row
            continue
        # Preferir o mais recente se houver duplicata no mesmo conjunto
        r_ca = getattr(row, "calculated_at", None)
        p_ca = getattr(prev, "calculated_at", None)
        if r_ca and (p_ca is None or r_ca > p_ca):
            by_sid[sid] = row

    for sid, info in (adap_valid or {}).items():
        if info.result is not None:
            by_sid[sid] = info.result
        elif sid in by_sid:
            # Pendente: não pode contar resultado antigo inválido
            del by_sid[sid]

    return list(by_sid.values())


def protect_adap_ids_in_roster(
    roster_ids: Set[str],
    adap_student_ids: Iterable[str],
) -> Set[str]:
    """Garante que ADAP 1/2 da turma atual não saiam do universo."""
    merged = set(roster_ids or set())
    for sid in adap_student_ids or []:
        if sid:
            merged.add(str(sid))
    return merged


def build_tabela_adap_rows(
    students_by_id: Dict[str, Any],
    adap_valid: Dict[str, AdapValidResult],
) -> List[Dict[str, Any]]:
    """Payload do bloco ``tabela_adap`` (só ADAP 1/2)."""
    rows: List[Dict[str, Any]] = []
    for sid, info in sorted(
        (adap_valid or {}).items(),
        key=lambda item: (
            getattr(students_by_id.get(item[0]), "name", "") or "",
            item[0],
        ),
    ):
        student = students_by_id.get(sid)
        turma = ""
        if student is not None and getattr(student, "class_", None) is not None:
            turma = getattr(student.class_, "name", None) or ""
        elif student is not None:
            classe = getattr(student, "class_", None)
            if classe is not None:
                turma = getattr(classe, "name", None) or ""
        result = info.result
        rows.append(
            {
                "id": sid,
                "nome": (getattr(student, "name", None) or "") if student else "",
                "nivel": info.level,
                "rotulo": f"ADAP {info.level}",
                "turma": turma,
                "prova_origem_id": info.source_test_id,
                "prova_origem_titulo": info.source_test_title,
                "acertos": int(getattr(result, "correct_answers", 0) or 0) if result else None,
                "total_questoes": int(getattr(result, "total_questions", 0) or 0) if result else None,
                "nota": float(getattr(result, "grade", 0) or 0) if result else None,
                "proficiencia": float(getattr(result, "proficiency", 0) or 0) if result else None,
                "classificacao": getattr(result, "classification", None) if result else None,
                "situacao": info.situation,
            }
        )
    return rows


def enrich_pendentes_com_marca_adap(
    pendentes: Sequence[Dict[str, Any]],
    adap_valid: Dict[str, AdapValidResult],
) -> List[Dict[str, Any]]:
    """Acrescenta campos opcionais sem remover os existentes."""
    out: List[Dict[str, Any]] = []
    for row in pendentes or []:
        item = dict(row)
        sid = str(item.get("id") or "")
        info = adap_valid.get(sid) if sid else None
        if info is not None:
            item["adap_nivel"] = info.level
            item["adap_rotulo"] = f"ADAP {info.level}"
        out.append(item)
    return out


def filter_ranking_excluding_adap(
    ranking: Sequence[Dict[str, Any]],
    adap_student_ids: Set[str],
) -> List[Dict[str, Any]]:
    if ADAP_INCLUDED_IN_RANKING:
        return list(ranking or [])
    if not adap_student_ids:
        return list(ranking or [])
    return [
        row
        for row in (ranking or [])
        if str(row.get("id") or "") not in adap_student_ids
    ]


def scope_wants_adap_pareamento(scope_info: Optional[dict]) -> bool:
    """True só quando Resultados enviou o parâmetro alunos (flag no scope)."""
    if not isinstance(scope_info, dict):
        return False
    return bool(scope_info.get("adap_pareamento"))


def _placement_from_student(student: Any) -> Optional[Dict[str, Any]]:
    class_id = getattr(student, "class_id", None) if student is not None else None
    if class_id is None:
        return None
    cls = getattr(student, "class_", None)
    school_id = getattr(cls, "school_id", None) if cls is not None else None
    grade_id = getattr(cls, "grade_id", None) if cls is not None else None
    if not school_id or grade_id is None:
        return None
    return {
        "school_id_snapshot": school_id,
        "class_id_snapshot": class_id,
        "grade_id_snapshot": grade_id,
    }


def _placement_from_snapshot(result: Any) -> Optional[Dict[str, Any]]:
    if result is None or not getattr(result, "school_id_snapshot", None):
        return None
    return {
        "school_id_snapshot": getattr(result, "school_id_snapshot", None),
        "class_id_snapshot": getattr(result, "class_id_snapshot", None),
        "grade_id_snapshot": getattr(result, "grade_id_snapshot", None),
    }


def project_result_onto_regular_test(
    result: Any, regular_test_id: str, student: Any = None, regular_result: Any = None
) -> Any:
    """
    Mantém nota/proficiência gravadas; se veio da prova ADAP, expõe test_id da regular
    para estatísticas/grupo virtual (sem regravar no banco).

    Escola/turma/série: turma atual do aluno; sem turma atual, a do resultado dele na
    prova regular; só então o snapshot da prova ADAP. O snapshot ADAP aponta para a
    turma de Suporte, que viraria uma série à parte na média hierárquica da regular.
    """
    if result is None:
        return None
    if str(getattr(result, "test_id", "") or "") == str(regular_test_id):
        return result
    from types import SimpleNamespace

    placement = (
        _placement_from_student(student)
        or _placement_from_snapshot(regular_result)
        or {
            "school_id_snapshot": getattr(result, "school_id_snapshot", None),
            "class_id_snapshot": getattr(result, "class_id_snapshot", None),
            "grade_id_snapshot": getattr(result, "grade_id_snapshot", None),
        }
    )
    return SimpleNamespace(
        id=getattr(result, "id", None),
        test_id=str(regular_test_id),
        student_id=getattr(result, "student_id", None),
        correct_answers=getattr(result, "correct_answers", 0),
        total_questions=getattr(result, "total_questions", 0),
        score_percentage=getattr(result, "score_percentage", 0),
        grade=getattr(result, "grade", 0),
        proficiency=getattr(result, "proficiency", 0),
        classification=getattr(result, "classification", None),
        subject_results=getattr(result, "subject_results", None),
        school_id_snapshot=placement["school_id_snapshot"],
        class_id_snapshot=placement["class_id_snapshot"],
        grade_id_snapshot=placement["grade_id_snapshot"],
        enrollment_id_snapshot=getattr(result, "enrollment_id_snapshot", None),
        calculated_at=getattr(result, "calculated_at", None),
        _adap_source_test_id=str(getattr(result, "test_id", "") or ""),
    )


def apply_pareamento_to_universe(
    regular_test_id: str,
    students: Sequence[Any],
    results: Sequence[Any],
) -> Tuple[List[Any], List[Any], Dict[str, AdapValidResult]]:
    """
    Protege ADAP 1/2 no roster, resolve resultado válido e devolve
    (students, results_efetivos, adap_valid).
    """
    students_list = list(students or [])
    results_list = list(results or [])
    try:
        adap_map = adap_students_level_12(students_list)
        if not adap_map and not find_paired_adap_tests(regular_test_id):
            return students_list, results_list, {}

        regular_by = {}
        for row in results_list:
            sid = str(getattr(row, "student_id", "") or "")
            if not sid:
                continue
            if str(getattr(row, "test_id", "") or "") != str(regular_test_id):
                continue
            prev = regular_by.get(sid)
            if prev is None:
                regular_by[sid] = row
                continue
            r_ca = getattr(row, "calculated_at", None)
            p_ca = getattr(prev, "calculated_at", None)
            if r_ca and (p_ca is None or r_ca > p_ca):
                regular_by[sid] = row

        adap_valid = resolve_adap_valid_results(
            regular_test_id,
            students_list,
            regular_results_by_student=regular_by,
        )
        if not adap_valid:
            return students_list, results_list, {}

        # Remover resultados da regular só dos ADAP (serão substituídos pelo válido)
        adap_ids = set(adap_valid.keys())
        kept = [
            row
            for row in results_list
            if str(getattr(row, "student_id", "") or "") not in adap_ids
        ]
        students_by_id = {str(getattr(s, "id", "") or ""): s for s in students_list}
        for sid, info in adap_valid.items():
            if info.result is None:
                continue
            kept.append(
                project_result_onto_regular_test(
                    info.result,
                    regular_test_id,
                    students_by_id.get(str(sid)),
                    regular_by.get(str(sid)),
                )
            )
        return students_list, kept, adap_valid
    except Exception as exc:
        logger.warning(
            "Pareamento ADAP: falha ao aplicar no universo da prova %s: %s",
            regular_test_id,
            exc,
            exc_info=True,
        )
        return students_list, results_list, {}
