# -*- coding: utf-8 -*-
"""
Comparação sequencial de gabaritos (cartões resposta) — espelha EvaluationComparisonService.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from app.answer_sheets.models.answerSheetGabarito import AnswerSheetGabarito
from app.answer_sheets.models.answerSheetResult import AnswerSheetResult
from app.models.skill import Skill
from app.models.student import Student
from app.models.studentClass import Class
from app.models.school import School
from app.reports.report_analysis.answer_sheet_report_builder import (
    question_skills_map_for_answer_sheet,
    union_target_class_ids_for_gabarito,
)
from app.evaluations.services.evaluation_comparison_service import EvaluationComparisonService
from app.services.skills_map_service import (
    _disciplinas_config_from_gabarito_blocks,
    _fetch_skills_batch,
    _gabarito_answer_map,
    _norm_skill_key,
    _parse_detected,
    _participating_answer_sheet_result,
    _question_num_to_subject_id,
)

logger = logging.getLogger(__name__)


class AnswerSheetComparisonService:
    """Compara múltiplos gabaritos de cartão resposta (evolução sequencial)."""

    @staticmethod
    def compare_gabaritos(
        gabarito_ids: List[str],
        *,
        scope_info: Optional[Dict[str, Any]] = None,
        nivel_granularidade: str = "municipio",
        user: Optional[dict] = None,
    ) -> Optional[Dict[str, Any]]:
        if len(gabarito_ids) < 2:
            logger.error("Mínimo de 2 gabaritos necessário. Recebido: %s", len(gabarito_ids))
            return None

        try:
            from app.answer_sheets.services.answer_sheet_result_snapshot import (
                query_answer_sheet_results_for_class_group,
                student_ids_for_answer_sheet_class_group,
            )
            from app.utils.school_equal_weight_means import (
                granularidade_to_hierarchical_target,
            )

            aggregation_level = granularidade_to_hierarchical_target(nivel_granularidade)

            gabaritos = AnswerSheetGabarito.query.filter(
                AnswerSheetGabarito.id.in_(gabarito_ids)
            ).all()
            if len(gabaritos) != len(gabarito_ids):
                missing = set(gabarito_ids) - {g.id for g in gabaritos}
                logger.error("Gabaritos não encontrados: %s", missing)
                return None

            gabaritos_with_dates: List[Dict[str, Any]] = []
            for gab in gabaritos:
                application_date = gab.created_at or datetime.min
                gabaritos_with_dates.append(
                    {"gabarito": gab, "application_date": application_date}
                )
            gabaritos_with_dates.sort(key=lambda x: x["application_date"])
            ordered_gabaritos = [item["gabarito"] for item in gabaritos_with_dates]

            def _load_scoped_results(gab_id: str, class_ids: List[Any]) -> List[AnswerSheetResult]:
                if not class_ids:
                    return []
                base_ids = {
                    s.id
                    for s in Student.query.filter(Student.class_id.in_(class_ids)).all()
                }
                merged_ids = student_ids_for_answer_sheet_class_group(
                    str(gab_id), class_ids, base_ids
                )
                raw = query_answer_sheet_results_for_class_group(
                    str(gab_id), class_ids, list(base_ids)
                ).all()
                # latest per student
                by_student: Dict[str, AnswerSheetResult] = {}
                for r in raw:
                    prev = by_student.get(r.student_id)
                    if prev is None:
                        by_student[r.student_id] = r
                        continue
                    prev_at = getattr(prev, "corrected_at", None)
                    cur_at = getattr(r, "corrected_at", None)
                    if cur_at and (not prev_at or cur_at >= prev_at):
                        by_student[r.student_id] = r
                return [
                    r
                    for r in by_student.values()
                    if r.student_id in merged_ids and _participating_answer_sheet_result(r)
                ]

            all_results: Dict[str, List[AnswerSheetResult]] = {}
            class_ids_by_gabarito: Dict[str, List[Any]] = {}
            for gab in ordered_gabaritos:
                if scope_info:
                    from app.answer_sheets.routes.answer_sheet_routes import (
                        _class_ids_alunos_previstos_cartao,
                    )

                    scope_gab = dict(scope_info)
                    scope_gab["gabarito"] = str(gab.id)
                    class_ids = _class_ids_alunos_previstos_cartao(
                        str(gab.id), scope_gab, nivel_granularidade, user
                    )
                    class_ids_by_gabarito[gab.id] = class_ids
                    participating = _load_scoped_results(str(gab.id), class_ids)
                else:
                    class_ids_by_gabarito[gab.id] = [
                        c
                        for c in AnswerSheetComparisonService._target_class_ids(gab.id)
                    ]
                    results = AnswerSheetResult.query.filter_by(gabarito_id=gab.id).all()
                    participating = [
                        r for r in results if _participating_answer_sheet_result(r)
                    ]
                if not participating:
                    logger.warning(
                        "Gabarito %s não possui resultados no escopo (%s)",
                        gab.id,
                        nivel_granularidade,
                    )
                    return None
                all_results[gab.id] = participating

            grade_info_by_gabarito = {
                gab.id: AnswerSheetComparisonService._resolve_gabarito_grade_info(gab)
                for gab in ordered_gabaritos
            }

            evaluations_data = []
            for i, item in enumerate(gabaritos_with_dates):
                gab = item["gabarito"]
                evaluations_data.append(
                    AnswerSheetComparisonService._build_gabarito_evaluation_entry(
                        gab,
                        i + 1,
                        item["application_date"],
                        grade_info_by_gabarito.get(gab.id),
                    )
                )

            comparisons = []
            for i in range(len(ordered_gabaritos) - 1):
                gab_from = ordered_gabaritos[i]
                gab_to = ordered_gabaritos[i + 1]
                results_from = all_results[gab_from.id]
                results_to = all_results[gab_to.id]

                comparisons.append(
                    {
                        "from_evaluation": AnswerSheetComparisonService._build_gabarito_evaluation_ref(
                            gab_from, i + 1, grade_info_by_gabarito.get(gab_from.id)
                        ),
                        "to_evaluation": AnswerSheetComparisonService._build_gabarito_evaluation_ref(
                            gab_to, i + 2, grade_info_by_gabarito.get(gab_to.id)
                        ),
                        "general_comparison": AnswerSheetComparisonService._get_general_comparison(
                            results_from,
                            results_to,
                            gab_from,
                            gab_to,
                            aggregation_level=aggregation_level,
                        ),
                        "subject_comparison": AnswerSheetComparisonService._get_subject_comparison(
                            gab_from,
                            gab_to,
                            results_from,
                            results_to,
                            aggregation_level=aggregation_level,
                        ),
                        "skills_comparison": AnswerSheetComparisonService._get_skills_comparison(
                            gab_from, gab_to, results_from, results_to
                        ),
                    }
                )

            participation_data = {"general": {}, "by_school": {}}
            for i, gab in enumerate(ordered_gabaritos):
                eval_key = f"evaluation_{i + 1}"
                cids = class_ids_by_gabarito.get(gab.id) or []
                participation_data["general"][eval_key] = (
                    AnswerSheetComparisonService._get_general_participation(
                        gab.id, class_ids=cids
                    )
                )
                participation_data["by_school"][eval_key] = (
                    AnswerSheetComparisonService._get_participation_by_school(
                        gab.id, class_ids=cids
                    )
                )

            filtros_aplicados = None
            if scope_info is not None:
                filtros_aplicados = {
                    "estado": scope_info.get("estado"),
                    "municipio": scope_info.get("municipio")
                    or scope_info.get("municipio_id"),
                    "escola": scope_info.get("escola"),
                    "serie": scope_info.get("serie"),
                    "turma": scope_info.get("turma"),
                }

            return {
                "source_type": "cartao_resposta",
                "nivel_granularidade": nivel_granularidade,
                "filtros_aplicados": filtros_aplicados,
                "evaluations": evaluations_data,
                "total_evaluations": len(ordered_gabaritos),
                "comparisons": comparisons,
                "total_comparisons": len(comparisons),
                "participation": participation_data,
            }
        except Exception as exc:
            logger.error(
                "Erro ao comparar gabaritos %s: %s", gabarito_ids, exc, exc_info=True
            )
            return None

    @staticmethod
    def compare_student_gabaritos_multiple(
        student_id: str, gabarito_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        if len(gabarito_ids) < 2:
            logger.error("Mínimo de 2 gabaritos necessário. Recebido: %s", len(gabarito_ids))
            return None

        try:
            student_obj = Student.query.filter_by(user_id=student_id).first()
            if not student_obj:
                student_obj = Student.query.get(student_id)
            if not student_obj:
                logger.error("Aluno não encontrado: %s", student_id)
                return None

            actual_student_id = student_obj.id
            gabaritos = AnswerSheetGabarito.query.filter(
                AnswerSheetGabarito.id.in_(gabarito_ids)
            ).all()
            if len(gabaritos) != len(gabarito_ids):
                missing = set(gabarito_ids) - {g.id for g in gabaritos}
                logger.error("Gabaritos não encontrados: %s", missing)
                return None

            gabaritos_with_dates = []
            for gab in gabaritos:
                application_date = gab.created_at or datetime.min
                gabaritos_with_dates.append(
                    {"gabarito": gab, "application_date": application_date}
                )
            gabaritos_with_dates.sort(key=lambda x: x["application_date"])
            ordered_gabaritos = [item["gabarito"] for item in gabaritos_with_dates]

            results_list = AnswerSheetResult.query.filter(
                AnswerSheetResult.student_id == actual_student_id,
                AnswerSheetResult.gabarito_id.in_(gabarito_ids),
            ).all()
            all_results = {
                r.gabarito_id: r
                for r in results_list
                if _participating_answer_sheet_result(r)
            }
            if len(all_results) != len(gabarito_ids):
                missing = set(gabarito_ids) - set(all_results.keys())
                logger.warning(
                    "Aluno %s não possui resultados nos gabaritos: %s",
                    actual_student_id,
                    missing,
                )
                return None

            grade_info_by_gabarito = {
                gab.id: AnswerSheetComparisonService._resolve_gabarito_grade_info(gab)
                for gab in ordered_gabaritos
            }

            evaluations_data = []
            for i, item in enumerate(gabaritos_with_dates):
                gab = item["gabarito"]
                evaluations_data.append(
                    AnswerSheetComparisonService._build_gabarito_evaluation_entry(
                        gab,
                        i + 1,
                        item["application_date"],
                        grade_info_by_gabarito.get(gab.id),
                    )
                )

            comparisons = []
            for i in range(len(ordered_gabaritos) - 1):
                gab_from = ordered_gabaritos[i]
                gab_to = ordered_gabaritos[i + 1]
                result_from = all_results.get(gab_from.id)
                result_to = all_results.get(gab_to.id)
                if not result_from or not result_to:
                    continue

                comparisons.append(
                    {
                        "from_evaluation": AnswerSheetComparisonService._build_gabarito_evaluation_ref(
                            gab_from, i + 1, grade_info_by_gabarito.get(gab_from.id)
                        ),
                        "to_evaluation": AnswerSheetComparisonService._build_gabarito_evaluation_ref(
                            gab_to, i + 2, grade_info_by_gabarito.get(gab_to.id)
                        ),
                        "general_comparison": AnswerSheetComparisonService._get_student_general_comparison(
                            result_from, result_to
                        ),
                        "subject_comparison": AnswerSheetComparisonService._get_student_subject_comparison(
                            gab_from, gab_to, result_from, result_to
                        ),
                        "skills_comparison": AnswerSheetComparisonService._get_student_skills_comparison(
                            gab_from, gab_to, result_from, result_to
                        ),
                    }
                )

            return {
                "source_type": "cartao_resposta",
                "student": {
                    "id": actual_student_id,
                    "user_id": student_obj.user_id,
                    "name": student_obj.name,
                },
                "evaluations": evaluations_data,
                "total_evaluations": len(ordered_gabaritos),
                "comparisons": comparisons,
                "total_comparisons": len(comparisons),
            }
        except Exception as exc:
            logger.error(
                "Erro ao comparar gabaritos do aluno %s: %s", student_id, exc, exc_info=True
            )
            return None

    @staticmethod
    def _course_meta_for_gabarito(gabarito: Optional[AnswerSheetGabarito]) -> Tuple[str, bool]:
        from app.answer_sheets.services.cartao_resposta.proficiency_by_subject import (
            course_name_and_has_matematica_for_gabarito,
        )

        gab_id = str(gabarito.id) if gabarito and getattr(gabarito, "id", None) else None
        return course_name_and_has_matematica_for_gabarito(gab_id)

    @staticmethod
    def _get_general_comparison(
        results_1: List[AnswerSheetResult],
        results_2: List[AnswerSheetResult],
        gab_1: Optional[AnswerSheetGabarito] = None,
        gab_2: Optional[AnswerSheetGabarito] = None,
        aggregation_level: str = "municipio",
    ) -> Dict[str, Any]:
        """Médias gerais com agregação hierárquica (mesma regra de resultados-agregados)."""
        try:
            from app.utils.school_equal_weight_means import (
                hierarchical_mean_grade_and_proficiency,
            )

            course_1, has_mat_1 = AnswerSheetComparisonService._course_meta_for_gabarito(gab_1)
            course_2, has_mat_2 = AnswerSheetComparisonService._course_meta_for_gabarito(gab_2)

            if results_1:
                avg_grade_1, avg_prof_1 = hierarchical_mean_grade_and_proficiency(
                    results_1,
                    aggregation_level,
                    course_name=course_1,
                    has_matematica=has_mat_1,
                )
            else:
                avg_grade_1, avg_prof_1 = 0.0, 0.0
            if results_2:
                avg_grade_2, avg_prof_2 = hierarchical_mean_grade_and_proficiency(
                    results_2,
                    aggregation_level,
                    course_name=course_2,
                    has_matematica=has_mat_2,
                )
            else:
                avg_grade_2, avg_prof_2 = 0.0, 0.0

            dist_1: Dict[str, int] = {}
            dist_2: Dict[str, int] = {}
            for result in results_1:
                cls = result.classification or "Não definido"
                dist_1[cls] = dist_1.get(cls, 0) + 1
            for result in results_2:
                cls = result.classification or "Não definido"
                dist_2[cls] = dist_2.get(cls, 0) + 1

            calc = EvaluationComparisonService._calculate_evolution_percentage
            return {
                "average_grade": {
                    "evaluation_1": round(avg_grade_1, 2),
                    "evaluation_2": round(avg_grade_2, 2),
                    "evolution": calc(avg_grade_1, avg_grade_2),
                },
                "average_proficiency": {
                    "evaluation_1": round(avg_prof_1, 2),
                    "evaluation_2": round(avg_prof_2, 2),
                    "evolution": calc(avg_prof_1, avg_prof_2),
                },
                "total_students": {
                    "evaluation_1": len(results_1),
                    "evaluation_2": len(results_2),
                },
                "classification_distribution": {
                    "evaluation_1": dist_1,
                    "evaluation_2": dist_2,
                },
            }
        except Exception as exc:
            logger.error("Erro ao calcular comparação geral (cartão): %s", exc)
            return {}

    @staticmethod
    def _extract_subjects_from_gabarito(gabarito: AnswerSheetGabarito) -> Dict[str, str]:
        blocks = _disciplinas_config_from_gabarito_blocks(
            getattr(gabarito, "blocks_config", None) or {}
        )
        if not blocks:
            return {"geral": "Geral"}
        return {str(b["id"]): (b.get("nome") or "Outras") for b in blocks}

    @staticmethod
    def _subject_entry(
        proficiency_by_subject: Optional[Dict], subject_id: str
    ) -> Optional[Dict[str, Any]]:
        if not proficiency_by_subject or not isinstance(proficiency_by_subject, dict):
            return None
        entry = proficiency_by_subject.get(subject_id)
        if entry is None:
            entry = proficiency_by_subject.get(str(subject_id))
        return entry if isinstance(entry, dict) else None

    @staticmethod
    def _get_subject_results_for_comparison(
        subject_id: str, results: List[AnswerSheetResult]
    ) -> List[Dict[str, Any]]:
        subject_results = []
        for result in results:
            entry = AnswerSheetComparisonService._subject_entry(
                result.proficiency_by_subject, subject_id
            )
            if not entry:
                continue
            subject_results.append(
                {
                    "student_id": result.student_id,
                    "grade": float(entry.get("grade") or 0),
                    "proficiency": float(entry.get("proficiency") or 0),
                    "classification": entry.get("classification"),
                    "class_id_snapshot": getattr(result, "class_id_snapshot", None),
                    "school_id_snapshot": getattr(result, "school_id_snapshot", None),
                    "grade_id_snapshot": getattr(result, "grade_id_snapshot", None),
                }
            )
        return subject_results

    @staticmethod
    def _get_subject_comparison(
        gab_1: AnswerSheetGabarito,
        gab_2: AnswerSheetGabarito,
        results_1: List[AnswerSheetResult],
        results_2: List[AnswerSheetResult],
        aggregation_level: str = "municipio",
    ) -> Dict[str, Any]:
        try:
            from app.utils.school_equal_weight_means import hierarchical_mean_from_subject_rows

            subjects_1 = AnswerSheetComparisonService._extract_subjects_from_gabarito(gab_1)
            subjects_2 = AnswerSheetComparisonService._extract_subjects_from_gabarito(gab_2)
            common_subjects = set(subjects_1.keys()) & set(subjects_2.keys())
            if not common_subjects:
                return {}

            course_1, has_mat_1 = AnswerSheetComparisonService._course_meta_for_gabarito(gab_1)
            course_2, has_mat_2 = AnswerSheetComparisonService._course_meta_for_gabarito(gab_2)

            calc = EvaluationComparisonService._calculate_evolution_percentage
            subject_comparison: Dict[str, Any] = {}

            for subject_id in common_subjects:
                subject_name = subjects_1.get(subject_id) or subjects_2.get(subject_id)
                subj_results_1 = AnswerSheetComparisonService._get_subject_results_for_comparison(
                    subject_id, results_1
                )
                subj_results_2 = AnswerSheetComparisonService._get_subject_results_for_comparison(
                    subject_id, results_2
                )
                if not subj_results_1 or not subj_results_2:
                    continue

                avg_grade_1, avg_prof_1, _ = hierarchical_mean_from_subject_rows(
                    subj_results_1,
                    aggregation_level,
                    course_name=course_1,
                    subject_name=subject_name or "GERAL",
                    has_matematica=has_mat_1,
                )
                avg_grade_2, avg_prof_2, _ = hierarchical_mean_from_subject_rows(
                    subj_results_2,
                    aggregation_level,
                    course_name=course_2,
                    subject_name=subject_name or "GERAL",
                    has_matematica=has_mat_2,
                )

                dist_1: Dict[str, int] = {}
                dist_2: Dict[str, int] = {}
                for row in subj_results_1:
                    cls = row.get("classification") or "Não definido"
                    dist_1[cls] = dist_1.get(cls, 0) + 1
                for row in subj_results_2:
                    cls = row.get("classification") or "Não definido"
                    dist_2[cls] = dist_2.get(cls, 0) + 1

                subject_comparison[subject_name] = {
                    "subject_id": subject_id,
                    "average_grade": {
                        "evaluation_1": round(avg_grade_1, 2),
                        "evaluation_2": round(avg_grade_2, 2),
                        "evolution": calc(avg_grade_1, avg_grade_2),
                    },
                    "average_proficiency": {
                        "evaluation_1": round(avg_prof_1, 2),
                        "evaluation_2": round(avg_prof_2, 2),
                        "evolution": calc(avg_prof_1, avg_prof_2),
                    },
                    "total_students": {
                        "evaluation_1": len(subj_results_1),
                        "evaluation_2": len(subj_results_2),
                    },
                    "classification_distribution": {
                        "evaluation_1": dist_1,
                        "evaluation_2": dist_2,
                    },
                }
            return subject_comparison
        except Exception as exc:
            logger.error("Erro ao calcular comparação por disciplina (cartão): %s", exc)
            return {}

    @staticmethod
    def _skills_index_for_gabarito(
        gabarito: AnswerSheetGabarito, subject_id: str
    ) -> Dict[str, Dict[str, str]]:
        """skill_norm -> {code, description} para questões da disciplina."""
        blocks_config = getattr(gabarito, "blocks_config", None) or {}
        disciplinas = _disciplinas_config_from_gabarito_blocks(blocks_config)
        gab_map = _gabarito_answer_map(gabarito)
        question_to_subject = _question_num_to_subject_id(disciplinas, gab_map)
        q_skills = question_skills_map_for_answer_sheet(gabarito)

        skill_ids: Set[str] = set()
        for qn, sids in q_skills.items():
            block_sid = question_to_subject.get(qn) or "geral"
            if str(block_sid) != str(subject_id):
                continue
            for sid in sids or []:
                if sid:
                    skill_ids.add(_norm_skill_key(str(sid).strip()))

        skills_db = _fetch_skills_batch(skill_ids)
        skills: Dict[str, Dict[str, str]] = {}
        for qn, sids in q_skills.items():
            block_sid = question_to_subject.get(qn) or "geral"
            if str(block_sid) != str(subject_id):
                continue
            for raw_sid in sids or []:
                if not raw_sid:
                    continue
                norm = _norm_skill_key(str(raw_sid).strip())
                if norm in skills:
                    continue
                obj = skills_db.get(norm)
                if not obj:
                    try:
                        UUID(norm)
                        obj = Skill.query.get(norm)
                    except ValueError:
                        obj = Skill.query.filter_by(code=norm).first()
                if obj:
                    skills[norm] = {"code": obj.code, "description": obj.description or obj.code}
                else:
                    clean = str(raw_sid).strip("{}")
                    skills[norm] = {
                        "code": clean,
                        "description": f"Skill {clean}",
                    }
        return skills

    @staticmethod
    def _question_numbers_for_skill(
        gabarito: AnswerSheetGabarito, subject_id: str, skill_norm: str
    ) -> List[int]:
        blocks_config = getattr(gabarito, "blocks_config", None) or {}
        disciplinas = _disciplinas_config_from_gabarito_blocks(blocks_config)
        gab_map = _gabarito_answer_map(gabarito)
        question_to_subject = _question_num_to_subject_id(disciplinas, gab_map)
        q_skills = question_skills_map_for_answer_sheet(gabarito)
        question_nums: List[int] = []
        for qn, sids in q_skills.items():
            block_sid = question_to_subject.get(qn) or "geral"
            if str(block_sid) != str(subject_id):
                continue
            for raw_sid in sids or []:
                if _norm_skill_key(str(raw_sid).strip()) == skill_norm:
                    question_nums.append(int(qn))
                    break
        return sorted(set(question_nums))

    @staticmethod
    def _get_skill_results_for_gabarito(
        gabarito: AnswerSheetGabarito,
        subject_id: str,
        skill_norm: str,
        results: List[AnswerSheetResult],
    ) -> Optional[Dict[str, Any]]:
        question_nums = AnswerSheetComparisonService._question_numbers_for_skill(
            gabarito, subject_id, skill_norm
        )
        if not question_nums:
            return None
        gab_map = _gabarito_answer_map(gabarito)
        correct = 0
        total = 0
        for result in results:
            detected = _parse_detected(result.detected_answers)
            for qn in question_nums:
                total += 1
                ca = gab_map.get(qn)
                st_ans = detected.get(qn, "")
                if ca is not None and st_ans and st_ans == ca:
                    correct += 1
        if total == 0:
            return None
        return {
            "correct_answers": correct,
            "total_questions": total,
            "percentage": (correct / total * 100) if total else 0,
        }

    @staticmethod
    def _get_skills_comparison(
        gab_1: AnswerSheetGabarito,
        gab_2: AnswerSheetGabarito,
        results_1: List[AnswerSheetResult],
        results_2: List[AnswerSheetResult],
    ) -> Dict[str, Any]:
        try:
            subjects_1 = AnswerSheetComparisonService._extract_subjects_from_gabarito(gab_1)
            subjects_2 = AnswerSheetComparisonService._extract_subjects_from_gabarito(gab_2)
            common_subjects = set(subjects_1.keys()) & set(subjects_2.keys())
            if not common_subjects:
                return {}

            calc = EvaluationComparisonService._calculate_evolution_percentage
            skills_comparison: Dict[str, Any] = {}

            for subject_id in common_subjects:
                subject_name = subjects_1.get(subject_id) or subjects_2.get(subject_id)
                skills_1 = AnswerSheetComparisonService._skills_index_for_gabarito(
                    gab_1, subject_id
                )
                skills_2 = AnswerSheetComparisonService._skills_index_for_gabarito(
                    gab_2, subject_id
                )
                common_skills = set(skills_1.keys()) & set(skills_2.keys())
                if not common_skills:
                    continue

                subject_skills: Dict[str, Any] = {}
                for skill_norm in common_skills:
                    info = skills_1.get(skill_norm) or skills_2.get(skill_norm) or {}
                    skill_results_1 = AnswerSheetComparisonService._get_skill_results_for_gabarito(
                        gab_1, subject_id, skill_norm, results_1
                    )
                    skill_results_2 = AnswerSheetComparisonService._get_skill_results_for_gabarito(
                        gab_2, subject_id, skill_norm, results_2
                    )
                    if not skill_results_1 or not skill_results_2:
                        continue
                    pct_1 = skill_results_1["percentage"]
                    pct_2 = skill_results_2["percentage"]
                    subject_skills[skill_norm] = {
                        "code": info.get("code", skill_norm),
                        "description": info.get("description", f"Skill {skill_norm}"),
                        "evaluation_1": {
                            "correct_answers": skill_results_1["correct_answers"],
                            "total_questions": skill_results_1["total_questions"],
                            "percentage": round(pct_1, 2),
                        },
                        "evaluation_2": {
                            "correct_answers": skill_results_2["correct_answers"],
                            "total_questions": skill_results_2["total_questions"],
                            "percentage": round(pct_2, 2),
                        },
                        "evolution": calc(pct_1, pct_2),
                    }
                if subject_skills:
                    skills_comparison[subject_name] = subject_skills
            return skills_comparison
        except Exception as exc:
            logger.error("Erro ao calcular comparação por habilidade (cartão): %s", exc)
            return {}

    @staticmethod
    def _target_class_ids(gabarito_id: str) -> List[str]:
        gab = AnswerSheetGabarito.query.get(gabarito_id)
        if not gab:
            return []
        return [str(c) for c in union_target_class_ids_for_gabarito(gab)]

    @staticmethod
    def _get_general_participation(
        gabarito_id: str, class_ids: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        try:
            if class_ids is None:
                class_ids = AnswerSheetComparisonService._target_class_ids(gabarito_id)
            if not class_ids:
                return {
                    "total_students": 0,
                    "participating_students": 0,
                    "participation_rate": 0.0,
                }

            try:
                class_uuids = [UUID(str(c)) for c in class_ids]
            except ValueError:
                class_uuids = class_ids

            total_students = Student.query.filter(
                Student.class_id.in_(class_uuids)
            ).count()

            from app.answer_sheets.services.answer_sheet_result_snapshot import (
                query_answer_sheet_results_for_class_group,
            )

            base_ids = [
                s.id
                for s in Student.query.filter(Student.class_id.in_(class_uuids))
                .with_entities(Student.id)
                .all()
            ]
            raw = query_answer_sheet_results_for_class_group(
                str(gabarito_id), class_uuids, base_ids
            ).all()
            seen = set()
            participating = 0
            for r in raw:
                if r.student_id in seen:
                    continue
                if _participating_answer_sheet_result(r):
                    seen.add(r.student_id)
                    participating += 1
            rate = (participating / total_students * 100) if total_students > 0 else 0.0
            return {
                "total_students": total_students,
                "participating_students": participating,
                "participation_rate": round(rate, 2),
            }
        except Exception as exc:
            logger.error(
                "Erro ao calcular participação geral (cartão) %s: %s",
                gabarito_id,
                exc,
                exc_info=True,
            )
            return {
                "total_students": 0,
                "participating_students": 0,
                "participation_rate": 0.0,
            }

    @staticmethod
    def _get_participation_by_school(
        gabarito_id: str, class_ids: Optional[List[Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        try:
            if class_ids is None:
                class_ids = AnswerSheetComparisonService._target_class_ids(gabarito_id)
            if not class_ids:
                return {}

            try:
                class_uuids = [UUID(str(c)) for c in class_ids]
            except ValueError:
                class_uuids = class_ids

            classes = Class.query.filter(Class.id.in_(class_uuids)).all()
            schools_data: Dict[str, Dict[str, Any]] = {}
            for class_obj in classes:
                if not class_obj.school_id:
                    continue
                school_id = str(class_obj.school_id)
                if school_id not in schools_data:
                    school = School.query.get(class_obj.school_id)
                    schools_data[school_id] = {
                        "school_id": school_id,
                        "school_name": school.name if school else f"Escola {school_id}",
                        "class_ids": [],
                    }
                schools_data[school_id]["class_ids"].append(class_obj.id)

            from app.answer_sheets.services.answer_sheet_result_snapshot import (
                query_answer_sheet_results_for_class_group,
            )

            participation_by_school: Dict[str, Dict[str, Any]] = {}
            for school_id, school_info in schools_data.items():
                class_ids_school = school_info["class_ids"]
                total_students = Student.query.filter(
                    Student.class_id.in_(class_ids_school)
                ).count()
                if total_students == 0:
                    continue

                base_ids = [
                    s.id
                    for s in Student.query.filter(Student.class_id.in_(class_ids_school))
                    .with_entities(Student.id)
                    .all()
                ]
                raw = query_answer_sheet_results_for_class_group(
                    str(gabarito_id), class_ids_school, base_ids
                ).all()
                seen = set()
                participating = 0
                for r in raw:
                    if r.student_id in seen:
                        continue
                    if _participating_answer_sheet_result(r):
                        seen.add(r.student_id)
                        participating += 1
                rate = (participating / total_students * 100) if total_students > 0 else 0.0
                participation_by_school[school_id] = {
                    "school_name": school_info["school_name"],
                    "total_students": total_students,
                    "participating_students": participating,
                    "participation_rate": round(rate, 2),
                }
            return participation_by_school
        except Exception as exc:
            logger.error(
                "Erro ao calcular participação por escola (cartão) %s: %s",
                gabarito_id,
                exc,
                exc_info=True,
            )
            return {}

    @staticmethod
    def _get_student_general_comparison(
        result_1: AnswerSheetResult, result_2: AnswerSheetResult
    ) -> Dict[str, Any]:
        calc = EvaluationComparisonService._calculate_evolution_percentage
        return {
            "student_grade": {
                "evaluation_1": round(result_1.grade, 2),
                "evaluation_2": round(result_2.grade, 2),
                "evolution": calc(result_1.grade, result_2.grade),
            },
            "student_proficiency": {
                "evaluation_1": round(result_1.proficiency or 0, 2),
                "evaluation_2": round(result_2.proficiency or 0, 2),
                "evolution": calc(result_1.proficiency or 0, result_2.proficiency or 0),
            },
            "student_classification": {
                "evaluation_1": result_1.classification or "Não definido",
                "evaluation_2": result_2.classification or "Não definido",
            },
        }

    @staticmethod
    def _get_student_subject_comparison(
        gab_1: AnswerSheetGabarito,
        gab_2: AnswerSheetGabarito,
        result_1: AnswerSheetResult,
        result_2: AnswerSheetResult,
    ) -> Dict[str, Any]:
        subjects_1 = AnswerSheetComparisonService._extract_subjects_from_gabarito(gab_1)
        subjects_2 = AnswerSheetComparisonService._extract_subjects_from_gabarito(gab_2)
        common = set(subjects_1.keys()) & set(subjects_2.keys())
        calc = EvaluationComparisonService._calculate_evolution_percentage
        out: Dict[str, Any] = {}
        for subject_id in common:
            name = subjects_1.get(subject_id) or subjects_2.get(subject_id)
            e1 = AnswerSheetComparisonService._subject_entry(
                result_1.proficiency_by_subject, subject_id
            )
            e2 = AnswerSheetComparisonService._subject_entry(
                result_2.proficiency_by_subject, subject_id
            )
            if not e1 or not e2:
                continue
            g1 = float(e1.get("grade") or 0)
            g2 = float(e2.get("grade") or 0)
            p1 = float(e1.get("proficiency") or 0)
            p2 = float(e2.get("proficiency") or 0)
            out[name] = {
                "subject_id": subject_id,
                "grade": {
                    "evaluation_1": round(g1, 2),
                    "evaluation_2": round(g2, 2),
                    "evolution": calc(g1, g2),
                },
                "proficiency": {
                    "evaluation_1": round(p1, 2),
                    "evaluation_2": round(p2, 2),
                    "evolution": calc(p1, p2),
                },
                "classification": {
                    "evaluation_1": e1.get("classification") or "Não definido",
                    "evaluation_2": e2.get("classification") or "Não definido",
                },
            }
        return out

    @staticmethod
    def _get_student_skills_comparison(
        gab_1: AnswerSheetGabarito,
        gab_2: AnswerSheetGabarito,
        result_1: AnswerSheetResult,
        result_2: AnswerSheetResult,
    ) -> Dict[str, Any]:
        subjects_1 = AnswerSheetComparisonService._extract_subjects_from_gabarito(gab_1)
        subjects_2 = AnswerSheetComparisonService._extract_subjects_from_gabarito(gab_2)
        common = set(subjects_1.keys()) & set(subjects_2.keys())
        calc = EvaluationComparisonService._calculate_evolution_percentage
        out: Dict[str, Any] = {}

        for subject_id in common:
            name = subjects_1.get(subject_id) or subjects_2.get(subject_id)
            skills_1 = AnswerSheetComparisonService._skills_index_for_gabarito(
                gab_1, subject_id
            )
            skills_2 = AnswerSheetComparisonService._skills_index_for_gabarito(
                gab_2, subject_id
            )
            common_skills = set(skills_1.keys()) & set(skills_2.keys())
            subject_out: Dict[str, Any] = {}

            detected_1 = _parse_detected(result_1.detected_answers)
            detected_2 = _parse_detected(result_2.detected_answers)
            gab_map_1 = _gabarito_answer_map(gab_1)
            gab_map_2 = _gabarito_answer_map(gab_2)

            for skill_norm in common_skills:
                qnums_1 = AnswerSheetComparisonService._question_numbers_for_skill(
                    gab_1, subject_id, skill_norm
                )
                qnums_2 = AnswerSheetComparisonService._question_numbers_for_skill(
                    gab_2, subject_id, skill_norm
                )
                if not qnums_1 or not qnums_2:
                    continue

                c1 = t1 = c2 = t2 = 0
                for qn in qnums_1:
                    t1 += 1
                    if detected_1.get(qn) == gab_map_1.get(qn):
                        c1 += 1
                for qn in qnums_2:
                    t2 += 1
                    if detected_2.get(qn) == gab_map_2.get(qn):
                        c2 += 1
                if t1 == 0 or t2 == 0:
                    continue

                pct_1 = c1 / t1 * 100
                pct_2 = c2 / t2 * 100
                info = skills_1.get(skill_norm) or skills_2.get(skill_norm) or {}
                subject_out[skill_norm] = {
                    "code": info.get("code", skill_norm),
                    "description": info.get("description", f"Skill {skill_norm}"),
                    "evaluation_1": {
                        "correct_answers": c1,
                        "total_questions": t1,
                        "percentage": round(pct_1, 2),
                    },
                    "evaluation_2": {
                        "correct_answers": c2,
                        "total_questions": t2,
                        "percentage": round(pct_2, 2),
                    },
                    "evolution": calc(pct_1, pct_2),
                }
            if subject_out:
                out[name] = subject_out
        return out

    @staticmethod
    def _resolve_gabarito_grade_info(gabarito: AnswerSheetGabarito) -> Dict[str, Any]:
        """Série(s) e turma(s) do gabarito (turmas-alvo / grade_id / grade_name)."""
        from uuid import UUID

        from app.models.grades import Grade

        grade_id_by_str: Dict[str, str] = {}
        class_id_set: Set[str] = set()
        classes_list: List[Dict[str, str]] = []

        stored_name = (getattr(gabarito, "grade_name", None) or "").strip()
        if getattr(gabarito, "grade_id", None):
            gid = str(gabarito.grade_id)
            if stored_name:
                grade_id_by_str[gid] = stored_name
            else:
                grade_obj = Grade.query.get(gabarito.grade_id)
                grade_id_by_str[gid] = grade_obj.name if grade_obj and grade_obj.name else gid

        if getattr(gabarito, "class_id", None):
            class_id_set.add(str(gabarito.class_id))

        try:
            class_id_set |= {str(x) for x in (union_target_class_ids_for_gabarito(gabarito) or set()) if x}
        except Exception:
            pass

        if class_id_set:
            uuid_ids = []
            for cid in class_id_set:
                try:
                    uuid_ids.append(UUID(str(cid)))
                except ValueError:
                    continue
            if uuid_ids:
                for class_obj in Class.query.filter(Class.id.in_(uuid_ids)).all():
                    classes_list.append(
                        {
                            "id": str(class_obj.id),
                            "name": class_obj.name or f"Turma {class_obj.id}",
                        }
                    )
                    if not class_obj.grade_id:
                        continue
                    gid = str(class_obj.grade_id)
                    if gid in grade_id_by_str:
                        continue
                    grade_obj = Grade.query.get(class_obj.grade_id)
                    grade_id_by_str[gid] = grade_obj.name if grade_obj and grade_obj.name else gid

        classes_list.sort(key=lambda item: (item.get("name") or "").lower())

        grade_names = sorted({name for name in grade_id_by_str.values() if name})
        grade_ids = sorted(grade_id_by_str.keys())

        grade_id = str(gabarito.grade_id) if getattr(gabarito, "grade_id", None) else None
        grade_name = stored_name or None

        if grade_ids:
            if grade_id and grade_id in grade_ids:
                grade_name = grade_name or grade_id_by_str.get(grade_id)
            else:
                grade_id = grade_ids[0]
                grade_name = grade_id_by_str.get(grade_id) or grade_name
        elif grade_id and not grade_name:
            grade_obj = Grade.query.get(gabarito.grade_id)
            grade_name = grade_obj.name if grade_obj and grade_obj.name else None

        if grade_names and not grade_name:
            grade_name = grade_names[0]
        if grade_name and grade_name not in grade_names:
            grade_names = sorted(set(grade_names) | {grade_name})

        return {
            "grade_id": grade_id,
            "grade_name": grade_name,
            "grade_names": grade_names,
            "classes": classes_list,
        }

    @staticmethod
    def _build_gabarito_evaluation_entry(
        gabarito: AnswerSheetGabarito,
        order: int,
        application_date,
        grade_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        info = grade_info or AnswerSheetComparisonService._resolve_gabarito_grade_info(gabarito)
        return {
            "order": order,
            "id": gabarito.id,
            "title": gabarito.title or "Cartão resposta",
            "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None,
            "application_date": application_date.isoformat() if application_date else None,
            **info,
        }

    @staticmethod
    def _build_gabarito_evaluation_ref(
        gabarito: AnswerSheetGabarito,
        order: int,
        grade_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        info = grade_info or AnswerSheetComparisonService._resolve_gabarito_grade_info(gabarito)
        return {
            "id": gabarito.id,
            "title": gabarito.title or "Cartão resposta",
            "order": order,
            **info,
        }
