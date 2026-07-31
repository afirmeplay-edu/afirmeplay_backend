# -*- coding: utf-8 -*-
"""Ranking de turmas iguais (nome + turno + série) entre escolas / dentro da escola."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models.evaluationResult import EvaluationResult
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.test import Test
from app.permissions.utils import get_teacher_classes
from app.services.dashboard_service import DashboardService
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.evaluation_result_snapshot import (
    municipal_evaluation_results_query,
    prefetch_placement_from_results,
    resolve_participant_display_context,
)
from app.utils.class_label_helpers import normalize_shift
from app.utils.school_equal_weight_means import (
    aggregated_grade_from_proficiency,
    hierarchical_mean_grade_and_proficiency,
)


@dataclass
class ClassPeerRankingRequest:
    scope: str
    evaluation_ids: List[str]
    page: int
    per_page: int
    municipio: Optional[str] = None
    escola: Optional[str] = None
    serie: Optional[str] = None
    turma_nome: Optional[str] = None
    turno: Optional[str] = None

    @property
    def evaluation_id(self) -> str:
        return self.evaluation_ids[0] if self.evaluation_ids else ""


class ClassPeerRankingService:
    """Compara turmas com mesmo nome+turno na mesma série (peers) e ranqueia turmas e alunos."""

    @staticmethod
    def _normalize_text(value: Any) -> str:
        normalized = unicodedata.normalize("NFD", str(value or ""))
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").strip().lower()

    @classmethod
    def _normalize_shift_key(cls, value: Any) -> str:
        return cls._normalize_text(normalize_shift(value) or "")

    @classmethod
    def _derive_course_label(cls, grade_name: str) -> str:
        normalized = cls._normalize_text(grade_name)
        if "anos iniciais" in normalized or "inicial" in normalized:
            return "Anos Iniciais"
        if "anos finais" in normalized or "final" in normalized:
            return "Anos Finais"
        numeric_match = re.search(r"\d+", normalized)
        grade_number = int(numeric_match.group(0)) if numeric_match else None
        if grade_number is not None:
            if 1 <= grade_number <= 5:
                return "Anos Iniciais"
            if 6 <= grade_number <= 9:
                return "Anos Finais"
        grade_name_clean = str(grade_name or "").strip()
        return f"Curso: {grade_name_clean}" if grade_name_clean else "Anos Iniciais"

    @staticmethod
    def _pagination(page: int, per_page: int, total: int) -> Dict[str, int]:
        total_pages = math.ceil(total / per_page) if total and per_page else 0
        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        }

    @classmethod
    def _classification(
        cls,
        proficiency: float,
        *,
        course_label: str,
        subject_name: str = "GERAL",
    ) -> str:
        return EvaluationCalculator.determine_classification(
            float(proficiency or 0),
            str(course_label or "Anos Iniciais"),
            str(subject_name or "GERAL"),
        )

    @classmethod
    def _peer_key(cls, class_name: Any, shift: Any) -> str:
        return f"{cls._normalize_text(class_name)}|{cls._normalize_shift_key(shift)}"

    @classmethod
    def _subject_name_is_lingua_portuguesa(cls, name: Any) -> bool:
        n = cls._normalize_text(name)
        return "portug" in n or n == "lp" or n.startswith("lp ")

    @classmethod
    def _portuguese_correct_answers(cls, subjects: Any) -> int:
        if not isinstance(subjects, list):
            return 0
        for subject in subjects:
            if not isinstance(subject, dict):
                continue
            if cls._subject_name_is_lingua_portuguesa(subject.get("subject_name")):
                return int(subject.get("correct_answers") or 0)
        return 0

    @classmethod
    def _raw_correct_sum(cls, subjects: Any, fallback_correct_answers: Any = 0) -> int:
        """Soma bruta de acertos por disciplina; fallback = correct_answers do topo."""
        if isinstance(subjects, list) and subjects:
            total = 0
            has_any = False
            for subject in subjects:
                if not isinstance(subject, dict):
                    continue
                has_any = True
                total += int(subject.get("correct_answers") or 0)
            if has_any:
                return total
        return int(fallback_correct_answers or 0)

    @classmethod
    def _education_level_suffix(cls, course_name: Any) -> Optional[str]:
        n = cls._normalize_text(course_name)
        if not n:
            return None
        if "superior" in n:
            return "SUPERIOR"
        if "medio" in n:
            return "ENSINO MÉDIO"
        return None

    @classmethod
    def _school_display_name(cls, school_name: Any, course_name: Any) -> str:
        base = str(school_name or "").strip() or "N/A"
        suffix = cls._education_level_suffix(course_name)
        if suffix:
            return f"{base} – {suffix}"
        return base

    @classmethod
    def _resolve_course_names_by_test_id(cls, tests: Sequence[Test]) -> Dict[str, str]:
        """Mapeia test_id -> nome do education_stage (Test.course = UUID do stage)."""
        from app.models.educationStage import EducationStage

        course_ids: List[Any] = []
        test_course: Dict[str, Any] = {}
        for test in tests:
            tid = str(test.id)
            course_ref = getattr(test, "course", None)
            test_course[tid] = course_ref
            if course_ref:
                course_ids.append(course_ref)

        if not course_ids:
            return {tid: "" for tid in test_course}

        stages = EducationStage.query.filter(EducationStage.id.in_(course_ids)).all()
        name_by_id = {str(s.id): str(s.name or "") for s in stages}

        resolved: Dict[str, str] = {}
        for tid, course_ref in test_course.items():
            if not course_ref:
                resolved[tid] = ""
                continue
            key = str(course_ref)
            # Se já for um rótulo textual (legado), usa direto.
            resolved[tid] = name_by_id.get(key) or (
                str(course_ref) if not cls._looks_like_uuid(key) else ""
            )
        return resolved

    @staticmethod
    def _looks_like_uuid(value: str) -> bool:
        text = str(value or "").strip()
        if len(text) != 36:
            return False
        parts = text.split("-")
        return len(parts) == 5

    @classmethod
    def _sort_key_metrics(
        cls,
        *,
        proficiency: Any,
        score: Any,
        correct_answers: Any,
        total_questions: Any,
        name: Any,
    ) -> tuple:
        """Ordenação de turmas (peers): pontos → taxa → acertos gerais → nome."""
        correct = float(correct_answers or 0)
        total_q = float(total_questions or 0)
        accuracy = (correct / total_q) if total_q > 0 else 0.0
        return (
            -float(proficiency or 0),
            -float(score or 0),
            -accuracy,
            -correct,
            str(name or "").lower(),
        )

    @classmethod
    def _sort_key_student(cls, row: Dict[str, Any]) -> tuple:
        """Ordenação de alunos: soma bruta de acertos → Português → nome (A→Z)."""
        raw = cls._raw_correct_sum(
            row.get("subjects"),
            row.get("raw_correct_answers", row.get("correct_answers")),
        )
        return (
            -float(raw),
            -float(cls._portuguese_correct_answers(row.get("subjects"))),
            str(row.get("name") or "").lower(),
        )

    @classmethod
    def _parse_evaluation_ids(cls, args) -> List[str]:
        raw_multi = args.get("evaluation_ids")
        ids: List[str] = []
        if raw_multi and str(raw_multi).strip():
            ids = [x.strip() for x in str(raw_multi).split(",") if x.strip()]
        if not ids:
            single = str(args.get("evaluation_id") or "").strip()
            if single:
                ids = [single]
        # Mantém ordem e remove duplicatas.
        seen = set()
        unique: List[str] = []
        for eid in ids:
            if eid in seen:
                continue
            seen.add(eid)
            unique.append(eid)
        if not unique:
            raise ValueError("evaluation_id ou evaluation_ids é obrigatório.")
        return unique

    @classmethod
    def build_request(cls, args) -> ClassPeerRankingRequest:
        scope = cls._normalize_text(args.get("scope") or "")
        if scope not in {"municipio", "escola"}:
            raise ValueError("scope deve ser 'municipio' ou 'escola'.")

        evaluation_ids = cls._parse_evaluation_ids(args)

        page = max(1, int(args.get("page", 1) or 1))
        per_page = max(1, min(100, int(args.get("per_page", 20) or 20)))

        def _clean(value: Any) -> Optional[str]:
            cleaned = str(value or "").strip()
            if not cleaned or cleaned.lower() == "all":
                return None
            return cleaned

        municipio = _clean(args.get("municipio"))
        escola = _clean(args.get("escola"))
        serie = _clean(args.get("serie"))
        turma_nome = _clean(args.get("turma_nome"))
        turno = _clean(args.get("turno"))

        if scope == "municipio" and not municipio:
            raise ValueError("municipio é obrigatório quando scope=municipio.")
        if scope == "escola" and not escola:
            raise ValueError("escola é obrigatória quando scope=escola.")

        return ClassPeerRankingRequest(
            scope=scope,
            evaluation_ids=evaluation_ids,
            page=page,
            per_page=per_page,
            municipio=municipio,
            escola=escola,
            serie=serie,
            turma_nome=turma_nome,
            turno=turno,
        )

    @classmethod
    def _resolve_tests(cls, evaluation_ids: Sequence[str]) -> List[Test]:
        tests = Test.query.filter(Test.id.in_([str(t) for t in evaluation_ids])).all()
        by_id = {str(t.id): t for t in tests}
        missing = [eid for eid in evaluation_ids if str(eid) not in by_id]
        if missing:
            raise ValueError(f"Avaliação(ões) não encontrada(s): {', '.join(missing)}")
        return [by_id[str(eid)] for eid in evaluation_ids]

    @classmethod
    def _evaluation_titles_payload(cls, tests: Sequence[Test]) -> Dict[str, Any]:
        items = [{"id": str(t.id), "title": t.title or ""} for t in tests]
        titles = [item["title"] for item in items if item["title"]]
        if len(titles) <= 1:
            joined = titles[0] if titles else None
        else:
            joined = " · ".join(titles)
        return {
            "evaluation_id": str(tests[0].id) if tests else "",
            "evaluation_ids": [str(t.id) for t in tests],
            "evaluation_title": joined,
            "evaluations": items,
        }

    @classmethod
    def get_report(cls, user: Dict[str, Any], req: ClassPeerRankingRequest) -> Dict[str, Any]:
        tests = cls._resolve_tests(req.evaluation_ids)
        primary_test = tests[0]
        course_name_by_test_id = cls._resolve_course_names_by_test_id(tests)

        scope = cls._resolve_and_authorize_scope(user, req)
        results = cls._load_latest_results(req, scope)
        if not results:
            return cls._empty_payload(req, scope, tests)

        schools_by_id, classes_by_id, grades_by_id = prefetch_placement_from_results(results)
        student_ids = list({str(r.student_id) for r in results if r.student_id})
        students_by_id = {
            str(s.id): s
            for s in Student.query.filter(Student.id.in_(student_ids)).all()
        } if student_ids else {}

        # Complementa escolas/turmas legadas (sem snapshot) a partir do aluno atual.
        legacy_class_ids = {
            s.class_id
            for s in students_by_id.values()
            if s.class_id and s.class_id not in classes_by_id
        }
        if legacy_class_ids:
            for c in (
                Class.query.options(joinedload(Class.grade))
                .filter(Class.id.in_(list(legacy_class_ids)))
                .all()
            ):
                classes_by_id[c.id] = c
                if getattr(c, "grade_id", None) and c.grade_id not in grades_by_id:
                    if c.grade:
                        grades_by_id[c.grade_id] = c.grade
                school_id = str(c.school_id) if c.school_id else None
                if school_id and school_id not in schools_by_id:
                    school = School.query.get(school_id)
                    if school:
                        schools_by_id[school_id] = school

        teacher_class_ids = scope.get("teacher_class_ids")
        rows = []
        for er in results:
            student = students_by_id.get(str(er.student_id))
            ctx = resolve_participant_display_context(
                student, er, schools_by_id, classes_by_id, grades_by_id
            )
            class_id = er.class_id_snapshot or (student.class_id if student else None)
            if teacher_class_ids is not None and str(class_id or "") not in teacher_class_ids:
                continue

            grade_id = er.grade_id_snapshot
            if grade_id is None and class_id and class_id in classes_by_id:
                grade_id = classes_by_id[class_id].grade_id
            if grade_id is None and student is not None:
                grade_id = student.grade_id

            grade_name = ctx.get("serie") or "Sem série"
            if grade_id and grade_id in grades_by_id:
                grade_name = grades_by_id[grade_id].name or grade_name

            class_name = ctx.get("turma") or ""
            shift = ctx.get("shift") or ""
            if class_id and class_id in classes_by_id:
                class_obj = classes_by_id[class_id]
                if not class_name or class_name == "N/A":
                    class_name = class_obj.name or ""
                if not shift:
                    shift = normalize_shift(class_obj.shift) or ""

            if req.serie and str(grade_id or "") != str(req.serie):
                continue
            if req.turma_nome and cls._normalize_text(class_name) != cls._normalize_text(req.turma_nome):
                continue
            if req.turno is not None and cls._normalize_shift_key(shift) != cls._normalize_shift_key(req.turno):
                continue

            source_evaluation_id = str(er.test_id) if er.test_id else None
            rows.append(
                {
                    "student_id": str(er.student_id),
                    "name": ctx.get("nome") or (student.name if student else "N/A"),
                    "school_id": ctx.get("escola_id"),
                    "school_name": ctx.get("escola") or "N/A",
                    "class_id": str(class_id) if class_id else None,
                    "class_name": class_name or "Turma",
                    "shift": shift or "",
                    "serie_id": str(grade_id) if grade_id else None,
                    "serie_name": grade_name,
                    "grade": float(er.grade or 0),
                    "proficiency": float(er.proficiency or 0),
                    "classification": er.classification or "",
                    "correct_answers": int(er.correct_answers or 0),
                    "total_questions": int(er.total_questions or 0),
                    "score_percentage": float(er.score_percentage or 0),
                    "subject_results": er.subject_results or {},
                    "source_evaluation_id": source_evaluation_id,
                    "course_name": course_name_by_test_id.get(source_evaluation_id or "", ""),
                    "result_obj": er,
                }
            )

        sections = cls._build_sections(
            rows, req, course_fallback=getattr(primary_test, "course", None)
        )
        payload = {
            **cls._evaluation_titles_payload(tests),
            "scope": req.scope,
            "filters": {
                "municipio": req.municipio,
                "escola": req.escola,
                "serie": req.serie,
                "turma_nome": req.turma_nome,
                "turno": req.turno,
            },
            "resolved_scope": {
                "scope": scope.get("scope"),
                "city_id": scope.get("city_id"),
                "school_ids": scope.get("school_ids") or [],
            },
            "sections": sections,
            "totals": {
                "sections_count": len(sections),
                "peer_groups_count": sum(len(s.get("peer_groups") or []) for s in sections),
                "students_count": len(rows),
            },
        }
        return payload

    @classmethod
    def _empty_payload(
        cls,
        req: ClassPeerRankingRequest,
        scope: Dict[str, Any],
        tests: Optional[Sequence[Test]] = None,
    ) -> Dict[str, Any]:
        resolved_tests = list(tests) if tests is not None else []
        if not resolved_tests and req.evaluation_ids:
            try:
                resolved_tests = cls._resolve_tests(req.evaluation_ids)
            except ValueError:
                resolved_tests = []
        titles = cls._evaluation_titles_payload(resolved_tests) if resolved_tests else {
            "evaluation_id": req.evaluation_id,
            "evaluation_ids": list(req.evaluation_ids),
            "evaluation_title": None,
            "evaluations": [],
        }
        return {
            **titles,
            "scope": req.scope,
            "filters": {
                "municipio": req.municipio,
                "escola": req.escola,
                "serie": req.serie,
                "turma_nome": req.turma_nome,
                "turno": req.turno,
            },
            "resolved_scope": {
                "scope": scope.get("scope"),
                "city_id": scope.get("city_id"),
                "school_ids": scope.get("school_ids") or [],
            },
            "sections": [],
            "totals": {"sections_count": 0, "peer_groups_count": 0, "students_count": 0},
        }

    @classmethod
    def _resolve_and_authorize_scope(
        cls, user: Dict[str, Any], req: ClassPeerRankingRequest
    ) -> Dict[str, Any]:
        if req.scope == "municipio":
            explicit = DashboardService._resolve_explicit_ranking_scope(
                user, "municipio", str(req.municipio)
            )
            if not explicit:
                raise ValueError("Sem permissão para o município informado.")
            scope = explicit
        else:
            explicit = DashboardService._resolve_explicit_ranking_scope(
                user, "escola", str(req.escola)
            )
            if not explicit:
                raise ValueError("Sem permissão para a escola informada.")
            scope = explicit

        if user.get("role") == "professor":
            teacher_classes = get_teacher_classes(user["id"]) or []
            scope["teacher_class_ids"] = {str(cid) for cid in teacher_classes if cid}
            if not scope["teacher_class_ids"]:
                scope["teacher_class_ids"] = set()
        return scope

    @classmethod
    def _load_latest_results(
        cls, req: ClassPeerRankingRequest, scope: Dict[str, Any]
    ) -> List[EvaluationResult]:
        evaluation_ids = [str(eid) for eid in req.evaluation_ids]

        if req.scope == "municipio":
            base_q = municipal_evaluation_results_query(str(req.municipio), evaluation_ids)
        else:
            school_id = str(req.escola)
            legacy_students = (
                db.session.query(Student.id)
                .filter(Student.school_id == school_id)
            )
            test_filter = (
                EvaluationResult.test_id == evaluation_ids[0]
                if len(evaluation_ids) == 1
                else EvaluationResult.test_id.in_(evaluation_ids)
            )
            base_q = EvaluationResult.query.filter(
                test_filter,
                or_(
                    EvaluationResult.school_id_snapshot == school_id,
                    and_(
                        EvaluationResult.school_id_snapshot.is_(None),
                        EvaluationResult.class_id_snapshot.is_(None),
                        EvaluationResult.student_id.in_(legacy_students),
                    ),
                ),
            )

        results = base_q.all()
        # Um aluno = um resultado (o mais recente entre as avaliações selecionadas).
        latest_by_student: Dict[str, EvaluationResult] = {}
        for er in results:
            sid = str(er.student_id)
            current = latest_by_student.get(sid)
            if current is None:
                latest_by_student[sid] = er
                continue
            cur_at = getattr(current, "calculated_at", None)
            new_at = getattr(er, "calculated_at", None)
            if new_at and (not cur_at or new_at > cur_at):
                latest_by_student[sid] = er
            elif new_at == cur_at and str(er.id) > str(current.id):
                latest_by_student[sid] = er
        return list(latest_by_student.values())

    @classmethod
    def _build_sections(
        cls,
        rows: List[Dict[str, Any]],
        req: ClassPeerRankingRequest,
        *,
        course_fallback: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        by_serie: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        serie_meta: Dict[str, Dict[str, str]] = {}
        for row in rows:
            serie_key = str(row.get("serie_id") or row.get("serie_name") or "sem-serie")
            by_serie[serie_key].append(row)
            if serie_key not in serie_meta:
                serie_meta[serie_key] = {
                    "serie_id": row.get("serie_id"),
                    "serie_name": row.get("serie_name") or "Sem série",
                }

        sections: List[Dict[str, Any]] = []
        for serie_key in sorted(
            by_serie.keys(),
            key=lambda k: cls._normalize_text(serie_meta[k].get("serie_name") or k),
        ):
            serie_rows = by_serie[serie_key]
            serie_name = serie_meta[serie_key]["serie_name"]
            course_label = (
                str(course_fallback).strip()
                if course_fallback and str(course_fallback).strip()
                else cls._derive_course_label(serie_name)
            )
            peer_groups = cls._build_peer_groups(serie_rows, req, course_label=course_label)
            sections.append(
                {
                    "serie_id": serie_meta[serie_key]["serie_id"],
                    "serie_name": serie_name,
                    "peer_groups": peer_groups,
                    "totals": {
                        "peer_groups_count": len(peer_groups),
                        "classes_count": sum(len(p.get("class_ranking") or []) for p in peer_groups),
                        "students_count": sum(
                            int((p.get("students_pagination") or {}).get("total") or 0)
                            for p in peer_groups
                        ),
                    },
                }
            )
        return sections

    @classmethod
    def _build_peer_groups(
        cls,
        serie_rows: List[Dict[str, Any]],
        req: ClassPeerRankingRequest,
        *,
        course_label: str,
    ) -> List[Dict[str, Any]]:
        by_peer: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        peer_labels: Dict[str, Tuple[str, str]] = {}
        for row in serie_rows:
            key = cls._peer_key(row.get("class_name"), row.get("shift"))
            by_peer[key].append(row)
            if key not in peer_labels:
                peer_labels[key] = (
                    str(row.get("class_name") or "Turma"),
                    str(row.get("shift") or ""),
                )

        groups: List[Dict[str, Any]] = []
        for peer_key in sorted(by_peer.keys()):
            peer_rows = by_peer[peer_key]
            turma_nome, shift = peer_labels[peer_key]
            class_ranking = cls._build_class_ranking(peer_rows, course_label=course_label)
            student_ranking_all = cls._build_student_ranking(peer_rows)
            total_students = len(student_ranking_all)
            offset = (req.page - 1) * req.per_page
            student_page = student_ranking_all[offset : offset + req.per_page]
            groups.append(
                {
                    "turma_nome": turma_nome,
                    "shift": shift,
                    "peer_key": peer_key,
                    "class_ranking": class_ranking,
                    "student_ranking": student_page,
                    "students_pagination": cls._pagination(req.page, req.per_page, total_students),
                    "totals": {
                        "classes_count": len(class_ranking),
                        "students_count": total_students,
                    },
                }
            )
        return groups

    @classmethod
    def _build_class_ranking(
        cls,
        peer_rows: List[Dict[str, Any]],
        *,
        course_label: str,
    ) -> List[Dict[str, Any]]:
        by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in peer_rows:
            class_key = str(row.get("class_id") or f"{row.get('school_id')}:{row.get('class_name')}")
            by_class[class_key].append(row)

        items: List[Dict[str, Any]] = []
        for _class_key, class_rows in by_class.items():
            sample = class_rows[0]
            result_objs = [
                SimpleNamespace(
                    student_id=r["student_id"],
                    grade=r["grade"],
                    proficiency=r["proficiency"],
                    class_id_snapshot=r.get("class_id"),
                    school_id_snapshot=r.get("school_id"),
                    grade_id_snapshot=r.get("serie_id"),
                )
                for r in class_rows
            ]
            avg_score, avg_prof = hierarchical_mean_grade_and_proficiency(
                result_objs,
                "turma",
                course_name=course_label,
                subject_name="GERAL",
            )
            total_correct = sum(int(r.get("correct_answers") or 0) for r in class_rows)
            total_questions = sum(int(r.get("total_questions") or 0) for r in class_rows)
            items.append(
                {
                    "school_id": sample.get("school_id"),
                    "school_name": sample.get("school_name"),
                    "class_id": sample.get("class_id"),
                    "class_name": sample.get("class_name"),
                    "shift": sample.get("shift") or "",
                    "average_proficiency": round(float(avg_prof or 0), 1),
                    "average_score": round(float(avg_score or 0), 1),
                    "classification": cls._classification(
                        float(avg_prof or 0), course_label=course_label
                    ),
                    "correct_answers": total_correct,
                    "total_questions": total_questions,
                    "accuracy_rate": round(
                        (total_correct / total_questions) * 100, 1
                    )
                    if total_questions > 0
                    else 0.0,
                    "participating_students": len(class_rows),
                    "subjects": cls._aggregate_subjects(class_rows, course_label=course_label),
                }
            )

        items.sort(
            key=lambda row: cls._sort_key_metrics(
                proficiency=row.get("average_proficiency"),
                score=row.get("average_score"),
                correct_answers=row.get("correct_answers"),
                total_questions=row.get("total_questions"),
                name=row.get("school_name"),
            )
        )
        for idx, row in enumerate(items):
            row["position"] = idx + 1
        return items

    @classmethod
    def _build_student_ranking(cls, peer_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for row in peer_rows:
            subjects = cls._student_subjects(row.get("subject_results") or {})
            fallback_correct = int(row.get("correct_answers") or 0)
            raw_correct = cls._raw_correct_sum(subjects, fallback_correct)
            school_name = row.get("school_name")
            course_name = row.get("course_name") or ""
            items.append(
                {
                    "student_id": row.get("student_id"),
                    "name": row.get("name"),
                    "school_id": row.get("school_id"),
                    "school_name": school_name,
                    "school_display_name": cls._school_display_name(school_name, course_name),
                    "class_id": row.get("class_id"),
                    "class_name": row.get("class_name"),
                    "shift": row.get("shift") or "",
                    "grade": round(float(row.get("grade") or 0), 1),
                    "proficiency": round(float(row.get("proficiency") or 0), 1),
                    "classification": row.get("classification") or "",
                    "correct_answers": fallback_correct,
                    "raw_correct_answers": raw_correct,
                    "total_questions": int(row.get("total_questions") or 0),
                    "accuracy_rate": round(float(row.get("score_percentage") or 0), 1),
                    "subjects": subjects,
                    "source_evaluation_id": row.get("source_evaluation_id"),
                    "course_name": course_name,
                }
            )
        items.sort(key=cls._sort_key_student)
        for idx, row in enumerate(items):
            row["position"] = idx + 1
        return items

    @classmethod
    def _student_subjects(cls, subject_results: Any) -> List[Dict[str, Any]]:
        if not isinstance(subject_results, dict):
            return []
        items: List[Dict[str, Any]] = []
        for subject_id, raw in subject_results.items():
            if not isinstance(raw, dict):
                continue
            correct = int(raw.get("correct_answers") or 0)
            total_q = int(raw.get("total_questions") or 0)
            items.append(
                {
                    "subject_id": str(subject_id),
                    "subject_name": str(raw.get("subject_name") or ""),
                    "grade": round(float(raw.get("grade") or 0), 1),
                    "proficiency": round(float(raw.get("proficiency") or 0), 1),
                    "classification": str(raw.get("classification") or ""),
                    "correct_answers": correct,
                    "total_questions": total_q,
                    "accuracy_rate": round((correct / total_q) * 100, 1) if total_q > 0 else 0.0,
                }
            )
        items.sort(key=lambda x: cls._normalize_text(x.get("subject_name")))
        return items

    @classmethod
    def _aggregate_subjects(
        cls,
        class_rows: Sequence[Dict[str, Any]],
        *,
        course_label: str,
    ) -> List[Dict[str, Any]]:
        bucket: Dict[str, Dict[str, Any]] = {}
        for row in class_rows:
            subjects = row.get("subject_results") or {}
            if not isinstance(subjects, dict):
                continue
            for subject_id, raw in subjects.items():
                if not isinstance(raw, dict):
                    continue
                sid = str(subject_id)
                entry = bucket.setdefault(
                    sid,
                    {
                        "subject_id": sid,
                        "subject_name": str(raw.get("subject_name") or ""),
                        "proficiencies": [],
                        "correct_answers": 0,
                        "total_questions": 0,
                    },
                )
                if raw.get("subject_name") and not entry["subject_name"]:
                    entry["subject_name"] = str(raw.get("subject_name"))
                if raw.get("proficiency") is not None:
                    entry["proficiencies"].append(float(raw.get("proficiency") or 0))
                entry["correct_answers"] += int(raw.get("correct_answers") or 0)
                entry["total_questions"] += int(raw.get("total_questions") or 0)

        items: List[Dict[str, Any]] = []
        for entry in bucket.values():
            profs = entry["proficiencies"]
            avg_prof = (sum(profs) / len(profs)) if profs else 0.0
            avg_score = aggregated_grade_from_proficiency(
                avg_prof, course_label, subject_name=entry["subject_name"] or "GERAL"
            )
            total_q = int(entry["total_questions"] or 0)
            correct = int(entry["correct_answers"] or 0)
            items.append(
                {
                    "subject_id": entry["subject_id"],
                    "subject_name": entry["subject_name"],
                    "average_proficiency": round(avg_prof, 1),
                    "average_score": round(float(avg_score or 0), 1),
                    "classification": cls._classification(
                        avg_prof,
                        course_label=course_label,
                        subject_name=entry["subject_name"] or "GERAL",
                    ),
                    "correct_answers": correct,
                    "total_questions": total_q,
                    "accuracy_rate": round((correct / total_q) * 100, 1) if total_q > 0 else 0.0,
                }
            )
        items.sort(key=lambda x: cls._normalize_text(x.get("subject_name")))
        return items
