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
import re
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
from app.models.subjectiveRubricMark import SubjectiveRubricMark, DEFAULT_RUBRIC_MARKS
from app.models.subjectivePresence import SubjectivePresence
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.evaluation_result_snapshot import build_placement_snapshots_from_student
from app.report_analysis.services import ReportAggregateService
from app.utils.decimal_helpers import round_to_two_decimals

# Níveis SAEB simplificados do dashboard da avaliação subjetiva (protótipo AVALIAÇÃO SUBJETIVA).
# Diferente da classificação TRI do EvaluationCalculator: aqui a faixa é só por % de acerto
# ponderado da rubrica (peso da marcação / peso máximo).
SAEB_LEVEL_LABELS = {
    'abaixo': 'Abaixo do Básico',
    'basico': 'Básico',
    'adequado': 'Adequado',
    'avancado': 'Avançado',
}

_HEX_COLOR = re.compile(r'^#?[0-9A-Fa-f]{6}$')


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
    # Marcações da rubrica
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_hex_color(raw: Any, fallback: str = '#64748b') -> str:
        text = str(raw or '').strip()
        if not text:
            return fallback
        if not text.startswith('#'):
            text = f'#{text}'
        if _HEX_COLOR.match(text):
            return text.lower()
        return fallback

    @staticmethod
    def _slug_code(label: str, used: set) -> str:
        base = re.sub(r'[^A-Za-z0-9]', '', (label or '').upper())[:12] or 'M'
        code = base
        n = 2
        while code in used:
            suffix = str(n)
            code = f'{base[: max(1, 12 - len(suffix))]}{suffix}'
            n += 1
        return code[:20]

    @staticmethod
    def normalize_rubric_marks_payload(raw: Any) -> List[Dict[str, Any]]:
        """
        Valida/normaliza a lista de marcações do POST/PUT.
        Se vazio/ausente, devolve o template padrão.
        """
        source = raw if isinstance(raw, list) and len(raw) > 0 else list(DEFAULT_RUBRIC_MARKS)
        if len(source) < 2:
            raise ValueError('Informe ao menos duas marcações na rubrica.')
        if len(source) > 12:
            raise ValueError('No máximo 12 marcações por avaliação.')

        used_codes = set()
        normalized = []
        for index, item in enumerate(source):
            if not isinstance(item, dict):
                raise ValueError('Cada marcação deve ser um objeto.')
            label = str(item.get('label') or item.get('name') or '').strip()
            if not label:
                raise ValueError(f'Marcação #{index + 1}: informe o rótulo.')
            code = str(item.get('code') or item.get('sigla') or '').strip().upper()
            code = ''.join(ch for ch in code if ch.isalnum() or ch in ('_', '-'))[:20]
            if not code:
                code = SubjectiveEvaluationService._slug_code(label, used_codes)
            if code in used_codes:
                raise ValueError(f'Sigla duplicada na rubrica: {code}')
            used_codes.add(code)
            try:
                weight = float(item.get('weight') if item.get('weight') is not None else 0)
            except (TypeError, ValueError):
                raise ValueError(f'Marcação {label}: peso inválido.')
            if weight < 0 or weight > 1:
                raise ValueError(f'Marcação {label}: o peso deve estar entre 0 e 1 (1 = acerto pleno).')
            color = SubjectiveEvaluationService._normalize_hex_color(item.get('color'))
            sort_order = item.get('sort_order')
            try:
                sort_order = int(sort_order) if sort_order is not None else index
            except (TypeError, ValueError):
                sort_order = index
            normalized.append({
                'code': code,
                'label': label[:80],
                'color': color,
                'weight': weight,
                'sort_order': sort_order,
            })
        normalized.sort(key=lambda m: m['sort_order'])
        for i, mark in enumerate(normalized):
            mark['sort_order'] = i
        return normalized

    @staticmethod
    def _replace_rubric_marks(subjective_test_id: str, marks: List[Dict[str, Any]]) -> None:
        SubjectiveRubricMark.query.filter_by(subjective_test_id=subjective_test_id).delete()
        for mark in marks:
            db.session.add(SubjectiveRubricMark(
                subjective_test_id=subjective_test_id,
                code=mark['code'],
                label=mark['label'],
                color=mark['color'],
                weight=mark['weight'],
                sort_order=mark['sort_order'],
            ))

    @staticmethod
    def get_rubric_marks(subjective_test_id: str) -> List[Dict[str, Any]]:
        fallback = [
            {**dict(m), 'id': None, 'subjective_test_id': subjective_test_id}
            for m in DEFAULT_RUBRIC_MARKS
        ]
        try:
            rows = (
                SubjectiveRubricMark.query
                .filter_by(subjective_test_id=subjective_test_id)
                .order_by(SubjectiveRubricMark.sort_order, SubjectiveRubricMark.code)
                .all()
            )
        except Exception:
            db.session.rollback()
            return fallback
        if rows:
            return [r.to_dict() for r in rows]
        return fallback

    @staticmethod
    def _weights_for_test(subjective_test_id: str) -> Dict[str, float]:
        marks = SubjectiveEvaluationService.get_rubric_marks(subjective_test_id)
        weights = {m['code']: float(m['weight']) for m in marks}
        return weights or dict(RUBRIC_WEIGHTS)

    @staticmethod
    def _allowed_codes(subjective_test_id: str) -> List[str]:
        marks = SubjectiveEvaluationService.get_rubric_marks(subjective_test_id)
        codes = [m['code'] for m in marks]
        return codes or list(RUBRIC_VALUES)

    @staticmethod
    def get_class_progress(subjective_test: SubjectiveTest) -> List[Dict[str, Any]]:
        """Progresso de correção por turma (pendente / em_correcao / concluida)."""
        try:
            return SubjectiveEvaluationService._get_class_progress(subjective_test)
        except Exception as e:
            logging.warning("Falha ao calcular progresso de turmas da subjetiva: %s", e)
            return []

    @staticmethod
    def _get_class_progress(subjective_test: SubjectiveTest) -> List[Dict[str, Any]]:
        class_ids = SubjectiveEvaluationService._resolve_target_class_ids(subjective_test)
        if not class_ids:
            return []

        questions_n = SubjectiveQuestion.query.filter_by(subjective_test_id=subjective_test.id).count()
        classes = Class.query.filter(Class.id.in_(class_ids)).order_by(Class.name).all()
        students = Student.query.filter(Student.class_id.in_(class_ids)).all()
        students_by_class: Dict[Any, List] = {}
        student_ids = []
        for student in students:
            students_by_class.setdefault(student.class_id, []).append(student)
            student_ids.append(student.id)

        filled_by_student: Dict[str, int] = {}
        if student_ids:
            for row in SubjectiveResult.query.filter(
                SubjectiveResult.subjective_test_id == subjective_test.id,
                SubjectiveResult.student_id.in_(student_ids),
            ).all():
                sid = str(row.student_id)
                filled_by_student[sid] = filled_by_student.get(sid, 0) + 1

        finalized_students = set()
        if subjective_test.shadow_test_id and student_ids:
            for er in EvaluationResult.query.filter(
                EvaluationResult.test_id == subjective_test.shadow_test_id,
                EvaluationResult.student_id.in_(student_ids),
            ).all():
                finalized_students.add(str(er.student_id))

        progress = []
        for cls in classes:
            class_students = students_by_class.get(cls.id, [])
            n_students = len(class_students)
            expected = n_students * questions_n
            filled = sum(filled_by_student.get(str(s.id), 0) for s in class_students)
            n_finalized = sum(1 for s in class_students if str(s.id) in finalized_students)
            if n_finalized > 0:
                status = 'concluida'
            elif filled > 0:
                status = 'em_correcao'
            else:
                status = 'pendente'
            school_obj = School.query.get(str(cls.school_id)) if getattr(cls, 'school_id', None) else None
            progress.append({
                'id': cls.id,
                'name': cls.name,
                'school': {'id': school_obj.id, 'name': school_obj.name} if school_obj else None,
                'students_count': n_students,
                'filled_cells': filled,
                'expected_cells': expected,
                'pct': round((filled / expected) * 100) if expected else 0,
                'finalized_students': n_finalized,
                'status': status,
            })
        return progress

    @staticmethod
    def recompute_status(subjective_test: SubjectiveTest, commit: bool = False) -> str:
        progress = SubjectiveEvaluationService.get_class_progress(subjective_test)
        if not progress:
            new_status = 'pendente'
        elif all(p['status'] == 'concluida' for p in progress):
            new_status = 'concluida'
        elif any(p['status'] != 'pendente' for p in progress):
            new_status = 'em_correcao'
        else:
            new_status = 'pendente'
        if subjective_test.status != new_status:
            subjective_test.status = new_status
            if commit:
                db.session.commit()
        return new_status

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

        marks = SubjectiveEvaluationService.normalize_rubric_marks_payload(
            data.get('rubric_marks') or data.get('marks')
        )
        SubjectiveEvaluationService._replace_rubric_marks(subjective_test.id, marks)

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

        if 'rubric_marks' in data or 'marks' in data:
            marks = SubjectiveEvaluationService.normalize_rubric_marks_payload(
                data.get('rubric_marks') if 'rubric_marks' in data else data.get('marks')
            )
            allowed_codes = {m['code'] for m in marks}
            used_codes = {
                r.value for r in SubjectiveResult.query.filter_by(subjective_test_id=subjective_test.id).all()
            }
            missing = used_codes - allowed_codes
            if missing:
                raise ValueError(
                    'Não é possível remover marcações já lançadas na correção: '
                    + ', '.join(sorted(missing))
                )
            SubjectiveEvaluationService._replace_rubric_marks(subjective_test.id, marks)

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
        """
        Matriz aluno x questão para a tela de correção manual de uma turma.

        Se já existir EvaluationResult no Test espelho (após finalizar), inclui em cada
        aluno o campo `evaluation` com nota/proficiência/classificação gravadas.
        """
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

        evaluation_by_student: Dict[str, Dict[str, Any]] = {}
        if subjective_test.shadow_test_id and student_ids:
            for er in EvaluationResult.query.filter(
                EvaluationResult.test_id == subjective_test.shadow_test_id,
                EvaluationResult.student_id.in_(student_ids),
            ).all():
                evaluation_by_student[str(er.student_id)] = {
                    "score_percentage": er.score_percentage,
                    "grade": er.grade,
                    "proficiency": er.proficiency,
                    "classification": er.classification,
                    "correct_answers": er.correct_answers,
                    "total_questions": er.total_questions,
                    "persisted": True,
                }

        return {
            "subjective_test": {
                "id": subjective_test.id,
                "title": subjective_test.title,
                "test_type": subjective_test.test_type,
            },
            "rubric_marks": SubjectiveEvaluationService.get_rubric_marks(subjective_test_id),
            "classification_legend": SubjectiveEvaluationService.get_classification_legend_for_test(
                subjective_test
            ),
            "questions": [q.to_dict() for q in questions],
            "students": [
                {
                    "id": s.id,
                    "name": s.name,
                    "registration": s.registration,
                    "present": presence_map.get(str(s.id), True),
                    "results": results_map.get(str(s.id), {}),
                    "evaluation": evaluation_by_student.get(str(s.id)),
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
        allowed = SubjectiveEvaluationService._allowed_codes(subjective_test_id)
        if value is not None and value not in allowed:
            raise ValueError(f"Valor de rubrica inválido: {value}. Aceitos: {', '.join(allowed)}")

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

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if subjective_test and subjective_test.status == 'pendente':
            subjective_test.status = 'em_correcao'

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
    def get_classification_legend_for_test(subjective_test: SubjectiveTest) -> Dict[str, Any]:
        """Legenda oficial (faixas de proficiência) para a avaliação subjetiva."""
        course_name, subject_name = SubjectiveEvaluationService._resolve_course_and_subject_names(
            subjective_test
        )
        return EvaluationCalculator.get_classification_legend(course_name, subject_name)

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
    def _compute_student_score(
        subjective_test: SubjectiveTest,
        student_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Calcula nota/proficiência/classificação a partir da rubrica já lançada.
        Não grava nada — usado pelo preview e pelo calculate_and_save.
        Retorna None se a avaliação não tiver questões.
        """
        questions = subjective_test.questions
        total_questions = len(questions)
        if total_questions == 0:
            return None

        question_ids = [q.id for q in questions]
        results = SubjectiveResult.query.filter(
            SubjectiveResult.subjective_test_id == subjective_test.id,
            SubjectiveResult.student_id == student_id,
            SubjectiveResult.subjective_question_id.in_(question_ids),
        ).all()
        value_by_question = {str(r.subjective_question_id): r.value for r in results}

        weights = SubjectiveEvaluationService._weights_for_test(subjective_test.id)
        max_weight = max(weights.values()) if weights else 1.0
        if max_weight <= 0:
            max_weight = 1.0

        weighted_sum = 0.0
        correct_equivalent_count = 0
        for qid in question_ids:
            v = value_by_question.get(str(qid))
            w = float(weights.get(v, 0.0)) if v else 0.0
            weighted_sum += w
            if v and w >= max_weight:
                correct_equivalent_count += 1

        course_name, subject_name = SubjectiveEvaluationService._resolve_course_and_subject_names(subjective_test)
        calc_result = EvaluationCalculator.calculate_complete_evaluation(
            correct_answers=weighted_sum,
            total_questions=total_questions,
            course_name=course_name,
            subject_name=subject_name,
            use_simple_calculation=False,
        )
        score_percentage = (
            round_to_two_decimals((weighted_sum / total_questions) * 100) if total_questions > 0 else 0.0
        )

        return {
            "skipped": False,
            "student_id": student_id,
            "subjective_test_id": subjective_test.id,
            "correct_answers": correct_equivalent_count,
            "total_questions": total_questions,
            "score_percentage": score_percentage,
            "grade": calc_result['grade'],
            "proficiency": calc_result['proficiency'],
            "classification": calc_result['classification'],
        }

    @staticmethod
    def preview_student_result(subjective_test_id: str, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Preview do resultado de um aluno: mesma fórmula do finalize, mas NÃO grava
        EvaluationResult nem marca relatórios dirty. Para atualizar a coluna da matriz
        a cada lançamento de rubrica.
        """
        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return None

        legend = SubjectiveEvaluationService.get_classification_legend_for_test(subjective_test)

        presence = SubjectivePresence.query.filter_by(
            subjective_test_id=subjective_test_id, student_id=student_id
        ).first()
        if presence and not presence.present:
            return {
                "skipped": True,
                "reason": "ausente",
                "student_id": student_id,
                "subjective_test_id": subjective_test_id,
                "persisted": False,
                "classification_legend": legend,
            }

        computed = SubjectiveEvaluationService._compute_student_score(subjective_test, student_id)
        if computed is None:
            return {
                "skipped": True,
                "reason": "sem_questoes",
                "student_id": student_id,
                "subjective_test_id": subjective_test_id,
                "persisted": False,
                "classification_legend": legend,
            }

        computed["persisted"] = False
        computed["classification_legend"] = legend
        return computed

    @staticmethod
    def calculate_and_save_result_for_student(
        subjective_test_id: str,
        student_id: str,
        corrected_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Calcula nota/proficiência/classificação de um aluno a partir da rubrica lançada
        e grava em EvaluationResult (via Test espelho + TestSession sintética).

        Pontuação do aluno = média aritmética dos itens (peso da marcação, 0–1)
        sobre o TOTAL de questões da avaliação — itens ainda não lançados
        contam como peso 0 (mesmo critério usado na tela de correção). Este cálculo
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

            computed = SubjectiveEvaluationService._compute_student_score(subjective_test, student_id)
            if computed is None:
                logging.warning("SubjectiveEvaluationService: avaliação %s sem questões", subjective_test_id)
                return None

            total_questions = computed["total_questions"]
            correct_equivalent_count = computed["correct_answers"]
            score_percentage = computed["score_percentage"]

            session = SubjectiveEvaluationService._get_or_create_synthetic_session(shadow_test_id, student_id)
            session.total_questions = total_questions
            session.correct_answers = correct_equivalent_count
            session.score = score_percentage
            session.grade = computed['grade']
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
                existing_result.grade = computed['grade']
                existing_result.proficiency = computed['proficiency']
                existing_result.classification = computed['classification']
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
                    grade=computed['grade'],
                    proficiency=computed['proficiency'],
                    classification=computed['classification'],
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
                "grade": computed['grade'],
                "proficiency": computed['proficiency'],
                "classification": computed['classification'],
                "persisted": True,
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
        if subjective_test:
            SubjectiveEvaluationService.recompute_status(subjective_test, commit=True)

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

        Além das agregações de questões (`saeb_levels` / `per_question`), retorna:
        - `student_saeb_levels` / `students_by_saeb_level`: alunos por faixa SAEB
          (para hover do gráfico e listagens);
        - `students`: tabelinha individual com rubrica e nível.
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

        marks = SubjectiveEvaluationService.get_rubric_marks(subjective_test_id)
        mark_codes = [m['code'] for m in marks] or list(RUBRIC_VALUES)
        weights = {m['code']: float(m['weight']) for m in marks} or dict(RUBRIC_WEIGHTS)
        mark_meta = {m['code']: m for m in marks}

        totals = {code: 0 for code in mark_codes}
        results_by_question: Dict[str, List[SubjectiveResult]] = {}
        results_by_student: Dict[str, Dict[str, str]] = {}
        respondent_ids = set()
        for r in results:
            if r.value not in totals:
                totals[r.value] = 0
            totals[r.value] += 1
            results_by_question.setdefault(str(r.subjective_question_id), []).append(r)
            results_by_student.setdefault(str(r.student_id), {})[str(r.subjective_question_id)] = r.value
            respondent_ids.add(str(r.student_id))

        total_responses = len(results)
        respondents = len(respondent_ids)
        presence_map = {str(p.student_id): bool(p.present) for p in presences}
        marked_absent = sum(1 for p in presences if not p.present)
        absent = max(marked_absent, max(0, total_students - respondents))

        weighted_sum = sum(totals.get(code, 0) * weights.get(code, 0.0) for code in totals)
        hit_rate_pct = round((weighted_sum / total_responses) * 100) if total_responses > 0 else 0
        saeb_global = saeb_from_pct(hit_rate_pct)
        participation_pct = round((respondents / total_students) * 100) if total_students > 0 else 0

        distribution = []
        for code in mark_codes:
            value = totals.get(code, 0)
            pct = round((value / total_responses) * 100) if total_responses > 0 else 0
            meta = mark_meta.get(code) or {}
            distribution.append({
                "code": code,
                "name": meta.get("label") or code,
                "label": meta.get("label") or code,
                "color": meta.get("color") or "#94a3b8",
                "weight": meta.get("weight", weights.get(code, 0)),
                "value": value,
                "pct": pct,
            })

        # Contagem de QUESTÕES por faixa (mantida para compatibilidade / habilidades).
        saeb_levels = {'abaixo': 0, 'basico': 0, 'adequado': 0, 'avancado': 0}
        per_question = []
        for q in questions:
            rows = results_by_question.get(str(q.id), [])
            counts = {code: 0 for code in mark_codes}
            for r in rows:
                if r.value not in counts:
                    counts[r.value] = 0
                counts[r.value] += 1
            q_total = len(rows)
            q_weighted = sum(counts.get(code, 0) * weights.get(code, 0.0) for code in counts)
            q_hit = round((q_weighted / q_total) * 100) if q_total > 0 else 0
            q_saeb = saeb_from_pct(q_hit) if q_total > 0 else {'level': None, 'label': None}
            if q_total > 0 and q_saeb['level']:
                saeb_levels[q_saeb['level']] += 1

            item = {
                "id": q.id,
                "number": q.number,
                "code": q.code,
                "skill_description": q.skill_description,
                "counts": counts,
                "total": q_total,
                "hit_rate_pct": q_hit,
                "saeb_level": q_saeb['level'],
                "saeb_label": q_saeb['label'],
            }
            # Compatibilidade com o dashboard anterior (chaves SIM/PARCIAL/...).
            for legacy in RUBRIC_VALUES:
                item[legacy] = counts.get(legacy, 0)
            per_question.append(item)

        # Alunos por nível SAEB simplificado (mesma fórmula do % individual da rubrica).
        # Usado no hover/seleção do gráfico e na tabelinha do relatório.
        n_questions = len(questions)
        students_by_saeb_level: Dict[str, List[Dict[str, Any]]] = {
            'abaixo': [], 'basico': [], 'adequado': [], 'avancado': [],
        }
        student_saeb_levels = {'abaixo': 0, 'basico': 0, 'adequado': 0, 'avancado': 0}
        students_payload: List[Dict[str, Any]] = []

        students_sorted = sorted(students, key=lambda s: (s.name or '').lower())
        for s in students_sorted:
            sid = str(s.id)
            is_present = presence_map.get(sid, True)
            value_by_q = results_by_student.get(sid, {})
            has_results = len(value_by_q) > 0

            score_pct = None
            saeb_info = None
            if is_present and has_results and n_questions > 0:
                weighted_student = 0.0
                for q in questions:
                    weighted_student += weights.get(value_by_q.get(str(q.id)), 0.0)
                score_pct = round((weighted_student / n_questions) * 100)
                saeb_info = saeb_from_pct(score_pct)
                entry = {
                    "id": s.id,
                    "name": s.name,
                    "registration": s.registration,
                    "score_percentage": score_pct,
                    "saeb_level": saeb_info['level'],
                    "saeb_label": saeb_info['label'],
                }
                students_by_saeb_level[saeb_info['level']].append(entry)
                student_saeb_levels[saeb_info['level']] += 1

            students_payload.append({
                "id": s.id,
                "name": s.name,
                "registration": s.registration,
                "present": is_present,
                "score_percentage": score_pct,
                "saeb_level": saeb_info['level'] if saeb_info else None,
                "saeb_label": saeb_info['label'] if saeb_info else None,
                "results": value_by_q,
            })

        return {
            "subjective_test": {
                "id": subjective_test.id,
                "title": subjective_test.title,
                "test_type": subjective_test.test_type,
            },
            "rubric_marks": marks,
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
            "student_saeb_levels": student_saeb_levels,
            "students_by_saeb_level": students_by_saeb_level,
            "students": students_payload,
            "per_question": per_question,
        }

    # ------------------------------------------------------------------
    # Opções de filtros (Estado → Município → Escola → Série → Avaliação → Turma)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_filter_all(value) -> bool:
        if value is None:
            return True
        s = str(value).strip().lower()
        return s == '' or s in ('all', 'todas', 'todos')

    @staticmethod
    def _user_city_id(user: dict) -> Optional[str]:
        return user.get('city_id') or user.get('tenant_id')

    @staticmethod
    def _corrected_subjective_tests() -> List[SubjectiveTest]:
        """Avaliações subjetivas que já têm pelo menos um lançamento de correção."""
        corrected_ids = [
            row[0]
            for row in db.session.query(SubjectiveResult.subjective_test_id).distinct().all()
        ]
        if not corrected_ids:
            return []
        return SubjectiveTest.query.filter(SubjectiveTest.id.in_(corrected_ids)).all()

    @staticmethod
    def _class_ids_with_correction(subjective_test_id: str) -> set:
        """Turmas que têm pelo menos um aluno com rubrica lançada nesta avaliação."""
        student_ids = [
            row[0]
            for row in db.session.query(SubjectiveResult.student_id).filter(
                SubjectiveResult.subjective_test_id == subjective_test_id
            ).distinct().all()
        ]
        if not student_ids:
            return set()
        return {
            s.class_id
            for s in Student.query.filter(Student.id.in_(student_ids)).all()
            if s.class_id is not None
        }

    @staticmethod
    def _test_intersects_school(subjective_test: SubjectiveTest, school_id: str, class_ids: List) -> bool:
        school_id_str = str(school_id)
        if subjective_test.schools:
            schools = (
                subjective_test.schools
                if isinstance(subjective_test.schools, list)
                else [subjective_test.schools]
            )
            if any(str(s) == school_id_str for s in schools):
                return True
        if not class_ids:
            return False
        return Class.query.filter(
            Class.id.in_(class_ids),
            Class.school_id == school_id_str,
        ).first() is not None

    @staticmethod
    def get_filter_options(
        user: dict,
        estado: Optional[str] = None,
        municipio: Optional[str] = None,
        escola: Optional[str] = None,
        serie: Optional[str] = None,
        avaliacao: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Opções hierárquicas para filtros da avaliação subjetiva.

        Ordem: Estado → Município → Escola → Série → Avaliação → Turma
        (diferente de evaluation-results, onde avaliação vem antes da escola).

        Só lista avaliações que já têm correção lançada (SubjectiveResult).
        Diretor/coordenador: pré-seleciona a escola vinculada.
        """
        from app.models.city import City
        from app.models.grades import Grade
        from app.permissions import get_user_permission_scope
        from app.permissions.utils import get_manager_school, get_teacher_schools, get_teacher_classes
        from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path
        from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list

        permissao = get_user_permission_scope(user)
        if not permissao.get('permitted'):
            return {"error": permissao.get('error') or "Sem permissão", "status": 403}

        role = str(user.get('role') or '').lower()
        user_city_id = SubjectiveEvaluationService._user_city_id(user)

        response: Dict[str, Any] = {}

        # --- Estados ---
        if permissao.get('scope') == 'all':
            estados = db.session.query(City.state).distinct().filter(City.state.isnot(None)).all()
        else:
            estados = db.session.query(City.state).distinct().filter(
                City.state.isnot(None),
                City.id == user_city_id,
            ).all()
        response["estados"] = [{"id": e[0], "nome": e[0]} for e in estados if e[0]]

        if SubjectiveEvaluationService._is_filter_all(estado):
            return response

        # --- Municípios ---
        if permissao.get('scope') == 'all':
            municipios = City.query.filter(City.state.ilike(f"%{estado}%")).all()
        else:
            municipios = City.query.filter(
                City.state.ilike(f"%{estado}%"),
                City.id == user_city_id,
            ).all()
        response["municipios"] = [{"id": str(m.id), "nome": m.name} for m in municipios]

        if SubjectiveEvaluationService._is_filter_all(municipio):
            return response

        municipio_str = str(municipio).strip()
        city = City.query.get(municipio_str)
        if not city:
            return {**response, "error": "Município não encontrado", "status": 404}
        if permissao.get('scope') != 'all' and str(user_city_id) != municipio_str:
            return {**response, "error": "Sem permissão para este município", "status": 403}

        # Schema do município (necessário para SubjectiveTest/School/Class no tenant).
        set_search_path(city_id_to_schema_name(municipio_str))

        # Pré-seleção de escola para diretor/coordenador.
        escola_pre_selecionada = None
        if role in ('diretor', 'coordenador'):
            escola_pre_selecionada = get_manager_school(user['id'])
            response["escola_pre_selecionada"] = escola_pre_selecionada

        escola_efetiva = None if SubjectiveEvaluationService._is_filter_all(escola) else str(escola).strip()
        if escola_efetiva is None and escola_pre_selecionada:
            escola_efetiva = str(escola_pre_selecionada)

        serie_efetiva = None if SubjectiveEvaluationService._is_filter_all(serie) else ensure_uuid(serie)
        avaliacao_efetiva = None if SubjectiveEvaluationService._is_filter_all(avaliacao) else str(avaliacao).strip()

        # Restrições por role.
        allowed_school_ids = None
        allowed_class_ids = None
        if role in ('diretor', 'coordenador'):
            manager_school = get_manager_school(user['id'])
            allowed_school_ids = {str(manager_school)} if manager_school else set()
        elif role == 'professor':
            allowed_school_ids = set(get_teacher_schools(user['id']) or [])
            allowed_class_ids = set(ensure_uuid_list(get_teacher_classes(user['id']) or []))

        corrected_tests = SubjectiveEvaluationService._corrected_subjective_tests()

        # Para cada avaliação corrigida: turmas do escopo ∩ turmas com lançamento ∩ permissão.
        test_contexts = []
        for test in corrected_tests:
            scope_class_ids = SubjectiveEvaluationService._resolve_target_class_ids(test)
            corrected_class_ids = SubjectiveEvaluationService._class_ids_with_correction(test.id)
            class_ids = [cid for cid in scope_class_ids if cid in corrected_class_ids]
            if allowed_class_ids is not None:
                class_ids = [cid for cid in class_ids if cid in allowed_class_ids]
            if not class_ids and not test.schools and not test.municipalities:
                continue
            if allowed_school_ids is not None:
                # Mantém só se intersecta escola permitida.
                intersects = False
                for sid in allowed_school_ids:
                    if SubjectiveEvaluationService._test_intersects_school(test, sid, class_ids):
                        intersects = True
                        break
                if not intersects:
                    continue
            test_contexts.append({"test": test, "class_ids": class_ids})

        # Escolas do município presentes no escopo das avaliações corrigidas.
        school_ids_set = set()
        for ctx in test_contexts:
            test = ctx["test"]
            class_ids = ctx["class_ids"]
            if class_ids:
                for c in Class.query.filter(Class.id.in_(class_ids)).all():
                    if c.school_id:
                        school_ids_set.add(str(c.school_id))
            if test.schools:
                schools = test.schools if isinstance(test.schools, list) else [test.schools]
                for s in schools:
                    school_ids_set.add(str(s))

        if allowed_school_ids is not None:
            school_ids_set &= allowed_school_ids

        schools_q = School.query.filter(
            School.city_id == municipio_str,
            School.id.in_(list(school_ids_set) or ['__none__']),
        ).order_by(School.name)
        response["escolas"] = [{"id": s.id, "nome": s.name} for s in schools_q.all()]

        # A partir daqui, estreita pelo nível selecionado (escola → série → avaliação → turma).
        filtered_contexts = test_contexts
        if escola_efetiva:
            filtered_contexts = [
                ctx for ctx in filtered_contexts
                if SubjectiveEvaluationService._test_intersects_school(
                    ctx["test"], escola_efetiva, ctx["class_ids"]
                )
            ]
            # Restringe class_ids à escola.
            narrowed = []
            for ctx in filtered_contexts:
                class_ids = ctx["class_ids"]
                if class_ids:
                    class_ids = [
                        c.id for c in Class.query.filter(
                            Class.id.in_(class_ids),
                            Class.school_id == str(escola_efetiva),
                        ).all()
                    ]
                narrowed.append({"test": ctx["test"], "class_ids": class_ids})
            filtered_contexts = narrowed

        # Séries
        grade_ids = {ctx["test"].grade_id for ctx in filtered_contexts if ctx["test"].grade_id}
        grades = (
            Grade.query.filter(Grade.id.in_(list(grade_ids))).order_by(Grade.name).all()
            if grade_ids else []
        )
        response["series"] = [{"id": str(g.id), "nome": g.name} for g in grades]

        if serie_efetiva:
            filtered_contexts = [
                ctx for ctx in filtered_contexts
                if ctx["test"].grade_id == serie_efetiva
            ]
            narrowed = []
            for ctx in filtered_contexts:
                class_ids = ctx["class_ids"]
                if class_ids:
                    class_ids = [
                        c.id for c in Class.query.filter(
                            Class.id.in_(class_ids),
                            Class.grade_id == serie_efetiva,
                        ).all()
                    ]
                narrowed.append({"test": ctx["test"], "class_ids": class_ids})
            filtered_contexts = narrowed

        # Avaliações (já corrigidas e no recorte)
        avaliacoes = []
        for ctx in filtered_contexts:
            test = ctx["test"]
            avaliacoes.append({
                "id": test.id,
                "titulo": test.title,
                "test_type": test.test_type,
                "grade_id": str(test.grade_id) if test.grade_id else None,
                "subject_id": test.subject_id,
            })
        # Dedup + sort
        seen = set()
        avaliacoes_unique = []
        for a in sorted(avaliacoes, key=lambda x: (x["titulo"] or "").lower()):
            if a["id"] not in seen:
                seen.add(a["id"])
                avaliacoes_unique.append(a)
        response["avaliacoes"] = avaliacoes_unique

        if avaliacao_efetiva:
            filtered_contexts = [
                ctx for ctx in filtered_contexts if ctx["test"].id == avaliacao_efetiva
            ]

        # Turmas
        turma_ids = set()
        for ctx in filtered_contexts:
            for cid in ctx["class_ids"]:
                turma_ids.add(cid)
        turmas = (
            Class.query.filter(Class.id.in_(list(turma_ids))).order_by(Class.name).all()
            if turma_ids else []
        )
        response["turmas"] = [{"id": str(t.id), "nome": t.name} for t in turmas]

        return response

