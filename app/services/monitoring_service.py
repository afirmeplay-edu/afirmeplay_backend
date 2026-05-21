from __future__ import annotations

import json
import re
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import String, and_, cast, func, not_, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.city import City
from app.models.classTest import ClassTest
from app.models.evaluationResult import EvaluationResult
from app.models.grades import Grade
from app.models.manager import Manager
from app.models.monitoring_action import MonitoringAction
from app.models.monitoring_action_history import MonitoringActionHistory
from app.models.question import Question
from app.models.school import School
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.studentClass import Class
from app.models.subject import Subject
from app.models.test import Test
from app.models.user import RoleEnum, User
from app.permissions.utils import get_user_scope
from app.services.evaluation_result_snapshot import municipal_evaluation_results_query


class MonitoringValidationError(Exception):
    """Erro de validação de negócio (HTTP 400)."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class MonitoringService:
    STAFF_ROLES = {"admin", "tecadm", "diretor", "coordenador", "professor"}
    STATUS_ALLOWED = {"pendente", "sendo_realizada", "nao_realizado"}

    @staticmethod
    def _normalize_source_type(raw: Optional[str]) -> str:
        value = (raw or "avaliacao").strip().lower()
        return "cartao_resposta" if value in {"cartao_resposta", "cartao", "gabarito"} else "avaliacao"

    @staticmethod
    def _str_id(value: Any) -> str:
        return str(value).strip() if value is not None else ""

    @staticmethod
    def _discipline_name_for_evaluation_result(
        result: EvaluationResult, discipline_filter: str = ""
    ) -> str:
        if isinstance(result.subject_results, dict) and result.subject_results:
            if discipline_filter:
                for data in result.subject_results.values():
                    if not isinstance(data, dict):
                        continue
                    name = str(data.get("subject_name") or data.get("name") or "").strip()
                    if name.lower() == discipline_filter:
                        return name
            else:
                first = next(iter(result.subject_results.values()))
                if isinstance(first, dict):
                    return str(first.get("subject_name") or first.get("name") or "").strip()
        test = result.test
        if test and getattr(test, "subject_rel", None):
            return str(test.subject_rel.name or "").strip()
        return ""

    @staticmethod
    def _school_list_sort_key(item: Dict[str, Any], sort_by: str) -> Any:
        value = item.get(sort_by)
        if sort_by == "escola_nome":
            return (value or "").lower() if isinstance(value, str) else ""
        if value is None:
            return 0
        return value

    @staticmethod
    def _parse_int(raw: Any, default: int) -> int:
        try:
            return int(raw)
        except Exception:
            return default

    @staticmethod
    def _parse_date(raw: Optional[str]) -> Optional[date]:
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None

    @staticmethod
    def _parse_periodo_bounds(periodo: Optional[str]) -> Optional[Tuple[datetime, datetime]]:
        s = (periodo or "").strip()
        if not s:
            return None
        match = re.match(r"^(\d{4})-(\d{2})$", s)
        if not match:
            return None
        year, month = int(match.group(1)), int(match.group(2))
        if month < 1 or month > 12:
            return None
        last_day = monthrange(year, month)[1]
        return datetime(year, month, 1), datetime(year, month, last_day)

    @staticmethod
    def _apply_class_test_application_period(query, bounds: Optional[Tuple[datetime, datetime]]):
        if bounds is None:
            return query
        dt_inicio, dt_fim = bounds
        d0 = dt_inicio.strftime("%Y-%m-%d")
        d1 = dt_fim.strftime("%Y-%m-%d")
        app_text = cast(ClassTest.application, String)
        iso_date_prefix = func.substring(app_text, 1, 10)
        matches_iso_date = iso_date_prefix.op("~")(r"^\d{4}-\d{2}-\d{2}$")
        cond_by_calendar_day = and_(
            matches_iso_date,
            iso_date_prefix >= d0,
            iso_date_prefix <= d1,
        )
        cond_lex_legacy = and_(
            not_(matches_iso_date),
            ClassTest.application >= d0,
            ClassTest.application <= d1 + "T23:59:59.999",
        )
        return query.filter(or_(cond_by_calendar_day, cond_lex_legacy))

    @staticmethod
    def _scope_filtered_school_ids(user: Dict[str, Any]) -> Optional[set]:
        scope = get_user_scope(user)
        if scope.get("scope") == "all":
            return None
        ids = set()
        if scope.get("school_id"):
            ids.add(str(scope["school_id"]))
        for school_id in scope.get("school_ids") or []:
            if school_id:
                ids.add(str(school_id))
        return ids

    @staticmethod
    def _apply_geo_scope_to_class_query(
        query,
        municipio: str,
        escola_id: str,
        scope_school_ids: Optional[set],
    ):
        if escola_id:
            return query.filter(Class.school_id == escola_id)
        if municipio:
            query = query.join(School, School.id == Class.school_id).filter(School.city_id == municipio)
        if scope_school_ids is not None:
            if not scope_school_ids:
                return query.filter(False)
            query = query.filter(Class.school_id.in_(list(scope_school_ids)))
        return query

    @staticmethod
    def _test_ids_for_options(user: Dict[str, Any], filters: Dict[str, Any]) -> Set[str]:
        """Avaliações disponíveis no recorte (estado/município/período), sem exigir escola."""
        municipio = (filters.get("municipio") or "").strip()
        periodo = (filters.get("periodo") or "").strip()
        scope_school_ids = MonitoringService._scope_filtered_school_ids(user)
        bounds = MonitoringService._parse_periodo_bounds(periodo)

        query = db.session.query(ClassTest.test_id).join(Class, Class.id == ClassTest.class_id)
        query = MonitoringService._apply_geo_scope_to_class_query(query, municipio, "", scope_school_ids)
        query = MonitoringService._apply_class_test_application_period(query, bounds)
        return {row[0] for row in query.distinct().all() if row[0]}

    @staticmethod
    def _test_ids_in_scope(user: Dict[str, Any], filters: Dict[str, Any]) -> Set[str]:
        escola_id = (filters.get("escola_id") or "").strip()
        municipio = (filters.get("municipio") or "").strip()
        periodo = (filters.get("periodo") or "").strip()
        scope_school_ids = MonitoringService._scope_filtered_school_ids(user)
        bounds = MonitoringService._parse_periodo_bounds(periodo)

        query = db.session.query(ClassTest.test_id).join(Class, Class.id == ClassTest.class_id)
        query = MonitoringService._apply_geo_scope_to_class_query(query, municipio, escola_id, scope_school_ids)
        query = MonitoringService._apply_class_test_application_period(query, bounds)
        return {row[0] for row in query.distinct().all() if row[0]}

    @staticmethod
    def _gabarito_ids_for_options(user: Dict[str, Any], filters: Dict[str, Any]) -> Set[str]:
        """Gabaritos no recorte geográfico, sem exigir escola."""
        return MonitoringService._gabarito_ids_in_scope(
            user,
            {**filters, "escola_id": ""},
        )

    @staticmethod
    def _gabarito_ids_in_scope(user: Dict[str, Any], filters: Dict[str, Any]) -> Set[str]:
        escola_id = (filters.get("escola_id") or "").strip()
        municipio = (filters.get("municipio") or "").strip()
        periodo = (filters.get("periodo") or "").strip()
        bounds = MonitoringService._parse_periodo_bounds(periodo)
        scope_school_ids = MonitoringService._scope_filtered_school_ids(user)

        query = AnswerSheetGabarito.query
        school_class_ids: Optional[List] = None
        if escola_id:
            school_class_ids = [
                row[0] for row in db.session.query(Class.id).filter(Class.school_id == escola_id).all()
            ]
            if not school_class_ids:
                return set()
            query = query.filter(
                or_(
                    AnswerSheetGabarito.class_id.in_(school_class_ids),
                    AnswerSheetGabarito.test_id.in_(list(MonitoringService._test_ids_in_scope(user, filters))),
                )
            )
        elif municipio:
            school_ids = [s.id for s in School.query.filter(School.city_id == municipio).all()]
            if not school_ids:
                return set()
            school_class_ids = [
                row[0] for row in db.session.query(Class.id).filter(Class.school_id.in_(school_ids)).all()
            ]
            if school_class_ids:
                query = query.filter(AnswerSheetGabarito.class_id.in_(school_class_ids))
            else:
                return set()
        if scope_school_ids is not None and not escola_id:
            if not scope_school_ids:
                return set()
            school_class_ids = [
                row[0]
                for row in db.session.query(Class.id).filter(Class.school_id.in_(list(scope_school_ids))).all()
            ]
            if school_class_ids:
                query = query.filter(AnswerSheetGabarito.class_id.in_(school_class_ids))
            else:
                return set()
        if bounds:
            query = query.filter(
                AnswerSheetGabarito.created_at >= bounds[0],
                AnswerSheetGabarito.created_at <= bounds[1],
            )
        return {row.id for row in query.order_by(AnswerSheetGabarito.created_at.desc()).limit(120).all()}

    @staticmethod
    def _school_ids_for_source(
        user: Dict[str, Any], filters: Dict[str, Any], source_type: str, source_id: str
    ) -> Set[str]:
        """Escolas onde a avaliação/cartão foi aplicado no município (ClassTest / turmas-alvo)."""
        if not source_id:
            return set()
        municipio = (filters.get("municipio") or "").strip()
        bounds = MonitoringService._parse_periodo_bounds((filters.get("periodo") or "").strip())
        scope_school_ids = MonitoringService._scope_filtered_school_ids(user)
        ids: Set[str] = set()

        def _apply_scope(school_id: Optional[str]) -> bool:
            if not school_id:
                return False
            sid = str(school_id)
            if scope_school_ids is not None and sid not in scope_school_ids:
                return False
            if municipio:
                school_row = School.query.get(sid)
                if not school_row or str(school_row.city_id) != str(municipio):
                    return False
            return True

        if source_type == "avaliacao":
            query = (
                db.session.query(School.id)
                .join(Class, School.id == cast(Class.school_id, String))
                .join(ClassTest, Class.id == ClassTest.class_id)
                .filter(ClassTest.test_id == source_id)
            )
            if municipio:
                query = query.filter(School.city_id == municipio)
            query = MonitoringService._apply_class_test_application_period(query, bounds)
            if scope_school_ids is not None:
                if not scope_school_ids:
                    return set()
                query = query.filter(School.id.in_(list(scope_school_ids)))
            ids.update(str(row[0]) for row in query.distinct().all() if row[0])

            result_query = (
                db.session.query(School.id)
                .select_from(EvaluationResult)
                .join(Student, Student.id == EvaluationResult.student_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .join(
                    School,
                    or_(
                        School.id == Student.school_id,
                        School.id == cast(Class.school_id, String),
                    ),
                )
                .filter(EvaluationResult.test_id == source_id)
            )
            if municipio:
                result_query = result_query.filter(School.city_id == municipio)
            if scope_school_ids is not None:
                result_query = result_query.filter(School.id.in_(list(scope_school_ids)))
            ids.update(str(row[0]) for row in result_query.distinct().all() if row[0])
        else:
            from app.report_analysis.answer_sheet_report_builder import (
                get_answer_sheet_target_classes_for_report,
            )

            gab = AnswerSheetGabarito.query.get(source_id)
            if not gab:
                return set()
            scope_kind = "city" if municipio else "overall"
            classes = get_answer_sheet_target_classes_for_report(gab, scope_kind, municipio or None)
            for class_obj in classes:
                if _apply_scope(getattr(class_obj, "school_id", None)):
                    ids.add(str(class_obj.school_id))
            if _apply_scope(gab.school_id):
                ids.add(str(gab.school_id))

            result_query = (
                db.session.query(School.id)
                .select_from(AnswerSheetResult)
                .join(Student, Student.id == AnswerSheetResult.student_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .join(
                    School,
                    or_(
                        School.id == Student.school_id,
                        School.id == cast(Class.school_id, String),
                    ),
                )
                .filter(AnswerSheetResult.gabarito_id == source_id)
            )
            if municipio:
                result_query = result_query.filter(School.city_id == municipio)
            if scope_school_ids is not None:
                result_query = result_query.filter(School.id.in_(list(scope_school_ids)))
            if bounds:
                result_query = result_query.filter(
                    AnswerSheetResult.created_at >= bounds[0],
                    AnswerSheetResult.created_at <= bounds[1],
                )
            ids.update(str(row[0]) for row in result_query.distinct().all() if row[0])

        return ids

    @staticmethod
    def _disciplines_for_source(source_type: str, source_id: str) -> List[Dict[str, str]]:
        if not source_id:
            return []

        options: Dict[str, str] = {}

        if source_type == "avaliacao":
            test = Test.query.get(source_id)
            if not test:
                return []
            if test.subject and test.subject_rel:
                options[str(test.subject)] = str(test.subject_rel.name or "Disciplina")

            subjects_info = getattr(test, "subjects_info", None)
            if isinstance(subjects_info, str):
                try:
                    subjects_info = json.loads(subjects_info)
                except Exception:
                    subjects_info = []
            if isinstance(subjects_info, list):
                for entry in subjects_info:
                    sid = ""
                    sname = ""
                    if isinstance(entry, dict):
                        sid = str(entry.get("id") or "").strip()
                        sname = str(entry.get("name") or entry.get("nome") or "").strip()
                    else:
                        sid = str(entry or "").strip()
                    if sid and not sname:
                        subject_row = Subject.query.get(sid)
                        sname = str(subject_row.name if subject_row else "").strip()
                    if sid:
                        options[sid] = sname or "Disciplina"
        else:
            results = AnswerSheetResult.query.filter_by(gabarito_id=source_id).limit(800).all()
            for result in results:
                payload = result.proficiency_by_subject
                if not isinstance(payload, dict):
                    continue
                for subject_data in payload.values():
                    if not isinstance(subject_data, dict):
                        continue
                    name = str(subject_data.get("subject_name") or subject_data.get("name") or "").strip()
                    if name:
                        options[name.lower()] = name

        return [{"id": sid, "name": name} for sid, name in sorted(options.items(), key=lambda item: item[1])]

    @staticmethod
    def _discover_source_ids(user: Dict[str, Any], filters: Dict[str, Any], source_type: str) -> List[str]:
        if source_type == "avaliacao":
            return list(MonitoringService._test_ids_in_scope(user, filters))[:80]
        return list(MonitoringService._gabarito_ids_in_scope(user, filters))[:80]

    @staticmethod
    def get_filter_options(user: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
        source_type = MonitoringService._normalize_source_type(filters.get("tipo_origem"))
        scope_school_ids = MonitoringService._scope_filtered_school_ids(user)
        city_id_scope = (get_user_scope(user) or {}).get("city_id")

        estado = (filters.get("estado") or "").strip()
        municipio = (filters.get("municipio") or "").strip()
        escola_id = (filters.get("escola_id") or "").strip()
        avaliacao_id = (filters.get("avaliacao_id") or "").strip()
        gabarito_id = (filters.get("gabarito_id") or "").strip()
        source_id = avaliacao_id if source_type == "avaliacao" else gabarito_id

        states_query = db.session.query(City.state).distinct()
        if city_id_scope:
            states_query = states_query.filter(City.id == city_id_scope)
        estados = [{"id": row[0], "name": row[0]} for row in states_query.order_by(City.state.asc()).all()]

        cities_query = City.query
        if city_id_scope:
            cities_query = cities_query.filter(City.id == city_id_scope)
        if estado:
            cities_query = cities_query.filter(City.state == estado)
        municipios = [{"id": c.id, "name": c.name, "state": c.state} for c in cities_query.order_by(City.name.asc()).all()]

        escolas: List[Dict[str, str]] = []
        if source_id:
            school_ids_for_source = MonitoringService._school_ids_for_source(
                user, filters, source_type, source_id
            )
            if school_ids_for_source:
                escolas = [
                    {"id": s.id, "name": s.name}
                    for s in School.query.filter(School.id.in_(list(school_ids_for_source)))
                    .order_by(School.name.asc())
                    .all()
                ]
            elif municipio:
                schools_query = School.query.filter(School.city_id == municipio)
                if scope_school_ids is not None:
                    if not scope_school_ids:
                        schools_query = schools_query.filter(False)
                    else:
                        schools_query = schools_query.filter(School.id.in_(list(scope_school_ids)))
                escolas = [
                    {"id": s.id, "name": s.name}
                    for s in schools_query.order_by(School.name.asc()).all()
                ]

        disciplinas = (
            MonitoringService._disciplines_for_source(source_type, source_id) if source_id else []
        )

        classes_query = Class.query
        if escola_id:
            classes_query = classes_query.filter(Class.school_id == escola_id)
        elif scope_school_ids:
            classes_query = classes_query.filter(Class.school_id.in_(list(scope_school_ids)))
        turmas = [{"id": str(t.id), "name": t.name} for t in classes_query.order_by(Class.name.asc()).all()]

        if escola_id:
            grade_ids = [
                row[0]
                for row in db.session.query(Class.grade_id)
                .filter(Class.school_id == escola_id, Class.grade_id.isnot(None))
                .distinct()
                .all()
                if row[0]
            ]
            series_query = Grade.query.filter(Grade.id.in_(grade_ids)) if grade_ids else Grade.query.filter(False)
        else:
            series_query = Grade.query
        series = [{"id": str(g.id), "name": g.name} for g in series_query.order_by(Grade.name.asc()).all()]

        avaliacoes: List[Dict[str, str]] = []
        gabaritos: List[Dict[str, str]] = []
        if estado and municipio:
            if source_type == "avaliacao":
                scoped_test_ids = MonitoringService._test_ids_for_options(user, filters)
                evaluations_query = Test.query.order_by(Test.created_at.desc())
                if scoped_test_ids:
                    evaluations_query = evaluations_query.filter(Test.id.in_(list(scoped_test_ids)))
                else:
                    evaluations_query = evaluations_query.filter(False)
                avaliacoes = [
                    {"id": t.id, "name": t.title or f"Avaliação {t.id[:8]}"}
                    for t in evaluations_query.limit(120).all()
                ]
            else:
                scoped_gabarito_ids = MonitoringService._gabarito_ids_for_options(user, filters)
                gabaritos_query = AnswerSheetGabarito.query.order_by(AnswerSheetGabarito.created_at.desc())
                if scoped_gabarito_ids:
                    gabaritos_query = gabaritos_query.filter(AnswerSheetGabarito.id.in_(list(scoped_gabarito_ids)))
                else:
                    gabaritos_query = gabaritos_query.filter(False)
                gabaritos = [
                    {
                        "id": g.id,
                        "name": g.title or f"Gabarito {g.id[:8]}",
                    }
                    for g in gabaritos_query.limit(120).all()
                ]

        coordinators_query = User.query.join(Manager, Manager.user_id == User.id).filter(
            User.role.in_([RoleEnum.COORDENADOR, RoleEnum.DIRETOR])
        )
        if escola_id:
            coordinators_query = coordinators_query.filter(Manager.school_id == escola_id)
        elif source_id:
            coord_school_ids = MonitoringService._school_ids_for_source(user, filters, source_type, source_id)
            if coord_school_ids:
                coordinators_query = coordinators_query.filter(Manager.school_id.in_(list(coord_school_ids)))
            else:
                coordinators_query = coordinators_query.filter(False)
        elif municipio:
            school_ids_in_city = [s.id for s in School.query.filter(School.city_id == municipio).all()]
            if school_ids_in_city:
                coordinators_query = coordinators_query.filter(Manager.school_id.in_(school_ids_in_city))
            else:
                coordinators_query = coordinators_query.filter(False)
        elif city_id_scope:
            school_ids_in_city = [s.id for s in School.query.filter(School.city_id == city_id_scope).all()]
            if school_ids_in_city:
                coordinators_query = coordinators_query.filter(Manager.school_id.in_(school_ids_in_city))
        coordenadores = [{"id": u.id, "name": u.name} for u in coordinators_query.order_by(User.name.asc()).all()]

        scope = get_user_scope(user) or {}
        user_role = (user.get("role") or "").strip().lower()
        default_escola = (scope.get("school_id") or "").strip()
        default_municipio = (scope.get("city_id") or city_id_scope or "").strip()
        default_estado = estado
        if default_escola and not default_municipio:
            school_row = School.query.get(default_escola)
            if school_row and school_row.city_id:
                default_municipio = str(school_row.city_id)
                city_row = City.query.get(school_row.city_id)
                if city_row:
                    default_estado = city_row.state

        lock_escola = user_role in {"diretor", "coordenador"} and bool(default_escola)
        lock_municipio = user_role in {"diretor", "coordenador"} and bool(default_municipio)

        return {
            "estados": estados,
            "municipios": municipios,
            "escolas": escolas,
            "avaliacoes": avaliacoes,
            "gabaritos": gabaritos,
            "disciplinas": disciplinas,
            "series": series,
            "turmas": turmas,
            "coordenadores": coordenadores,
            "defaults": {
                "tipo_origem": source_type,
                "estado": default_estado or "",
                "municipio": default_municipio or "",
                "escola_id": default_escola or "",
                "lock_escola": lock_escola,
                "lock_municipio": lock_municipio,
            },
        }

    @staticmethod
    def _critical_descriptors_for_test(test_id: str, student_ids: List[str]) -> Dict[str, List[str]]:
        if not test_id or not student_ids:
            return {}
        rows = (
            db.session.query(StudentAnswer.student_id, Question.skill)
            .join(Question, Question.id == StudentAnswer.question_id)
            .filter(StudentAnswer.test_id == test_id, StudentAnswer.student_id.in_(student_ids))
            .filter((StudentAnswer.is_correct == False) | (StudentAnswer.is_correct.is_(None)))
            .all()
        )
        grouped: Dict[str, List[str]] = defaultdict(list)
        for student_id, skill in rows:
            text = (skill or "").strip()
            if text and text not in grouped[student_id]:
                grouped[student_id].append(text)
        return {k: v[:4] for k, v in grouped.items()}

    @staticmethod
    def _action_key(source_type: str, source_id: str, student_id: str, discipline: str) -> str:
        return f"{source_type}:{source_id}:{student_id}:{(discipline or '').lower()}"

    @staticmethod
    def _fetch_actions_map(source_type: str, source_id: str) -> Dict[str, MonitoringAction]:
        actions = MonitoringAction.query.filter_by(source_type=source_type, source_id=source_id).all()
        result: Dict[str, MonitoringAction] = {}
        for action in actions:
            key = MonitoringService._action_key(
                source_type,
                source_id,
                action.student_id,
                action.discipline or "",
            )
            result[key] = action
        return result

    @staticmethod
    def _build_rows(user: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        source_type = MonitoringService._normalize_source_type(filters.get("tipo_origem"))
        explicit_id = (filters.get("avaliacao_id") or filters.get("gabarito_id") or filters.get("source_id") or "").strip()
        source_ids = [explicit_id] if explicit_id else MonitoringService._discover_source_ids(user, filters, source_type)
        if not source_ids:
            return []

        rows: List[Dict[str, Any]] = []
        for source_id in source_ids:
            rows.extend(MonitoringService._build_rows_for_source(user, filters, source_type, source_id))
        return MonitoringService._dedupe_rows(rows)

    @staticmethod
    def _dedupe_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Um aluno/disciplina/escola aparece uma vez mesmo com várias avaliações no recorte."""
        nivel_rank = {
            "Abaixo do Básico": 0,
            "Básico": 1,
            "Adequado": 2,
            "Avançado": 3,
        }
        merged: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = f"{row.get('student_id')}:{(row.get('discipline') or '').lower()}:{row.get('school_id')}"
            current = merged.get(key)
            if not current:
                merged[key] = row
                continue
            current_rank = nivel_rank.get((current.get("nivel") or "").strip(), 99)
            row_rank = nivel_rank.get((row.get("nivel") or "").strip(), 99)
            current_action = current.get("monitoring_action")
            row_action = row.get("monitoring_action")
            if row_rank < current_rank:
                merged[key] = row
            elif row_rank == current_rank and row_action and not current_action:
                merged[key] = row
        return list(merged.values())

    @staticmethod
    def _build_rows_for_source(
        user: Dict[str, Any],
        filters: Dict[str, Any],
        source_type: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        if not source_id:
            return []

        school_id_filter = (filters.get("escola_id") or "").strip()
        municipio = (filters.get("municipio") or "").strip()
        class_id_filter = (filters.get("turma_id") or filters.get("class_id") or "").strip()
        grade_id_filter = (filters.get("serie_id") or filters.get("grade_id") or "").strip()
        discipline_filter = (filters.get("disciplina") or "").strip().lower()
        scope_school_ids = MonitoringService._scope_filtered_school_ids(user)

        rows: List[Dict[str, Any]] = []

        if source_type == "avaliacao":
            query = (
                db.session.query(EvaluationResult, Student, School, Class, Grade)
                .join(Student, Student.id == EvaluationResult.student_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .outerjoin(
                    School,
                    or_(
                        School.id == Student.school_id,
                        School.id == cast(Class._school_id, String),
                        School.id == EvaluationResult.school_id_snapshot,
                    ),
                )
                .outerjoin(Grade, Grade.id == Student.grade_id)
                .options(joinedload(EvaluationResult.test).joinedload(Test.subject_rel))
                .filter(EvaluationResult.test_id == source_id)
            )
            if school_id_filter:
                query = query.filter(
                    or_(
                        Student.school_id == school_id_filter,
                        cast(Class._school_id, String) == school_id_filter,
                        EvaluationResult.school_id_snapshot == school_id_filter,
                    )
                )
            elif municipio:
                municipal_ids = [
                    row[0]
                    for row in municipal_evaluation_results_query(municipio, source_id)
                    .with_entities(EvaluationResult.id)
                    .all()
                ]
                if not municipal_ids:
                    return []
                query = query.filter(EvaluationResult.id.in_(municipal_ids))
            if class_id_filter:
                query = query.filter(Student.class_id == class_id_filter)
            if grade_id_filter:
                query = query.filter(Student.grade_id == grade_id_filter)
            if scope_school_ids is not None:
                query = query.filter(Student.school_id.in_(list(scope_school_ids)))

            query_rows = query.all()
            student_ids = [student.id for _, student, _, _, _ in query_rows]
            descriptors_map = MonitoringService._critical_descriptors_for_test(source_id, student_ids)
            actions_map = MonitoringService._fetch_actions_map(source_type, source_id)

            for result, student, school, class_, grade in query_rows:
                discipline_name = MonitoringService._discipline_name_for_evaluation_result(
                    result, discipline_filter
                )
                if discipline_filter and discipline_name.lower() != discipline_filter:
                    continue
                action_key = MonitoringService._action_key(source_type, source_id, student.id, discipline_name)
                action = actions_map.get(action_key)
                school_id = (
                    MonitoringService._str_id(school.id if school else None)
                    or MonitoringService._str_id(result.school_id_snapshot)
                    or MonitoringService._str_id(student.school_id)
                    or MonitoringService._str_id(getattr(class_, "school_id", None))
                )
                rows.append(
                    {
                        "source_type": source_type,
                        "source_id": source_id,
                        "student_id": student.id,
                        "student_name": student.name,
                        "registration": student.registration,
                        "school_id": school_id or None,
                        "school_name": (school.name if school and school.name else None) or "Escola",
                        "class_id": str(student.class_id) if student.class_id else None,
                        "class_name": class_.name if class_ else "—",
                        "grade_id": str(student.grade_id) if student.grade_id else None,
                        "grade_name": grade.name if grade else "—",
                        "discipline": discipline_name,
                        "nota": float(result.grade or 0),
                        "proficiencia": float(result.proficiency or 0),
                        "nivel": result.classification or "Abaixo do Básico",
                        "descritores_criticos": descriptors_map.get(student.id, []),
                        "monitoring_action": action,
                    }
                )
        else:
            query = (
                db.session.query(AnswerSheetResult, Student, School, Class, Grade)
                .join(Student, Student.id == AnswerSheetResult.student_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .outerjoin(
                    School,
                    or_(
                        School.id == Student.school_id,
                        School.id == cast(Class._school_id, String),
                    ),
                )
                .outerjoin(Grade, Grade.id == Student.grade_id)
                .filter(AnswerSheetResult.gabarito_id == source_id)
            )
            if school_id_filter:
                query = query.filter(
                    or_(
                        Student.school_id == school_id_filter,
                        cast(Class._school_id, String) == school_id_filter,
                    )
                )
            elif municipio:
                query = query.filter(School.city_id == municipio)
            if class_id_filter:
                query = query.filter(Student.class_id == class_id_filter)
            if grade_id_filter:
                query = query.filter(Student.grade_id == grade_id_filter)
            if scope_school_ids is not None:
                query = query.filter(Student.school_id.in_(list(scope_school_ids)))

            query_rows = query.all()
            actions_map = MonitoringService._fetch_actions_map(source_type, source_id)
            for result, student, school, class_, grade in query_rows:
                discipline_name = ""
                if isinstance(result.proficiency_by_subject, dict) and result.proficiency_by_subject:
                    first = next(iter(result.proficiency_by_subject.values()))
                    if isinstance(first, dict):
                        discipline_name = str(first.get("subject_name") or "").strip()
                if discipline_filter and discipline_name.lower() != discipline_filter:
                    continue
                action_key = MonitoringService._action_key(source_type, source_id, student.id, discipline_name)
                action = actions_map.get(action_key)
                critical_subjects: List[str] = []
                if isinstance(result.proficiency_by_subject, dict):
                    for subject_data in result.proficiency_by_subject.values():
                        if not isinstance(subject_data, dict):
                            continue
                        classification = str(subject_data.get("classification") or "")
                        if classification in {"Abaixo do Básico", "Básico"}:
                            subject_name = str(subject_data.get("subject_name") or "").strip()
                            if subject_name:
                                critical_subjects.append(subject_name)
                rows.append(
                    {
                        "source_type": source_type,
                        "source_id": source_id,
                        "student_id": student.id,
                        "student_name": student.name,
                        "registration": student.registration,
                        "school_id": (
                            MonitoringService._str_id(school.id if school else None)
                            or MonitoringService._str_id(student.school_id)
                            or MonitoringService._str_id(getattr(class_, "school_id", None))
                            or None
                        ),
                        "school_name": (school.name if school and school.name else None) or "Escola",
                        "class_id": str(student.class_id) if student.class_id else None,
                        "class_name": class_.name if class_ else "—",
                        "grade_id": str(student.grade_id) if student.grade_id else None,
                        "grade_name": grade.name if grade else "—",
                        "discipline": discipline_name,
                        "nota": float(result.grade or 0),
                        "proficiencia": float(result.proficiency or 0),
                        "nivel": result.classification or "Abaixo do Básico",
                        "descritores_criticos": critical_subjects[:4],
                        "monitoring_action": action,
                    }
                )
        return rows

    @staticmethod
    def _empty_school_aggregate(school_id: str, school_name: str) -> Dict[str, Any]:
        return {
            "escola_id": school_id,
            "escola_nome": school_name,
            "total_alunos": 0,
            "abaixo_basico": 0,
            "basico": 0,
            "adequado": 0,
            "avancado": 0,
            "acoes_realizadas": 0,
            "vistos_semed": 0,
        }

    @staticmethod
    def list_schools(user: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
        rows = MonitoringService._build_rows(user, filters)
        search = (filters.get("q") or "").strip().lower()
        grouped: Dict[str, Dict[str, Any]] = {}

        source_type = MonitoringService._normalize_source_type(filters.get("tipo_origem"))
        explicit_id = (filters.get("avaliacao_id") or filters.get("gabarito_id") or "").strip()
        if explicit_id:
            for school_id in MonitoringService._school_ids_for_source(
                user, filters, source_type, explicit_id
            ):
                school_key = MonitoringService._str_id(school_id) or "unknown"
                if school_key in grouped:
                    continue
                school_row = School.query.get(school_key)
                school_name = (school_row.name if school_row and school_row.name else None) or "Escola"
                if search and search not in school_name.lower():
                    continue
                grouped[school_key] = MonitoringService._empty_school_aggregate(school_key, school_name)

        for row in rows:
            if search and search not in (row.get("school_name") or "").lower():
                continue
            school_key = MonitoringService._str_id(row.get("school_id")) or "unknown"
            if school_key not in grouped:
                grouped[school_key] = {
                    "escola_id": school_key,
                    "escola_nome": row.get("school_name") or "Escola",
                    "total_alunos": 0,
                    "abaixo_basico": 0,
                    "basico": 0,
                    "adequado": 0,
                    "avancado": 0,
                    "acoes_realizadas": 0,
                    "vistos_semed": 0,
                }
            current = grouped[school_key]
            current["total_alunos"] += 1
            level = (row.get("nivel") or "").strip()
            if level == "Avançado":
                current["avancado"] += 1
            elif level == "Adequado":
                current["adequado"] += 1
            elif level == "Básico":
                current["basico"] += 1
            else:
                current["abaixo_basico"] += 1
            action: Optional[MonitoringAction] = row.get("monitoring_action")
            if action and action.pedagogical_action and action.status != "pendente":
                current["acoes_realizadas"] += 1
            if action and action.seen_by_semed:
                current["vistos_semed"] += 1

        items = sorted(
            grouped.values(),
            key=lambda item: MonitoringService._school_list_sort_key(item, "escola_nome"),
        )
        sort_by = (filters.get("sort_by") or "escola_nome").strip()
        sort_order = (filters.get("sort_order") or "asc").strip().lower()
        reverse = sort_order == "desc"
        sortable_fields = {
            "escola_nome",
            "total_alunos",
            "abaixo_basico",
            "basico",
            "adequado",
            "avancado",
            "acoes_realizadas",
            "vistos_semed",
        }
        if sort_by in sortable_fields:
            items = sorted(
                items,
                key=lambda item: MonitoringService._school_list_sort_key(item, sort_by),
                reverse=reverse,
            )
        page = MonitoringService._parse_int(filters.get("page"), 1)
        page_size = max(1, min(200, MonitoringService._parse_int(filters.get("page_size"), 20)))
        start = (page - 1) * page_size
        end = start + page_size
        paged = items[start:end]
        total = len(items)

        summary = {
            "total_escolas": total,
            "total_alunos": sum(i["total_alunos"] for i in items),
            "total_acoes": sum(i["acoes_realizadas"] for i in items),
            "total_vistos_semed": sum(i["vistos_semed"] for i in items),
        }
        return {
            "items": paged,
            "summary": summary,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if page_size else 1,
            },
        }

    @staticmethod
    def list_students(user: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
        rows = MonitoringService._build_rows(user, filters)
        search = (filters.get("q") or "").strip().lower()
        if search:
            rows = [
                row
                for row in rows
                if search in (row.get("student_name") or "").lower()
                or search in (row.get("class_name") or "").lower()
                or search in (row.get("grade_name") or "").lower()
            ]
        page = MonitoringService._parse_int(filters.get("page"), 1)
        page_size = max(1, min(300, MonitoringService._parse_int(filters.get("page_size"), 40)))
        start = (page - 1) * page_size
        end = start + page_size

        items = []
        for row in rows[start:end]:
            action: Optional[MonitoringAction] = row.get("monitoring_action")
            items.append(
                {
                    "aluno_id": row["student_id"],
                    "aluno_nome": row["student_name"],
                    "matricula": row["registration"],
                    "escola_id": row["school_id"],
                    "escola_nome": row["school_name"],
                    "serie": row["grade_name"],
                    "turma": row["class_name"],
                    "nota": row["nota"],
                    "proficiencia": row["proficiencia"],
                    "nivel": row["nivel"],
                    "disciplina": row["discipline"],
                    "descritores_criticos": row["descritores_criticos"],
                    "acao_id": action.id if action else None,
                    "acao_pedagogica": action.pedagogical_action if action else "",
                    "responsavel_id": action.responsible_id if action else None,
                    "responsavel_nome": action.responsible.name if (action and action.responsible) else "",
                    "coordenador_id": action.coordinator_id if action else None,
                    "coordenador_nome": action.coordinator.name if (action and action.coordinator) else "",
                    "prazo": action.deadline.isoformat() if (action and action.deadline) else None,
                    "status": action.status if action else "pendente",
                    "realizada_em": action.completed_at.isoformat() if (action and action.completed_at) else None,
                    "feita_pela_escola": bool(action.done_by_school) if action else False,
                    "vista_pela_semed": bool(action.seen_by_semed) if action else False,
                    "updated_at": action.updated_at.isoformat() if (action and action.updated_at) else None,
                    "updated_by": action.updated_by if action else None,
                    "source_type": row["source_type"],
                    "source_id": row["source_id"],
                }
            )

        total = len(rows)
        return {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if page_size else 1,
            },
        }

    @staticmethod
    def _load_or_create_action(action_id: str, payload: Dict[str, Any]) -> MonitoringAction:
        source_type = MonitoringService._normalize_source_type(payload.get("source_type"))
        source_id = (payload.get("source_id") or "").strip()
        student_id = (payload.get("student_id") or "").strip()
        discipline = (payload.get("disciplina") or payload.get("discipline") or "").strip()
        action = None
        if action_id and action_id not in {"new", "novo"}:
            action = MonitoringAction.query.get(action_id)
        if not action and source_id and student_id:
            action = MonitoringAction.query.filter_by(
                source_type=source_type,
                source_id=source_id,
                student_id=student_id,
                discipline=discipline,
            ).first()
        if action:
            return action
        action = MonitoringAction(
            source_type=source_type,
            source_id=source_id,
            student_id=student_id,
            school_id=payload.get("school_id"),
            class_id=payload.get("class_id"),
            grade_id=payload.get("grade_id"),
            discipline=discipline,
        )
        db.session.add(action)
        return action

    @staticmethod
    def _validate_action_payload(user: Dict[str, Any], payload: Dict[str, Any]) -> None:
        acao = (payload.get("acao_pedagogica") or "").strip()
        if not acao:
            raise MonitoringValidationError("Informe a ação pedagógica.")
        if not (payload.get("responsavel_id") or "").strip():
            raise MonitoringValidationError("Selecione o responsável pela ação.")
        if not payload.get("prazo"):
            raise MonitoringValidationError("Informe o prazo da ação.")
        status = (payload.get("status") or "pendente").strip().lower()
        if status not in MonitoringService.STATUS_ALLOWED:
            raise MonitoringValidationError("Status inválido.")

        prazo = MonitoringService._parse_date(payload.get("prazo"))
        realizada = MonitoringService._parse_date(payload.get("realizada_em"))
        if prazo and realizada and realizada < prazo and not (payload.get("observacao") or "").strip():
            raise MonitoringValidationError(
                "Data de realização anterior ao prazo exige observação no histórico."
            )

        role = (user.get("role") or "").strip().lower()
        if payload.get("vista_pela_semed") and role not in {"admin", "tecadm"}:
            raise MonitoringValidationError("Somente admin ou tecadm podem marcar vista pela SEMED.")

    @staticmethod
    def update_action(user: Dict[str, Any], action_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        MonitoringService._validate_action_payload(user, payload)
        action = MonitoringService._load_or_create_action(action_id, payload)
        track_fields = {
            "pedagogical_action": payload.get("acao_pedagogica"),
            "responsible_id": payload.get("responsavel_id"),
            "coordinator_id": payload.get("coordenador_id"),
            "deadline": MonitoringService._parse_date(payload.get("prazo")),
            "status": (payload.get("status") or action.status or "pendente").strip().lower(),
            "completed_at": MonitoringService._parse_date(payload.get("realizada_em")),
            "done_by_school": bool(payload.get("feita_pela_escola", False)),
            "seen_by_semed": bool(payload.get("vista_pela_semed", False)),
            "note": payload.get("observacao"),
        }
        if track_fields["status"] not in MonitoringService.STATUS_ALLOWED:
            track_fields["status"] = "pendente"
        if track_fields["done_by_school"] and track_fields["completed_at"] is None:
            track_fields["completed_at"] = date.today()

        old_values: Dict[str, Any] = {}
        new_values: Dict[str, Any] = {}
        changed_fields: List[str] = []
        for field, value in track_fields.items():
            old = getattr(action, field)
            if old != value:
                old_values[field] = old.isoformat() if isinstance(old, date) else old
                new_values[field] = value.isoformat() if isinstance(value, date) else value
                setattr(action, field, value)
                changed_fields.append(field)

        action.updated_by = user.get("id")
        if not action.created_by:
            action.created_by = user.get("id")
        db.session.flush()

        history_entry = None
        if changed_fields:
            history_entry = MonitoringActionHistory(
                monitoring_action_id=action.id,
                changed_by=user.get("id"),
                changed_fields=changed_fields,
                old_values=old_values,
                new_values=new_values,
                note=payload.get("observacao"),
            )
            db.session.add(history_entry)

        db.session.commit()
        return {
            "item": action.to_dict(),
            "history_entry_id": history_entry.id if history_entry else None,
        }

    @staticmethod
    def get_history(action_id: str) -> Dict[str, Any]:
        if not action_id or action_id in {"new", "novo"}:
            return {"items": []}
        action = MonitoringAction.query.get(action_id)
        if not action:
            raise MonitoringValidationError("Ação pedagógica não encontrada.")
        history = (
            MonitoringActionHistory.query.filter_by(monitoring_action_id=action_id)
            .order_by(MonitoringActionHistory.changed_at.desc())
            .all()
        )
        return {"items": [h.to_dict() for h in history]}

    @staticmethod
    def report_data(user: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
        periodicidade = (filters.get("periodicidade") or "mensal").strip().lower()
        if periodicidade not in {"semanal", "mensal"}:
            periodicidade = "mensal"

        school_data = MonitoringService.list_schools(user, {**filters, "page": 1, "page_size": 1000})
        students_data = MonitoringService.list_students(user, {**filters, "page": 1, "page_size": 5000})
        grouped_by_period: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"acoes": 0, "vistos_semed": 0, "feitas_escola": 0}
        )
        for student in students_data.get("items", []):
            date_value = student.get("realizada_em") or student.get("prazo") or ""
            period_key = "Sem período"
            if isinstance(date_value, str) and len(date_value) >= 10:
                try:
                    dt = datetime.strptime(date_value[:10], "%Y-%m-%d")
                    if periodicidade == "semanal":
                        year, week, _ = dt.isocalendar()
                        period_key = f"{year}-S{week:02d}"
                    else:
                        period_key = dt.strftime("%Y-%m")
                except Exception:
                    period_key = "Sem período"
            grouped_by_period[period_key]["acoes"] += 1
            if student.get("vista_pela_semed"):
                grouped_by_period[period_key]["vistos_semed"] += 1
            if student.get("feita_pela_escola"):
                grouped_by_period[period_key]["feitas_escola"] += 1

        metadata = {
            "periodicidade": periodicidade,
            "periodo_referencia": filters.get("periodo") or "",
            "gerado_em": datetime.now().isoformat(),
            "usuario_gerador": user.get("email") or user.get("id"),
        }
        filtros_aplicados = {
            "tipo_origem": MonitoringService._normalize_source_type(filters.get("tipo_origem")),
            "estado": filters.get("estado") or "",
            "municipio": filters.get("municipio") or "",
            "escola_id": filters.get("escola_id") or "",
            "avaliacao_id": filters.get("avaliacao_id") or "",
            "gabarito_id": filters.get("gabarito_id") or "",
            "disciplina": filters.get("disciplina") or "",
            "serie_id": filters.get("serie_id") or "",
            "turma_id": filters.get("turma_id") or "",
            "coordenador_id": filters.get("coordenador_id") or "",
        }
        return {
            "metadata": metadata,
            "filtros_aplicados": filtros_aplicados,
            "resumo_geral": school_data.get("summary", {}),
            "tabela_escolas": school_data.get("items", []),
            "tabela_alunos": students_data.get("items", []),
            "agrupado_periodo": dict(grouped_by_period),
            "assinaturas": {
                "coordenador_label": "Assinatura Coordenador(a)",
                "professor_label": "Assinatura Professor(a)",
                "semed_label": "Assinatura SEMED",
            },
        }
