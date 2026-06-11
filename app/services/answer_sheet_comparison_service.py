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

from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.skill import Skill
from app.models.student import Student
from app.models.studentClass import Class
from app.models.school import School
from app.report_analysis.answer_sheet_report_builder import (
    question_skills_map_for_answer_sheet,
    union_target_class_ids_for_gabarito,
)
from app.services.evaluation_comparison_service import EvaluationComparisonService
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
    def compare_gabaritos(gabarito_ids: List[str]) -> Optional[Dict[str, Any]]:
        if len(gabarito_ids) < 2:
            logger.error("Mínimo de 2 gabaritos necessário. Recebido: %s", len(gabarito_ids))
            return None

        try:
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

            all_results: Dict[str, List[AnswerSheetResult]] = {}
            for gab in ordered_gabaritos:
                results = AnswerSheetResult.query.filter_by(gabarito_id=gab.id).all()
                participating = [r for r in results if _participating_answer_sheet_result(r)]
                if not participating:
                    logger.warning("Gabarito %s não possui resultados calculados", gab.id)
                    return None
                all_results[gab.id] = participating

            evaluations_data = []
            for i, item in enumerate(gabaritos_with_dates):
                gab = item["gabarito"]
                evaluations_data.append(
                    {
                        "order": i + 1,
                        "id": gab.id,
                        "title": gab.title or "Cartão resposta",
                        "created_at": gab.created_at.isoformat() if gab.created_at else None,
                        "application_date": item["application_date"].isoformat()
                        if item["application_date"]
                        else None,
                    }
                )

            comparisons = []
            for i in range(len(ordered_gabaritos) - 1):
                gab_from = ordered_gabaritos[i]
                gab_to = ordered_gabaritos[i + 1]
                results_from = all_results[gab_from.id]
                results_to = all_results[gab_to.id]

                comparisons.append(
                    {
                        "from_evaluation": {
                            "id": gab_from.id,
                            "title": gab_from.title or "Cartão resposta",
                            "order": i + 1,
                        },
                        "to_evaluation": {
                            "id": gab_to.id,
                            "title": gab_to.title or "Cartão resposta",
                            "order": i + 2,
                        },
                        "general_comparison": AnswerSheetComparisonService._get_general_comparison(
                            results_from, results_to
                        ),
                        "subject_comparison": AnswerSheetComparisonService._get_subject_comparison(
                            gab_from, gab_to, results_from, results_to
                        ),
                        "skills_comparison": AnswerSheetComparisonService._get_skills_comparison(
                            gab_from, gab_to, results_from, results_to
                        ),
                    }
                )

            participation_data = {"general": {}, "by_school": {}}
            for i, gab in enumerate(ordered_gabaritos):
                eval_key = f"evaluation_{i + 1}"
                participation_data["general"][eval_key] = (
                    AnswerSheetComparisonService._get_general_participation(gab.id)
                )
                participation_data["by_school"][eval_key] = (
                    AnswerSheetComparisonService._get_participation_by_school(gab.id)
                )

            return {
                "source_type": "cartao_resposta",
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

            evaluations_data = []
            for i, item in enumerate(gabaritos_with_dates):
                gab = item["gabarito"]
                evaluations_data.append(
                    {
                        "order": i + 1,
                        "id": gab.id,
                        "title": gab.title or "Cartão resposta",
                        "created_at": gab.created_at.isoformat() if gab.created_at else None,
                        "application_date": item["application_date"].isoformat()
                        if item["application_date"]
                        else None,
                    }
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
                        "from_evaluation": {
                            "id": gab_from.id,
                            "title": gab_from.title or "Cartão resposta",
                            "order": i + 1,
                        },
                        "to_evaluation": {
                            "id": gab_to.id,
                            "title": gab_to.title or "Cartão resposta",
                            "order": i + 2,
                        },
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
    def _get_general_comparison(
        results_1: List[AnswerSheetResult], results_2: List[AnswerSheetResult]
    ) -> Dict[str, Any]:
        try:
            avg_grade_1 = sum(r.grade for r in results_1) / len(results_1) if results_1 else 0
            avg_prof_1 = (
                sum(r.proficiency or 0 for r in results_1) / len(results_1)
                if results_1
                else 0
            )
            avg_grade_2 = sum(r.grade for r in results_2) / len(results_2) if results_2 else 0
            avg_prof_2 = (
                sum(r.proficiency or 0 for r in results_2) / len(results_2)
                if results_2
                else 0
            )

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
                }
            )
        return subject_results

    @staticmethod
    def _get_subject_comparison(
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

                avg_grade_1 = sum(r["grade"] for r in subj_results_1) / len(subj_results_1)
                avg_prof_1 = sum(r["proficiency"] for r in subj_results_1) / len(subj_results_1)
                avg_grade_2 = sum(r["grade"] for r in subj_results_2) / len(subj_results_2)
                avg_prof_2 = sum(r["proficiency"] for r in subj_results_2) / len(subj_results_2)

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
    def _get_general_participation(gabarito_id: str) -> Dict[str, Any]:
        try:
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

            participating = (
                AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
                .join(Student, AnswerSheetResult.student_id == Student.id)
                .filter(Student.class_id.in_(class_uuids))
                .count()
            )
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
    def _get_participation_by_school(gabarito_id: str) -> Dict[str, Dict[str, Any]]:
        try:
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

            participation_by_school: Dict[str, Dict[str, Any]] = {}
            for school_id, school_info in schools_data.items():
                class_ids_school = school_info["class_ids"]
                total_students = Student.query.filter(
                    Student.class_id.in_(class_ids_school)
                ).count()
                if total_students == 0:
                    continue

                student_ids = [
                    s[0]
                    for s in Student.query.filter(Student.class_id.in_(class_ids_school))
                    .with_entities(Student.id)
                    .all()
                ]
                participating = AnswerSheetResult.query.filter(
                    AnswerSheetResult.gabarito_id == gabarito_id,
                    AnswerSheetResult.student_id.in_(student_ids),
                ).count()
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
