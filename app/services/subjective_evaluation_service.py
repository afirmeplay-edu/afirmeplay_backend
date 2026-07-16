# -*- coding: utf-8 -*-
"""
Serviço da avaliação subjetiva: CRUD da estrutura (SubjectiveTest/SubjectiveQuestion),
correção manual e cálculo de resultados.

Avaliação subjetiva é uma entidade própria, separada de Test/Question: a prova em si é
física/impressa e fica fora do sistema. O sistema só guarda a ESTRUTURA (quantidade de
questões e, por questão, uma habilidade digitada livremente). Não há resposta online do
aluno: o professor aplica a prova e lança o resultado diretamente aqui, por aluno e por
questão, usando a rubrica SIM / PARCIAL / NAO / BRANCO (ver app.models.subjectiveResult).

Ao finalizar a turma, calculamos nota/proficiência/classificação por aluno reaproveitando
EvaluationCalculator (mesmas fórmulas das avaliações online) e gravamos em EvaluationResult
através de um Test "espelho" (`SubjectiveTest.shadow_test_id`) + uma TestSession "sintética"
(status 'corrigida'), apenas para satisfazer as FKs obrigatórias e reaproveitar 100% do
pipeline de relatórios existente (GET /evaluation-results/avaliacoes, mapa de habilidades,
hierarchical_mean_grade_and_proficiency) sem duplicar lógica. O Test espelho nunca é
exposto/editado diretamente pelo frontend.

Agregações acima do nível turma (série/escola/município) continuam usando
app.utils.school_equal_weight_means.hierarchical_mean_grade_and_proficiency, já aplicada
pelas rotas de evaluation-results — este serviço só calcula o resultado POR ALUNO.
"""
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.subjectiveTest import SubjectiveTest
from app.models.subjectiveQuestion import SubjectiveQuestion
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

# Níveis SAEB simplificados do dashboard da avaliação subjetiva (protótipo AVALIAÇÃO SUBJETIVA).
# Diferente da classificação TRI do EvaluationCalculator: aqui a faixa é só por % de acerto
# da rubrica (SIM=1, PARCIAL=0.5, NAO/BRANCO=0).
SAEB_LEVEL_LABELS = {
    'abaixo': 'Abaixo do Básico',
    'basico': 'Básico',
    'adequado': 'Adequado',
    'avancado': 'Avançado',
}


def saeb_from_pct(pct: float) -> Dict[str, str]:
    """Mapeia % de acerto ponderado da rubrica para o nível SAEB simplificado do dashboard."""
    if pct >= 80:
        level = 'avancado'
    elif pct >= 60:
        level = 'adequado'
    elif pct >= 40:
        level = 'basico'
    else:
        level = 'abaixo'
    return {'level': level, 'label': SAEB_LEVEL_LABELS[level]}


