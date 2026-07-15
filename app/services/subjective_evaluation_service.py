# -*- coding: utf-8 -*-
"""
Serviço de correção manual e cálculo de resultados da avaliação subjetiva
(Test.evaluation_mode == 'subjective').

Fluxo: sem resposta online do aluno. O professor aplica a prova (impressa/presencial)
e lança o resultado diretamente aqui, por aluno e por questão, usando a rubrica
SIM / PARCIAL / NAO / BRANCO (ver app.models.subjectiveResult). Ao finalizar a turma,
calculamos nota/proficiência/classificação por aluno reaproveitando EvaluationCalculator
(mesmas fórmulas das avaliações online) e gravamos em EvaluationResult através de uma
TestSession "sintética" (status 'corrigida'), apenas para satisfazer a FK obrigatória e
reaproveitar 100% do pipeline de relatórios existente (GET /evaluation-results/avaliacoes,
mapa de habilidades, hierarchical_mean_grade_and_proficiency) sem duplicar lógica.

Agregações acima do nível turma (série/escola/município) continuam usando
app.utils.school_equal_weight_means.hierarchical_mean_grade_and_proficiency, já aplicada
pelas rotas de evaluation-results — este serviço só calcula o resultado POR ALUNO.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.student import Student
from app.models.studentClass import Class
from app.models.school import School
from app.models.testSession import TestSession
from app.models.evaluationResult import EvaluationResult
from app.models.subjectiveResult import SubjectiveResult, RUBRIC_VALUES, RUBRIC_WEIGHTS
from app.models.subjectivePresence import SubjectivePresence
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.evaluation_result_snapshot import build_placement_snapshots_from_student
from app.report_analysis.services import ReportAggregateService
from app.utils.decimal_helpers import round_to_two_decimals


class SubjectiveEvaluationService:

    @staticmethod
    def get_questions_for_test(test_id: str) -> List[Question]:
        """Questões da avaliação, na ordem definida em TestQuestion.order."""
        test_question_ids = [
            tq.question_id
            for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
        ]
        if not test_question_ids:
            return []
        questions_by_id = {q.id: q for q in Question.query.filter(Question.id.in_(test_question_ids)).all()}
        return [questions_by_id[qid] for qid in test_question_ids if qid in questions_by_id]

    @staticmethod
    def get_correction_matrix(test_id: str, class_id) -> Optional[Dict[str, Any]]:
        """Matriz aluno x questão para a tela de correção manual de uma turma."""
        test = Test.query.get(test_id)
        if not test:
            return None

        questions = SubjectiveEvaluationService.get_questions_for_test(test_id)
        students = Student.query.filter(Student.class_id == class_id).order_by(Student.name).all()
        student_ids = [s.id for s in students]

        results = (
            SubjectiveResult.query.filter(
                SubjectiveResult.test_id == test_id,
                SubjectiveResult.student_id.in_(student_ids),
            ).all()
            if student_ids else []
        )
        results_map: Dict[str, Dict[str, str]] = {}
        for r in results:
            results_map.setdefault(str(r.student_id), {})[str(r.question_id)] = r.value

        presences = (
            SubjectivePresence.query.filter(
                SubjectivePresence.test_id == test_id,
                SubjectivePresence.student_id.in_(student_ids),
            ).all()
            if student_ids else []
        )
        presence_map = {str(p.student_id): p.present for p in presences}

        return {
            "test": {
                "id": test.id,
                "title": test.title,
                "evaluation_mode": test.evaluation_mode,
            },
            "questions": [
                {
                    "id": q.id,
                    "number": q.number,
                    "text": q.text,
                    "question_type": q.question_type,
                    "skill": q.skill,
                    "interaction_config": q.interaction_config,
                }
                for q in questions
            ],
            "students": [
                {
                    "id": s.id,
                    "name": s.name,
                    "registration": s.registration,
                    "present": presence_map.get(str(s.id), True),
                    "results": results_map.get(str(s.id), {}),
                }
                for s in students
            ],
        }

    @staticmethod
    def upsert_rubric_value(
        test_id: str,
        question_id: str,
        student_id: str,
        value: Optional[str],
        corrected_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lança/atualiza a rubrica de uma célula (aluno x questão).
        value=None ou repetir o mesmo valor já lançado remove o lançamento
        (mesma UX de "clicar de novo para desmarcar" do protótipo).
        """
        if value is not None and value not in RUBRIC_VALUES:
            raise ValueError(f"Valor de rubrica inválido: {value}. Aceitos: {', '.join(RUBRIC_VALUES)}")

        existing = SubjectiveResult.query.filter_by(
            test_id=test_id, question_id=question_id, student_id=student_id
        ).first()

        if value is None or (existing and existing.value == value):
            if existing:
                db.session.delete(existing)
                db.session.commit()
            return {"removed": True}

        if existing:
            existing.value = value
            existing.corrected_by = corrected_by
            existing.corrected_at = datetime.utcnow()
        else:
            existing = SubjectiveResult(
                test_id=test_id,
                question_id=question_id,
                student_id=student_id,
                value=value,
                corrected_by=corrected_by,
            )
            db.session.add(existing)

        db.session.commit()
        return {"removed": False, "result": existing.to_dict()}

    @staticmethod
    def set_presence(
        test_id: str,
        student_id: str,
        present: bool,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atualiza (ou cria) a presença de um aluno na avaliação subjetiva."""
        existing = SubjectivePresence.query.filter_by(test_id=test_id, student_id=student_id).first()
        if existing:
            existing.present = present
            existing.updated_by = updated_by
            existing.updated_at = datetime.utcnow()
        else:
            existing = SubjectivePresence(
                test_id=test_id, student_id=student_id, present=present, updated_by=updated_by
            )
            db.session.add(existing)
        db.session.commit()
        return existing.to_dict()

    @staticmethod
    def _resolve_course_and_subject_names(test: Test) -> Tuple[str, str]:
        course_name = "Anos Iniciais"
        if test.course:
            try:
                from app.models.educationStage import EducationStage
                import uuid as _uuid

                course_uuid = _uuid.UUID(test.course)
                course_obj = EducationStage.query.get(course_uuid)
                if course_obj:
                    course_name = course_obj.name
            except (ValueError, TypeError):
                pass

        subject_name = "Outras"
        if getattr(test, "subject_rel", None):
            subject_name = test.subject_rel.name
        return course_name, subject_name

    @staticmethod
    def _get_or_create_synthetic_session(test_id: str, student_id: str) -> TestSession:
        """
        TestSession "sintética": não representa uma sessão online real (não existe nesse
        fluxo — o aluno não responde online). Serve apenas para satisfazer
        EvaluationResult.session_id (FK obrigatória) e reaproveitar o pipeline de
        relatórios existente sem duplicar lógica.
        """
        session = (
            TestSession.query.filter_by(test_id=test_id, student_id=student_id)
            .order_by(TestSession.created_at.desc())
            .first()
        )
        if session:
            return session
        session = TestSession(student_id=student_id, test_id=test_id)
        session.status = 'corrigida'
        db.session.add(session)
        db.session.flush()
        return session

    @staticmethod
    def calculate_and_save_result_for_student(
        test_id: str,
        student_id: str,
        corrected_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Calcula nota/proficiência/classificação de um aluno a partir da rubrica lançada
        e grava em EvaluationResult (via TestSession sintética).

        Pontuação do aluno = média aritmética dos itens (SIM=1, PARCIAL=0.5, NAO=0,
        BRANCO=0) sobre o TOTAL de questões da avaliação — itens ainda não lançados
        contam como BRANCO=0 (mesmo critério usado na tela de correção). Este cálculo
        é por aluno; agregações acima da turma usam a média hierárquica com peso igual
        entre unidades (ver docs/FONTE_DA_VERDADE_CALCULOS_RESULTADOS.md §7).

        Alunos marcados como ausentes não geram/mantêm resultado.
        """
        try:
            test = Test.query.get(test_id)
            if not test:
                logging.error("SubjectiveEvaluationService: teste %s não encontrado", test_id)
                return None

            presence = SubjectivePresence.query.filter_by(test_id=test_id, student_id=student_id).first()
            if presence and not presence.present:
                existing = EvaluationResult.query.filter_by(test_id=test_id, student_id=student_id).first()
                if existing:
                    db.session.delete(existing)
                    db.session.commit()
                return {"skipped": True, "reason": "ausente", "student_id": student_id}

            questions = SubjectiveEvaluationService.get_questions_for_test(test_id)
            total_questions = len(questions)
            if total_questions == 0:
                logging.warning("SubjectiveEvaluationService: teste %s sem questões", test_id)
                return None

            question_ids = [q.id for q in questions]
            results = SubjectiveResult.query.filter(
                SubjectiveResult.test_id == test_id,
                SubjectiveResult.student_id == student_id,
                SubjectiveResult.question_id.in_(question_ids),
            ).all()
            value_by_question = {str(r.question_id): r.value for r in results}

            weighted_sum = 0.0
            correct_equivalent_count = 0
            for qid in question_ids:
                v = value_by_question.get(str(qid))
                weighted_sum += RUBRIC_WEIGHTS.get(v, 0.0)
                if v == 'SIM':
                    correct_equivalent_count += 1

            course_name, subject_name = SubjectiveEvaluationService._resolve_course_and_subject_names(test)
            use_simple_calculation = test.grade_calculation_type == 'simple'

            calc_result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=weighted_sum,
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name,
                use_simple_calculation=use_simple_calculation,
            )

            score_percentage = round_to_two_decimals((weighted_sum / total_questions) * 100) if total_questions > 0 else 0.0

            session = SubjectiveEvaluationService._get_or_create_synthetic_session(test_id, student_id)
            session.total_questions = total_questions
            session.correct_answers = correct_equivalent_count
            session.score = score_percentage
            session.grade = calc_result['grade']
            session.status = 'corrigida'
            session.corrected_by = corrected_by
            session.corrected_at = datetime.utcnow()
            if not session.submitted_at:
                session.submitted_at = datetime.utcnow()

            student_obj = Student.query.get(student_id)
            placement = build_placement_snapshots_from_student(student_obj) if student_obj else {}

            existing_result = EvaluationResult.query.filter_by(test_id=test_id, student_id=student_id).first()
            if existing_result:
                existing_result.correct_answers = correct_equivalent_count
                existing_result.total_questions = total_questions
                existing_result.score_percentage = score_percentage
                existing_result.grade = calc_result['grade']
                existing_result.proficiency = calc_result['proficiency']
                existing_result.classification = calc_result['classification']
                existing_result.calculated_at = datetime.utcnow()
                for snap_key in (
                    "school_id_snapshot", "class_id_snapshot", "grade_id_snapshot", "enrollment_id_snapshot",
                ):
                    if getattr(existing_result, snap_key, None) is None and placement.get(snap_key) is not None:
                        setattr(existing_result, snap_key, placement[snap_key])
                evaluation_result = existing_result
            else:
                evaluation_result = EvaluationResult(
                    test_id=test_id,
                    student_id=student_id,
                    session_id=session.id,
                    correct_answers=correct_equivalent_count,
                    total_questions=total_questions,
                    score_percentage=score_percentage,
                    grade=calc_result['grade'],
                    proficiency=calc_result['proficiency'],
                    classification=calc_result['classification'],
                )
                for snap_key, snap_val in placement.items():
                    if snap_val is not None:
                        setattr(evaluation_result, snap_key, snap_val)
                db.session.add(evaluation_result)

            db.session.commit()

            SubjectiveEvaluationService._mark_reports_dirty(test_id, evaluation_result, student_obj)

            return {
                "skipped": False,
                "student_id": student_id,
                "test_id": test_id,
                "correct_answers": correct_equivalent_count,
                "total_questions": total_questions,
                "score_percentage": score_percentage,
                "grade": calc_result['grade'],
                "proficiency": calc_result['proficiency'],
                "classification": calc_result['classification'],
            }
        except Exception as e:
            logging.error(
                "Erro ao calcular resultado subjetivo aluno=%s test=%s: %s",
                student_id, test_id, str(e), exc_info=True,
            )
            db.session.rollback()
            return None

    @staticmethod
    def _mark_reports_dirty(test_id: str, evaluation_result: EvaluationResult, student_obj) -> None:
        try:
            scope_school_id = getattr(evaluation_result, "school_id_snapshot", None) or (
                getattr(student_obj, "school_id", None) if student_obj else None
            )
            class_identifier = getattr(evaluation_result, "class_id_snapshot", None) or (
                getattr(student_obj, "class_id", None) if student_obj else None
            )

            if not scope_school_id and class_identifier:
                class_obj = Class.query.get(class_identifier)
                if class_obj and getattr(class_obj, "school_id", None):
                    scope_school_id = class_obj.school_id

            scope_city_id = None
            if scope_school_id:
                school_obj = School.query.get(scope_school_id)
                if school_obj and getattr(school_obj, "city_id", None):
                    scope_city_id = school_obj.city_id

            ReportAggregateService.mark_dirty(test_id, 'overall', None, commit=False)
            ReportAggregateService.mark_ai_dirty(test_id, 'overall', None, commit=False)
            if scope_school_id:
                ReportAggregateService.mark_dirty(test_id, 'school', scope_school_id, commit=False)
                ReportAggregateService.mark_ai_dirty(test_id, 'school', scope_school_id, commit=False)
            if scope_city_id:
                ReportAggregateService.mark_dirty(test_id, 'city', scope_city_id, commit=False)
                ReportAggregateService.mark_ai_dirty(test_id, 'city', scope_city_id, commit=False)
            db.session.commit()

            if scope_city_id:
                try:
                    from app.report_analysis.tasks import rebuild_reports_for_test
                    rebuild_reports_for_test.delay(test_id, str(scope_city_id))
                except Exception as e:
                    logging.warning("Rebuild não agendado (avaliação subjetiva): %s", str(e))
        except Exception as e:
            logging.warning("Falha ao marcar relatórios dirty (avaliação subjetiva): %s", str(e))

    @staticmethod
    def finalize_class(test_id: str, class_id, corrected_by: Optional[str] = None) -> Dict[str, Any]:
        """Calcula e grava o resultado de todos os alunos de uma turma para a avaliação."""
        students = Student.query.filter(Student.class_id == class_id).all()
        processed = []
        skipped = []
        errors = []
        for student in students:
            outcome = SubjectiveEvaluationService.calculate_and_save_result_for_student(
                test_id, student.id, corrected_by=corrected_by
            )
            if outcome is None:
                errors.append(str(student.id))
            elif outcome.get("skipped"):
                skipped.append(str(student.id))
            else:
                processed.append(outcome)
        return {
            "processed_count": len(processed),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "processed": processed,
            "skipped_student_ids": skipped,
            "error_student_ids": errors,
        }
