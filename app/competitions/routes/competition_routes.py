# -*- coding: utf-8 -*-
"""
Rotas CRUD e ações de competições.
"""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.permissions import role_required, get_current_user_from_token
from app.competitions.models import Competition, CompetitionEnrollment, CompetitionResult
from app.competitions.services import CompetitionService, ValidationError, validate_reward_config
from app.services.competition_student_ranking_service import (
    CompetitionStudentRankingService,
)
from app.services.competition_ranking_service import CompetitionRankingService
from app.models.student import Student
from app.models.studentTestOlimpics import StudentTestOlimpics
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.testSession import TestSession
from app.competitions.constants import is_valid_level, LEVEL_OPTIONS, validate_scope_and_filter, get_competition_status_display
from app.competitions.scope_permissions import (
    get_allowed_competition_scopes,
    validate_scope_and_filter_for_user,
)
from app.competitions.schema_resolution import get_competition_schema
from app.utils.tenant_middleware import set_search_path, get_current_tenant_context, ensure_tenant_schema_for_user
from app.utils.timezone_utils import get_local_time
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
import logging

bp = Blueprint('competitions', __name__, url_prefix='/competitions')

# Mensagem padrão quando operação exige tenant (município)
MSG_TENANT_REQUIRED = (
    "É necessário informar o município (header X-City-ID ou usuário vinculado à cidade) para esta operação."
)

# Página de gerenciamento de competições: admin, coordenador, diretor, tecadm, professor
ROLES_EDIT = ("admin", "coordenador", "diretor", "tecadm", "professor")
# Rotas de listagem disponível / inscrição: roles acima + aluno
ROLES_STUDENT_OR_EDIT = ("admin", "coordenador", "diretor", "tecadm", "professor", "aluno")


def _filter_ranking_by_student_grade(ranking: list, user: dict) -> list:
    """
    Quando o usuário é aluno, filtra o ranking para mostrar apenas alunos da mesma série (grade).
    Reatribui as posições após o filtro.
    """
    if not user or (user.get("role") or "").strip().lower() != "aluno":
        return ranking
    student = Student.query.filter_by(user_id=user["id"]).first()
    if not student:
        return ranking
    viewer_grade_id = str(student.grade_id) if getattr(student, "grade_id", None) else None
    filtered = []
    for r in ranking:
        row_grade_id = r.get("grade_id")
        if row_grade_id is None and viewer_grade_id is None:
            filtered.append(r)
        elif row_grade_id is not None and viewer_grade_id is not None:
            if str(row_grade_id).strip().lower() == str(viewer_grade_id).strip().lower():
                filtered.append(r)
        # else: grade diferente, não incluir
    for idx, r in enumerate(filtered, start=1):
        r["position"] = idx
    return filtered


def _resolve_student_id():
    """
    Resolve student_id para rotas de aluno/competição.
    - Se usuário é aluno: usa o student_id vinculado ao user.
    - Se outro role: usa student_id da query ou do body (opcional).
    Retorna (student_id, error_response) onde error_response é (response, status) ou None.
    """
    user = get_current_user_from_token()
    if not user:
        return None, (jsonify({"error": "Usuário não autenticado"}), 401)
    role = (user.get("role") or "").strip().lower()
    if role == "aluno":
        student = Student.query.filter_by(user_id=user["id"]).first()
        if not student:
            return None, (jsonify({"error": "Estudante não vinculado ao usuário"}), 403)
        return student.id, None
    sid = request.args.get("student_id") or (request.get_json() or {}).get("student_id")
    if not sid:
        return None, (jsonify({"error": "student_id é obrigatório (query ou body)"}), 400)
    return sid, None


def _competition_to_dict_with_enrolled(c, student_id):
    """Como _competition_to_dict mas adiciona is_enrolled e can_start_test (fluxo de aplicação implementado)."""
    d = _competition_to_dict(c)
    is_enrolled = CompetitionService.is_student_enrolled(c.id, student_id) if student_id else False
    d["is_enrolled"] = is_enrolled
    # Frontend: true = pode chamar POST /competitions/:id/start para abrir a prova
    d["can_start_test"] = bool(
        c.test_id
        and is_enrolled
        and c.is_application_open
        and not c.is_finished
    )
    return d


def _safe_enrolled_count(c):
    """Retorna enrolled_count sem lançar (ex.: se student_test_olimpics não existir)."""
    try:
        return c.enrolled_count
    except Exception as e:
        logging.warning("enrolled_count falhou para competition %s: %s", c.id, e)
        return 0


def _safe_available_slots(c):
    """Retorna available_slots sem lançar."""
    try:
        return c.available_slots
    except Exception as e:
        logging.warning("available_slots falhou para competition %s: %s", c.id, e)
        return None


def _get_selected_question_ids(test_id, question_rules_fallback=None):
    """Retorna lista de question_id na ordem do teste. Se test_questions não existir, usa question_rules.selected_question_ids (primeira aleatorização só com tabela question)."""
    if not test_id:
        if question_rules_fallback and isinstance(question_rules_fallback, dict):
            return list(question_rules_fallback.get("selected_question_ids") or [])
        return []
    rows = []
    try:
        rows = (
            TestQuestion.query.filter_by(test_id=test_id)
            .order_by(TestQuestion.order)
            .with_entities(TestQuestion.question_id)
            .all()
        )
    except Exception as e:
        err_msg = str(e).lower()
        if "test_questions" not in err_msg or ("does not exist" not in err_msg and "undefinedtable" not in err_msg):
            logging.warning("selected_question_ids falhou para test_id %s: %s", test_id, e)
        if question_rules_fallback and isinstance(question_rules_fallback, dict):
            ids = question_rules_fallback.get("selected_question_ids")
            if ids:
                return list(ids)
        return []
    if rows:
        return [r[0] for r in rows]
    # Primeira query retornou vazio: prova pode estar no tenant ou em public (fallback de criação)
    ctx = get_current_tenant_context()
    tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
    if not tenant_schema or tenant_schema == "public":
        user = get_current_user_from_token()
        if user:
            ensure_tenant_schema_for_user(user["id"])
        ctx = get_current_tenant_context()
        tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
    prev = "public"
    try:
        prev = db.session.execute(text("SELECT current_schema()")).scalar() or "public"
        if tenant_schema and tenant_schema != "public":
            set_search_path(tenant_schema)
            rows = (
                TestQuestion.query.filter_by(test_id=test_id)
                .order_by(TestQuestion.order)
                .with_entities(TestQuestion.question_id)
                .all()
            )
            if rows:
                return [r[0] for r in rows]
        set_search_path("public")
        rows = (
            TestQuestion.query.filter_by(test_id=test_id)
            .order_by(TestQuestion.order)
            .with_entities(TestQuestion.question_id)
            .all()
        )
        result = [r[0] for r in rows]
        if not result and question_rules_fallback and isinstance(question_rules_fallback, dict):
            result = list(question_rules_fallback.get("selected_question_ids") or [])
        return result
    except Exception as e2:
        logging.debug("selected_question_ids (tenant/public) falhou para test_id %s: %s", test_id, e2)
        if question_rules_fallback and isinstance(question_rules_fallback, dict):
            return list(question_rules_fallback.get("selected_question_ids") or [])
        return []
    finally:
        set_search_path(prev)


