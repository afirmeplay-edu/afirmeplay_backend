# -*- coding: utf-8 -*-
"""
Médias de nota e proficiência com agregação hierárquica e peso igual entre unidades do mesmo nível:

- **Município**: média das médias **escolares** (cada escola calculada como abaixo).
- **Escola**: média das médias de **série**; cada série = média das médias de **turma**.
- **Série**: média das médias de **turma** (peso igual por turma).
- **Turma**: média dos **alunos**.

Objetos em ``results`` devem expor ``student_id``, ``grade`` e ``proficiency`` (AnswerSheetResult,
EvaluationResult ou SimpleNamespace equivalente).

Fallback: alunos sem turma/escola mapeável entram numa média simples global se não houver árvore.
"""
from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace

from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import joinedload

from app.models.student import Student
from app.models.studentClass import Class

Tree = Dict[str, Dict[str, Dict[str, List[Tuple[float, float]]]]]
Pair = Tuple[float, float]


def granularidade_to_hierarchical_target(nivel: Optional[str]) -> str:
    """
    Converte strings de nível de relatório/filtro (ex.: ``avaliacao``) para o
    ``target_level`` aceito por :func:`hierarchical_mean_grade_and_proficiency`.
    """
    if not nivel:
        return "municipio"
    n = str(nivel).strip().lower()
    mapping = {
        "municipio": "municipio",
        "escola": "escola",
        "serie": "serie",
        "turma": "turma",
        "avaliacao": "municipio",
        "estado": "municipio",
    }
    return mapping.get(n, "municipio")


def student_ids_to_school_id_map(student_ids: Sequence[str]) -> Dict[str, Optional[str]]:
    """Mapeia student.id -> school.id (string) ou None se não houver turma/escola."""
    if not student_ids:
        return {}
    uniq = list({str(x) for x in student_ids if x})
    if not uniq:
        return {}
    students = Student.query.filter(Student.id.in_(uniq)).all()
    class_ids = [s.class_id for s in students if s.class_id]
    if not class_ids:
        return {s.id: None for s in students}
    classes = {
        str(c.id): c for c in Class.query.filter(Class.id.in_(class_ids)).all()
    }
    out: Dict[str, Optional[str]] = {}
    for s in students:
        if not s.class_id:
            out[s.id] = None
            continue
        co = classes.get(str(s.class_id))
        out[s.id] = str(co.school_id) if co and co.school_id else None
    return out


def _mean_pair(pairs: List[Pair]) -> Pair:
    if not pairs:
        return 0.0, 0.0
    gs = [p[0] for p in pairs]
    ps = [p[1] for p in pairs]
    return sum(gs) / len(gs), sum(ps) / len(ps)


def _rollup_turma(pairs_by_class: Dict[str, List[Pair]]) -> Optional[Pair]:
    """Uma série: média das médias de turma (peso igual por turma)."""
    if not pairs_by_class:
        return None
    gms, pms = [], []
    for _cid, pairs in pairs_by_class.items():
        if not pairs:
            continue
        tg, tp = _mean_pair(pairs)
        gms.append(tg)
        pms.append(tp)
    if not gms:
        return None
    return sum(gms) / len(gms), sum(pms) / len(pms)


def _rollup_escola(grade_to_classes: Dict[str, Dict[str, List[Pair]]]) -> Optional[Pair]:
    """Uma escola: média das médias de série; cada série = média das turmas."""
    if not grade_to_classes:
        return None
    gmg, gmp = [], []
    for _gid, classes_map in grade_to_classes.items():
        rp = _rollup_turma(classes_map)
        if rp is None:
            continue
        gmg.append(rp[0])
        gmp.append(rp[1])
    if not gmg:
        return None
    return sum(gmg) / len(gmg), sum(gmp) / len(gmp)


def _rollup_municipio(tree: Tree) -> Optional[Pair]:
    """Município: média das médias escolares."""
    if not tree:
        return None
    smg, smp = [], []
    for _sch, grade_tree in tree.items():
        rp = _rollup_escola(grade_tree)
        if rp is None:
            continue
        smg.append(rp[0])
        smp.append(rp[1])
    if not smg:
        return None
    return sum(smg) / len(smg), sum(smp) / len(smp)


def _simple_mean_results(results: Sequence[Any]) -> Pair:
    if not results:
        return 0.0, 0.0
    gs = [float(getattr(r, "grade", None) or 0) for r in results]
    ps = [float(getattr(r, "proficiency", None) or 0) for r in results]
    return sum(gs) / len(gs), sum(ps) / len(ps)


def _build_school_grade_class_tree(
    results: Sequence[Any],
) -> Tree:
    """Monta árvore escola -> série -> turma -> [(nota, proficiência)]."""
    tree: Tree = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    ids = [str(getattr(r, "student_id", None)) for r in results if getattr(r, "student_id", None)]
    if not ids:
        return {}
    students = (
        Student.query.options(joinedload(Student.class_).joinedload(Class.grade))
        .filter(Student.id.in_(ids))
        .all()
    )
    by_stu = {str(s.id): s for s in students}
    for r in results:
        sid = getattr(r, "student_id", None)
        if not sid:
            continue
        g = float(getattr(r, "grade", None) or 0)
        p = float(getattr(r, "proficiency", None) or 0)
        st = by_stu.get(str(sid))
        if not st or not st.class_id:
            continue
        co = st.class_
        if not co:
            continue
        sch = str(co.school_id) if co.school_id else None
        if not sch:
            continue
        gid = str(co.grade_id) if co.grade_id else "_sem_serie"
        cid = str(co.id)
        tree[sch][gid][cid].append((g, p))
    return tree


