# -*- coding: utf-8 -*-
"""
Monta o payload de relatório (cartão-resposta) compatível com o consumo de /reports/dados-json.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload

from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.city import City
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.teacherClass import TeacherClass
from app.routes.report_routes import _load_default_logo
from app.services.ai_analysis_service import AIAnalysisService
from app.utils.decimal_helpers import round_to_two_decimals


def _norm_skill_uuid_key(sid: str) -> str:
    from uuid import UUID

    try:
        return str(UUID(str(sid).strip()))
    except ValueError:
        return str(sid).strip()


def _fetch_skill_code_description_by_ids(skill_ids: List[str]) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """Busca code e description em public.skills para os UUIDs usados na topologia."""
    from uuid import UUID

    from app.models.skill import Skill

    uuids = []
    for raw in skill_ids:
        if not raw:
            continue
        try:
            uuids.append(UUID(str(raw).strip()))
        except ValueError:
            continue
    if not uuids:
        return {}
    rows = Skill.query.filter(Skill.id.in_(uuids)).all()
    return {str(sk.id): (sk.code, sk.description) for sk in rows}


def _correct_answers_int_keys(gabarito: AnswerSheetGabarito) -> Dict[int, Any]:
    raw = gabarito.correct_answers
    if isinstance(raw, str):
        import json

        raw = json.loads(raw) or {}
    out: Dict[int, Any] = {}
    for k, v in (raw or {}).items():
        try:
            out[int(k)] = v
        except (TypeError, ValueError):
            continue
    return out


def answer_sheet_total_question_count(gabarito: AnswerSheetGabarito) -> int:
    """
    Total de questões do cartão: alinha num_questions, chaves do gabarito e topologia
    (evita listar só o subconjunto da topology quando há duplicatas ou buracos).
    """
    n = int(gabarito.num_questions or 0)
    correct = _correct_answers_int_keys(gabarito)
    if correct:
        n = max(n, max(correct.keys()))
    cfg = gabarito.blocks_config or {}
    topo = cfg.get("topology") or {}
    blocks = topo.get("blocks") or []
    flat_n = 0
    explicit_max = 0
    for block in blocks:
        for q in block.get("questions") or []:
            flat_n += 1
            raw = q.get("q")
            if raw is None:
                raw = q.get("numero")
            if raw is not None:
                try:
                    explicit_max = max(explicit_max, int(raw))
                except (TypeError, ValueError):
                    pass
    return max(n, explicit_max, flat_n)


def ordered_question_numbers_for_gabarito(gabarito: AnswerSheetGabarito) -> List[int]:
    """Lista 1..N como nas avaliações em prova (N = total de questões do gabarito)."""
    n = answer_sheet_total_question_count(gabarito)
    if n <= 0:
        return []
    return list(range(1, n + 1))


def _question_skills_map_from_gabarito(gabarito: AnswerSheetGabarito) -> Dict[int, List[str]]:
    """
    Mapeia número da questão -> IDs de habilidade na ordem da topologia (blocos/questões).
    Se faltar q/numero, usa a posição sequencial na folha (1..) como nas avaliações normais.
    Duas entradas com o mesmo número de questão unificam as habilidades sem sobrescrever.
    """
    out: Dict[int, List[str]] = {}
    cfg = gabarito.blocks_config or {}
    topo = cfg.get("topology") or {}
    blocks = topo.get("blocks") or []
    flat_index = 0

    def _merge_skills(qn: int, skills: List[Any]) -> None:
        skill_strs = [str(s) for s in (skills or []) if s]
        if not skill_strs:
            return
        if qn not in out:
            out[qn] = list(skill_strs)
            return
        seen = set(out[qn])
        for s in skill_strs:
            if s not in seen:
                out[qn].append(s)
                seen.add(s)

    for block in blocks:
        for q in block.get("questions") or []:
            flat_index += 1
            raw_q = q.get("q")
            if raw_q is None:
                raw_q = q.get("numero")
            if raw_q is not None:
                try:
                    qn = int(raw_q)
                except (TypeError, ValueError):
                    qn = flat_index
            else:
                qn = flat_index
            _merge_skills(qn, q.get("skills") or [])

    return out


def _fetch_results_scoped(
    gabarito_id: str, scope_type: str, scope_ref_id: Optional[str]
) -> List[AnswerSheetResult]:
    q = (
        AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
        .options(
            joinedload(AnswerSheetResult.student).joinedload(Student.class_).joinedload(Class.grade)
        )
    )
    if scope_type == "city" and scope_ref_id:
        q = (
            q.join(Student, AnswerSheetResult.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .join(School, Class._school_id == School.id)
            .filter(School.city_id == scope_ref_id)
        )
    elif scope_type == "school" and scope_ref_id:
        q = (
            q.join(Student, AnswerSheetResult.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .filter(Class._school_id == scope_ref_id)
        )
    elif scope_type == "teacher" and scope_ref_id:
        tcs = TeacherClass.query.filter_by(teacher_id=scope_ref_id).all()
        cids = [tc.class_id for tc in tcs]
        if not cids:
            return []
        q = q.join(Student, AnswerSheetResult.student_id == Student.id).filter(
            Student.class_id.in_(cids)
        )
    # overall: sem join extra (todo o tenant)
    rows = q.all()
    return list({r.id: r for r in rows}.values())


def _class_ids_from_answer_sheet_results(gabarito_id: str) -> Set[str]:
    q = (
        db.session.query(Student.class_id)
        .join(AnswerSheetResult, AnswerSheetResult.student_id == Student.id)
        .filter(AnswerSheetResult.gabarito_id == gabarito_id)
        .distinct()
    )
    return {str(row[0]) for row in q.all() if row[0] is not None}


def _resolve_target_class_ids(
    gab: AnswerSheetGabarito,
    report_scope_type: str,
    report_scope_ref_id: Optional[str],
) -> List[str]:
    """
    Turmas que fazem parte do cartão (histórico de geração + metadados do gabarito),
    filtradas pelo escopo do relatório (city/school/teacher/overall).

    Se houver escopo explícito de geração (scope_snapshot ou batch com turmas), não expande
    escola/série/cidade inteiras — apenas o que foi gerado (+ turmas com resultado).
    Sem isso, mantém o comportamento legado (expansão por scope_type do gabarito).
    """
    ids_snapshot: Set[str] = set()
    try:
        from app.services.cartao_resposta.answer_sheet_gabarito_generation import (
            AnswerSheetGabaritoGeneration,
        )

        row = (
            AnswerSheetGabaritoGeneration.query.filter_by(gabarito_id=str(gab.id))
            .order_by(desc(AnswerSheetGabaritoGeneration.created_at))
            .first()
        )
        if row and row.scope_snapshot and isinstance(row.scope_snapshot, dict):
            raw = row.scope_snapshot.get("class_ids") or []
            for item in raw:
                if isinstance(item, dict) and item.get("class_id"):
                    ids_snapshot.add(str(item["class_id"]))
                elif isinstance(item, str) and item:
                    ids_snapshot.add(item)
    except Exception:
        pass

    ids_batch: Set[str] = set()
    if gab.batch_id:
        others = (
            AnswerSheetGabarito.query.filter(
                AnswerSheetGabarito.batch_id == gab.batch_id,
                AnswerSheetGabarito.class_id.isnot(None),
            ).all()
        )
        for o in others:
            ids_batch.add(str(o.class_id))

    ids_results = _class_ids_from_answer_sheet_results(str(gab.id))

    ids_gab: Set[str] = set()
    if gab.class_id:
        ids_gab.add(str(gab.class_id))

    explicit_generation_scope = bool(ids_snapshot) or bool(ids_batch)

    ids: Set[str] = set()
    ids |= ids_snapshot
    ids |= ids_batch
    ids |= ids_results
    ids |= ids_gab

    if not explicit_generation_scope:
        st = (gab.scope_type or "").lower()
        if st == "school" and gab.school_id:
            for c in Class.query.filter(Class.school_id == gab.school_id).all():
                ids.add(str(c.id))
        elif st == "grade" and gab.school_id and gab.grade_id:
            for c in Class.query.filter(
                Class.school_id == gab.school_id,
                Class.grade_id == gab.grade_id,
            ).all():
                ids.add(str(c.id))
        elif st == "city" and report_scope_ref_id:
            school_ids = [
                s[0]
                for s in db.session.query(School.id)
                .filter(School.city_id == report_scope_ref_id)
                .all()
            ]
            if school_ids:
                for c in Class.query.filter(Class.school_id.in_(school_ids)).all():
                    ids.add(str(c.id))

    filtered: List[Class] = []
    rtype = (report_scope_type or "overall").lower()
    from uuid import UUID

    for cid in ids:
        try:
            uid = UUID(str(cid))
        except ValueError:
            continue
        co = Class.query.get(uid)
        if not co:
            continue
        if rtype == "school" and report_scope_ref_id:
            if str(co.school_id) != str(report_scope_ref_id):
                continue
        elif rtype == "city" and report_scope_ref_id:
            sch = co.school
            if not sch or str(sch.city_id) != str(report_scope_ref_id):
                continue
        elif rtype == "teacher" and report_scope_ref_id:
            tcs = TeacherClass.query.filter_by(teacher_id=report_scope_ref_id).all()
            allowed = {str(tc.class_id) for tc in tcs}
            if str(co.id) not in allowed:
                continue
        filtered.append(co)

    by_id = {str(c.id): c for c in filtered}

    def sort_key(c: Class) -> Tuple[str, str, str]:
        g = (c.grade.name if c.grade else "") or ""
        return (g.upper(), (c.name or "").upper(), str(c.id))

    ordered = sorted(by_id.values(), key=sort_key)
    return [str(c.id) for c in ordered]


def _load_classes_ordered(class_ids: List[str]) -> List[Class]:
    from uuid import UUID

    if not class_ids:
        return []
    uuids = []
    for x in class_ids:
        try:
            uuids.append(UUID(str(x)))
        except ValueError:
            continue
    if not uuids:
        return []
    rows = (
        Class.query.options(joinedload(Class.grade))
        .filter(Class.id.in_(uuids))
        .all()
    )
    by_id = {str(c.id): c for c in rows}
    return [by_id[i] for i in class_ids if i in by_id]


def get_answer_sheet_target_classes_for_report(
    gab: AnswerSheetGabarito,
    report_scope_type: str,
    report_scope_ref_id: Optional[str],
) -> List[Class]:
    """Turmas-alvo do cartão para o escopo do relatório (listagens / PDF / detalhe)."""
    ids = _resolve_target_class_ids(gab, report_scope_type, report_scope_ref_id)
    return _load_classes_ordered(ids)


def _student_count_by_class(class_ids: List[Any]) -> Dict[str, int]:
    if not class_ids:
        return {}
    rows = (
        db.session.query(Student.class_id, func.count(Student.id))
        .filter(Student.class_id.in_(class_ids))
        .group_by(Student.class_id)
        .all()
    )
    return {str(row[0]): int(row[1]) for row in rows if row[0] is not None}


def _school_name_map_from_ids(school_ids: Set[str]) -> Dict[str, str]:
    ids = {x for x in school_ids if x and x != "_sem_escola"}
    if not ids:
        return {}
    rows = School.query.filter(School.id.in_(ids)).all()
    return {str(s.id): (s.name.strip() if s.name else "Escola") for s in rows}


def _question_subject_name_by_num(gabarito: AnswerSheetGabarito) -> Dict[int, str]:
    """Número da questão -> nome da disciplina (bloco na topology)."""
    out: Dict[int, str] = {}
    cfg = gabarito.blocks_config or {}
    topo = cfg.get("topology") or {}
    for block in topo.get("blocks") or []:
        subj = (block.get("subject_name") or "").strip() or "Disciplina Geral"
        for q in block.get("questions") or []:
            raw = q.get("q")
            if raw is None:
                raw = q.get("numero")
            if raw is None:
                continue
            try:
                qn = int(raw)
            except (TypeError, ValueError):
                continue
            out[qn] = subj
    return out


def _build_acertos_por_habilidade(
    results: List[AnswerSheetResult],
    gabarito: AnswerSheetGabarito,
    q_skills: Dict[int, List[str]],
) -> Dict[str, Any]:
    """
    Mesmo formato de relatório de avaliação normal: por disciplina com lista `questoes`
    (uma entrada por questão do cartão), com % mesmo quando zerado.
    """
    correct_json = gabarito.correct_answers or {}
    if isinstance(correct_json, str):
        import json

        correct_json = json.loads(correct_json) or {}
    gab_map: Dict[int, str] = {}
    for k, v in (correct_json or {}).items():
        try:
            gab_map[int(k)] = str(v).upper() if v else ""
        except (TypeError, ValueError):
            continue

    subject_by_qn = _question_subject_name_by_num(gabarito)
    question_nums = ordered_question_numbers_for_gabarito(gabarito)
    if not question_nums:
        question_nums = sorted(
            set(q_skills.keys()) | set(gab_map.keys()) | set(subject_by_qn.keys())
        )

    per_q: Dict[int, Dict[str, int]] = {
        qn: {"correct": 0, "total": 0} for qn in question_nums
    }

    for res in results:
        detected = res.detected_answers or {}
        for qn in question_nums:
            ca = gab_map.get(qn)
            raw = detected.get(str(qn), detected.get(qn))
            st = str(raw).upper() if raw else ""
            ok = bool(ca is not None and st and st == ca)
            per_q[qn]["total"] += 1
            if ok:
                per_q[qn]["correct"] += 1

    skill_ids_for_fetch: List[str] = []
    for qn in question_nums:
        for sid in q_skills.get(qn) or []:
            if sid:
                skill_ids_for_fetch.append(str(sid).strip())
    code_map = _fetch_skill_code_description_by_ids(list(dict.fromkeys(skill_ids_for_fetch)))

    questoes_flat: List[Dict[str, Any]] = []
    for qn in question_nums:
        disc = subject_by_qn.get(qn) or "Disciplina Geral"
        sids = q_skills.get(qn) or []
        first = str(sids[0]).strip() if sids else ""
        nk = _norm_skill_uuid_key(first) if first else ""
        code, description = code_map.get(nk, (None, None)) if first else (None, None)
        code_out = (code or "").strip() or (first if first else "—")
        desc_out = (description or "").strip() or (
            f"Questão {qn}" if not first else f"Habilidade ({code_out})"
        )

        pq = per_q.get(qn, {"correct": 0, "total": 0})
        c, t = int(pq["correct"]), int(pq["total"])
        pct = round_to_two_decimals((c / t * 100) if t > 0 else 0.0)

        questoes_flat.append(
            {
                "disciplina": disc,
                "numero_questao": qn,
                "codigo": code_out,
                "descricao": desc_out,
                "acertos": c,
                "total": t,
                "percentual": float(pct),
            }
        )

    by_disc: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    disc_order: List[str] = []
    for row in questoes_flat:
        d = row["disciplina"]
        if d not in disc_order:
            disc_order.append(d)
        by_disc[d].append(
            {
                "numero_questao": row["numero_questao"],
                "codigo": row["codigo"],
                "descricao": row["descricao"],
                "acertos": row["acertos"],
                "total": row["total"],
                "percentual": row["percentual"],
            }
        )

    out_ord: "OrderedDict[str, Any]" = OrderedDict()
    for d in disc_order:
        out_ord[d] = {"questoes": by_disc[d]}

    out_ord["GERAL"] = {
        "questoes": [
            {
                "numero_questao": r["numero_questao"],
                "codigo": r["codigo"],
                "descricao": r["descricao"],
                "acertos": r["acertos"],
                "total": r["total"],
                "percentual": r["percentual"],
            }
            for r in questoes_flat
        ]
    }

    return dict(out_ord) if out_ord else {}


def _build_total_alunos(
    results: List[AnswerSheetResult],
    school_name_map: Dict[str, str],
    target_classes: List[Class],
    student_count_by_class: Dict[str, int],
) -> Dict[str, Any]:
    """Matriculados = alunos da turma no escopo do cartão; avaliados = com resultado (como prova)."""
    by_class_results: Dict[str, List[AnswerSheetResult]] = defaultdict(list)
    for r in results:
        st = r.student
        if st and st.class_id:
            by_class_results[str(st.class_id)].append(r)

    por_turma: List[Dict[str, Any]] = []
    for c in target_classes:
        cid = str(c.id)
        mat = int(student_count_by_class.get(cid, 0))
        ava = len({r.student_id for r in by_class_results.get(cid, [])})
        pct = round_to_two_decimals((ava / mat * 100) if mat > 0 else 0.0)
        por_turma.append(
            {
                "turma": c.name or "Turma",
                "turma_id": cid,
                "matriculados": mat,
                "avaliados": ava,
                "percentual": pct,
                "faltosos": mat - ava,
            }
        )
    por_turma.sort(key=lambda x: (x.get("turma") or "").upper())

    agg: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"mat": 0, "ava": 0, "label": "Sem escola"}
    )
    for c in target_classes:
        cid = str(c.id)
        sid = str(c.school_id) if c.school_id else "_sem_escola"
        mat = int(student_count_by_class.get(cid, 0))
        ava = len({r.student_id for r in by_class_results.get(cid, [])})
        agg[sid]["mat"] += mat
        agg[sid]["ava"] += ava
        if sid != "_sem_escola":
            agg[sid]["label"] = school_name_map.get(sid) or (
                (c.school.name.strip() if c.school and c.school.name else None) or "Escola"
            )

    por_escola: List[Dict[str, Any]] = []
    for sid, v in agg.items():
        mat, ava = v["mat"], v["ava"]
        pct = round_to_two_decimals((ava / mat * 100) if mat > 0 else 0.0)
        por_escola.append(
            {
                "escola": v["label"],
                "matriculados": mat,
                "avaliados": ava,
                "percentual": pct,
                "faltosos": mat - ava,
            }
        )
    por_escola.sort(key=lambda x: (x.get("escola") or "").upper())

    total_mat = sum(int(student_count_by_class.get(str(c.id), 0)) for c in target_classes)
    total_ava = sum(
        len({r.student_id for r in by_class_results.get(str(c.id), [])})
        for c in target_classes
    )
    total_pct = round_to_two_decimals((total_ava / total_mat * 100) if total_mat > 0 else 0.0)

    return {
        "por_turma": por_turma,
        "por_escola": por_escola,
        "total_geral": {
            "matriculados": total_mat,
            "avaliados": total_ava,
            "percentual": total_pct,
            "faltosos": total_mat - total_ava,
        },
    }


def _empty_nivel_buckets() -> Dict[str, int]:
    return {
        "abaixo_do_basico": 0,
        "basico": 0,
        "adequado": 0,
        "avancado": 0,
    }


def _bucket_for_classification(classification: str) -> str:
    """
    Mapeia texto de classificação para as quatro faixas esperadas pelo template
    report_organized.html (mesmo padrão de _filtrar_payload_por_turmas_professor).
    """
    t = (classification or "").strip().lower()
    if not t:
        return "basico"
    if "abaixo" in t:
        return "abaixo_do_basico"
    if "avançado" in t or "avancado" in t:
        return "avancado"
    if "adequado" in t:
        return "adequado"
    if "básico" in t or "basico" in t:
        return "basico"
    return "basico"


def _totais_niveis(b: Dict[str, int]) -> Dict[str, Any]:
    total = b["abaixo_do_basico"] + b["basico"] + b["adequado"] + b["avancado"]
    return {
        "abaixo_do_basico": b["abaixo_do_basico"],
        "basico": b["basico"],
        "adequado": b["adequado"],
        "avancado": b["avancado"],
        "total": total,
    }


def _build_niveis(
    results: List[AnswerSheetResult],
    school_name_map: Dict[str, str],
    target_classes: List[Class],
) -> Dict[str, Any]:
    """
    Mesma forma que relatório de prova: por_turma / por_escola com colunas fixas
    e bloco geral com .total (PDF report_organized.html). Turmas sem resultado aparecem zeradas.
    """
    by_class_results: Dict[str, List[AnswerSheetResult]] = defaultdict(list)
    for r in results:
        st = r.student
        if st and st.class_id:
            by_class_results[str(st.class_id)].append(r)

    por_turma: List[Dict[str, Any]] = []
    for c in target_classes:
        cid = str(c.id)
        lst = by_class_results.get(cid, [])
        b = _empty_nivel_buckets()
        for r in lst:
            b[_bucket_for_classification(r.classification or "")] += 1
        row = _totais_niveis(b)
        row["turma"] = c.name or "Turma"
        row["turma_id"] = cid
        por_turma.append(row)
    por_turma.sort(key=lambda x: (x.get("turma") or "").upper())

    school_b: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"abaixo_do_basico": 0, "basico": 0, "adequado": 0, "avancado": 0}
    )
    for c in target_classes:
        sid = str(c.school_id) if c.school_id else "_sem_escola"
        for r in by_class_results.get(str(c.id), []):
            k = _bucket_for_classification(r.classification or "")
            school_b[sid][k] += 1

    por_escola: List[Dict[str, Any]] = []
    for sid, b in school_b.items():
        row = _totais_niveis(b)
        nome = "Sem escola"
        if sid != "_sem_escola":
            nome = school_name_map.get(sid) or "Escola"
        row["escola"] = nome
        por_escola.append(row)
    por_escola.sort(key=lambda x: (x.get("escola") or "").upper())

    geral_b = _empty_nivel_buckets()
    for r in results:
        geral_b[_bucket_for_classification(r.classification or "")] += 1

    return {
        "GERAL": {
            "por_turma": por_turma,
            "por_escola": por_escola,
            "geral": _totais_niveis(geral_b),
        }
    }


def _build_proficiencia_nota(
    results: List[AnswerSheetResult],
    school_name_map: Dict[str, str],
    target_classes: List[Class],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Mesmo formato do relatório de prova (report_organized.html): por disciplina,
    ``media_geral``, ``por_turma`` (``proficiencia`` / ``nota``) e ``por_escola``.
    Inclui todas as turmas-alvo, com zero quando não há média.
    """
    prof_by_class: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    prof_by_school: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    nota_by_class: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    nota_by_school: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    class_id_to_name: Dict[str, str] = {}
    for c in target_classes:
        class_id_to_name[str(c.id)] = c.name or "Sem turma"

    for r in results:
        st = r.student
        cid = str(st.class_id) if st and st.class_id else "_sem_turma"
        sid = "_sem_escola"
        if st and st.class_:
            class_id_to_name.setdefault(cid, st.class_.name or "Sem turma")
            raw_sid = st.class_.school_id
            if raw_sid:
                sid = str(raw_sid)
        elif st and st.class_id:
            class_id_to_name.setdefault(cid, "Sem turma")

        pbs = r.proficiency_by_subject or {}
        if isinstance(pbs, dict):
            for subj_id, block in pbs.items():
                if not isinstance(block, dict):
                    continue
                name = block.get("subject_name") or str(subj_id)
                pr = block.get("proficiency")
                if pr is not None:
                    try:
                        v = float(pr)
                        prof_by_class[name][cid].append(v)
                        prof_by_school[name][sid].append(v)
                    except (TypeError, ValueError):
                        pass
                gr = block.get("grade")
                if gr is not None:
                    try:
                        gv = float(gr)
                        nota_by_class[name][cid].append(gv)
                        nota_by_school[name][sid].append(gv)
                    except (TypeError, ValueError):
                        pass
        if r.proficiency is not None:
            try:
                v = float(r.proficiency)
                prof_by_class["GERAL"][cid].append(v)
                prof_by_school["GERAL"][sid].append(v)
            except (TypeError, ValueError):
                pass
        try:
            gv = float(r.grade or 0)
            nota_by_class["GERAL"][cid].append(gv)
            nota_by_school["GERAL"][sid].append(gv)
        except (TypeError, ValueError):
            pass

    class_id_to_name.setdefault("_sem_turma", "Sem turma")

    def _mean(vals: List[float]) -> float:
        return round_to_two_decimals(sum(vals) / len(vals)) if vals else 0.0

    def _label_escola(sc_id: str) -> str:
        if sc_id == "_sem_escola":
            return "Sem escola"
        return school_name_map.get(sc_id) or "Escola"

    def _assemble_por_disciplina(
        by_class: Dict[str, Dict[str, List[float]]],
        by_school: Dict[str, Dict[str, List[float]]],
        value_key: str,
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        all_names: Set[str] = set(by_class.keys()) | set(by_school.keys())
        if target_classes and "GERAL" not in all_names:
            all_names.add("GERAL")
        for name in all_names:
            all_vals: List[float] = []
            for vs in by_class.get(name, {}).values():
                all_vals.extend(vs)
            if not all_vals and not target_classes:
                continue
            por_turma: List[Dict[str, Any]] = []
            for c in target_classes:
                cl_id = str(c.id)
                vals = by_class.get(name, {}).get(cl_id, [])
                por_turma.append(
                    {
                        "turma": c.name or "Turma",
                        "turma_id": cl_id,
                        value_key: _mean(vals),
                    }
                )
            por_turma.sort(key=lambda x: (x.get("turma") or "").upper())
            school_vals: Dict[str, List[float]] = defaultdict(list)
            for c in target_classes:
                cl_id = str(c.id)
                sid = str(c.school_id) if c.school_id else "_sem_escola"
                school_vals[sid].extend(by_class.get(name, {}).get(cl_id, []))
            schools_order = sorted(
                {str(c.school_id) if c.school_id else "_sem_escola" for c in target_classes},
                key=lambda s: _label_escola(s),
            )
            por_escola: List[Dict[str, Any]] = []
            for sc_id in schools_order:
                vals = school_vals.get(sc_id, [])
                por_escola.append(
                    {"escola": _label_escola(sc_id), value_key: _mean(vals)}
                )
            media_geral = _mean(all_vals) if all_vals else 0.0
            out[name] = {
                "por_turma": por_turma,
                "por_escola": por_escola,
                "media_geral": media_geral,
                "media": media_geral,
                "alunos": len(all_vals),
            }
        return out

    prof_disc = _assemble_por_disciplina(prof_by_class, prof_by_school, "proficiencia")
    nota_disc = _assemble_por_disciplina(nota_by_class, nota_by_school, "nota")

    return (
        {"por_disciplina": prof_disc, "geral": prof_disc.get("GERAL", {})},
        {"por_disciplina": nota_disc, "geral": nota_disc.get("GERAL", {})},
    )


def empty_answer_sheet_payload(gabarito: AnswerSheetGabarito, scope_type: str, scope_ref_id: Optional[str]) -> Dict[str, Any]:
    """Payload mínimo quando não há resultados no escopo (relatório vazio)."""
    q_skills = _question_skills_map_from_gabarito(gabarito)
    acertos_empty = _build_acertos_por_habilidade([], gabarito, q_skills)
    avaliacao_data = {
        "id": str(gabarito.id),
        "titulo": gabarito.title or "Cartão resposta",
        "descricao": None,
        "course_name": gabarito.institution or "",
        "disciplinas": [],
        "series": [],
        "series_label": None,
        "report_entity_type": "answer_sheet",
    }
    metadados = {
        "scope_type": scope_type,
        "scope_id": scope_ref_id,
        "report_entity_type": "answer_sheet",
        "general_label": "Cartão resposta",
    }
    z = {
        "matriculados": 0,
        "avaliados": 0,
        "percentual": 0.0,
        "faltosos": 0,
    }
    return {
        "acertos_por_habilidade": acertos_empty,
        "analise_ia": {},
        "avaliacao": avaliacao_data,
        "metadados": metadados,
        "niveis_aprendizagem": {},
        "nota_geral": {"por_disciplina": {}, "geral": {}},
        "proficiencia": {"por_disciplina": {}, "geral": {}},
        "total_alunos": {"por_turma": [], "por_escola": [], "total_geral": z},
        "default_logo": _load_default_logo(),
    }


def build_answer_sheet_report_payload(
    gabarito_id: str,
    scope_type: str,
    scope_ref_id: Optional[str],
    include_ai: bool = True,
) -> Dict[str, Any]:
    gab = AnswerSheetGabarito.query.get(gabarito_id)
    if not gab:
        raise ValueError("Gabarito não encontrado")

    results = _fetch_results_scoped(gabarito_id, scope_type, scope_ref_id)
    target_classes = get_answer_sheet_target_classes_for_report(gab, scope_type, scope_ref_id)
    if not results and not target_classes:
        raise LookupError("Nenhum resultado de cartão-resposta para o escopo")

    counts = _student_count_by_class([c.id for c in target_classes])
    school_ids: Set[str] = set()
    for c in target_classes:
        if c.school_id:
            school_ids.add(str(c.school_id))
    for r in results:
        st = r.student
        if st and st.class_ and st.class_.school_id:
            school_ids.add(str(st.class_.school_id))
    school_names = _school_name_map_from_ids(school_ids)

    q_skills = _question_skills_map_from_gabarito(gab)
    acertos = _build_acertos_por_habilidade(results or [], gab, q_skills)
    total_alunos = _build_total_alunos(results, school_names, target_classes, counts)
    niveis = _build_niveis(results, school_names, target_classes)
    proficiencia, nota_geral = _build_proficiencia_nota(
        results, school_names, target_classes
    )

    series_ordered: List[str] = []
    seen = set()
    for c in target_classes:
        if c.grade and c.grade.name:
            gname = c.grade.name.strip()
            if gname and gname not in seen:
                seen.add(gname)
                series_ordered.append(gname)
    for r in results:
        st = r.student
        if st and st.class_ and st.class_.grade and st.class_.grade.name:
            gname = st.class_.grade.name.strip()
            if gname and gname not in seen:
                seen.add(gname)
                series_ordered.append(gname)

    avaliacao_data = {
        "id": str(gab.id),
        "titulo": gab.title or "Cartão resposta",
        "descricao": None,
        "course_name": gab.institution or "",
        "disciplinas": list(proficiencia.get("por_disciplina", {}).keys()),
        "series": series_ordered,
        "series_label": ", ".join(series_ordered) if series_ordered else None,
        "report_entity_type": "answer_sheet",
    }

    now = datetime.now()
    metadados: Dict[str, Any] = {
        "scope_type": scope_type,
        "scope_id": scope_ref_id,
        "mes": now.strftime("%B").capitalize(),
        "ano": now.year,
        "data_geracao": now.strftime("%d/%m/%Y %H:%M"),
        "series": series_ordered,
        "series_label": avaliacao_data["series_label"],
        "general_label": "Cartão resposta",
        "report_entity_type": "answer_sheet",
    }

    if scope_type == "school" and scope_ref_id:
        school = School.query.get(scope_ref_id)
        if school:
            metadados.update(
                {
                    "escola": school.name,
                    "escola_id": str(school.id),
                    "municipio": school.city.name if school.city else None,
                    "municipio_id": str(school.city.id) if school.city else None,
                    "uf": school.city.state if school.city else None,
                }
            )
    elif scope_type == "city" and scope_ref_id:
        city = City.query.get(scope_ref_id)
        if city:
            metadados.update(
                {
                    "municipio": city.name,
                    "municipio_id": str(city.id),
                    "uf": city.state,
                }
            )

    analise_ia: Dict[str, Any] = {}
    if include_ai:
        try:
            ai = AIAnalysisService()
            analise_ia = ai.analyze_report_data(
                {
                    "avaliacao": avaliacao_data,
                    "total_alunos": total_alunos,
                    "niveis_aprendizagem": niveis,
                    "proficiencia": proficiencia,
                    "nota_geral": nota_geral,
                    "acertos_por_habilidade": acertos,
                    "scope_type": scope_type,
                    "scope_id": scope_ref_id,
                }
            )
        except Exception:
            analise_ia = {}

    return {
        "acertos_por_habilidade": acertos,
        "analise_ia": analise_ia,
        "avaliacao": avaliacao_data,
        "metadados": metadados,
        "niveis_aprendizagem": niveis,
        "nota_geral": nota_geral,
        "proficiencia": proficiencia,
        "total_alunos": total_alunos,
        "default_logo": _load_default_logo(),
    }