def _get_subject_name_from_public(subject_id):
    """Busca nome da disciplina em public.subject (tabela qualificada; não altera search_path)."""
    if not subject_id:
        return None
    try:
        sid = str(subject_id)
        row = db.session.execute(
            text("SELECT name FROM public.subject WHERE id = :sid"),
            {"sid": sid},
        ).fetchone()
        return row[0] if row else None
    except Exception as e:
        logging.debug("_get_subject_name_from_public(%s): %s", subject_id, e)
        return None


def _get_subject_name_from_current_schema(subject_id):
    """Busca nome da disciplina no schema atual (ex.: tenant). Usar quando public.subject não tiver o id."""
    if not subject_id:
        return None
    try:
        current = db.session.execute(text("SELECT current_schema()")).scalar() or "public"
        if not current or current == "public":
            return None
        safe_schema = current.replace('"', '""')
        row = db.session.execute(
            text(f'SELECT name FROM "{safe_schema}".subject WHERE id = :sid'),
            {"sid": str(subject_id)},
        ).fetchone()
        return row[0] if row else None
    except Exception as e:
        logging.debug("_get_subject_name_from_current_schema(%s): %s", subject_id, e)
        return None


def _competition_to_dict(c, subject_name_override=None):
    """Serializa Competition para dict. subject_name_override evita lazy load de c.subject no schema tenant."""
    # Buscar subject_name: public.subject, depois relação c.subject, depois subject do schema atual (tenant)
    subject_name = subject_name_override
    if subject_name is None and getattr(c, 'subject_id', None):
        subject_name = _get_subject_name_from_public(c.subject_id)
    if subject_name is None:
        try:
            if c.subject:
                subject_name = c.subject.name
        except Exception:
            pass
    if subject_name is None and getattr(c, 'subject_id', None):
        subject_name = _get_subject_name_from_current_schema(c.subject_id)

    d = {
        'id': c.id,
        'name': c.name,
        'description': c.description,
        'test_id': c.test_id,
        'subject_id': c.subject_id,
        'level': c.level,
        'scope': c.scope,
        'scope_filter': c.scope_filter,
        'enrollment_start': c.enrollment_start.isoformat() if c.enrollment_start else None,
        'enrollment_end': c.enrollment_end.isoformat() if c.enrollment_end else None,
        'application': c.application.isoformat() if c.application else None,
        'expiration': c.expiration.isoformat() if c.expiration else None,
        'timezone': c.timezone,
        'question_mode': c.question_mode,
        'question_rules': c.question_rules,
        'reward_config': c.reward_config if c.reward_config is not None else {},
        'ranking_criteria': c.ranking_criteria,
        'ranking_tiebreaker': c.ranking_tiebreaker,
        'ranking_visibility': c.ranking_visibility,
        'max_participants': c.max_participants,
        'recurrence': c.recurrence,
        'status': ('encerrada' if getattr(c, 'is_finished', False) else c.status) or '',
        'status_display': get_competition_status_display('encerrada' if getattr(c, 'is_finished', False) else c.status),
        'created_by': c.created_by,
        'created_at': c.created_at.isoformat() if c.created_at else None,
        'updated_at': c.updated_at.isoformat() if c.updated_at else None,
        'is_enrollment_open': c.is_enrollment_open,
        'is_application_open': c.is_application_open,
        'is_finished': c.is_finished,
        'enrolled_count': _safe_enrolled_count(c),
        'available_slots': _safe_available_slots(c),
        'selected_question_ids': _get_selected_question_ids(c.test_id, getattr(c, 'question_rules', None)),
        'subject_name': subject_name,
    }
    return d