class SubjectiveEvaluationService:

    # ------------------------------------------------------------------
    # CRUD da avaliação subjetiva
    # ------------------------------------------------------------------

    @staticmethod
    def _create_shadow_test(subjective_test: SubjectiveTest, created_by: Optional[str]) -> Test:
        """
        Cria o registro-espelho em tenant.test usado internamente para reaproveitar
        EvaluationResult/ClassTest/relatórios. Nunca é exposto ao frontend.
        """
        shadow = Test(
            title=subjective_test.title,
            description=subjective_test.description,
            type='AVALIACAO',
            subject=subjective_test.subject_id,
            grade_id=subjective_test.grade_id,
            evaluation_mode='subjective',
            created_by=created_by,
            municipalities=subjective_test.municipalities,
            schools=subjective_test.schools,
            classes=subjective_test.classes,
            model='SUBJETIVA',
            status='pendente',
        )
        db.session.add(shadow)
        db.session.flush()
        return shadow

    @staticmethod
    def _resolve_target_class_ids(subjective_test: SubjectiveTest) -> List:
        """
        Resolve as turmas-alvo a partir do escopo (mesma prioridade do padrão de Test):
        turmas específicas > escolas (+ série) > municípios (+ série).
        """
        from app.utils.uuid_helpers import ensure_uuid_list

        if subjective_test.classes:
            class_ids = (
                subjective_test.classes if isinstance(subjective_test.classes, list) else [subjective_test.classes]
            )
            return ensure_uuid_list(class_ids)

        if subjective_test.schools:
            school_ids = (
                subjective_test.schools if isinstance(subjective_test.schools, list) else [subjective_test.schools]
            )
            classes = Class.query.filter(
                Class.grade_id == subjective_test.grade_id,
                Class.school_id.in_([str(s) for s in school_ids]),
            ).all()
            return [c.id for c in classes]

        if subjective_test.municipalities:
            municipality_ids = (
                subjective_test.municipalities
                if isinstance(subjective_test.municipalities, list)
                else [subjective_test.municipalities]
            )
            schools_in_cities = School.query.filter(School.city_id.in_(municipality_ids)).with_entities(School.id).all()
            school_ids = [s.id for s in schools_in_cities]
            if not school_ids:
                return []
            classes = Class.query.filter(
                Class.grade_id == subjective_test.grade_id,
                Class.school_id.in_(school_ids),
            ).all()
            return [c.id for c in classes]

        return []

    @staticmethod
    def _sync_shadow_class_tests(subjective_test: SubjectiveTest) -> None:
        """
        Mantém tenant.class_test sincronizado com o escopo da avaliação subjetiva,
        usando o Test espelho — é isso que faz o resultado aparecer nas rotas de
        evaluation-results (que filtram/agrupam via ClassTest). `application`/
        `expiration` só têm efeito no filtro de período dos relatórios; aqui usamos a
        data de aplicação informada (ou a data de criação, se não houver).
        """
        if not subjective_test.shadow_test_id:
            return

        target_class_ids = set(SubjectiveEvaluationService._resolve_target_class_ids(subjective_test))

        existing = ClassTest.query.filter_by(test_id=subjective_test.shadow_test_id).all()
        existing_by_class = {ct.class_id: ct for ct in existing}

        for class_id, class_test in existing_by_class.items():
            if class_id not in target_class_ids:
                db.session.delete(class_test)

        reference_date = subjective_test.application_date or datetime.utcnow().date()
        application_iso = datetime.combine(reference_date, datetime.min.time()).isoformat()

        for class_id in target_class_ids:
            if class_id in existing_by_class:
                continue
            db.session.add(ClassTest(
                class_id=class_id,
                test_id=subjective_test.shadow_test_id,
                status='agendada',
                application=application_iso,
                expiration=application_iso,
            ))

    @staticmethod
    def create_subjective_test(data: Dict[str, Any], created_by: Optional[str]) -> SubjectiveTest:
        """
        Cria a avaliação subjetiva + questões (habilidades) + Test espelho.
        `data['questions']` é uma lista de {number, code, skill_description}.
        """
        application_date = None
        if data.get('application_date'):
            raw = data['application_date']
            application_date = raw if isinstance(raw, date) else datetime.fromisoformat(str(raw)).date()

        subjective_test = SubjectiveTest(
            title=data.get('title'),
            description=data.get('description'),
            test_type=data.get('test_type') or 'Diagnóstica',
            subject_id=data.get('subject_id') or data.get('subject'),
            grade_id=data.get('grade_id') or data.get('grade'),
            application_date=application_date,
            municipalities=data.get('municipalities'),
            schools=data.get('schools'),
            classes=data.get('classes'),
            status='pendente',
            created_by=created_by,
        )
        db.session.add(subjective_test)
        db.session.flush()

        questions = data.get('questions') or []
        for index, q in enumerate(questions):
            db.session.add(SubjectiveQuestion(
                subjective_test_id=subjective_test.id,
                number=q.get('number') or (index + 1),
                code=q.get('code'),
                skill_description=q.get('skill_description') or q.get('skillDescription') or '',
            ))

        shadow_test = SubjectiveEvaluationService._create_shadow_test(subjective_test, created_by)
        subjective_test.shadow_test_id = shadow_test.id
        SubjectiveEvaluationService._sync_shadow_class_tests(subjective_test)

        db.session.commit()
        return subjective_test

    @staticmethod
    def update_subjective_test(subjective_test: SubjectiveTest, data: Dict[str, Any]) -> SubjectiveTest:
        """
        Atualiza campos da avaliação e, se `questions` for enviado, substitui a lista
        de questões por completo (mais simples e seguro que fazer diff parcial).
        """
        simple_fields = ('title', 'description', 'test_type', 'municipalities', 'schools', 'classes')
        for field in simple_fields:
            if field in data:
                setattr(subjective_test, field, data[field])

        if 'subject_id' in data or 'subject' in data:
            subjective_test.subject_id = data.get('subject_id') or data.get('subject')
        if 'grade_id' in data or 'grade' in data:
            subjective_test.grade_id = data.get('grade_id') or data.get('grade')
        if 'application_date' in data:
            raw = data['application_date']
            subjective_test.application_date = (
                (raw if isinstance(raw, date) else datetime.fromisoformat(str(raw)).date()) if raw else None
            )

        if 'questions' in data and isinstance(data['questions'], list):
            SubjectiveQuestion.query.filter_by(subjective_test_id=subjective_test.id).delete()
            for index, q in enumerate(data['questions']):
                db.session.add(SubjectiveQuestion(
                    subjective_test_id=subjective_test.id,
                    number=q.get('number') or (index + 1),
                    code=q.get('code'),
                    skill_description=q.get('skill_description') or q.get('skillDescription') or '',
                ))

        # Mantém o Test espelho e as ClassTest sincronizados nos campos usados por relatórios/escopo.
        if subjective_test.shadow_test:
            shadow = subjective_test.shadow_test
            shadow.title = subjective_test.title
            shadow.description = subjective_test.description
            shadow.subject = subjective_test.subject_id
            shadow.grade_id = subjective_test.grade_id
            shadow.municipalities = subjective_test.municipalities
            shadow.schools = subjective_test.schools
            shadow.classes = subjective_test.classes
        SubjectiveEvaluationService._sync_shadow_class_tests(subjective_test)

        db.session.commit()
        return subjective_test

    @staticmethod
    def delete_subjective_test(subjective_test: SubjectiveTest) -> None:
        """Remove a avaliação (cascade cuida de questions/results/presences) e o Test espelho."""
        shadow_test_id = subjective_test.shadow_test_id
        db.session.delete(subjective_test)
        db.session.flush()

        if shadow_test_id:
            from app.models.classTest import ClassTest
            ClassTest.query.filter_by(test_id=shadow_test_id).delete()
            EvaluationResult.query.filter_by(test_id=shadow_test_id).delete()
            TestSession.query.filter_by(test_id=shadow_test_id).delete()
            shadow = Test.query.get(shadow_test_id)
            if shadow:
                db.session.delete(shadow)

        db.session.commit()

    # ------------------------------------------------------------------
    # Correção manual
    # ------------------------------------------------------------------

    @staticmethod
    def get_correction_matrix(subjective_test_id: str, class_id) -> Optional[Dict[str, Any]]:
        """Matriz aluno x questão para a tela de correção manual de uma turma."""
        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return None

        questions = subjective_test.questions
        students = Student.query.filter(Student.class_id == class_id).order_by(Student.name).all()
        student_ids = [s.id for s in students]

        results = (
            SubjectiveResult.query.filter(
                SubjectiveResult.subjective_test_id == subjective_test_id,
                SubjectiveResult.student_id.in_(student_ids),
            ).all()
            if student_ids else []
        )
        results_map: Dict[str, Dict[str, str]] = {}
        for r in results:
            results_map.setdefault(str(r.student_id), {})[str(r.subjective_question_id)] = r.value

        presences = (
            SubjectivePresence.query.filter(
                SubjectivePresence.subjective_test_id == subjective_test_id,
                SubjectivePresence.student_id.in_(student_ids),
            ).all()
            if student_ids else []
        )
        presence_map = {str(p.student_id): p.present for p in presences}

        return {
            "subjective_test": {
                "id": subjective_test.id,
                "title": subjective_test.title,
                "test_type": subjective_test.test_type,
            },
            "questions": [q.to_dict() for q in questions],
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
        subjective_test_id: str,
        subjective_question_id: str,
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
            subjective_test_id=subjective_test_id,
            subjective_question_id=subjective_question_id,
            student_id=student_id,
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
                subjective_test_id=subjective_test_id,
                subjective_question_id=subjective_question_id,
                student_id=student_id,
                value=value,
                corrected_by=corrected_by,
            )
            db.session.add(existing)

        db.session.commit()
        return {"removed": False, "result": existing.to_dict()}

    @staticmethod
    def set_presence(
        subjective_test_id: str,
        student_id: str,
        present: bool,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atualiza (ou cria) a presença de um aluno na avaliação subjetiva."""
        existing = SubjectivePresence.query.filter_by(
            subjective_test_id=subjective_test_id, student_id=student_id
        ).first()
        if existing:
            existing.present = present
            existing.updated_by = updated_by
            existing.updated_at = datetime.utcnow()
        else:
            existing = SubjectivePresence(
                subjective_test_id=subjective_test_id, student_id=student_id, present=present, updated_by=updated_by
            )
            db.session.add(existing)
        db.session.commit()
        return existing.to_dict()

    # ------------------------------------------------------------------
    # Cálculo de nota/proficiência
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_course_and_subject_names(subjective_test: SubjectiveTest) -> Tuple[str, str]:
        course_name = "Anos Iniciais"
        grade_obj = subjective_test.grade
        if grade_obj and getattr(grade_obj, "education_stage_id", None):
            from app.models.educationStage import EducationStage
            course_obj = EducationStage.query.get(grade_obj.education_stage_id)
            if course_obj:
                course_name = course_obj.name

        subject_name = "Outras"
        if subjective_test.subject_rel:
            subject_name = subjective_test.subject_rel.name
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
        subjective_test_id: str,
        student_id: str,
        corrected_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Calcula nota/proficiência/classificação de um aluno a partir da rubrica lançada
        e grava em EvaluationResult (via Test espelho + TestSession sintética).

        Pontuação do aluno = média aritmética dos itens (SIM=1, PARCIAL=0.5, NAO=0,
        BRANCO=0) sobre o TOTAL de questões da avaliação — itens ainda não lançados
        contam como BRANCO=0 (mesmo critério usado na tela de correção). Este cálculo
        é por aluno; agregações acima da turma usam a média hierárquica com peso igual
        entre unidades (ver docs/FONTE_DA_VERDADE_CALCULOS_RESULTADOS.md §7).

        Alunos marcados como ausentes não geram/mantêm resultado.
        """
        try:
            subjective_test = SubjectiveTest.query.get(subjective_test_id)
            if not subjective_test:
                logging.error("SubjectiveEvaluationService: avaliação %s não encontrada", subjective_test_id)
                return None
            if not subjective_test.shadow_test_id:
                logging.error(
                    "SubjectiveEvaluationService: avaliação %s sem Test espelho", subjective_test_id
                )
                return None
            shadow_test_id = subjective_test.shadow_test_id

            presence = SubjectivePresence.query.filter_by(
                subjective_test_id=subjective_test_id, student_id=student_id
            ).first()
            if presence and not presence.present:
                existing = EvaluationResult.query.filter_by(test_id=shadow_test_id, student_id=student_id).first()
                if existing:
                    db.session.delete(existing)
                    db.session.commit()
                return {"skipped": True, "reason": "ausente", "student_id": student_id}

            questions = subjective_test.questions
            total_questions = len(questions)
            if total_questions == 0:
                logging.warning("SubjectiveEvaluationService: avaliação %s sem questões", subjective_test_id)
                return None

            question_ids = [q.id for q in questions]
            results = SubjectiveResult.query.filter(
                SubjectiveResult.subjective_test_id == subjective_test_id,
                SubjectiveResult.student_id == student_id,
                SubjectiveResult.subjective_question_id.in_(question_ids),
            ).all()
            value_by_question = {str(r.subjective_question_id): r.value for r in results}

            weighted_sum = 0.0
            correct_equivalent_count = 0
            for qid in question_ids:
                v = value_by_question.get(str(qid))
                weighted_sum += RUBRIC_WEIGHTS.get(v, 0.0)
                if v == 'SIM':
                    correct_equivalent_count += 1

            course_name, subject_name = SubjectiveEvaluationService._resolve_course_and_subject_names(subjective_test)

            calc_result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=weighted_sum,
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name,
                use_simple_calculation=False,
            )

            score_percentage = round_to_two_decimals((weighted_sum / total_questions) * 100) if total_questions > 0 else 0.0

            session = SubjectiveEvaluationService._get_or_create_synthetic_session(shadow_test_id, student_id)
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

            existing_result = EvaluationResult.query.filter_by(test_id=shadow_test_id, student_id=student_id).first()
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
                    test_id=shadow_test_id,
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

            SubjectiveEvaluationService._mark_reports_dirty(shadow_test_id, evaluation_result, student_obj)

            return {
                "skipped": False,
                "student_id": student_id,
                "subjective_test_id": subjective_test_id,
                "correct_answers": correct_equivalent_count,
                "total_questions": total_questions,
                "score_percentage": score_percentage,
                "grade": calc_result['grade'],
                "proficiency": calc_result['proficiency'],
                "classification": calc_result['classification'],
            }
        except Exception as e:
            logging.error(
                "Erro ao calcular resultado subjetivo aluno=%s avaliacao=%s: %s",
                student_id, subjective_test_id, str(e), exc_info=True,
            )
            db.session.rollback()
            return None

    @staticmethod
    def _mark_reports_dirty(shadow_test_id: str, evaluation_result: EvaluationResult, student_obj) -> None:
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

            ReportAggregateService.mark_dirty(shadow_test_id, 'overall', None, commit=False)
            ReportAggregateService.mark_ai_dirty(shadow_test_id, 'overall', None, commit=False)
            if scope_school_id:
                ReportAggregateService.mark_dirty(shadow_test_id, 'school', scope_school_id, commit=False)
                ReportAggregateService.mark_ai_dirty(shadow_test_id, 'school', scope_school_id, commit=False)
            if scope_city_id:
                ReportAggregateService.mark_dirty(shadow_test_id, 'city', scope_city_id, commit=False)
                ReportAggregateService.mark_ai_dirty(shadow_test_id, 'city', scope_city_id, commit=False)
            db.session.commit()

            if scope_city_id:
                try:
                    from app.report_analysis.tasks import rebuild_reports_for_test
                    rebuild_reports_for_test.delay(shadow_test_id, str(scope_city_id))
                except Exception as e:
                    logging.warning("Rebuild não agendado (avaliação subjetiva): %s", str(e))
        except Exception as e:
            logging.warning("Falha ao marcar relatórios dirty (avaliação subjetiva): %s", str(e))

    @staticmethod
    def finalize_class(subjective_test_id: str, class_id, corrected_by: Optional[str] = None) -> Dict[str, Any]:
        """Calcula e grava o resultado de todos os alunos de uma turma para a avaliação."""
        students = Student.query.filter(Student.class_id == class_id).all()
        processed = []
        skipped = []
        errors = []
        for student in students:
            outcome = SubjectiveEvaluationService.calculate_and_save_result_for_student(
                subjective_test_id, student.id, corrected_by=corrected_by
            )
            if outcome is None:
                errors.append(str(student.id))
            elif outcome.get("skipped"):
                skipped.append(str(student.id))
            else:
                processed.append(outcome)

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if subjective_test and subjective_test.status != 'concluida':
            subjective_test.status = 'concluida'
            db.session.commit()

        return {
            "processed_count": len(processed),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "processed": processed,
            "skipped_student_ids": skipped,
            "error_student_ids": errors,
        }

    # ------------------------------------------------------------------
    # Dashboard de resultados (distribuição da rubrica + SAEB simplificado)
    # ------------------------------------------------------------------

    @staticmethod
    def get_dashboard(
        subjective_test_id: str,
        class_id=None,
        allowed_class_ids: Optional[List] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Agrega os dados do painel de resultados da avaliação subjetiva.

        Escopo: uma turma (`class_id`) ou todas as turmas do escopo da avaliação.
        `allowed_class_ids`, se informado (ex.: turmas do professor), restringe o conjunto.

        Não usa EvaluationResult/TRI: trabalha só com SubjectiveResult (rubrica) e
        SubjectivePresence — alinhado ao dashboard do protótipo AVALIAÇÃO SUBJETIVA.
        """
        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return None

        scope_class_ids = SubjectiveEvaluationService._resolve_target_class_ids(subjective_test)
        if allowed_class_ids is not None:
            allowed_set = set(allowed_class_ids)
            scope_class_ids = [cid for cid in scope_class_ids if cid in allowed_set]

        # Lista de turmas do filtro (escopo completo acessível), independente do class_id selecionado.
        filter_classes = (
            Class.query.filter(Class.id.in_(scope_class_ids)).order_by(Class.name).all()
            if scope_class_ids else []
        )
        classes_payload = [{"id": c.id, "name": c.name} for c in filter_classes]

        if class_id is not None:
            if scope_class_ids and class_id not in scope_class_ids:
                return {"error": "class_out_of_scope"}
            target_class_ids = [class_id]
        else:
            target_class_ids = scope_class_ids

        students = (
            Student.query.filter(Student.class_id.in_(target_class_ids)).all()
            if target_class_ids else []
        )
        student_ids = [s.id for s in students]
        total_students = len(students)

        questions = (
            SubjectiveQuestion.query
            .filter_by(subjective_test_id=subjective_test_id)
            .order_by(SubjectiveQuestion.number)
            .all()
        )

        results = (
            SubjectiveResult.query.filter(
                SubjectiveResult.subjective_test_id == subjective_test_id,
                SubjectiveResult.student_id.in_(student_ids),
            ).all()
            if student_ids else []
        )
        presences = (
            SubjectivePresence.query.filter(
                SubjectivePresence.subjective_test_id == subjective_test_id,
                SubjectivePresence.student_id.in_(student_ids),
            ).all()
            if student_ids else []
        )

        totals = {v: 0 for v in RUBRIC_VALUES}
        results_by_question: Dict[str, List[SubjectiveResult]] = {}
        respondent_ids = set()
        for r in results:
            if r.value in totals:
                totals[r.value] += 1
            results_by_question.setdefault(str(r.subjective_question_id), []).append(r)
            respondent_ids.add(str(r.student_id))

        total_responses = len(results)
        respondents = len(respondent_ids)
        marked_absent = sum(1 for p in presences if not p.present)
        absent = max(marked_absent, max(0, total_students - respondents))

        weighted_sum = totals['SIM'] + totals['PARCIAL'] * 0.5
        hit_rate_pct = round((weighted_sum / total_responses) * 100) if total_responses > 0 else 0
        saeb_global = saeb_from_pct(hit_rate_pct)
        participation_pct = round((respondents / total_students) * 100) if total_students > 0 else 0

        distribution = []
        for name in RUBRIC_VALUES:
            value = totals[name]
            pct = round((value / total_responses) * 100) if total_responses > 0 else 0
            distribution.append({"name": name, "value": value, "pct": pct})

        saeb_levels = {'abaixo': 0, 'basico': 0, 'adequado': 0, 'avancado': 0}
        per_question = []
        for q in questions:
            rows = results_by_question.get(str(q.id), [])
            counts = {v: 0 for v in RUBRIC_VALUES}
            for r in rows:
                if r.value in counts:
                    counts[r.value] += 1
            q_total = len(rows)
            q_weighted = counts['SIM'] + counts['PARCIAL'] * 0.5
            q_hit = round((q_weighted / q_total) * 100) if q_total > 0 else 0
            q_saeb = saeb_from_pct(q_hit) if q_total > 0 else {'level': None, 'label': None}
            if q_total > 0 and q_saeb['level']:
                saeb_levels[q_saeb['level']] += 1

            per_question.append({
                "id": q.id,
                "number": q.number,
                "code": q.code,
                "skill_description": q.skill_description,
                "SIM": counts['SIM'],
                "PARCIAL": counts['PARCIAL'],
                "NAO": counts['NAO'],
                "BRANCO": counts['BRANCO'],
                "total": q_total,
                "hit_rate_pct": q_hit,
                "saeb_level": q_saeb['level'],
                "saeb_label": q_saeb['label'],
            })

        return {
            "subjective_test": {
                "id": subjective_test.id,
                "title": subjective_test.title,
                "test_type": subjective_test.test_type,
            },
            "filters": {
                "class_id": str(class_id) if class_id is not None else None,
                "classes": classes_payload,
            },
            "kpis": {
                "total_students": total_students,
                "respondents": respondents,
                "participation_pct": participation_pct,
                "absent": absent,
                "hit_rate_pct": hit_rate_pct,
                "saeb_level": saeb_global['level'],
                "saeb_label": saeb_global['label'],
                "total_responses": total_responses,
            },
            "totals": totals,
            "distribution": distribution,
            "saeb_levels": saeb_levels,
            "per_question": per_question,
        }
