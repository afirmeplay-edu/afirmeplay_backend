# -*- coding: utf-8 -*-
"""
Monta o payload de relatório (cartão-resposta) compatível com o consumo de /reports/dados-json.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

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


def _question_skills_map_from_gabarito(gabarito: AnswerSheetGabarito) -> Dict[int, List[str]]:
    """Mapeia número da questão -> lista de IDs de habilidade (topology)."""
    out: Dict[int, List[str]] = {}
    cfg = gabarito.blocks_config or {}
    topo = cfg.get("topology") or {}
    blocks = topo.get("blocks") or []
    for block in blocks:
        for q in block.get("questions") or []:
            qn = q.get("q") or q.get("numero")
            if qn is None:
                continue
            try:
                n = int(qn)
            except (TypeError, ValueError):
                continue
            skills = q.get("skills") or []
            if skills:
                out[n] = [str(s) for s in skills]
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


def _school_name_map_from_results(results: List[AnswerSheetResult]) -> Dict[str, str]:
    """
    Nomes de escola via consulta em lote. ``Class.school`` é property (não relationship),
    então o PDF não deve depender só do lazy load para preencher rótulos no escopo city.
    """
    ids: Set[str] = set()
    for r in results:
        st = r.student
        if st and st.class_ and st.class_.school_id:
            ids.add(str(st.class_.school_id))
    if not ids:
        return {}
    rows = School.query.filter(School.id.in_(ids)).all()
    return {str(s.id): (s.name.strip() if s.name else "Escola") for s in rows}


def _build_acertos_por_habilidade(
    results: List[AnswerSheetResult],
    gabarito: AnswerSheetGabarito,
    q_skills: Dict[int, List[str]],
) -> Dict[str, Any]:
    if not q_skills:
        return {}
    correct_json = gabarito.correct_answers or {}
    if isinstance(correct_json, str):
        import json

        correct_json = json.loads(correct_json)
    gab: Dict[int, str] = {}
    for k, v in (correct_json or {}).items():
        try:
            gab[int(k)] = str(v).upper() if v else ""
        except (TypeError, ValueError):
            continue

    # skill_id -> {correct, total}
    acc: Dict[str, Dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})

    for res in results:
        detected = res.detected_answers or {}
        for qn, skill_ids in q_skills.items():
            ca = gab.get(qn)
            if ca is None:
                continue
            st = detected.get(str(qn), detected.get(qn))
            st = str(st).upper() if st else ""
            ok = bool(st) and st == ca
            for sid in skill_ids:
                acc[sid]["total"] += 1
                if ok:
                    acc[sid]["correct"] += 1

    code_map = _fetch_skill_code_description_by_ids(list(acc.keys()))

    # Formato simplificado por "disciplina" única GERAL de habilidades
    habilidades: Dict[str, Any] = {}
    for sid, v in acc.items():
        t = v["total"]
        c = v["correct"]
        pct = round_to_two_decimals((c / t * 100) if t else 0.0)
        nk = _norm_skill_uuid_key(sid)
        code, description = code_map.get(nk, (None, None))
        habilidades[sid] = {
            "habilidade_id": sid,
            "code": code,
            "description": description,
            "acertos": c,
            "total": t,
            "percentual": pct,
        }
    return {"GERAL": habilidades} if habilidades else {}


def _build_total_alunos(
    results: List[AnswerSheetResult],
    school_name_map: Dict[str, str],
) -> Dict[str, Any]:
    by_class: Dict[str, List[AnswerSheetResult]] = defaultdict(list)
    by_school: Dict[str, List[AnswerSheetResult]] = defaultdict(list)
    for r in results:
        st = r.student
        cid = str(st.class_id) if st and st.class_id else "_sem_turma"
        by_class[cid].append(r)
        sid = "_sem_escola"
        if st and st.class_ and st.class_.school_id:
            sid = str(st.class_.school_id)
        by_school[sid].append(r)

    por_turma: List[Dict[str, Any]] = []
    total_avaliados = len(results)
    for cid, lst in by_class.items():
        nome = "Sem turma"
        if lst and lst[0].student and lst[0].student.class_:
            nome = lst[0].student.class_.name or nome
        por_turma.append(
            {
                "turma": nome,
                "turma_id": cid if cid != "_sem_turma" else None,
                "matriculados": len(lst),
                "avaliados": len(lst),
                "percentual": 100.0 if lst else 0.0,
                "faltosos": 0,
            }
        )
    por_turma.sort(key=lambda x: (x.get("turma") or "").upper())

    por_escola: List[Dict[str, Any]] = []
    for sid, lst in by_school.items():
        label = "Sem escola"
        if sid != "_sem_escola":
            label = school_name_map.get(sid) or "Escola"
        por_escola.append(
            {
                "escola": label,
                "matriculados": len(lst),
                "avaliados": len(lst),
                "percentual": round_to_two_decimals(100.0) if lst else 0.0,
                "faltosos": 0,
            }
        )
    por_escola.sort(key=lambda x: (x.get("escola") or "").upper())

    return {
        "por_turma": por_turma,
        "por_escola": por_escola,
        "total_geral": {
            "matriculados": total_avaliados,
            "avaliados": total_avaliados,
            "percentual": 100.0 if total_avaliados else 0.0,
            "faltosos": 0,
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
) -> Dict[str, Any]:
    """
    Mesma forma que relatório de prova: por_turma / por_escola com colunas fixas
    e bloco geral com .total (PDF report_organized.html).
    """
    if not results:
        z = _totais_niveis(_empty_nivel_buckets())
        return {
            "GERAL": {
                "por_turma": [],
                "por_escola": [],
                "geral": z,
            }
        }

    by_class: Dict[str, List[AnswerSheetResult]] = defaultdict(list)
    by_school: Dict[str, List[AnswerSheetResult]] = defaultdict(list)
    for r in results:
        st = r.student
        cid = str(st.class_id) if st and st.class_id else "_sem_turma"
        by_class[cid].append(r)
        sid = "_sem_escola"
        if st and st.class_ and st.class_.school_id:
            sid = str(st.class_.school_id)
        by_school[sid].append(r)

    por_turma: List[Dict[str, Any]] = []
    for cid, lst in by_class.items():
        nome = "Sem turma"
        if lst and lst[0].student and lst[0].student.class_:
            nome = lst[0].student.class_.name or nome
        b = _empty_nivel_buckets()
        for r in lst:
            b[_bucket_for_classification(r.classification or "")] += 1
        row = _totais_niveis(b)
        row["turma"] = nome
        row["turma_id"] = cid if cid != "_sem_turma" else None
        por_turma.append(row)
    por_turma.sort(key=lambda x: (x.get("turma") or "").upper())

    por_escola: List[Dict[str, Any]] = []
    for sid, lst in by_school.items():
        nome = "Sem escola"
        if sid != "_sem_escola":
            nome = school_name_map.get(sid) or "Escola"
        b = _empty_nivel_buckets()
        for r in lst:
            b[_bucket_for_classification(r.classification or "")] += 1
        row = _totais_niveis(b)
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
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Mesmo formato do relatório de prova (report_organized.html): por disciplina,
    ``media_geral``, ``por_turma`` (``proficiencia`` / ``nota``) e ``por_escola``.
    """
    prof_by_class: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    prof_by_school: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    nota_by_class: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    nota_by_school: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    class_id_to_name: Dict[str, str] = {}

    for r in results:
        st = r.student
        cid = str(st.class_id) if st and st.class_id else "_sem_turma"
        sid = "_sem_escola"
        if st and st.class_:
            class_id_to_name[cid] = st.class_.name or "Sem turma"
            raw_sid = st.class_.school_id
            if raw_sid:
                sid = str(raw_sid)
        elif st and st.class_id:
            class_id_to_name[cid] = "Sem turma"

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
        all_names = set(by_class.keys()) | set(by_school.keys())
        for name in all_names:
            all_vals: List[float] = []
            for vs in by_class.get(name, {}).values():
                all_vals.extend(vs)
            if not all_vals:
                continue
            por_turma: List[Dict[str, Any]] = []
            for cl_id, vals in sorted(
                by_class.get(name, {}).items(),
                key=lambda x: (class_id_to_name.get(x[0], x[0]), x[0]),
            ):
                if not vals:
                    continue
                por_turma.append(
                    {
                        "turma": class_id_to_name.get(cl_id, "Sem turma"),
                        "turma_id": cl_id if cl_id != "_sem_turma" else None,
                        value_key: _mean(vals),
                    }
                )
            por_escola: List[Dict[str, Any]] = []
            for sc_id, vals in sorted(
                by_school.get(name, {}).items(),
                key=lambda x: (_label_escola(x[0]), x[0]),
            ):
                if not vals:
                    continue
                por_escola.append(
                    {
                        "escola": _label_escola(sc_id),
                        value_key: _mean(vals),
                    }
                )
            media_geral = _mean(all_vals)
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
        "acertos_por_habilidade": {},
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
    if not results:
        raise LookupError("Nenhum resultado de cartão-resposta para o escopo")

    q_skills = _question_skills_map_from_gabarito(gab)
    acertos = _build_acertos_por_habilidade(results, gab, q_skills)
    school_names = _school_name_map_from_results(results)
    total_alunos = _build_total_alunos(results, school_names)
    niveis = _build_niveis(results, school_names)
    proficiencia, nota_geral = _build_proficiencia_nota(results, school_names)

    series_ordered: List[str] = []
    seen = set()
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