def _parse_dt(val):
    """
    Converte valor para datetime naive (sem timezone) para salvar no banco.
    Se receber datetime com timezone, converte para UTC e remove timezone.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        # Se já é datetime, garantir que seja naive
        if val.tzinfo is not None:
            # Converter para UTC primeiro, depois remover timezone
            val = val.astimezone(timezone.utc).replace(tzinfo=None)
        return val
    if isinstance(val, str):
        # Parse ISO string
        dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
        # Se tem timezone, converter para UTC e remover
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    raise ValueError("Data deve ser string ISO ou datetime")


@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    import traceback
    db.session.rollback()
    logging.error("Competitions DB error: %s\n%s", str(error), traceback.format_exc())
    return jsonify({"error": "Erro no banco de dados", "details": str(error)}), 500


@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error(f"Competitions integrity error: {str(error)}")
    return jsonify({"error": "Erro de integridade", "details": str(error)}), 400


@bp.errorhandler(ValidationError)
def handle_validation_error(error):
    db.session.rollback()
    return jsonify({"error": str(error)}), 400


@bp.errorhandler(ExpiredSignatureError)
def handle_jwt_expired(error):
    return jsonify({"error": "Token expirado", "details": "Faça login novamente."}), 401


@bp.errorhandler(InvalidTokenError)
def handle_jwt_invalid(error):
    return jsonify({"error": "Token inválido", "details": str(error)}), 401


@bp.errorhandler(Exception)
def handle_any_error(error):
    if isinstance(error, (ExpiredSignatureError, InvalidTokenError)):
        return jsonify({"error": "Token expirado" if isinstance(error, ExpiredSignatureError) else "Token inválido", "details": "Faça login novamente." if isinstance(error, ExpiredSignatureError) else str(error)}), 401
    import traceback
    db.session.rollback()
    logging.error("Competitions error: %s\n%s", str(error), traceback.format_exc())
    return jsonify({"error": "Erro interno", "details": str(error)}), 500


@bp.route('/level-options', methods=['GET'])
@jwt_required()
@role_required(*ROLES_EDIT)
def level_options():
    """Retorna os níveis permitidos para competição (1 e 2) com rótulos."""
    return jsonify({"levels": LEVEL_OPTIONS}), 200


@bp.route('', methods=['GET'])
@jwt_required()
@role_required(*ROLES_EDIT)
def list_competitions():
    """Lista competições com filtros opcionais (status, level, subject_id, scope). União de public + tenant."""
    status = request.args.get('status')
    level = None
    if request.args.get('level') is not None:
        try:
            level_val = int(request.args.get('level'))
            if is_valid_level(level_val):
                level = level_val
        except (TypeError, ValueError):
            pass
    subject_id = request.args.get('subject_id')
    scope = request.args.get('scope')
    items = CompetitionService.list_competitions_merged(
        status=status, level=level, subject_id=subject_id, scope=scope
    )
    return jsonify(items), 200


# ---------- Etapa 3: rotas para aluno (disponíveis, detalhes, inscrição, cancelar) ----------

@bp.route('/available', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def list_available_competitions():
    """Lista competições disponíveis para o aluno (nível, escopo, período, vagas)."""
    user = get_current_user_from_token()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401
    if not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": "Contexto do município não disponível. Acesse pelo subdomínio da cidade ou informe X-City-ID."}), 400
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    subject_id = request.args.get('subject_id')
    competitions = CompetitionService.get_available_competitions_for_student(student_id, subject_id=subject_id)
    # competitions já é lista de dicts; adicionar is_enrolled e can_start_test
    out = []
    for c in competitions:
        d = dict(c)
        d["is_enrolled"] = CompetitionService.is_student_enrolled(c["id"], student_id)
        d["can_start_test"] = bool(
            d.get("test_id") and d["is_enrolled"] and d.get("is_application_open") and not d.get("is_finished")
        )
        out.append(d)
    return jsonify(out), 200


@bp.route('/my', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def list_my_competitions():
    """
    Lista competições do aluno (histórico).

    Critérios:
    - competições em que o aluno está/esteve inscrito
    - competições em que o aluno possui StudentTestOlimpics (prova agendada/realizada)

    Query params opcionais:
    - status=finished  → apenas competições finalizadas
    - status=active    → competições ativas (não finalizadas)
    - status=upcoming  → competições futuras (ainda não iniciadas)
    - status=qualquer/coisa ou ausente → todas
    """
    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    status = request.args.get('status')
    competitions = CompetitionService.get_student_competitions(student_id, status=status)
    # get_student_competitions retorna lista de dicts; adicionar is_enrolled e can_start_test
    out = []
    for d in competitions:
        d = dict(d)
        d["is_enrolled"] = CompetitionService.is_student_enrolled(d["id"], student_id)
        d["can_start_test"] = bool(
            d.get("test_id") and d["is_enrolled"] and d.get("is_application_open") and not d.get("is_finished")
        )
        out.append(d)
    return jsonify(out), 200


@bp.route('/<competition_id>/details', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def get_competition_details_for_student(competition_id):
    """Detalhes da competição para o aluno (inclui is_enrolled, available_slots)."""
    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    c = CompetitionService.get_competition_or_404(competition_id)
    out = _competition_to_dict_with_enrolled(c, student_id)
    return jsonify(out), 200


@bp.route('/<competition_id>/enroll', methods=['POST'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def enroll_in_competition(competition_id):
    """Inscreve o aluno na competição."""
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    CompetitionService.get_competition_or_404(competition_id)
    try:
        enrollment = CompetitionService.enroll_student(competition_id, student_id)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({
        "message": "Inscrição realizada com sucesso",
        "enrollment": {
            "id": enrollment.id,
            "competition_id": enrollment.competition_id,
            "student_id": enrollment.student_id,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        },
    }), 201


@bp.route('/<competition_id>/unenroll', methods=['DELETE'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def unenroll_from_competition(competition_id):
    """Cancela inscrição do aluno na competição (antes do período de aplicação)."""
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    CompetitionService.get_competition_or_404(competition_id)
    try:
        CompetitionService.unenroll_student(competition_id, student_id)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Inscrição cancelada com sucesso"}), 200


@bp.route('/<competition_id>/enrolled-students', methods=['GET'])
@jwt_required()
@role_required(*ROLES_EDIT)
def list_enrolled_students(competition_id):
    """
    Lista alunos inscritos na competição (status=inscrito).
    Filtros: ?limit=... (default 500), ?offset=... (default 0).
    """
    competition = CompetitionService.get_competition_or_404(competition_id)
    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400
    try:
        limit = int(request.args.get('limit', 500))
        offset = int(request.args.get('offset', 0))
        limit = min(max(1, limit), 1000)
    except (TypeError, ValueError):
        limit = 500
        offset = 0

    enrollments = (
        CompetitionEnrollment.query.filter_by(
            competition_id=competition_id,
            status='inscrito',
        )
        .order_by(CompetitionEnrollment.enrolled_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    out = []
    for enr in enrollments:
        student = enr.student
        out.append({
            'id': student.id,
            'name': student.name,
            'class_id': student.class_id,
            'school_id': student.school_id,
            'enrolled_at': enr.enrolled_at.isoformat() if enr.enrolled_at else None,
            'enrollment_id': enr.id,
        })
    return jsonify(out), 200


# ---------- Etapa 4: aplicação e entrega (sessão de prova pela competição) ----------

def _session_to_dict(session):
    """Serializa TestSession para resposta da API. Evita acessar objeto após commit (Instance has been deleted)."""
    if not session:
        return None
    try:
        return {
            'id': session.id,
            'student_id': session.student_id,
            'test_id': session.test_id,
            'status': session.status,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'time_limit_minutes': session.time_limit_minutes,
            'total_questions': session.total_questions,
            'correct_answers': session.correct_answers,
            'score': session.score,
            'grade': session.grade,
        }
    except Exception as e:
        if 'deleted' in str(e).lower() or 'detached' in str(e).lower():
            return {'id': getattr(session, 'id', None), 'status': getattr(session, 'status', None)}
        raise


@bp.route('/<competition_id>/my-session', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def get_my_competition_session(competition_id):
    """
    Retorna a sessão de prova do aluno nesta competição (se existir).
    Usado para saber se o aluno já iniciou/finalizou a prova.
    Consulta TestSession no mesmo schema do teste (comp_schema); se não achar, tenta no schema do tenant (evita polling infinito).
    """
    try:
        student_id, err = _resolve_student_id()
        if err:
            return err[0], err[1]
        # Obter tenant_schema antes de qualquer troca de schema (middleware já definiu o contexto)
        ctx = get_current_tenant_context()
        tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
        c = CompetitionService.get_competition_or_404(competition_id)
        test_id = getattr(c, 'test_id', None)
        user = get_current_user_from_token()
        if not user or not ensure_tenant_schema_for_user(user["id"]):
            return jsonify({"error": MSG_TENANT_REQUIRED}), 400
        if not test_id:
            return jsonify({"test_session": None}), 200
        comp_schema = get_competition_schema(competition_id, tenant_schema=tenant_schema)
        session = None
        if comp_schema:
            set_search_path(comp_schema)
            session = (
                TestSession.query.filter_by(student_id=student_id, test_id=test_id)
                .order_by(TestSession.created_at.desc())
                .first()
            )
        if not session and tenant_schema and tenant_schema != comp_schema:
            set_search_path(tenant_schema)
            session = (
                TestSession.query.filter_by(student_id=student_id, test_id=test_id)
                .order_by(TestSession.created_at.desc())
                .first()
            )
        return jsonify({"test_session": _session_to_dict(session)}), 200
    except Exception as e:
        logging.exception("get_my_competition_session: %s", e)
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar sessão da competição", "details": str(e)}), 500


@bp.route('/<competition_id>/start', methods=['POST'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def start_competition_test(competition_id):
    """
    Inicia a prova da competição (cria test_session).
    Valida: aluno inscrito, período de aplicação, não possui sessão finalizada.
    Retorna a sessão criada ou a existente em andamento.
    """
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    c = CompetitionService.get_competition_or_404(competition_id)
    if not c.test_id:
        return jsonify({"error": "Competição sem prova vinculada"}), 400
    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400

    # Aluno deve estar inscrito
    enrollment = CompetitionEnrollment.query.filter_by(
        competition_id=c.id,
        student_id=student_id,
        status='inscrito',
    ).first()
    if not enrollment:
        return jsonify({"error": "Aluno não inscrito nesta competição"}), 403

    # Período de aplicação - usar property que já considera timezone correto
    if not c.is_application_open:
        if c.is_finished:
            return jsonify({"error": "Período de aplicação da competição encerrado"}), 410
        else:
            return jsonify({"error": "Fora do período de aplicação da competição"}), 410

    # TestSession deve ficar no mesmo schema do teste (competition_schema)
    ctx = get_current_tenant_context()
    tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
    comp_schema = get_competition_schema(competition_id, tenant_schema=tenant_schema)
    if comp_schema:
        set_search_path(comp_schema)

    # Sessão existente: em_andamento → retornar (mesmo formato de sucesso para o front abrir a prova); finalizada/expirada → não permitir nova
    existing = (
        TestSession.query.filter_by(student_id=student_id, test_id=c.test_id)
        .order_by(TestSession.created_at.desc())
        .first()
    )
    if existing:
        if existing.status in ('finalizada', 'expirada', 'corrigida', 'revisada'):
            return jsonify({
                "error": "Prova já foi realizada",
                "test_session": _session_to_dict(existing),
            }), 400
        # em_andamento: serializar antes de qualquer outro acesso (evita Instance has been deleted)
        existing_dict = _session_to_dict(existing)
        payload = {
            "message": "Sessão já iniciada",
            "session_id": (existing_dict or {}).get("id"),
            "test_session": existing_dict,
            "already_started": True,
        }
        return jsonify(payload), 200

    # Criar nova sessão
    session = TestSession(
        student_id=student_id,
        test_id=c.test_id,
        time_limit_minutes=None,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
    )
    session.start_session()
    db.session.add(session)
    db.session.flush()
    # Montar payload antes do commit para evitar "Instance has been deleted" após teardown/expire
    test_session_dict = _session_to_dict(session)
    db.session.commit()
    payload = {
        "message": "Sessão iniciada com sucesso",
        "session_id": (test_session_dict or {}).get("id"),
        "test_session": test_session_dict,
        "already_started": False,
    }
    return jsonify(payload), 201


# ---------- Etapa 5: ranking e recompensas ----------

def _serialize_ranking_item(item):
    """Serializa item do ranking para JSON (datas em isoformat, numéricos como float)."""
    out = dict(item)
    if out.get('submitted_at') and hasattr(out['submitted_at'], 'isoformat'):
        out['submitted_at'] = out['submitted_at'].isoformat()
    for key in ('grade', 'proficiency', 'score_percentage', 'value'):
        if key in out and out[key] is not None and not isinstance(out[key], (int, float)):
            try:
                out[key] = float(out[key])
            except (TypeError, ValueError):
                pass
    return out


@bp.route('/<competition_id>/ranking', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def get_competition_ranking(competition_id):
    """
    Retorna o ranking da competição.
    Durante a competição: ranking em tempo real (não lê competition_results).
    Após encerrar: lê de competition_results (snapshot).
    ranking_visibility = 'realtime' → retorna sempre (se houver sessões finalizadas).
    ranking_visibility = 'final' → só retorna se competition.status = 'encerrada'.
    """
    c = CompetitionService.get_competition_or_404(competition_id)
    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400
    visibility = (c.ranking_visibility or 'final').strip().lower()
    effective_encerrada = (c.status or '').strip().lower() == 'encerrada' or getattr(c, 'is_finished', False)
    if visibility == 'final' and not effective_encerrada:
        return jsonify({"error": "Ranking só é exibido após o encerramento da competição"}), 403
    try:
        limit = request.args.get('limit', type=int) or 100
        limit = min(max(1, limit), 500)
    except (TypeError, ValueError):
        limit = 100
    ranking = CompetitionRankingService.get_ranking(competition_id, limit=limit, enriquecer=True)
    if user and ensure_tenant_schema_for_user(user["id"]):
        ranking = _filter_ranking_by_student_grade(ranking, user or {})
    return jsonify({"ranking": [_serialize_ranking_item(r) for r in ranking[:limit]]}), 200


@bp.route('/<competition_id>/ranking-by-scope', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def get_competition_ranking_by_scope(competition_id):
    """
    Retorna o ranking da competição filtrado por escopo:
    - scope=global        → ranking completo (igual ao /ranking)
    - scope=state         → ranking por estado (query param: state)
    - scope=municipality  → ranking por município (query param: city_id)
    - scope=school        → ranking por escola (query param: school_id)

    Usa o mesmo cálculo de ranking, apenas filtrando os itens pelo escopo solicitado.
    """
    CompetitionService.get_competition_or_404(competition_id)
    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400
    scope = (request.args.get('scope') or 'global').strip().lower()
    try:
        limit = request.args.get('limit', type=int) or 100
        limit = min(max(1, limit), 500)
    except (TypeError, ValueError):
        limit = 100

    base_ranking = CompetitionRankingService.get_ranking(competition_id, limit=10000, enriquecer=True)

    def _filter_item(item):
        if scope in ('', 'global'):
            return True
        if scope == 'state':
            state = (request.args.get('state') or '').strip().lower()
            if not state:
                return False
            return (item.get('state_name') or '').strip().lower() == state
        if scope == 'municipality':
            city_id = request.args.get('city_id')
            if city_id:
                return str(item.get('city_id') or '').lower() == str(city_id).lower()
            # Alternativamente, permitir filtro por nome de município
            city_name = (request.args.get('city_name') or '').strip().lower()
            if city_name:
                return (item.get('city_name') or '').strip().lower() == city_name
            return False
        if scope == 'school':
            school_id = request.args.get('school_id')
            if not school_id:
                return False
            return str(item.get('school_id') or '').lower() == str(school_id).lower()
        return False

    filtered = [r for r in base_ranking if _filter_item(r)]
    # Reatribuir posições dentro do escopo
    for idx, r in enumerate(filtered, start=1):
        r['position'] = idx
    # Aluno vê apenas ranking da mesma série (grade)
    user = get_current_user_from_token()
    if user and ensure_tenant_schema_for_user(user["id"]):
        filtered = _filter_ranking_by_student_grade(filtered, user or {})

    return jsonify({"ranking": [_serialize_ranking_item(r) for r in filtered[:limit]]}), 200


@bp.route('/<competition_id>/analytics', methods=['GET'])
@jwt_required()
@role_required(*ROLES_EDIT)
def get_competition_analytics(competition_id):
    """
    Retorna analytics completos da competição (apenas admin/coordenador).
    Inclui: taxa de inscrição, taxa de participação, médias, distribuição de notas, top 10, comparação com anteriores.
    """
    CompetitionService.get_competition_or_404(competition_id)
    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400
    try:
        from app.services.competition_analytics_service import CompetitionAnalyticsService
        analytics = CompetitionAnalyticsService.get_analytics(competition_id)
        return jsonify(analytics), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.exception("Erro ao calcular analytics da competição %s: %s", competition_id, str(e))
        return jsonify({"error": "Erro ao calcular analytics", "details": str(e)}), 500


@bp.route('/<competition_id>/my-ranking', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def get_my_competition_ranking(competition_id):
    """
    Retorna a posição do aluno logado no ranking.
    Retorna: position, total_participants, value, grade, coins_earned (se premiado), etc.
    """
    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    c = CompetitionService.get_competition_or_404(competition_id)
    visibility = (c.ranking_visibility or 'final').strip().lower()
    effective_encerrada = (c.status or '').strip().lower() == 'encerrada' or getattr(c, 'is_finished', False)
    if visibility == 'final' and not effective_encerrada:
        return jsonify({"error": "Ranking só é exibido após o encerramento da competição"}), 403
    result = CompetitionRankingService.get_my_ranking(competition_id, student_id)
    if result is None:
        return jsonify({
            "message": "Você ainda não possui resultado nesta competição",
            "position": None,
            "total_participants": 0,
        }), 200
    return jsonify(result), 200


@bp.route('/students/me/competition-ranking-classification', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def get_my_competition_rank_classification():
    """
    Retorna a classificação global do aluno baseada apenas em competições.

    Exemplo de resposta:
    {
      "band": "Destaque",
      "first_places": 3,
      "second_places": 2,
      "third_places": 2,
      "total_podiums": 7,
    }
    """
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    data = CompetitionStudentRankingService.get_student_competition_rank_classification(
        student_id
    )
    if not data:
        return jsonify({
            "band": None,
            "first_places": 0,
            "second_places": 0,
            "third_places": 0,
            "total_podiums": 0,
        }), 200
    return jsonify(data), 200


@bp.route('/<competition_id>/finalize', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def finalize_competition(competition_id):
    """
    Finaliza a competição manualmente: grava ranking em competition_results,
    paga moedas de ranking e define status='encerrada'.
    Só permite se expiration já passou e status é aberta/em_andamento.
    """
    c = CompetitionService.get_competition_or_404(competition_id)
    if c.status not in ('aberta', 'em_andamento'):
        return jsonify({
            "error": "Competição já encerrada ou não está aberta.",
            "status": c.status,
        }), 400
    # Usar property is_finished que já considera o timezone correto
    if not c.is_finished:
        return jsonify({
            "error": "Competição ainda não expirou. Aguarde a data de expiração.",
            "expiration": c.expiration.isoformat() if c.expiration else None,
        }), 400
    if CompetitionResult.query.filter_by(competition_id=c.id).count() > 0:
        return jsonify({
            "message": "Competição já foi finalizada (ranking já gerado).",
            "status": c.status,
        }), 200
    try:
        CompetitionRankingService.finalize_competition_and_save_results(c.id)
        c.status = 'encerrada'
        db.session.commit()
        return jsonify({
            "message": "Competição finalizada com sucesso. Ranking gerado e recompensas pagas.",
            "status": "encerrada",
        }), 200
    except Exception as e:
        logging.exception("Erro ao finalizar competição %s: %s", competition_id, str(e))
        db.session.rollback()
        return jsonify({"error": "Erro ao finalizar competição", "details": str(e)}), 500


@bp.route('/<competition_id>/stop', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def stop_competition(competition_id):
    """
    Para (encerra) a competição em andamento imediatamente. Apenas admin.
    Gera ranking e paga recompensas, então define status='encerrada'.
    Diferente de /finalize: não exige que a data de expiração já tenha passado.
    """
    c = CompetitionService.get_competition_or_404(competition_id)
    if c.status not in ('aberta', 'em_andamento'):
        return jsonify({
            "error": "Só é possível parar competição em aberta ou em andamento.",
            "status": c.status,
        }), 400
    user = get_current_user_from_token()
    if (user.get('role') or '').strip().lower() != 'admin':
        return jsonify({"error": "Apenas o administrador pode parar competições em andamento"}), 403
    cid = c.id
    if CompetitionResult.query.filter_by(competition_id=cid).count() > 0:
        c.status = 'encerrada'
        db.session.commit()
        return jsonify({
            "message": "Competição encerrada. Ranking já existia.",
            "status": "encerrada",
        }), 200
    try:
        CompetitionRankingService.finalize_competition_and_save_results(cid)
        # Re-carregar a competição no schema correto (finalize faz commit e pode trocar schema)
        ctx = get_current_tenant_context()
        tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
        schema = get_competition_schema(cid, tenant_schema=tenant_schema)
        if schema:
            set_search_path(schema)
            comp = Competition.query.get(cid)
            if comp:
                comp.status = 'encerrada'
                db.session.commit()
        return jsonify({
            "message": "Competição parada com sucesso. Ranking gerado e recompensas pagas.",
            "status": "encerrada",
        }), 200
    except Exception as e:
        logging.exception("Erro ao parar competição %s: %s", competition_id, str(e))
        db.session.rollback()
        return jsonify({"error": "Erro ao parar competição", "details": str(e)}), 500


@bp.route('/<competition_id>/randomize-questions', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def randomize_competition_questions(competition_id):
    """
    Re-sorteia as questões da prova de uma competição aberta ou em andamento (question_mode=auto_random).
    Acionável por botão na tela de competição.
    """
    try:
        result = CompetitionService.randomize_competition_questions(competition_id)
        return jsonify({
            "message": "Questões aleatorizadas com sucesso.",
            "test_id": result["test_id"],
            "num_questions": result["num_questions"],
        }), 200
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400


@bp.route('/<competition_id>/eligible-students', methods=['GET'])
@jwt_required()
@role_required(*ROLES_EDIT)
def list_eligible_students(competition_id):
    """
    Lista alunos que PODEM se inscrever agora na competição especificada.

    Regras de elegibilidade:
    - Competição status='aberta'
    - Agora (horário local do servidor) entre enrollment_start e enrollment_end
    - test_id não nulo
    - Nível e escopo compatíveis (mesma lógica de get_available_competitions_for_student)
    - Ainda não inscritos nem com StudentTestOlimpics criado para esse test_id

    Filtros opcionais:
    - ?class_id=...  → restringe a uma turma
    - ?school_id=... → restringe a uma escola (se class_id não for informado)
    - ?limit=...     → máximo de registros (default: 100)
    - ?offset=...    → deslocamento para paginação (default: 0)
    - ?include_meta=1 → inclui meta com diagnóstico (students_checked, excluded_*)
    """
    try:
        competition = CompetitionService.get_competition_or_404(competition_id)
    except Exception as e:
        logging.exception("eligible-students: get_competition_or_404 failed for %s", competition_id)
        return jsonify({"error": "Erro ao carregar competição", "details": str(e)}), 500

    include_meta = request.args.get('include_meta', '').lower() in ('1', 'true', 'yes')

    # Capturar valores da competição antes de trocar o schema (evita "Instance has been deleted")
    comp_id = competition.id
    comp_test_id = competition.test_id
    comp_subject_id = competition.subject_id

    # Verificações globais da competição
    if competition.status != 'aberta' or not comp_test_id:
        if include_meta:
            return jsonify({
                "eligible": [],
                "meta": {
                    "reason": "competition_not_open_or_no_test",
                    "status": competition.status,
                    "has_test_id": bool(comp_test_id),
                },
            }), 200
        return jsonify([]), 200
    
    # Usar property is_enrollment_open que já considera timezone correto
    if not competition.is_enrollment_open:
        # Determinar se está antes ou depois do período
        from app.utils.timezone_utils import get_local_time
        from app.competitions.models.competition import _normalize_datetime_for_comparison
        now = get_local_time()
        now_naive = _normalize_datetime_for_comparison(now)
        start_normalized = _normalize_datetime_for_comparison(competition.enrollment_start, competition.timezone)
        
        if start_normalized and now_naive < start_normalized:
            reason = "before_enrollment_period"
            detail = {"enrollment_start": competition.enrollment_start.isoformat() if competition.enrollment_start else None}
        else:
            reason = "after_enrollment_period"
            detail = {"enrollment_end": competition.enrollment_end.isoformat() if competition.enrollment_end else None}
        
        if include_meta:
            return jsonify({
                "eligible": [],
                "meta": {"reason": reason, **detail},
            }), 200
        return jsonify([]), 200

    # student, class, school etc. existem apenas no schema do tenant
    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({
            "error": MSG_TENANT_REQUIRED,
        }), 400

    class_id = request.args.get('class_id')
    school_id = request.args.get('school_id')
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        limit = 100
        offset = 0

    query = Student.query
    if class_id:
        query = query.filter(Student.class_id == class_id)
    elif school_id:
        query = query.filter(Student.school_id == school_id)

    students = query.order_by(Student.name).offset(offset).limit(limit).all()
    eligible = []
    excluded_enrolled = 0
    excluded_olympics = 0
    excluded_level_scope = 0

    for student in students:
        if CompetitionService.is_student_enrolled(comp_id, student.id):
            excluded_enrolled += 1
            continue
        if StudentTestOlimpics.query.filter_by(
            student_id=student.id,
            test_id=comp_test_id,
        ).first():
            excluded_olympics += 1
            continue
        available = CompetitionService.get_available_competitions_for_student(
            student.id,
            subject_id=comp_subject_id,
        )
        if not any(c.get('id') == comp_id for c in available):
            excluded_level_scope += 1
            continue
        eligible.append({
            "id": student.id,
            "name": student.name,
            "class_id": student.class_id,
            "school_id": student.school_id,
        })

    if include_meta:
        return jsonify({
            "eligible": eligible,
            "meta": {
                "students_checked": len(students),
                "excluded_enrolled": excluded_enrolled,
                "excluded_has_olympics": excluded_olympics,
                "excluded_level_or_scope": excluded_level_scope,
            },
        }), 200
    return jsonify(eligible), 200


@bp.route('/<competition_id>', methods=['GET'])
@jwt_required()
@role_required(*ROLES_EDIT)
def get_competition(competition_id):
    """Detalhe de uma competição. subject_name vem de public.subject (multi-tenant)."""
    db.session.rollback()
    ctx = get_current_tenant_context()
    tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
    schema = get_competition_schema(competition_id, tenant_schema=tenant_schema)
    if not schema:
        from flask import abort
        abort(404)
    set_search_path(schema)
    db.session.expire_all()
    c = Competition.query.filter_by(id=competition_id).first_or_404()
    if c.test_id and schema == 'public':
        user = get_current_user_from_token()
        if user:
            ensure_tenant_schema_for_user(user["id"])
    return jsonify(_competition_to_dict(c)), 200


@bp.route('/allowed-scopes', methods=['GET'])
@jwt_required()
@role_required(*ROLES_EDIT)
def get_allowed_scopes():
    """Retorna os escopos que o usuário pode usar ao criar/editar competição (conforme seu perfil)."""
    user = get_current_user_from_token()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401
    allowed = get_allowed_competition_scopes(user)
    return jsonify({"allowed_scopes": allowed}), 200


@bp.route('/eligible-classes', methods=['GET'])
@jwt_required()
@role_required(*ROLES_EDIT)
def get_eligible_classes():
    """
    Lista turmas elegíveis para escopo 'turma', filtradas pelo nível da competição (1 ou 2).
    Query param: level (obrigatório) = 1 ou 2. Só retorna turmas cuja série (grade) pertence ao nível.
    """
    from app.competitions.constants import STAGE_NAMES_BY_LEVEL, is_valid_level
    from app.models.studentClass import Class
    from app.models.school import School
    from app.models.grades import Grade
    from app.models.educationStage import EducationStage

    level_param = request.args.get('level')
    if level_param is None:
        return jsonify({"error": "Query param 'level' é obrigatório (1 ou 2)"}), 400
    try:
        level = int(level_param)
    except (TypeError, ValueError):
        return jsonify({"error": "level deve ser 1 ou 2"}), 400
    if not is_valid_level(level):
        return jsonify({"error": "level deve ser 1 ou 2"}), 400

    stage_names = STAGE_NAMES_BY_LEVEL.get(level)
    if not stage_names:
        return jsonify([]), 200

    user = get_current_user_from_token()
    if not user or not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400

    classes = (
        Class.query.join(Grade, Class.grade_id == Grade.id)
        .join(EducationStage, Grade.education_stage_id == EducationStage.id)
        .filter(EducationStage.name.in_(stage_names))
        .outerjoin(School, Class.school_id == School.id)
        .all()
    )
    results = []
    for c in classes:
        results.append({
            'id': str(c.id),
            'name': c.name or '',
            'school_id': str(c.school_id) if c.school_id else None,
            'school_name': c.school.name if c.school else None,
            'grade_id': str(c.grade_id) if c.grade_id else None,
            'grade_name': c.grade.name if c.grade else None,
        })
    return jsonify(results), 200


@bp.route('', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def create_competition():
    """Cria competição."""
    db.session.rollback()  # Limpar transação abortada (ex.: conexão reutilizada do pool)
    user = get_current_user_from_token()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"error": "Body JSON obrigatório"}), 400
    required = ('name', 'subject_id', 'level', 'enrollment_start', 'enrollment_end', 'application', 'expiration', 'reward_config')
    for field in required:
        if field not in data:
            return jsonify({"error": f"Campo obrigatório ausente: {field}"}), 400
    scope = (data.get('scope') or 'individual').strip().lower()
    question_mode = (data.get('question_mode') or 'auto_random').strip().lower()
    if scope != 'individual' and (not ensure_tenant_schema_for_user(user["id"])):
        return jsonify({"error": MSG_TENANT_REQUIRED}), 400
    if question_mode == 'auto_random' and not ensure_tenant_schema_for_user(user["id"]):
        return jsonify({
            "error": "Para competição com questões automáticas é necessário informar o município (header X-City-ID ou usuário vinculado à cidade)."
        }), 400
    try:
        validate_scope_and_filter_for_user(
            scope,
            data.get('scope_filter'),
            user,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    competition_id, schema = CompetitionService.create_competition(data, user['id'])
    if data.get('publish'):
        try:
            CompetitionService.publish_competition(competition_id)
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400
    db.session.rollback()
    ctx = get_current_tenant_context()
    tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
    schema = get_competition_schema(competition_id, tenant_schema=tenant_schema)
    if not schema:
        return jsonify({"error": "Competição não encontrada"}), 404
    set_search_path(schema)
    db.session.expire_all()
    competition = Competition.query.filter_by(id=competition_id).first_or_404()
    return jsonify(_competition_to_dict(competition)), 201


@bp.route('/<competition_id>', methods=['PUT'])
@jwt_required()
@role_required(*ROLES_EDIT)
def update_competition(competition_id):
    """
    Atualiza competição.
    - Rascunho: edição completa (nome, descrição, datas, nível, escopo, prova, etc.).
    - Aberta ou em andamento: apenas datas (fim da inscrição, início da aplicação, fim da competição) e timezone.
    """
    c = CompetitionService.get_competition_or_404(competition_id)
    if c.status not in ('rascunho', 'aberta', 'em_andamento'):
        return jsonify({"error": "Só é possível editar competição em rascunho, aberta ou em andamento"}), 400
    data = request.get_json()
    if not data:
        return jsonify({"error": "Body JSON obrigatório"}), 400

    if c.status in ('aberta', 'em_andamento'):
        editable = ('enrollment_end', 'application', 'expiration', 'timezone')
    else:
        editable = ('name', 'description', 'level', 'scope', 'scope_filter', 'enrollment_start', 'enrollment_end',
                    'application', 'expiration', 'timezone', 'question_mode', 'question_rules', 'reward_config',
                    'ranking_criteria', 'ranking_tiebreaker', 'ranking_visibility', 'max_participants', 'recurrence')

    # Parse todas as datas primeiro
    parsed_dates = {}
    for key in ('enrollment_start', 'enrollment_end', 'application', 'expiration'):
        if key in data:
            try:
                parsed_dates[key] = _parse_dt(data[key])
            except (ValueError, TypeError) as e:
                return jsonify({"error": f"Data inválida em '{key}': {str(e)}"}), 400
    
    # Validar ordem das datas se todas foram fornecidas
    enrollment_start = parsed_dates.get('enrollment_start') or c.enrollment_start
    enrollment_end = parsed_dates.get('enrollment_end') or c.enrollment_end
    application = parsed_dates.get('application') or c.application
    expiration = parsed_dates.get('expiration') or c.expiration
    
    if enrollment_start and enrollment_end:
        if enrollment_end <= enrollment_start:
            return jsonify({"error": "Data de fim da inscrição deve ser após início da inscrição"}), 400
    
    if enrollment_end and application:
        if application < enrollment_end:
            return jsonify({"error": "Data de aplicação deve ser após ou igual ao fim da inscrição"}), 400
    
    if application and expiration:
        if expiration <= application:
            return jsonify({"error": "Data de expiração deve ser após início da aplicação"}), 400
    
    if enrollment_start and expiration:
        if expiration <= enrollment_start:
            return jsonify({"error": "Data de expiração deve ser após início das inscrições"}), 400
    
    # Aplicar mudanças
    for key in editable:
        if key in data:
            val = data[key]
            if key in ('enrollment_start', 'enrollment_end', 'application', 'expiration'):
                val = parsed_dates.get(key)  # Usar valor já parseado
            if key == 'level' and val is not None and not is_valid_level(val):
                return jsonify({
                    "error": "Nível deve ser 1 (Educação Infantil, Anos Iniciais, Educação Especial, EJA) ou 2 (Anos Finais e Ensino Médio)"
                }), 400
            if key == 'reward_config':
                try:
                    validate_reward_config(val)
                except ValidationError as e:
                    return jsonify({"error": str(e)}), 400
            if key in ('scope', 'scope_filter'):
                scope_val = val if key == 'scope' else data.get('scope', c.scope)
                scope_filter_val = val if key == 'scope_filter' else data.get('scope_filter', c.scope_filter)
                try:
                    validate_scope_and_filter(scope_val, scope_filter_val)
                except ValueError as e:
                    return jsonify({"error": str(e)}), 400
                user = get_current_user_from_token()
                if user and scope_val != 'individual' and not ensure_tenant_schema_for_user(user["id"]):
                    return jsonify({"error": MSG_TENANT_REQUIRED}), 400
                if user:
                    try:
                        validate_scope_and_filter_for_user(
                            scope_val, scope_filter_val, user
                        )
                    except ValueError as e:
                        return jsonify({"error": str(e)}), 400
            setattr(c, key, val)

    # auto_random + question_rules: criar ou recriar prova (sorteio de questões) — apenas em rascunho
    if c.status == 'rascunho' and c.question_mode == 'auto_random' and c.question_rules:
        user = get_current_user_from_token()
        if not user or not ensure_tenant_schema_for_user(user["id"]):
            return jsonify({"error": MSG_TENANT_REQUIRED}), 400
        try:
            old_test_id = c.test_id
            if old_test_id:
                TestQuestion.query.filter_by(test_id=old_test_id).delete()
                Test.query.filter_by(id=old_test_id).delete()
            _ctx = get_current_tenant_context()
            _tenant = (_ctx.schema if (_ctx and getattr(_ctx, "has_tenant_context", False)) else None) or None
            try:
                test_id = CompetitionService._create_test_with_random_questions(c)
            except ValidationError as e:
                err_lower = str(e).lower()
                if 'insuficientes' not in err_lower and 'questões' not in err_lower:
                    raise
                current_sch = db.session.execute(text("SELECT current_schema()")).scalar() or "public"
                other_sch = ('public' if current_sch != 'public' else (_tenant if _tenant and _tenant != 'public' else None))
                if other_sch:
                    set_search_path(other_sch)
                    test_id = CompetitionService._create_test_with_random_questions(c)
                else:
                    raise
            comp_schema = get_competition_schema(competition_id, tenant_schema=_tenant)
            db.session.commit()
            if comp_schema == 'public':
                set_search_path('public')
                comp = Competition.query.filter_by(id=competition_id).first_or_404()
                comp.test_id = test_id
                db.session.commit()
            else:
                set_search_path(_tenant)
                comp = Competition.query.filter_by(id=competition_id).first_or_404()
                comp.test_id = test_id
                db.session.commit()
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400
    else:
        db.session.commit()
    ctx = get_current_tenant_context()
    tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
    schema = get_competition_schema(competition_id, tenant_schema=tenant_schema)
    if not schema:
        from flask import abort
        abort(404)
    set_search_path(schema)
    db.session.expire_all()
    c = Competition.query.filter_by(id=competition_id).first_or_404()
    return jsonify(_competition_to_dict(c)), 200


@bp.route('/<competition_id>', methods=['DELETE'])
@jwt_required()
@role_required(*ROLES_EDIT)
def delete_competition(competition_id):
    """Remove competição (rascunho, cancelada, aberta ou em andamento). Apenas admin pode excluir em andamento."""
    c = CompetitionService.get_competition_or_404(competition_id)
    if c.status in ('aberta', 'em_andamento'):
        user = get_current_user_from_token()
        if (user.get('role') or '').strip().lower() != 'admin':
            return jsonify({"error": "Apenas o administrador pode excluir competições em andamento"}), 403
    try:
        CompetitionService.delete_competition(competition_id)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Competição excluída"}), 200


@bp.route('/<competition_id>/publish', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def publish_competition(competition_id):
    """Publica competição (rascunho → aberta)."""
    CompetitionService.get_competition_or_404(competition_id)
    CompetitionService.publish_competition(competition_id)
    # Recarregar no schema correto: limpar cache da sessão e refazer SELECT
    ctx = get_current_tenant_context()
    tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
    schema = get_competition_schema(competition_id, tenant_schema=tenant_schema)
    if not schema:
        from flask import abort
        abort(404)
    set_search_path(schema)
    db.session.expire_all()  # forçar SELECT novo (evitar instância de outro schema)
    c = Competition.query.filter_by(id=competition_id).first_or_404()
    return jsonify(_competition_to_dict(c)), 200


@bp.route('/<competition_id>/cancel', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def cancel_competition(competition_id):
    """Cancela competição."""
    CompetitionService.get_competition_or_404(competition_id)
    data = request.get_json() or {}
    reason = data.get('reason')
    CompetitionService.cancel_competition(competition_id, reason=reason)
    ctx = get_current_tenant_context()
    tenant_schema = (ctx.schema if (ctx and ctx.has_tenant_context) else None) or None
    schema = get_competition_schema(competition_id, tenant_schema=tenant_schema)
    if not schema:
        from flask import abort
        abort(404)
    set_search_path(schema)
    db.session.expire_all()
    c = Competition.query.filter_by(id=competition_id).first_or_404()
    return jsonify(_competition_to_dict(c)), 200


@bp.route('/<competition_id>/questions', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def add_questions(competition_id):
    """Adiciona questões manualmente (question_mode = 'manual')."""
    data = request.get_json()
    if not data or 'question_ids' not in data:
        return jsonify({"error": "question_ids obrigatório"}), 400
    CompetitionService.get_competition_or_404(competition_id)
    CompetitionService.add_questions_manually(competition_id, data['question_ids'])
    c = CompetitionService.get_competition_or_404(competition_id)
    return jsonify(_competition_to_dict(c)), 200