def hierarchical_mean_grade_and_proficiency(
    results: Sequence[Any],
    target_level: str,
) -> Tuple[float, float]:
    """
    Agregação hierárquica conforme ``target_level``:

    - ``municipio``: média das escolas (cada escola = regra escola).
    - ``escola``: média das séries na escola (cada série = regra série).
    - ``serie``: média das turmas (cada turma = média dos alunos).
    - ``turma``: média dos alunos (uma ou mais turmas no recorte: se várias, média das médias de turma).

    ``target_level`` aceita aliases em inglês: municipality, school, grade, class.
    """
    if not results:
        return 0.0, 0.0
    tl = (target_level or "turma").strip().lower()
    aliases = {
        "municipality": "municipio",
        "city": "municipio",
        "school": "escola",
        "grade": "serie",
        "class": "turma",
        "series": "serie",
    }
    tl = aliases.get(tl, tl)
    if tl not in {"municipio", "escola", "serie", "turma"}:
        tl = "turma"

    tree = _build_school_grade_class_tree(results)

    if not tree:
        return _simple_mean_results(results)

    if tl == "municipio":
        out = _rollup_municipio(tree)
        if out is None:
            return _simple_mean_results(results)
        return out[0], out[1]

    if tl == "escola":
        if len(tree) == 1:
            only = next(iter(tree.values()))
            out = _rollup_escola(only)
            if out is None:
                return _simple_mean_results(results)
            return out[0], out[1]
        out = _rollup_municipio(tree)
        if out is None:
            return _simple_mean_results(results)
        return out[0], out[1]

    if tl == "serie":
        smg, smp = [], []
        for _sch, grade_tree in tree.items():
            if len(grade_tree) == 1:
                only_classes = next(iter(grade_tree.values()))
                rp = _rollup_turma(only_classes)
            else:
                rp = _rollup_escola(grade_tree)
            if rp is not None:
                smg.append(rp[0])
                smp.append(rp[1])
        if smg:
            return sum(smg) / len(smg), sum(smp) / len(smp)
        return _simple_mean_results(results)

    # turma: média dos alunos em cada turma; se várias turmas no recorte, média das médias de turma
    flat_classes: Dict[str, List[Pair]] = defaultdict(list)
    for _sch, grades in tree.items():
        for _gid, classes_map in grades.items():
            for cid, pairs in classes_map.items():
                flat_classes[cid].extend(pairs)
    if not flat_classes:
        return _simple_mean_results(results)
    gms, pms = [], []
    for _cid, pairs in flat_classes.items():
        if not pairs:
            continue
        tg, tp = _mean_pair(pairs)
        gms.append(tg)
        pms.append(tp)
    if not gms:
        return _simple_mean_results(results)
    return sum(gms) / len(gms), sum(pms) / len(pms)


def mean_grade_and_proficiency_equal_weight_by_school(
    results: Sequence[Any],
) -> Tuple[float, float]:
    """
    Compatibilidade: delega para agregação hierárquica em nível município
    (média das escolas, cada escola com série/turma/alunos conforme regra global).
    """
    return hierarchical_mean_grade_and_proficiency(results, "municipio")


def hierarchical_mean_from_subject_rows(
    subject_rows: List[Dict[str, Any]],
    target_level: str,
    student_id_key: str = "student_id",
) -> Tuple[float, float, float]:
    """
    Mesma hierarquia que ``hierarchical_mean_grade_and_proficiency``, a partir de dicts
    com grade, proficiency e score_percentage. A árvore de escopo usa ``student_id``;
    o score segue a mesma estrutura (valores replicados em grade/proficiência internos
    só para reaproveitar o rollup).
    """
    if not subject_rows:
        return 0.0, 0.0, 0.0
    ns_gp: List[Any] = []
    ns_sp: List[Any] = []
    for row in subject_rows:
        sid = row.get(student_id_key)
        if not sid:
            continue
        g = float(row.get("grade") or 0)
        p = float(row.get("proficiency") or 0)
        sp = float(row.get("score_percentage") or 0)
        ns_gp.append(SimpleNamespace(student_id=sid, grade=g, proficiency=p))
        ns_sp.append(SimpleNamespace(student_id=sid, grade=sp, proficiency=sp))
    if not ns_gp:
        return 0.0, 0.0, 0.0
    mg, mp = hierarchical_mean_grade_and_proficiency(ns_gp, target_level)
    msp, _ = hierarchical_mean_grade_and_proficiency(ns_sp, target_level)
    return mg, mp, msp


def mean_grade_and_proficiency_equal_weight_by_school_from_subject_rows(
    subject_rows: List[Dict[str, Any]],
    student_id_key: str = "student_id",
) -> Tuple[float, float, float]:
    """
    subject_rows: lista de dicts com student_id, grade, proficiency (e opcionalmente score_percentage).
    Retorna (avg_grade, avg_proficiency, avg_score_pct) com agregação hierárquica municipal.
    """
    return hierarchical_mean_from_subject_rows(subject_rows, "municipio", student_id_key=student_id_key)
