from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import case, distinct, func
from sqlalchemy.orm import aliased

from app import db
from app.models.city import City
from app.models.classTest import ClassTest
from app.models.game import Game
from app.models.manager import Manager
from app.models.question import Question
from app.models.school import School
from app.models.skill import Skill
from app.models.schoolTeacher import SchoolTeacher
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.teacher import Teacher
from app.models.teacherClass import TeacherClass
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.testSession import TestSession
from app.models.user import User
from app.models.evaluationResult import EvaluationResult
from app.utils.uuid_helpers import ensure_uuid_list, uuid_list_to_str
from app.permissions.utils import (
    get_manager_school,
    get_teacher,
    get_teacher_classes,
    get_user_scope,
)
from app.certification.services.certificate_service import CertificateService


class DashboardService:
    """
    Serviço responsável por montar os payloads dos dashboards do frontend.
    """

    MAX_LIST_SIZE = 10

    # ------------------------------------------------------------------ #
    # Entry points públicos
    # ------------------------------------------------------------------ #

    @classmethod
    def get_admin_dashboard(cls, user: Dict[str, Any]) -> Dict[str, Any]:
        scope = cls._resolve_scope(user)
        summary = cls._build_summary(scope)
        kpis = cls._build_main_kpis(scope)
        secondary_cards = cls._build_secondary_cards(scope)
        rankings = cls._build_rankings(scope)
        recent_evaluations = cls._build_recent_evaluations(scope)
        recent_students = cls._build_recent_students(scope)
        engagement = cls._build_engagement(scope)
        filters_available = cls._build_filters(scope)

        return {
            "summary": summary,
            "kpis": kpis,
            "secondary_cards": secondary_cards,
            "rankings": rankings,
            "recent_evaluations": recent_evaluations,
            "recent_students": recent_students,
            "engagement": engagement,
            "filters_available": filters_available,
            "meta": cls._build_meta(len(recent_evaluations), len(recent_students)),
            "error_recovery": cls._build_error_recovery(),
        }

    @classmethod
    def get_tecadm_dashboard(cls, user: Dict[str, Any]) -> Dict[str, Any]:
        scope = cls._resolve_scope(user)
        # Força escopo municipal
        scope["scope"] = "municipio"
        return cls.get_admin_dashboard(user)

    @classmethod
    def get_school_dashboard(cls, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dashboard compartilhado por Diretor e Coordenador.
        """
        scope = cls._resolve_scope(user)

        return {
            "summary": cls._build_school_summary(scope),
            "kpis": cls._build_school_kpis(scope),
            "class_ranking": cls._build_class_ranking(scope),
            "teacher_ranking": cls._build_teacher_ranking(scope),
            "recent_evaluations": cls._build_recent_evaluations(scope, limit=5),
            "students_overview": cls._build_students_overview(scope),
            "notifications": cls._build_notifications_placeholder(),
            "filters_available": cls._build_filters(scope),
            "meta": cls._build_meta(),
            "error_recovery": cls._build_error_recovery(),
        }

    @classmethod
    def get_professor_dashboard(cls, user: Dict[str, Any]) -> Dict[str, Any]:
        scope = cls._resolve_scope(user)
        teacher = get_teacher(user["id"])

        return {
            "summary": cls._build_professor_summary(scope, teacher),
            "kpis": cls._build_professor_kpis(scope, teacher),
            "classes": cls._build_professor_classes(scope, teacher),
            "evaluations": cls._build_professor_evaluations(scope, teacher),
            "notifications": cls._build_notifications_placeholder(),
            "filters_available": cls._build_filters(scope),
            "meta": cls._build_meta(),
            "error_recovery": cls._build_error_recovery(),
        }

    # ------------------------------------------------------------------ #
    # Helpers de escopo
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_scope(user: Dict[str, Any]) -> Dict[str, Any]:
        scope = get_user_scope(user)
        scope["user"] = user
        scope["school_ids"] = DashboardService._extract_school_ids(scope)
        scope["class_ids"] = DashboardService._extract_class_ids(scope)
        return scope

    @staticmethod
    def _extract_school_ids(scope: Dict[str, Any]) -> Optional[List[str]]:
        if scope["scope"] == "all":
            return None
        if scope["scope"] == "municipio":
            city_id = scope.get("city_id")
            if not city_id:
                return []
            schools = School.query.filter(School.city_id == city_id).with_entities(School.id).all()
            # Garantir que todos os IDs sejam strings (School.id é VARCHAR)
            result = [str(row.id) for row in schools]
            return result
        if scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if not school_ids and scope.get("school_id"):
                school_ids = [scope["school_id"]]
            # Garantir que todos os IDs sejam strings (School.id é VARCHAR)
            result = [str(sid) if sid else sid for sid in school_ids]
            return result
        return []

    @staticmethod
    def _extract_class_ids(scope: Dict[str, Any]) -> Optional[List[str]]:
        # Se tem escopo global ou municipal, não limitamos as turmas
        if scope["scope"] in {"all", "municipio"}:
            return None

        school_ids = scope.get("school_ids") or []
        if not school_ids:
            return []

        # ✅ CORRIGIDO: Converter school_ids para strings (Class.school_id é VARCHAR, igual School.id)
        school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
        classes = Class.query.filter(Class.school_id.in_(school_ids_str)).with_entities(Class.id).all() if school_ids_str else []
        return [row.id for row in classes]

    # ------------------------------------------------------------------ #
    # Blocos comuns (Admin / TecAdm)
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_summary(cls, scope: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "students": cls._count_students(scope),
            "schools": cls._count_schools(scope),
            "evaluations": cls._count_evaluations(scope),
            "games": cls._count_games(scope),
            "users": cls._count_users(scope),
            "questions": cls._count_questions(scope),
            "classes": cls._count_classes(scope),
            "teachers": cls._count_teachers(scope),
            "last_sync": datetime.utcnow().isoformat(),
        }

    @classmethod
    def _build_main_kpis(cls, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        students_current, students_prev = cls._period_counts(
            Student, Student.created_at, scope, cls._student_scope_filter
        )
        evaluations_current, evaluations_prev = cls._period_counts(
            Test, Test.created_at, scope, cls._evaluation_scope_filter
        )
        sessions_current, sessions_prev = cls._period_counts(
            TestSession, TestSession.started_at, scope, cls._session_scope_filter
        )

        return [
            {
                "id": "students",
                "label": "Alunos",
                "value": cls._count_students(scope),
                "trend": {
                    "current": students_current,
                    "previous": students_prev,
                },
            },
            {
                "id": "evaluations",
                "label": "Avaliações",
                "value": cls._count_evaluations(scope),
                "trend": {
                    "current": evaluations_current,
                    "previous": evaluations_prev,
                },
            },
            {
                "id": "engagement",
                "label": "Sessões iniciadas",
                "value": sessions_current,
                "trend": {
                    "current": sessions_current,
                    "previous": sessions_prev,
                },
            },
        ]

    @classmethod
    def _build_secondary_cards(cls, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"id": "users", "label": "Usuários", "value": cls._count_users(scope)},
            {"id": "questions", "label": "Questões no banco", "value": cls._count_questions(scope)},
            {
                "id": "notices",
                "label": "Avisos",
                "value": cls._count_notices(scope),
            },
            {
                "id": "certificates",
                "label": "Certificados",
                "value": cls._count_certificates(scope),
            },
        ]

    @classmethod
    def _build_rankings(cls, scope: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "classes": cls._build_class_rankings(scope),
            "students": cls._build_student_rankings(scope),
            "teacher_rankings": [],  # Ainda não suportado
        }

    @classmethod
    def _build_recent_evaluations(cls, scope: Dict[str, Any], limit: int = MAX_LIST_SIZE) -> List[Dict[str, Any]]:
        # Usar subquery para evitar duplicatas quando há joins
        # Incluir created_at na seleção para permitir ORDER BY com DISTINCT
        test_query = Test.query.with_entities(Test.id, Test.created_at).order_by(Test.created_at.desc())

        if scope["scope"] == "municipio" and scope.get("city_id"):
            city_school_ids = cls._extract_school_ids(scope) or []
            if city_school_ids:
                # ✅ CORRIGIDO: Class.school_id é VARCHAR, converter para strings
                city_school_ids_str = uuid_list_to_str(city_school_ids) if city_school_ids else []
                test_query = (
                    test_query.join(ClassTest, ClassTest.test_id == Test.id)
                    .join(Class, Class.id == ClassTest.class_id)
                    .filter(Class.school_id.in_(city_school_ids_str))
                    .distinct()
                ) if city_school_ids_str else test_query.filter(False)
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if school_ids:
                # ✅ CORRIGIDO: Class.school_id é VARCHAR, converter para strings
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                test_query = (
                    test_query.join(ClassTest, ClassTest.test_id == Test.id)
                    .join(Class, Class.id == ClassTest.class_id)
                    .filter(Class.school_id.in_(school_ids_str))
                    .distinct()
                ) if school_ids_str else test_query.filter(False)

        # Obter IDs únicos (ordenados por created_at)
        test_ids = [row.id for row in test_query.limit(limit).all()]
        
        # Buscar objetos Test completos mantendo a ordem
        # Criar um dicionário para preservar a ordem original
        if test_ids:
            tests_dict = {test.id: test for test in Test.query.filter(Test.id.in_(test_ids)).all()}
            tests = [tests_dict[tid] for tid in test_ids if tid in tests_dict]
        else:
            tests = []
        results = []

        for test in tests:
            class_tests = (
                ClassTest.query.filter(ClassTest.test_id == test.id)
                .join(Class, Class.id == ClassTest.class_id)
                .all()
            )
            class_ids = [ct.class_id for ct in class_tests]
            student_count = (
                Student.query.filter(Student.class_id.in_(class_ids)).count() if class_ids else 0
            )

            sessions = (
                TestSession.query.filter(TestSession.test_id == test.id)
                .with_entities(
                    func.count(TestSession.id).label("total"),
                    func.sum(case((TestSession.submitted_at.isnot(None), 1), else_=0)).label("completed"),
                )
                .first()
            )

            if sessions and sessions.total:
                progress_percentage = round((sessions.completed or 0) / sessions.total * 100, 2)
            else:
                progress_percentage = 0.0

            avg_score = (
                db.session.query(func.avg(EvaluationResult.grade))
                .filter(EvaluationResult.test_id == test.id)
                .scalar()
            )

            class_name = class_tests[0].class_.name if class_tests else None
            if class_tests and class_tests[0].class_:
                class_obj = class_tests[0].class_
                school_obj = class_obj.school
                school_name = school_obj.name if school_obj else None
            else:
                school_name = None

            if class_tests and class_tests[0].application:
                application = class_tests[0].application
                # application é db.Text (string), não datetime
                start_date = str(application) if application else None
            else:
                start_date = None

            if class_tests and class_tests[0].expiration:
                expiration = class_tests[0].expiration
                # expiration é db.Text (string), não datetime
                end_date = str(expiration) if expiration else None
            else:
                end_date = None

            results.append(
                {
                    "evaluation_id": test.id,
                    "title": test.title,
                    "subject": test.subject_rel.name if test.subject_rel else None,
                    "school": school_name,
                    "status": test.status,
                    "progress_percentage": progress_percentage,
                    "total_students": student_count,
                    "completed_students": int(sessions.completed or 0) if sessions else 0,
                    "average_score": float(avg_score or 0),
                    "start_date": start_date,
                    "end_date": end_date,
                    "class_name": class_name,
                }
            )

        return results

    TYPE_AVALIACAO = "AVALIACAO"

    @classmethod
    def get_recent_evaluations_avaliacao(
        cls, scope: Dict[str, Any], limit: int = MAX_LIST_SIZE
    ) -> List[Dict[str, Any]]:
        """
        Retorna avaliações recentes (Tests) com type == AVALIACAO, para card/listagem.
        Campos: quantidade de alunos que fizeram, que vão fazer, prazo, progresso,
        status, disciplina, escola(s).
        """
        test_query = (
            Test.query.filter(Test.type == cls.TYPE_AVALIACAO)
            .with_entities(Test.id, Test.created_at)
            .order_by(Test.created_at.desc())
        )

        if scope["scope"] == "municipio" and scope.get("city_id"):
            city_school_ids = cls._extract_school_ids(scope) or []
            if city_school_ids:
                city_school_ids_str = uuid_list_to_str(city_school_ids) if city_school_ids else []
                test_query = (
                    test_query.join(ClassTest, ClassTest.test_id == Test.id)
                    .join(Class, Class.id == ClassTest.class_id)
                    .filter(Class.school_id.in_(city_school_ids_str))
                    .distinct()
                ) if city_school_ids_str else test_query.filter(False)
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if school_ids:
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                test_query = (
                    test_query.join(ClassTest, ClassTest.test_id == Test.id)
                    .join(Class, Class.id == ClassTest.class_id)
                    .filter(Class.school_id.in_(school_ids_str))
                    .distinct()
                ) if school_ids_str else test_query.filter(False)
        elif scope["scope"] == "all":
            # Admin sem cidade: filtrar apenas por tipo, qualquer escola
            test_query = (
                test_query.join(ClassTest, ClassTest.test_id == Test.id)
                .join(Class, Class.id == ClassTest.class_id)
                .distinct()
            )

        test_ids = [row.id for row in test_query.limit(limit).all()]

        if not test_ids:
            return []

        tests_dict = {test.id: test for test in Test.query.filter(Test.id.in_(test_ids)).all()}
        tests = [tests_dict[tid] for tid in test_ids if tid in tests_dict]

        results = []
        for test in tests:
            class_tests = (
                ClassTest.query.filter(ClassTest.test_id == test.id)
                .join(Class, Class.id == ClassTest.class_id)
                .all()
            )
            class_ids = [ct.class_id for ct in class_tests]
            alunos_que_vao_fazer = (
                Student.query.filter(Student.class_id.in_(class_ids)).count() if class_ids else 0
            )

            sessions_row = (
                TestSession.query.filter(TestSession.test_id == test.id)
                .with_entities(
                    func.count(TestSession.id).label("total"),
                    func.sum(case((TestSession.submitted_at.isnot(None), 1), else_=0)).label("completed"),
                )
                .first()
            )
            alunos_que_fizeram = int(sessions_row.completed or 0) if sessions_row else 0

            if alunos_que_vao_fazer and alunos_que_vao_fazer > 0:
                progresso = round((alunos_que_fizeram / alunos_que_vao_fazer) * 100, 2)
            else:
                progresso = 0.0

            # Prazo: Test.end_time (datetime) ou primeiro ClassTest.expiration (text)
            if test.end_time:
                prazo = test.end_time.isoformat() if hasattr(test.end_time, "isoformat") else str(test.end_time)
            elif class_tests and class_tests[0].expiration:
                prazo = str(class_tests[0].expiration)
            else:
                prazo = None

            # Disciplina
            disciplina = test.subject_rel.name if test.subject_rel else None

            # Escola(s): nomes distintos das escolas das turmas aplicadas
            escolas_nomes = []
            for ct in class_tests:
                if ct.class_ and getattr(ct.class_, "school", None) and ct.class_.school:
                    nome = ct.class_.school.name
                    if nome and nome not in escolas_nomes:
                        escolas_nomes.append(nome)
            escola = ", ".join(escolas_nomes) if escolas_nomes else None

            results.append({
                "avaliacao_id": test.id,
                "titulo": test.title,
                "quantidade_alunos_fizeram": alunos_que_fizeram,
                "quantidade_alunos_vao_fazer": alunos_que_vao_fazer,
                "prazo": prazo,
                "progresso": progresso,
                "status": test.status or "pendente",
                "disciplina": disciplina,
                "escola": escola,
                "escolas": escolas_nomes,
            })

        return results

    @classmethod
    def _build_recent_students(cls, scope: Dict[str, Any], limit: int = MAX_LIST_SIZE) -> List[Dict[str, Any]]:
        student_query = Student.query.order_by(Student.created_at.desc())

        if scope["scope"] == "municipio" and scope.get("city_id"):
            school_ids = cls._extract_school_ids(scope) or []
            if school_ids:
                student_query = student_query.filter(Student.school_id.in_(school_ids))
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if school_ids:
                student_query = student_query.filter(Student.school_id.in_(school_ids))

        students = student_query.limit(limit).all()
        results = []

        school_ids = {student.school_id for student in students if getattr(student, "school_id", None)}
        school_map = {}
        if school_ids:
            # Converter school_ids para strings (School.id é VARCHAR, student.school_id pode ser UUID)
            school_ids_str = uuid_list_to_str(list(school_ids))
            school_records = School.query.filter(School.id.in_(school_ids_str)).with_entities(School.id, School.name).all()
            school_map = {school_id: school_name for school_id, school_name in school_records}

        for student in students:
            results.append(
                {
                    "student_id": student.id,
                    "name": student.name,
                    "email": student.user.email if student.user else None,
                    "registration": student.registration,
                    "school": school_map.get(student.school_id),
                    "class": student.class_.name if student.class_ else None,
                    "created_at": student.created_at.isoformat() if student.created_at else None,
                }
            )
        return results

    @classmethod
    def _build_engagement(cls, scope: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.utcnow()
        start_today = datetime(now.year, now.month, now.day)
        start_week = start_today - timedelta(days=start_today.weekday())
        start_month = datetime(now.year, now.month, 1)

        def session_counts(start: datetime, end: Optional[datetime] = None) -> Tuple[int, int]:
            query = TestSession.query.filter(TestSession.started_at >= start)
            if end:
                query = query.filter(TestSession.started_at < end)
            query = cls._session_scope_filter(query, scope)
            total_users = query.with_entities(func.count(distinct(TestSession.student_id))).scalar() or 0
            total_minutes = query.with_entities(
                func.sum(
                    func.extract("epoch", (func.coalesce(TestSession.submitted_at, now) - TestSession.started_at))
                )
            ).scalar()
            total_minutes = int(total_minutes / 60) if total_minutes else 0
            return total_users, total_minutes

        today_users, today_minutes = session_counts(start_today)
        week_users, week_minutes = session_counts(start_week)
        month_users, month_minutes = session_counts(start_month)

        prev_month_start = (start_month - timedelta(days=1)).replace(day=1)
        prev_month_end = start_month
        prev_month_users, prev_month_minutes = session_counts(prev_month_start, prev_month_end)

        def growth(current: int, previous: int) -> float:
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return round(((current - previous) / previous) * 100, 2)

        popular_evaluations = cls._popular_evaluations(scope)
        return_rate = cls._return_rate(scope)

        return {
            "active_users": {
                "today": today_users,
                "this_week": week_users,
                "this_month": month_users,
                "growth_percentage": growth(month_users, prev_month_users),
            },
            "session_time": {
                "average_minutes": round(month_minutes / month_users, 2) if month_users else 0,
                "total_minutes": month_minutes,
                "growth_percentage": growth(month_minutes, prev_month_minutes),
            },
            "popular_evaluations": popular_evaluations,
            "return_rate": return_rate,
        }

    @classmethod
    def _build_filters(cls, scope: Dict[str, Any]) -> Dict[str, Any]:
        municipalities = []
        schools = []
        classes = []
        subjects = []

        if scope["scope"] == "all":
            municipalities = [
                {"id": city.id, "name": city.name}
                for city in City.query.order_by(City.name.asc()).limit(50).all()
            ]
        elif scope.get("city_id"):
            city = City.query.get(scope["city_id"])
            if city:
                municipalities = [{"id": city.id, "name": city.name}]

        school_ids = cls._extract_school_ids(scope)
        if school_ids is None:
            school_query = School.query
        else:
            # Converter school_ids para strings (School.id é VARCHAR)
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            school_query = School.query.filter(School.id.in_(school_ids_str)) if school_ids_str else School.query.filter(False)

        schools = [{"id": school.id, "name": school.name} for school in school_query.order_by(School.name.asc()).all()]

        class_query = Class.query
        if school_ids:
            # ✅ CORRIGIDO: Converter school_ids para strings (Class.school_id é VARCHAR)
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            class_query = class_query.filter(Class.school_id.in_(school_ids_str)) if school_ids_str else class_query.filter(False)

        classes = [{"id": class_.id, "name": class_.name} for class_ in class_query.order_by(Class.name.asc()).all()]

        subject_ids = [
            subject_id
            for (subject_id,) in Question.query.with_entities(Question.subject_id)
            .distinct()
            .limit(50)
            .all()
            if subject_id
        ]

        if subject_ids:
            from app.models.subject import Subject

            subject_map = {
                record.id: record.name
                for record in Subject.query.filter(Subject.id.in_(subject_ids)).with_entities(Subject.id, Subject.name).all()
            }
            subjects = [{"id": sid, "name": subject_map.get(sid)} for sid in subject_ids if sid in subject_map]
        else:
            subjects = []

        return {
            "municipalities": municipalities,
            "schools": schools,
            "classes": classes,
            "subjects": subjects,
        }

    @staticmethod
    def _build_meta(recent_evaluations_count: int = 0, recent_students_count: int = 0) -> Dict[str, Any]:
        return {
            "recent_evaluations": {
                "total": recent_evaluations_count,
                "page": 1,
                "per_page": max(recent_evaluations_count, 1),
            },
            "recent_students": {
                "total": recent_students_count,
                "page": 1,
                "per_page": max(recent_students_count, 1),
            },
        }

    @staticmethod
    def _build_error_recovery() -> Dict[str, Any]:
        return {
            "notices": "Seção em implementação. Entre em contato com o suporte para mais detalhes.",
            "certificates": "Seção em implementação. Disponível em breve.",
        }

    # ------------------------------------------------------------------ #
    # Contadores
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_school_filter(query, scope: Dict[str, Any]):
        school_ids = scope.get("school_ids")
        if school_ids is None:
            return query
        if not school_ids:
            return query.filter(False)
        # Converter school_ids para strings (School.id é VARCHAR)
        school_ids_str = uuid_list_to_str(school_ids)
        return query.filter(School.id.in_(school_ids_str))

    @classmethod
    def _count_students(cls, scope: Dict[str, Any]) -> int:
        query = Student.query
        if scope["scope"] == "municipio":
            school_ids = cls._extract_school_ids(scope) or []
            query = query.filter(Student.school_id.in_(school_ids)) if school_ids else query.filter(False)
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            query = query.filter(Student.school_id.in_(school_ids)) if school_ids else query.filter(False)
        return query.count()

    @classmethod
    def _count_schools(cls, scope: Dict[str, Any]) -> int:
        query = School.query
        if scope["scope"] == "municipio" and scope.get("city_id"):
            query = query.filter(School.city_id == scope["city_id"])
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            # Converter school_ids para strings (School.id é VARCHAR)
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            query = query.filter(School.id.in_(school_ids_str)) if school_ids_str else query.filter(False)
        return query.count()

    @classmethod
    def _count_notices(cls, scope: Dict[str, Any]) -> int:
        """
        Retorna a quantidade de avisos no escopo do usuário.
        Quando existir modelo/tabela de avisos, implementar a contagem aqui.
        """
        return 0

    @classmethod
    def _count_certificates(cls, scope: Dict[str, Any]) -> int:
        """Retorna a quantidade de certificados emitidos no escopo do usuário."""
        school_ids = cls._extract_school_ids(scope)
        return CertificateService.count_issued(school_ids)

    @classmethod
    def _count_evaluations(cls, scope: Dict[str, Any]) -> int:
        query = Test.query.with_entities(Test.id)

        if scope["scope"] == "municipio":
            school_ids = cls._extract_school_ids(scope) or []
            if school_ids:
                # ✅ CORRIGIDO: Class.school_id é VARCHAR, converter para strings
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                query = (
                    query.join(ClassTest, ClassTest.test_id == Test.id)
                    .join(Class, Class.id == ClassTest.class_id)
                    .filter(Class.school_id.in_(school_ids_str))
                ) if school_ids_str else query.filter(False)
            else:
                query = query.filter(False)
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if school_ids:
                # ✅ CORRIGIDO: Class.school_id é VARCHAR, converter para strings
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                query = (
                    query.join(ClassTest, ClassTest.test_id == Test.id)
                    .join(Class, Class.id == ClassTest.class_id)
                    .filter(Class.school_id.in_(school_ids_str))
                ) if school_ids_str else query.filter(False)
            else:
                query = query.filter(False)

        return query.distinct().count()

    @classmethod
    def _count_games(cls, scope: Dict[str, Any]) -> int:
        query = Game.query
        if scope["scope"] == "municipio" and scope.get("city_id"):
            query = query.join(User, User.id == Game.userId).filter(User.city_id == scope["city_id"])
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if school_ids:
                query = query.join(User, User.id == Game.userId).join(Student, Student.user_id == User.id, isouter=True)
        return query.count()

    @classmethod
    def _count_users(cls, scope: Dict[str, Any]) -> int:
        query = User.query
        if scope["scope"] == "municipio" and scope.get("city_id"):
            query = query.filter(User.city_id == scope["city_id"])
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if school_ids:
                # Converter school_ids para strings (Student.school_id, SchoolTeacher.school_id, Manager.school_id são VARCHAR)
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                student_ids = (
                    Student.query.filter(Student.school_id.in_(school_ids_str)).with_entities(Student.user_id).all()
                )
                teacher_ids = (
                    Teacher.query.join(SchoolTeacher, SchoolTeacher.teacher_id == Teacher.id)
                    .filter(SchoolTeacher.school_id.in_(school_ids_str))
                    .with_entities(Teacher.user_id)
                    .all()
                )
                manager_ids = (
                    Manager.query.filter(Manager.school_id.in_(school_ids_str)).with_entities(Manager.user_id).all()
                )
                user_ids = {row.user_id for row in student_ids + teacher_ids + manager_ids if row.user_id}
                if not user_ids:
                    return 0
                query = query.filter(User.id.in_(user_ids))
            else:
                return 0
        return query.count()

    @classmethod
    def _count_questions(cls, scope: Dict[str, Any]) -> int:
        query = Question.query
        if scope["scope"] == "municipio" and scope.get("city_id"):
            query = query.join(User, User.id == Question.created_by).filter(User.city_id == scope["city_id"])
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if school_ids:
                # Converter school_ids para strings (SchoolTeacher.school_id é VARCHAR)
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                teacher_ids = (
                    Teacher.query.join(SchoolTeacher, SchoolTeacher.teacher_id == Teacher.id)
                    .filter(SchoolTeacher.school_id.in_(school_ids_str))
                    .with_entities(Teacher.user_id)
                    .all()
                )
                user_ids = [row.user_id for row in teacher_ids if row.user_id]
                if user_ids:
                    query = query.filter(Question.created_by.in_(user_ids))
                else:
                    return 0
            else:
                return 0
        return query.count()

    @classmethod
    def _questions_base_query(cls, scope: Dict[str, Any]):
        """Query base de questões com filtro de escopo (reutilizada para listagem e contagem)."""
        query = Question.query
        if scope["scope"] == "municipio" and scope.get("city_id"):
            query = query.join(User, User.id == Question.created_by).filter(User.city_id == scope["city_id"])
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if school_ids:
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                teacher_ids = (
                    Teacher.query.join(SchoolTeacher, SchoolTeacher.teacher_id == Teacher.id)
                    .filter(SchoolTeacher.school_id.in_(school_ids_str))
                    .with_entities(Teacher.user_id)
                    .all()
                )
                user_ids = [row.user_id for row in teacher_ids if row.user_id]
                if user_ids:
                    query = query.filter(Question.created_by.in_(user_ids))
                else:
                    query = query.filter(False)
            else:
                query = query.filter(False)
        return query

    @classmethod
    def get_questoes_dashboard(
        cls, scope: Dict[str, Any], limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """
        Lista questões para o card do dashboard com detalhes ricos: quantidade de
        respostas, taxa de acerto, quantidade de avaliações em que aparece,
        última utilização, disciplina, ano, autor, dificuldade, tipo.
        """
        from sqlalchemy.exc import SQLAlchemyError

        try:
            query = cls._questions_base_query(scope).order_by(Question.created_at.desc())
            total = query.count()
            questions = (
                query.options(
                    db.joinedload(Question.subject),
                    db.joinedload(Question.grade),
                    db.joinedload(Question.creator),
                )
                .offset(offset)
                .limit(limit)
                .all()
            )
            if not questions:
                return {"questoes": [], "total": total, "limit": limit, "offset": offset}

            question_ids = [q.id for q in questions]

            # Estatísticas de respostas por questão: total, corretas, última resposta
            answers_subq = (
                db.session.query(
                    StudentAnswer.question_id,
                    func.count(StudentAnswer.id).label("total_respostas"),
                    func.sum(case((StudentAnswer.is_correct == True, 1), else_=0)).label("corretas"),
                    func.max(StudentAnswer.answered_at).label("ultima_resposta"),
                )
                .filter(StudentAnswer.question_id.in_(question_ids))
                .group_by(StudentAnswer.question_id)
            ).subquery()

            answers_map = {}
            for row in db.session.query(answers_subq).all():
                qid = str(row.question_id)
                total_r = int(row.total_respostas or 0)
                corretas = int(row.corretas or 0)
                answers_map[qid] = {
                    "quantidade_respostas": total_r,
                    "taxa_acerto": round((corretas / total_r * 100), 2) if total_r else None,
                    "ultima_utilizacao": row.ultima_resposta.isoformat() if row.ultima_resposta and hasattr(row.ultima_resposta, "isoformat") else str(row.ultima_resposta) if row.ultima_resposta else None,
                }

            # Quantidade de avaliações (testes) em que a questão aparece
            tests_subq = (
                db.session.query(
                    TestQuestion.question_id,
                    func.count(distinct(TestQuestion.test_id)).label("quantidade_avaliacoes"),
                )
                .filter(TestQuestion.question_id.in_(question_ids))
                .group_by(TestQuestion.question_id)
            ).subquery()

            tests_map = {}
            for row in db.session.query(tests_subq).all():
                tests_map[str(row.question_id)] = int(row.quantidade_avaliacoes or 0)

            # Resolver habilidade: Question.skill guarda ID da Skill; retornar o código (nome)
            skill_ids_clean = set()
            for q in questions:
                if q.skill and str(q.skill).strip() and str(q.skill).strip() != "{}":
                    skill_ids_clean.add(str(q.skill).strip().strip("{}"))
            skill_code_map = {}
            if skill_ids_clean:
                import uuid as uuid_module
                for sid in skill_ids_clean:
                    skill_obj = None
                    try:
                        skill_uuid = uuid_module.UUID(sid)
                        skill_obj = Skill.query.filter(Skill.id == str(skill_uuid)).first()
                    except (ValueError, TypeError):
                        pass
                    if not skill_obj:
                        skill_obj = Skill.query.filter(Skill.code == sid).first()
                    if skill_obj:
                        skill_code_map[sid] = skill_obj.code
                    else:
                        skill_code_map[sid] = sid  # fallback: usar o valor como está (ex.: já é código)

            listagem = []
            for q in questions:
                stats = answers_map.get(q.id, {"quantidade_respostas": 0, "taxa_acerto": None, "ultima_utilizacao": None})
                skill_raw = q.skill.strip("{}").strip() if q.skill and str(q.skill).strip() and str(q.skill).strip() != "{}" else None
                habilidade_codigo = skill_code_map.get(skill_raw, skill_raw) if skill_raw else None
                listagem.append({
                    "id": q.id,
                    "titulo": (q.title or (q.text[:80] + "..." if (q.text and len(q.text) > 80) else (q.text or ""))),
                    "disciplina": q.subject.name if q.subject else None,
                    "ano_serie": q.grade.name if q.grade else None,
                    "autor": q.creator.name if q.creator else None,
                    "data_criacao": q.created_at.isoformat() if q.created_at and hasattr(q.created_at, "isoformat") else str(q.created_at) if q.created_at else None,
                    "dificuldade": q.difficulty_level or "Médio",
                    "tipo_questao": q.question_type or "multipleChoice",
                    "quantidade_respostas": stats["quantidade_respostas"],
                    "taxa_acerto": stats["taxa_acerto"],
                    "quantidade_avaliacoes": tests_map.get(q.id, 0),
                    "ultima_utilizacao": stats["ultima_utilizacao"],
                    "habilidade": habilidade_codigo,
                })

            return {
                "questoes": listagem,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        except SQLAlchemyError as e:
            db.session.rollback()
            raise

    @classmethod
    def _count_classes(cls, scope: Dict[str, Any]) -> int:
        query = Class.query
        if scope["scope"] == "municipio":
            school_ids = cls._extract_school_ids(scope) or []
            # ✅ CORRIGIDO: Converter school_ids para strings (Class.school_id é VARCHAR)
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            query = query.filter(Class.school_id.in_(school_ids_str)) if school_ids_str else query.filter(False)
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            # ✅ CORRIGIDO: Converter school_ids para strings (Class.school_id é VARCHAR)
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            query = query.filter(Class.school_id.in_(school_ids_str)) if school_ids_str else query.filter(False)
        return query.count()

    @classmethod
    def _count_teachers(cls, scope: Dict[str, Any]) -> int:
        teacher_query = Teacher.query
        if scope["scope"] == "municipio":
            school_ids = cls._extract_school_ids(scope) or []
            # Converter school_ids para strings (SchoolTeacher.school_id é VARCHAR)
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            teacher_query = (
                teacher_query.join(SchoolTeacher, SchoolTeacher.teacher_id == Teacher.id)
                .filter(SchoolTeacher.school_id.in_(school_ids_str))
                if school_ids_str
                else teacher_query.filter(False)
            )
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            # Converter school_ids para strings (SchoolTeacher.school_id é VARCHAR)
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            teacher_query = (
                teacher_query.join(SchoolTeacher, SchoolTeacher.teacher_id == Teacher.id)
                .filter(SchoolTeacher.school_id.in_(school_ids_str))
                if school_ids_str
                else teacher_query.filter(False)
            )
        return teacher_query.distinct().count()

    # ------------------------------------------------------------------ #
    # KPIs auxiliares
    # ------------------------------------------------------------------ #

    @staticmethod
    def _student_scope_filter(query, scope: Dict[str, Any]):
        if scope["scope"] == "municipio":
            school_ids = DashboardService._extract_school_ids(scope) or []
            return query.filter(Student.school_id.in_(school_ids)) if school_ids else query.filter(False)
        if scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            return query.filter(Student.school_id.in_(school_ids)) if school_ids else query.filter(False)
        return query

    @staticmethod
    def _evaluation_scope_filter(query, scope: Dict[str, Any]):
        if scope["scope"] in {"municipio", "escola"}:
            school_ids = DashboardService._extract_school_ids(scope) or []
            if not school_ids:
                return query.filter(False)
            return (
                query.join(ClassTest, ClassTest.test_id == Test.id)
                .join(Class, Class.id == ClassTest.class_id)
                .filter(Class.school_id.in_(school_ids))
            )
        return query

    @staticmethod
    def _session_scope_filter(query, scope: Dict[str, Any]):
        if scope["scope"] == "municipio":
            school_ids = DashboardService._extract_school_ids(scope) or []
            if not school_ids:
                return query.filter(False)
            return query.join(Student, Student.id == TestSession.student_id).filter(Student.school_id.in_(school_ids))
        if scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if not school_ids:
                return query.filter(False)
            return query.join(Student, Student.id == TestSession.student_id).filter(Student.school_id.in_(school_ids))
        return query

    @classmethod
    def _period_counts(cls, model, date_column, scope: Dict[str, Any], filter_callback):
        now = datetime.utcnow()
        current_start = now - timedelta(days=30)
        previous_start = current_start - timedelta(days=30)

        current_query = model.query.filter(date_column >= current_start)
        current_query = filter_callback(current_query, scope)

        previous_query = model.query.filter(date_column >= previous_start, date_column < current_start)
        previous_query = filter_callback(previous_query, scope)

        return current_query.count(), previous_query.count()

    # ------------------------------------------------------------------ #
    # Rankings
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_school_rankings(cls, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import VARCHAR
        
        try:
            school_ids = cls._extract_school_ids(scope)
            query = (
                db.session.query(
                    School.id.label("school_id"),
                    School.name.label("school_name"),
                    City.name.label("municipality"),
                    func.count(distinct(Student.id)).label("total_students"),
                    func.coalesce(func.avg(EvaluationResult.score_percentage), 0).label("average_score"),
                    func.count(distinct(EvaluationResult.test_id)).label("total_evaluations"),
                )
                # ✅ CORRIGIDO: Garantir que ambos sejam strings no join (School.id é VARCHAR)
                .join(Student, cast(Student.school_id, VARCHAR) == cast(School.id, VARCHAR))
                .outerjoin(EvaluationResult, EvaluationResult.student_id == Student.id)
                .outerjoin(City, City.id == School.city_id)
            )

            if scope["scope"] == "municipio" and scope.get("city_id"):
                query = query.filter(School.city_id == scope["city_id"])
            elif school_ids is not None:
                # Converter school_ids para strings (School.id é VARCHAR)
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                query = query.filter(School.id.in_(school_ids_str)) if school_ids_str else query.filter(False)

            query = query.group_by(School.id, School.name, City.name).order_by(func.coalesce(func.avg(EvaluationResult.score_percentage), 0).desc())

            school_stats = query.limit(cls.MAX_LIST_SIZE).all()

            completion_subquery = (
                db.session.query(
                    cast(Student.school_id, VARCHAR).label("school_id"),
                    func.sum(case((TestSession.submitted_at.isnot(None), 1), else_=0)).label("completed_sessions"),
                    func.count(TestSession.id).label("total_sessions"),
                )
                .join(Student, Student.id == TestSession.student_id)
                .group_by(Student.school_id)
                .subquery()
            )

            completion_map = {
                str(row.school_id): (row.completed_sessions or 0, row.total_sessions or 0)
                for row in db.session.query(completion_subquery).all()
            }

            rankings = []
            for idx, row in enumerate(school_stats):
                # ✅ CORRIGIDO: Garantir string para comparação
                school_id_str = str(row.school_id)
                completed, total = completion_map.get(school_id_str, (0, 0))
                completion_rate = round((completed / total) * 100, 2) if total else 0.0

                rankings.append(
                    {
                        "position": idx + 1,
                        "school_id": school_id_str,
                        "school_name": row.school_name,
                        "municipality": row.municipality,
                        "average_score": float(row.average_score or 0),
                        "completion_rate": completion_rate,
                        "total_students": int(row.total_students or 0),
                        "total_evaluations": int(row.total_evaluations or 0),
                    }
                )
            return rankings
        except SQLAlchemyError as e:
            db.session.rollback()
            raise

    @classmethod
    def _build_class_rankings(cls, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Ranking de turmas: turma, série, média, acerto, conclusão, alunos, avaliações."""
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import VARCHAR

        try:
            school_ids = cls._extract_school_ids(scope)
            if school_ids is not None:
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                if not school_ids_str:
                    return []

            query = (
                db.session.query(
                    Class.id.label("class_id"),
                    Class.name.label("turma"),
                    Grade.name.label("serie"),
                    func.count(distinct(Student.id)).label("alunos"),
                    func.coalesce(func.avg(EvaluationResult.grade), 0).label("media"),
                    func.coalesce(func.sum(EvaluationResult.correct_answers), 0).label("acerto_total"),
                    func.coalesce(func.avg(EvaluationResult.score_percentage), 0).label("acerto_percent"),
                    func.count(distinct(EvaluationResult.test_id)).label("avaliacoes"),
                )
                .outerjoin(Grade, Class.grade_id == Grade.id)
                .join(Student, Student.class_id == Class.id)
                .outerjoin(EvaluationResult, EvaluationResult.student_id == Student.id)
            )

            if scope["scope"] == "municipio" and scope.get("city_id"):
                query = query.join(School, cast(Class._school_id, VARCHAR) == cast(School.id, VARCHAR)).filter(
                    School.city_id == scope["city_id"]
                )
            elif school_ids is not None:
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                query = query.filter(Class._school_id.in_(school_ids_str))

            query = query.group_by(Class.id, Class.name, Grade.name).order_by(
                func.coalesce(func.avg(EvaluationResult.grade), 0).desc()
            )

            class_stats = query.limit(cls.MAX_LIST_SIZE).all()

            # Taxa de conclusão por turma: sessões finalizadas / total de sessões
            completion_subquery = (
                db.session.query(
                    Student.class_id.label("class_id"),
                    func.sum(case((TestSession.submitted_at.isnot(None), 1), else_=0)).label("completed_sessions"),
                    func.count(TestSession.id).label("total_sessions"),
                )
                .join(Student, Student.id == TestSession.student_id)
                .group_by(Student.class_id)
                .subquery()
            )
            completion_map = {
                str(row.class_id): (row.completed_sessions or 0, row.total_sessions or 0)
                for row in db.session.query(completion_subquery).all()
            }

            rankings = []
            for idx, row in enumerate(class_stats):
                class_id_str = str(row.class_id)
                completed, total = completion_map.get(class_id_str, (0, 0))
                conclusao = round((completed / total) * 100, 2) if total else 0.0
                rankings.append(
                    {
                        "position": idx + 1,
                        "class_id": class_id_str,
                        "turma": row.turma or "",
                        "serie": row.serie or "",
                        "media": float(row.media or 0),
                        "acerto": int(row.acerto_total or 0),
                        "acerto_percent": float(row.acerto_percent or 0),
                        "conclusao": conclusao,
                        "alunos": int(row.alunos or 0),
                        "avaliacoes": int(row.avaliacoes or 0),
                    }
                )
            return rankings
        except SQLAlchemyError as e:
            db.session.rollback()
            raise

    @classmethod
    def get_school_ranking_card(
        cls,
        scope: Dict[str, Any],
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Retorna ranking de escolas para card, com métricas para exibição e ordenação.
        Inclui: média (nota 0-10 e %), quantidade de alunos, taxa de conclusão,
        quantidade de avaliações, total de turmas, total de provas entregues.
        """
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import VARCHAR

        try:
            school_ids = cls._extract_school_ids(scope)
            query = (
                db.session.query(
                    School.id.label("school_id"),
                    School.name.label("school_name"),
                    City.name.label("municipality"),
                    func.count(distinct(Student.id)).label("total_students"),
                    func.coalesce(func.avg(EvaluationResult.grade), 0).label("media"),
                    func.coalesce(func.avg(EvaluationResult.score_percentage), 0).label("media_score_percent"),
                    func.count(distinct(EvaluationResult.test_id)).label("quantidade_avaliacoes"),
                    func.count(EvaluationResult.id).label("total_provas_entregues"),
                )
                .join(Student, cast(Student.school_id, VARCHAR) == cast(School.id, VARCHAR))
                .outerjoin(EvaluationResult, EvaluationResult.student_id == Student.id)
                .outerjoin(City, City.id == School.city_id)
            )

            if scope["scope"] == "municipio" and scope.get("city_id"):
                query = query.filter(School.city_id == scope["city_id"])
            elif school_ids is not None:
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                query = query.filter(School.id.in_(school_ids_str)) if school_ids_str else query.filter(False)

            query = query.group_by(School.id, School.name, City.name).order_by(
                func.coalesce(func.avg(EvaluationResult.grade), 0).desc()
            )

            # Contar total de escolas (sem limit/offset) para paginação
            total_count = query.count()
            school_stats = query.offset(offset).limit(limit).all()

            # Taxa de conclusão: sessões finalizadas / total de sessões por escola
            completion_subquery = (
                db.session.query(
                    cast(Student.school_id, VARCHAR).label("school_id"),
                    func.sum(case((TestSession.submitted_at.isnot(None), 1), else_=0)).label("completed_sessions"),
                    func.count(TestSession.id).label("total_sessions"),
                )
                .join(Student, Student.id == TestSession.student_id)
                .group_by(Student.school_id)
                .subquery()
            )
            completion_map = {
                str(row.school_id): (row.completed_sessions or 0, row.total_sessions or 0)
                for row in db.session.query(completion_subquery).all()
            }

            # Total de turmas por escola
            classes_subquery = (
                db.session.query(
                    cast(Class._school_id, VARCHAR).label("school_id"),
                    func.count(distinct(Class.id)).label("total_turmas"),
                )
                .group_by(Class._school_id)
                .subquery()
            )
            classes_map = {
                str(row.school_id): int(row.total_turmas or 0)
                for row in db.session.query(classes_subquery).all()
            }

            ranking = []
            for idx, row in enumerate(school_stats):
                school_id_str = str(row.school_id)
                completed, total = completion_map.get(school_id_str, (0, 0))
                taxa_conclusao = round((completed / total) * 100, 2) if total else 0.0

                ranking.append({
                    "posicao": offset + idx + 1,
                    "escola_id": school_id_str,
                    "nome_escola": row.school_name,
                    "municipio": row.municipality,
                    "media": float(row.media or 0),
                    "media_score_percent": float(row.media_score_percent or 0),
                    "quantidade_alunos": int(row.total_students or 0),
                    "taxa_conclusao": taxa_conclusao,
                    "quantidade_avaliacoes": int(row.quantidade_avaliacoes or 0),
                    "total_turmas": classes_map.get(school_id_str, 0),
                    "total_provas_entregues": int(row.total_provas_entregues or 0),
                })

            return {
                "ranking": ranking,
                "total": total_count,
                "limit": limit,
                "offset": offset,
            }
        except SQLAlchemyError as e:
            db.session.rollback()
            raise

    @classmethod
    def get_class_ranking_card(
        cls,
        scope: Dict[str, Any],
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Retorna ranking de turmas para o card: turma, série, média, acerto, conclusão,
        alunos, avaliações. Respeita o escopo do usuário (município ou escola).
        """
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import VARCHAR

        try:
            school_ids = cls._extract_school_ids(scope)
            if school_ids is not None:
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                if not school_ids_str:
                    return {"ranking": [], "total": 0, "limit": limit, "offset": offset}

            query = (
                db.session.query(
                    Class.id.label("class_id"),
                    Class.name.label("turma"),
                    Grade.name.label("serie"),
                    func.count(distinct(Student.id)).label("alunos"),
                    func.coalesce(func.avg(EvaluationResult.grade), 0).label("media"),
                    func.coalesce(func.sum(EvaluationResult.correct_answers), 0).label("acerto_total"),
                    func.coalesce(func.avg(EvaluationResult.score_percentage), 0).label("acerto_percent"),
                    func.count(distinct(EvaluationResult.test_id)).label("avaliacoes"),
                )
                .outerjoin(Grade, Class.grade_id == Grade.id)
                .join(Student, Student.class_id == Class.id)
                .outerjoin(EvaluationResult, EvaluationResult.student_id == Student.id)
            )

            if scope["scope"] == "municipio" and scope.get("city_id"):
                query = query.join(School, cast(Class._school_id, VARCHAR) == cast(School.id, VARCHAR)).filter(
                    School.city_id == scope["city_id"]
                )
            elif school_ids is not None:
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                query = query.filter(Class._school_id.in_(school_ids_str))

            query = query.group_by(Class.id, Class.name, Grade.name).order_by(
                func.coalesce(func.avg(EvaluationResult.grade), 0).desc()
            )

            total_count = query.count()
            class_stats = query.offset(offset).limit(limit).all()

            completion_subquery = (
                db.session.query(
                    Student.class_id.label("class_id"),
                    func.sum(case((TestSession.submitted_at.isnot(None), 1), else_=0)).label("completed_sessions"),
                    func.count(TestSession.id).label("total_sessions"),
                )
                .join(Student, Student.id == TestSession.student_id)
                .group_by(Student.class_id)
                .subquery()
            )
            completion_map = {
                str(row.class_id): (row.completed_sessions or 0, row.total_sessions or 0)
                for row in db.session.query(completion_subquery).all()
            }

            ranking = []
            for idx, row in enumerate(class_stats):
                class_id_str = str(row.class_id)
                completed, total = completion_map.get(class_id_str, (0, 0))
                conclusao = round((completed / total) * 100, 2) if total else 0.0
                ranking.append({
                    "posicao": offset + idx + 1,
                    "class_id": class_id_str,
                    "turma": row.turma or "",
                    "serie": row.serie or "",
                    "media": float(row.media or 0),
                    "acerto": int(row.acerto_total or 0),
                    "acerto_percent": float(row.acerto_percent or 0),
                    "conclusao": conclusao,
                    "alunos": int(row.alunos or 0),
                    "avaliacoes": int(row.avaliacoes or 0),
                })

            return {
                "ranking": ranking,
                "total": total_count,
                "limit": limit,
                "offset": offset,
            }
        except SQLAlchemyError as e:
            db.session.rollback()
            raise

    @classmethod
    def _build_student_rankings(cls, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import VARCHAR

        school_alias = aliased(School)
        class_alias = aliased(Class)

        query = (
            db.session.query(
                Student.id.label("student_id"),
                Student.name.label("student_name"),
                school_alias.name.label("school_name"),
                class_alias.name.label("class_name"),
                Grade.name.label("serie"),
                func.coalesce(func.avg(EvaluationResult.grade), 0).label("average_grade"),
                func.count(distinct(EvaluationResult.test_id)).label("completed_evaluations"),
            )
            .join(EvaluationResult, EvaluationResult.student_id == Student.id)
            .outerjoin(school_alias, cast(school_alias.id, VARCHAR) == cast(Student.school_id, VARCHAR))
            .outerjoin(class_alias, class_alias.id == Student.class_id)
            .outerjoin(Grade, Grade.id == Student.grade_id)
            .group_by(Student.id, Student.name, school_alias.name, class_alias.name, Grade.name)
            .order_by(func.coalesce(func.avg(EvaluationResult.grade), 0).desc())
        )

        if scope["scope"] == "municipio" and scope.get("city_id"):
            query = query.filter(school_alias.city_id == scope["city_id"])
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            query = query.filter(Student.school_id.in_(school_ids_str)) if school_ids_str else query.filter(False)

        ranking = []
        for idx, row in enumerate(query.limit(DashboardService.MAX_LIST_SIZE).all()):
            ranking.append(
                {
                    "student_id": row.student_id,
                    "name": row.student_name,
                    "school_name": row.school_name,
                    "class_name": row.class_name,
                    "serie": row.serie or "",
                    "media": float(row.average_grade or 0),
                    "completed_evaluations": int(row.completed_evaluations or 0),
                    "position": idx + 1,
                }
            )
        return ranking

    @classmethod
    def get_ranking_alunos(cls, scope: Dict[str, Any], limit: int = 20) -> Dict[str, Any]:
        """
        Retorna o top de alunos (ranking) para o dashboard, respeitando o escopo
        do usuário (município, escola ou global para admin).
        Inclui série e média (nota 0-10, 2 decimais).
        """
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import VARCHAR

        school_alias = aliased(School)
        class_alias = aliased(Class)
        limit = min(max(1, limit), 50)

        query = (
            db.session.query(
                Student.id.label("student_id"),
                Student.name.label("student_name"),
                school_alias.name.label("school_name"),
                class_alias.name.label("class_name"),
                Grade.name.label("serie"),
                func.coalesce(func.avg(EvaluationResult.grade), 0).label("average_grade"),
                func.count(distinct(EvaluationResult.test_id)).label("completed_evaluations"),
            )
            .join(EvaluationResult, EvaluationResult.student_id == Student.id)
            .outerjoin(school_alias, cast(school_alias.id, VARCHAR) == cast(Student.school_id, VARCHAR))
            .outerjoin(class_alias, class_alias.id == Student.class_id)
            .outerjoin(Grade, Grade.id == Student.grade_id)
            .group_by(Student.id, Student.name, school_alias.name, class_alias.name, Grade.name)
            .order_by(func.coalesce(func.avg(EvaluationResult.grade), 0).desc())
        )

        if scope["scope"] == "municipio" and scope.get("city_id"):
            query = query.filter(school_alias.city_id == scope["city_id"])
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            query = query.filter(Student.school_id.in_(school_ids_str)) if school_ids_str else query.filter(False)

        rows = query.limit(limit).all()
        ranking = [
            {
                "student_id": row.student_id,
                "name": row.student_name,
                "school_name": row.school_name,
                "class_name": row.class_name,
                "serie": row.serie or "",
                "media": float(row.average_grade or 0),
                "completed_evaluations": int(row.completed_evaluations or 0),
                "position": idx + 1,
            }
            for idx, row in enumerate(rows)
        ]
        return {"ranking": ranking, "total": len(ranking)}

    # ------------------------------------------------------------------ #
    # Engajamento
    # ------------------------------------------------------------------ #

    @classmethod
    def _popular_evaluations(cls, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = (
            db.session.query(
                Test.id.label("evaluation_id"),
                Test.title.label("title"),
                func.count(TestSession.id).label("views"),
                func.sum(case((TestSession.submitted_at.isnot(None), 1), else_=0)).label("completions"),
            )
            .join(TestSession, TestSession.test_id == Test.id)
            .group_by(Test.id, Test.title)
            .order_by(func.count(TestSession.id).desc())
        )

        if scope["scope"] == "municipio":
            school_ids = cls._extract_school_ids(scope) or []
            if school_ids:
                # ✅ CORRIGIDO: Class.school_id é VARCHAR, converter para strings
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                query = (
                    query.join(ClassTest, ClassTest.test_id == Test.id)
                    .join(Class, Class.id == ClassTest.class_id)
                    .filter(Class.school_id.in_(school_ids_str))
                ) if school_ids_str else query.filter(False)
            else:
                return []
        elif scope["scope"] == "escola":
            school_ids = scope.get("school_ids") or []
            if school_ids:
                # ✅ CORRIGIDO: Class.school_id é VARCHAR, converter para strings
                school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
                query = (
                    query.join(ClassTest, ClassTest.test_id == Test.id)
                    .join(Class, Class.id == ClassTest.class_id)
                    .filter(Class.school_id.in_(school_ids_str))
                ) if school_ids_str else query.filter(False)
            else:
                return []

        popular = []
        for row in query.limit(5).all():
            popular.append(
                {
                    "evaluation_id": row.evaluation_id,
                    "title": row.title,
                    "views": int(row.views or 0),
                    "completions": int(row.completions or 0),
                }
            )
        return popular

    @classmethod
    def _return_rate(cls, scope: Dict[str, Any]) -> Dict[str, Any]:
        session_query = TestSession.query
        session_query = cls._session_scope_filter(session_query, scope)

        total_users = session_query.with_entities(distinct(TestSession.student_id)).count()
        returning_users = (
            session_query.group_by(TestSession.student_id)
            .having(func.count(TestSession.id) > 1)
            .with_entities(TestSession.student_id)
            .count()
        )

        percentage = round((returning_users / total_users) * 100, 2) if total_users else 0.0

        return {
            "percentage": percentage,
            "total_users": total_users,
            "returning_users": returning_users,
            "growth_percentage": 0,  # Falta histórico
        }

    # ------------------------------------------------------------------ #
    # Diretor/Coordenador
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_school_summary(cls, scope: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "students": cls._count_students(scope),
            "classes": cls._count_classes(scope),
            "evaluations": cls._count_evaluations(scope),
            "teachers": cls._count_teachers(scope),
            "last_sync": datetime.utcnow().isoformat(),
        }

    @classmethod
    def _build_school_kpis(cls, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"id": "students", "label": "Alunos da escola", "value": cls._count_students(scope)},
            {"id": "classes", "label": "Turmas", "value": cls._count_classes(scope)},
            {"id": "evaluations", "label": "Avaliações", "value": cls._count_evaluations(scope)},
            {"id": "teachers", "label": "Professores", "value": cls._count_teachers(scope)},
        ]

    @classmethod
    def _build_class_ranking(cls, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = (
            db.session.query(
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                func.avg(EvaluationResult.grade).label("average_grade"),
                func.sum(case((TestSession.submitted_at.isnot(None), 1), else_=0)).label("completed_sessions"),
                func.count(TestSession.id).label("total_sessions"),
                func.count(distinct(Student.id)).label("active_students"),
            )
            .join(Student, Student.class_id == Class.id)
            .join(EvaluationResult, EvaluationResult.student_id == Student.id, isouter=True)
            .join(TestSession, TestSession.student_id == Student.id, isouter=True)
        )

        if scope.get("class_ids"):
            query = query.filter(Class.id.in_(scope["class_ids"]))

        query = query.group_by(Class.id, Class.name).order_by(func.avg(EvaluationResult.grade).desc())

        ranking = []
        for idx, row in enumerate(query.limit(DashboardService.MAX_LIST_SIZE).all()):
            total_sessions = int(row.total_sessions or 0)
            completed_sessions = int(row.completed_sessions or 0)
            completion_rate = round((completed_sessions / total_sessions) * 100, 2) if total_sessions else 0.0

            ranking.append(
                {
                    "class_id": row.class_id,
                    "class_name": row.class_name,
                    "average_score": float(row.average_grade or 0),
                    "completion_rate": completion_rate,
                    "active_students": int(row.active_students or 0),
                    "position": idx + 1,
                }
            )
        return ranking

    @classmethod
    def _build_teacher_ranking(cls, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        teacher_alias = aliased(Teacher)
        query = (
            db.session.query(
                teacher_alias.id.label("teacher_id"),
                teacher_alias.name.label("teacher_name"),
                func.avg(EvaluationResult.grade).label("average_grade"),
                func.count(distinct(EvaluationResult.test_id)).label("total_evaluations"),
                func.count(distinct(TeacherClass.class_id)).label("classes_count"),
            )
            .join(TeacherClass, TeacherClass.teacher_id == teacher_alias.id)
            .join(Class, Class.id == TeacherClass.class_id)
            .join(Student, Student.class_id == Class.id)
            .join(EvaluationResult, EvaluationResult.student_id == Student.id, isouter=True)
        )

        school_ids = scope.get("school_ids") or []
        if school_ids:
            # Converter school_ids para strings (SchoolTeacher.school_id é VARCHAR)
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            query = query.join(SchoolTeacher, SchoolTeacher.teacher_id == teacher_alias.id).filter(
                SchoolTeacher.school_id.in_(school_ids_str)
            )
        else:
            return []

        query = query.group_by(teacher_alias.id, teacher_alias.name).order_by(func.avg(EvaluationResult.grade).desc())

        ranking = []
        for idx, row in enumerate(query.limit(DashboardService.MAX_LIST_SIZE).all()):
            ranking.append(
                {
                    "teacher_id": row.teacher_id,
                    "teacher_name": row.teacher_name,
                    "average_score": float(row.average_grade or 0),
                    "total_evaluations": int(row.total_evaluations or 0),
                    "classes_count": int(row.classes_count or 0),
                    "position": idx + 1,
                }
            )
        return ranking

    @classmethod
    def _build_students_overview(cls, scope: Dict[str, Any]) -> Dict[str, Any]:
        school_ids = scope.get("school_ids") or []
        new_students = (
            Student.query.filter(Student.school_id.in_(school_ids))
            .order_by(Student.created_at.desc())
            .limit(5)
            .all()
            if school_ids
            else []
        )

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        inactive_students = (
            Student.query.filter(Student.school_id.in_(school_ids))
            .outerjoin(TestSession, TestSession.student_id == Student.id)
            .group_by(Student.id)
            .having(func.max(TestSession.updated_at) < thirty_days_ago)
            .limit(5)
            .all()
            if school_ids
            else []
        )

        return {
            "new_students": [
                {
                    "student_id": student.id,
                    "name": student.name,
                    "class": student.class_.name if student.class_ else None,
                    "created_at": student.created_at.isoformat() if student.created_at else None,
                }
                for student in new_students
            ],
            "inactive_students": [
                {
                    "student_id": student.id,
                    "name": student.name,
                    "last_login": None,
                }
                for student in inactive_students
            ],
        }

    @staticmethod
    def _build_notifications_placeholder() -> List[Dict[str, Any]]:
        return []

    # ------------------------------------------------------------------ #
    # Professor
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_professor_summary(cls, scope: Dict[str, Any], teacher: Optional[Teacher]) -> Dict[str, Any]:
        class_ids = get_teacher_classes(scope["user"]["id"]) if teacher else []
        students = (
            Student.query.filter(Student.class_id.in_(class_ids)).count() if class_ids else 0
        )
        active_students = (
            TestSession.query.join(Student, Student.id == TestSession.student_id)
            .filter(Student.class_id.in_(class_ids))
            .filter(TestSession.updated_at >= datetime.utcnow() - timedelta(days=7))
            .with_entities(distinct(TestSession.student_id))
            .count()
            if class_ids
            else 0
        )
        return {
            "students": students,
            "classes": len(class_ids),
            "evaluations": cls._count_professor_evaluations(scope, teacher),
            "active_students": active_students,
            "last_sync": datetime.utcnow().isoformat(),
        }

    @classmethod
    def _count_professor_evaluations(cls, scope: Dict[str, Any], teacher: Optional[Teacher]) -> int:
        if not teacher:
            return 0
        class_ids = get_teacher_classes(scope["user"]["id"])
        if not class_ids:
            return 0
        return (
            Test.query.with_entities(Test.id)
            .join(ClassTest, ClassTest.test_id == Test.id)
            .filter(ClassTest.class_id.in_(class_ids))
            .distinct()
            .count()
        )

    @classmethod
    def _build_professor_kpis(cls, scope: Dict[str, Any], teacher: Optional[Teacher]) -> List[Dict[str, Any]]:
        class_ids = get_teacher_classes(scope["user"]["id"]) if teacher else []

        evaluations_count = cls._count_professor_evaluations(scope, teacher)
        completed_sessions = (
            TestSession.query.join(Student, Student.id == TestSession.student_id)
            .filter(Student.class_id.in_(class_ids))
            .filter(TestSession.submitted_at.isnot(None))
            .count()
            if class_ids
            else 0
        )
        total_sessions = (
            TestSession.query.join(Student, Student.id == TestSession.student_id)
            .filter(Student.class_id.in_(class_ids))
            .count()
            if class_ids
            else 0
        )
        average_grade = (
            db.session.query(func.avg(EvaluationResult.grade))
            .join(Student, Student.id == EvaluationResult.student_id)
            .filter(Student.class_id.in_(class_ids))
            .scalar()
            if class_ids
            else 0
        )

        return [
            {
                "id": "students",
                "label": "Alunos total",
                "value": cls._build_professor_summary(scope, teacher)["students"],
                "active_this_week": (
                    TestSession.query.join(Student, Student.id == TestSession.student_id)
                    .filter(Student.class_id.in_(class_ids))
                    .filter(TestSession.updated_at >= datetime.utcnow() - timedelta(days=7))
                    .distinct(TestSession.student_id)
                    .count()
                    if class_ids
                    else 0
                ),
            },
            {
                "id": "evaluations",
                "label": "Avaliações",
                "value": evaluations_count,
                "created_this_month": (
                    Test.query.with_entities(Test.id)
                    .join(ClassTest, ClassTest.test_id == Test.id)
                    .filter(ClassTest.class_id.in_(class_ids))
                    .filter(Test.created_at >= datetime.utcnow() - timedelta(days=30))
                    .distinct()
                    .count()
                    if class_ids
                    else 0
                ),
            },
            {
                "id": "completed_evaluations",
                "label": "Concluídas",
                "value": completed_sessions,
                "pending_corrections": max(total_sessions - completed_sessions, 0),
            },
            {
                "id": "average_score",
                "label": "Média geral",
                "value": float(average_grade or 0),
                "trend_percentage": 0,
            },
        ]

    @classmethod
    def _build_professor_classes(cls, scope: Dict[str, Any], teacher: Optional[Teacher]) -> List[Dict[str, Any]]:
        class_ids = get_teacher_classes(scope["user"]["id"]) if teacher else []
        if not class_ids:
            return []

        classes = Class.query.filter(Class.id.in_(class_ids)).all()
        data = []
        for class_obj in classes:
            students = Student.query.filter(Student.class_id == class_obj.id).with_entities(Student.id).all()
            student_ids = [row.id for row in students]
            active_students = (
                TestSession.query.filter(TestSession.student_id.in_(student_ids))
                .filter(TestSession.updated_at >= datetime.utcnow() - timedelta(days=7))
                .distinct(TestSession.student_id)
                .count()
                if student_ids
                else 0
            )

            average_grade = (
                db.session.query(func.avg(EvaluationResult.grade))
                .filter(EvaluationResult.student_id.in_(student_ids))
                .scalar()
                if student_ids
                else 0
            )

            pending_evaluations = (
                TestSession.query.filter(TestSession.student_id.in_(student_ids))
                .filter(TestSession.submitted_at.is_(None))
                .count()
                if student_ids
                else 0
            )

            data.append(
                {
                    "class_id": class_obj.id,
                    "class_name": class_obj.name,
                    "students": len(student_ids),
                    "active_students": active_students,
                    "average_score": float(average_grade or 0),
                    "pending_evaluations": pending_evaluations,
                }
            )
        return data

    @classmethod
    def _build_professor_evaluations(cls, scope: Dict[str, Any], teacher: Optional[Teacher]) -> List[Dict[str, Any]]:
        class_ids = get_teacher_classes(scope["user"]["id"]) if teacher else []
        if not class_ids:
            return []

        # Usar subquery para evitar duplicatas quando há joins
        test_ids_query = (
            Test.query.with_entities(Test.id)
            .join(ClassTest, ClassTest.test_id == Test.id)
            .filter(ClassTest.class_id.in_(class_ids))
            .distinct()
            .limit(cls.MAX_LIST_SIZE)
        )
        
        # Obter IDs únicos
        test_ids = [row.id for row in test_ids_query.all()]
        
        # Buscar objetos Test completos
        evaluations = (
            Test.query.filter(Test.id.in_(test_ids))
            .order_by(Test.created_at.desc())
            .all()
            if test_ids
            else []
        )

        data = []
        for evaluation in evaluations:
            sessions = TestSession.query.filter(TestSession.test_id == evaluation.id).all()
            completed = len([s for s in sessions if s.submitted_at])
            average_score = (
                db.session.query(func.avg(EvaluationResult.grade))
                .filter(EvaluationResult.test_id == evaluation.id)
                .scalar()
            )

            class_test = ClassTest.query.filter(
                ClassTest.test_id == evaluation.id, ClassTest.class_id.in_(class_ids)
            ).first()

            data.append(
                {
                    "evaluation_id": evaluation.id,
                    "title": evaluation.title,
                    "class_name": class_test.class_.name if class_test and class_test.class_ else None,
                    "status": evaluation.status,
                    "total_questions": len(evaluation.questions or []),
                    "total_students": len(sessions),
                    "completed_students": completed,
                    "created_at": evaluation.created_at.isoformat() if evaluation.created_at else None,
                    "due_date": str(class_test.expiration) if class_test and class_test.expiration else None,
                    "average_score": float(average_score or 0),
                }
            )
        return data

    # ------------------------------------------------------------------ #
    # Análise do sistema (modal administração)
    # ------------------------------------------------------------------ #

    @classmethod
    def get_analise_sistema(cls) -> Dict[str, Any]:
        """
        Retorna dados agregados para o modal de análise do sistema: métricas gerais,
        dados técnicos, dados por escopo (geral, estado, município, escola) e
        séries para gráficos (evolução, distribuição, taxas).
        """
        import os
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import VARCHAR
        from sqlalchemy.exc import SQLAlchemyError

        scope_all = {"scope": "all", "city_id": None, "school_ids": None}

        try:
            # --- Métricas gerais (escopo global) ---
            metricas_gerais = cls._build_summary(scope_all)
            certificados = CertificateService.count_issued(None)
            metricas_gerais["certificates"] = certificados

            # --- Dados técnicos ---
            dados_tecnicos = {
                "ambiente": os.getenv("APP_ENV", "development"),
                "timestamp": datetime.utcnow().isoformat(),
                "timezone": "UTC",
            }

            # --- Dados de conexão (DB e backend) ---
            try:
                db_engine_name = (db.engine.url.drivername if db.engine and db.engine.url else None) or "unknown"
                db_host = (db.engine.url.host if db.engine and db.engine.url else None) or ""
                # Não expor porta/senha; apenas indicar se é remoto ou local
                db_origem = "remoto" if (db_host and db_host not in ("localhost", "127.0.0.1")) else "local"
            except Exception:
                db_engine_name = "unknown"
                db_origem = "unknown"
            conexao = {
                "db_engine": db_engine_name,
                "db_origem": db_origem,
                "db_status": "ok",
                "verificado_em": datetime.utcnow().isoformat(),
                "ambiente": dados_tecnicos["ambiente"],
                "timezone": dados_tecnicos["timezone"],
            }

            # --- Por escopo: ESTADO (agregação por City.state) ---
            estados_rows = (
                db.session.query(
                    City.state.label("estado"),
                    func.count(distinct(City.id)).label("municipios"),
                    func.count(distinct(School.id)).label("escolas"),
                    func.count(distinct(Student.id)).label("alunos"),
                )
                .outerjoin(School, School.city_id == City.id)
                .outerjoin(Student, cast(Student.school_id, VARCHAR) == cast(School.id, VARCHAR))
                .group_by(City.state)
                .order_by(func.count(distinct(Student.id)).desc())
                .all()
            )
            por_estado = [
                {
                    "estado": row.estado or "N/I",
                    "municipios": int(row.municipios or 0),
                    "escolas": int(row.escolas or 0),
                    "alunos": int(row.alunos or 0),
                }
                for row in estados_rows
            ]

            # Avaliações por estado (via Class -> School -> City)
            test_per_state = (
                db.session.query(
                    City.state,
                    func.count(distinct(Test.id)).label("avaliacoes"),
                )
                .join(School, School.city_id == City.id)
                .join(Class, cast(Class._school_id, VARCHAR) == cast(School.id, VARCHAR))
                .join(ClassTest, ClassTest.class_id == Class.id)
                .join(Test, Test.id == ClassTest.test_id)
                .group_by(City.state)
                .all()
            )
            avaliacoes_por_estado = {str(r.state or "N/I"): int(r.avaliacoes or 0) for r in test_per_state}
            for item in por_estado:
                item["avaliacoes"] = avaliacoes_por_estado.get(item["estado"], 0)

            # --- Por escopo: MUNICÍPIO (lista de cidades com totais) ---
            municipios_rows = (
                db.session.query(
                    City.id,
                    City.name,
                    City.state,
                    func.count(distinct(School.id)).label("escolas"),
                    func.count(distinct(Student.id)).label("alunos"),
                )
                .outerjoin(School, School.city_id == City.id)
                .outerjoin(Student, cast(Student.school_id, VARCHAR) == cast(School.id, VARCHAR))
                .group_by(City.id, City.name, City.state)
                .order_by(func.count(distinct(Student.id)).desc())
                .limit(50)
                .all()
            )
            por_municipio = [
                {
                    "municipio_id": str(row.id),
                    "nome": row.name,
                    "estado": row.state,
                    "escolas": int(row.escolas or 0),
                    "alunos": int(row.alunos or 0),
                }
                for row in municipios_rows
            ]

            # --- Por escopo: ESCOLA (lista de escolas com totais, top N) ---
            escolas_rows = (
                db.session.query(
                    School.id,
                    School.name,
                    City.name.label("municipio_nome"),
                    City.state,
                    func.count(distinct(Student.id)).label("alunos"),
                    func.count(distinct(Class.id)).label("turmas"),
                )
                .outerjoin(City, City.id == School.city_id)
                .outerjoin(Student, cast(Student.school_id, VARCHAR) == cast(School.id, VARCHAR))
                .outerjoin(Class, cast(Class._school_id, VARCHAR) == cast(School.id, VARCHAR))
                .group_by(School.id, School.name, City.name, City.state)
                .order_by(func.count(distinct(Student.id)).desc())
                .limit(50)
                .all()
            )
            por_escola = [
                {
                    "escola_id": str(row.id),
                    "nome": row.name,
                    "municipio": row.municipio_nome,
                    "estado": row.state,
                    "alunos": int(row.alunos or 0),
                    "turmas": int(row.turmas or 0),
                }
                for row in escolas_rows
            ]

            # --- Gráficos: evolução últimos 12 meses (do mais antigo ao mais recente) ---
            now = datetime.utcnow()
            primeiro_dia_atual = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            evolucao_meses = []
            for i in range(11, -1, -1):
                mes_start = primeiro_dia_atual
                for _ in range(i):
                    mes_start = (mes_start - timedelta(days=1)).replace(day=1)
                mes_end = (mes_start.replace(day=28) + timedelta(days=5)).replace(day=1) - timedelta(days=1)
                if mes_end > now:
                    mes_end = now
                mes_end = mes_end.replace(hour=23, minute=59, second=59, microsecond=999999)
                label = mes_start.strftime("%Y-%m")
                alunos_mes = Student.query.filter(
                    Student.created_at >= mes_start,
                    Student.created_at <= mes_end,
                ).count()
                avaliacoes_mes = Test.query.filter(
                    Test.created_at >= mes_start,
                    Test.created_at <= mes_end,
                ).count()
                sessoes_mes = TestSession.query.filter(
                    TestSession.started_at >= mes_start,
                    TestSession.started_at <= mes_end,
                ).count()
                evolucao_meses.append({
                    "mes": label,
                    "alunos": alunos_mes,
                    "avaliacoes": avaliacoes_mes,
                    "sessoes": sessoes_mes,
                })

            # --- Gráficos: distribuição (para gráfico de barras/pizza) ---
            distribuicao_estado = [
                {"estado": item["estado"], "alunos": item["alunos"], "escolas": item["escolas"]}
                for item in por_estado
            ]
            distribuicao_municipio = [
                {"municipio": item["nome"], "estado": item["estado"], "alunos": item["alunos"]}
                for item in por_municipio[:15]
            ]

            # --- Taxa de conclusão e sessões (não repetir certificados; já está em metricas) ---
            sessao_totais = db.session.query(
                func.count(TestSession.id).label("total"),
                func.sum(case((TestSession.submitted_at.isnot(None), 1), else_=0)).label("concluidas"),
            ).first()
            total_sessoes = int(sessao_totais.total or 0)
            concluidas_sessoes = int(sessao_totais.concluidas or 0)
            taxa_conclusao = round((concluidas_sessoes / total_sessoes * 100), 2) if total_sessoes else 0.0

            # --- Métricas únicas para administração (evitar repetir o que já está em metricas) ---
            media_notas_geral = db.session.query(func.avg(EvaluationResult.grade)).scalar()
            total_respostas_questoes = StudentAnswer.query.count()
            alunos_com_pelo_menos_uma = db.session.query(func.count(distinct(TestSession.student_id))).scalar() or 0
            total_alunos = metricas_gerais.get("students", 0)
            percentual_participacao = round((alunos_com_pelo_menos_uma / total_alunos * 100), 2) if total_alunos else 0.0
            escolas_ativas = db.session.query(func.count(distinct(Student.school_id))).join(
                TestSession, TestSession.student_id == Student.id
            ).scalar() or 0
            ultima_atividade = db.session.query(func.max(TestSession.submitted_at)).scalar()
            avaliacoes_por_tipo_rows = (
                db.session.query(Test.type, func.count(Test.id).label("total"))
                .group_by(Test.type)
                .all()
            )
            avaliacoes_por_tipo = [{"tipo": row.type or "N/I", "total": int(row.total or 0)} for row in avaliacoes_por_tipo_rows]
            disciplinas_com_questoes = db.session.query(func.count(distinct(Question.subject_id))).filter(
                Question.subject_id.isnot(None)
            ).scalar() or 0

            administracao = {
                "taxa_conclusao_geral": taxa_conclusao,
                "total_sessoes": total_sessoes,
                "sessoes_concluidas": concluidas_sessoes,
                "media_notas_geral": float(media_notas_geral or 0),
                "total_respostas_questoes": int(total_respostas_questoes or 0),
                "alunos_com_pelo_menos_uma_avaliacao": int(alunos_com_pelo_menos_uma or 0),
                "percentual_participacao": percentual_participacao,
                "escolas_ativas": int(escolas_ativas or 0),
                "ultima_atividade": ultima_atividade.isoformat() if ultima_atividade and hasattr(ultima_atividade, "isoformat") else str(ultima_atividade) if ultima_atividade else None,
                "avaliacoes_por_tipo": avaliacoes_por_tipo,
                "disciplinas_com_questoes": int(disciplinas_com_questoes or 0),
            }

            # --- Gráficos adicionais (dados únicos para gráficos) ---
            participacao_grafico = {
                "total_alunos": total_alunos,
                "alunos_com_pelo_menos_uma_avaliacao": int(alunos_com_pelo_menos_uma or 0),
                "percentual_participacao": percentual_participacao,
            }

            return {
                "metricas": metricas_gerais,
                "dados_tecnicos": dados_tecnicos,
                "conexao": conexao,
                "por_escopo": {
                    "geral": metricas_gerais,
                    "estado": por_estado,
                    "municipio": por_municipio,
                    "escola": por_escola,
                },
                "graficos": {
                    "evolucao_ultimos_12_meses": evolucao_meses,
                    "distribuicao_por_estado": distribuicao_estado,
                    "distribuicao_por_municipio": distribuicao_municipio,
                    "avaliacoes_por_tipo": avaliacoes_por_tipo,
                    "participacao": participacao_grafico,
                },
                "administracao": administracao,
            }
        except SQLAlchemyError as e:
            db.session.rollback()
            raise


