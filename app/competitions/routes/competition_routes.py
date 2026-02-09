# -*- coding: utf-8 -*-
"""
Rotas CRUD e ações de competições.
"""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.permissions import role_required, get_current_user_from_token
from app.competitions.models import Competition, CompetitionEnrollment
from app.competitions.services import CompetitionService, ValidationError, validate_reward_config
from app.services.competition_ranking_service import CompetitionRankingService
from app.models.student import Student
from app.models.studentTestOlimpics import StudentTestOlimpics
from app.models.testQuestion import TestQuestion
from app.models.testSession import TestSession
from app.competitions.constants import is_valid_level, LEVEL_OPTIONS
from app.utils.timezone_utils import get_local_time
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

bp = Blueprint('competitions', __name__, url_prefix='/competitions')

# Página de gerenciamento de competições: admin, coordenador, diretor, tecadm, professor
ROLES_EDIT = ("admin", "coordenador", "diretor", "tecadm", "professor")
# Rotas de listagem disponível / inscrição: roles acima + aluno
ROLES_STUDENT_OR_EDIT = ("admin", "coordenador", "diretor", "tecadm", "professor", "aluno")


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


def _get_selected_question_ids(test_id):
    """Retorna lista de question_id na ordem do teste (para competição com auto_random)."""
    if not test_id:
        return []
    try:
        rows = (
            TestQuestion.query.filter_by(test_id=test_id)
            .order_by(TestQuestion.order)
            .with_entities(TestQuestion.question_id)
            .all()
        )
        return [r[0] for r in rows]
    except Exception as e:
        logging.warning("selected_question_ids falhou para test_id %s: %s", test_id, e)
        return []


def _competition_to_dict(c):
    """Serializa Competition para dict. Datas/horas no mesmo padrão de tests (isoformat ou None)."""
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
        'template_id': c.template_id,
        'status': c.status,
        'created_by': c.created_by,
        'created_at': c.created_at.isoformat() if c.created_at else None,
        'updated_at': c.updated_at.isoformat() if c.updated_at else None,
        'is_enrollment_open': c.is_enrollment_open,
        'is_application_open': c.is_application_open,
        'is_finished': c.is_finished,
        'enrolled_count': _safe_enrolled_count(c),
        'available_slots': _safe_available_slots(c),
        'selected_question_ids': _get_selected_question_ids(c.test_id),
    }
    if c.subject:
        d['subject_name'] = c.subject.name
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
    return val


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
    return jsonify({"error": str(error)}), 400


@bp.errorhandler(Exception)
def handle_any_error(error):
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
    """Lista competições com filtros opcionais (status, level, subject_id)."""
    query = Competition.query
    if request.args.get('status'):
        query = query.filter(Competition.status == request.args.get('status'))
    if request.args.get('level') is not None:
        try:
            level_val = int(request.args.get('level'))
            if is_valid_level(level_val):
                query = query.filter(Competition.level == level_val)
        except (TypeError, ValueError):
            pass
    if request.args.get('subject_id'):
        query = query.filter(Competition.subject_id == request.args.get('subject_id'))
    if request.args.get('scope'):
        query = query.filter(Competition.scope == request.args.get('scope'))
    items = query.order_by(Competition.created_at.desc()).all()
    return jsonify([_competition_to_dict(c) for c in items]), 200


# ---------- Etapa 3: rotas para aluno (disponíveis, detalhes, inscrição, cancelar) ----------

@bp.route('/available', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def list_available_competitions():
    """Lista competições disponíveis para o aluno (nível, escopo, período, vagas)."""
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    subject_id = request.args.get('subject_id')
    competitions = CompetitionService.get_available_competitions_for_student(student_id, subject_id=subject_id)
    return jsonify([_competition_to_dict_with_enrolled(c, student_id) for c in competitions]), 200


@bp.route('/<competition_id>/details', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def get_competition_details_for_student(competition_id):
    """Detalhes da competição para o aluno (inclui is_enrolled, available_slots)."""
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    c = Competition.query.get_or_404(competition_id)
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
    competition = Competition.query.get_or_404(competition_id)
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
    """Serializa TestSession para resposta da API."""
    if not session:
        return None
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


@bp.route('/<competition_id>/my-session', methods=['GET'])
@jwt_required()
@role_required(*ROLES_STUDENT_OR_EDIT)
def get_my_competition_session(competition_id):
    """
    Retorna a sessão de prova do aluno nesta competição (se existir).
    Usado para saber se o aluno já iniciou/finalizou a prova.
    """
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    c = Competition.query.get_or_404(competition_id)
    if not c.test_id:
        return jsonify({"test_session": None}), 200
    session = (
        TestSession.query.filter_by(student_id=student_id, test_id=c.test_id)
        .order_by(TestSession.created_at.desc())
        .first()
    )
    return jsonify({"test_session": _session_to_dict(session)}), 200


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
    c = Competition.query.get_or_404(competition_id)
    if not c.test_id:
        return jsonify({"error": "Competição sem prova vinculada"}), 400

    # Aluno deve estar inscrito
    enrollment = CompetitionEnrollment.query.filter_by(
        competition_id=c.id,
        student_id=student_id,
        status='inscrito',
    ).first()
    if not enrollment:
        return jsonify({"error": "Aluno não inscrito nesta competição"}), 403

    # Período de aplicação (application / expiration)
    now = get_local_time()
    now_naive = now.replace(tzinfo=None) if now.tzinfo else now
    if c.application and now_naive < c.application:
        return jsonify({"error": "Fora do período de aplicação da competição"}), 410
    if c.expiration and now_naive > c.expiration:
        return jsonify({"error": "Período de aplicação da competição encerrado"}), 410

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
        # em_andamento: retornar mesmo formato de sucesso para o front poder abrir a prova
        payload = {
            "message": "Sessão já iniciada",
            "session_id": existing.id,
            "test_session": _session_to_dict(existing),
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
    db.session.commit()
    payload = {
        "message": "Sessão iniciada com sucesso",
        "session_id": session.id,
        "test_session": _session_to_dict(session),
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
    c = Competition.query.get_or_404(competition_id)
    visibility = (c.ranking_visibility or 'final').strip().lower()
    if visibility == 'final' and c.status != 'encerrada':
        return jsonify({"error": "Ranking só é exibido após o encerramento da competição"}), 403
    try:
        limit = request.args.get('limit', type=int) or 100
        limit = min(max(1, limit), 500)
    except (TypeError, ValueError):
        limit = 100
    ranking = CompetitionRankingService.get_ranking(competition_id, limit=limit, enriquecer=True)
    return jsonify({"ranking": [_serialize_ranking_item(r) for r in ranking]}), 200


@bp.route('/<competition_id>/analytics', methods=['GET'])
@jwt_required()
@role_required(*ROLES_EDIT)
def get_competition_analytics(competition_id):
    """
    Retorna analytics completos da competição (apenas admin/coordenador).
    Inclui: taxa de inscrição, taxa de participação, médias, distribuição de notas, top 10, comparação com anteriores.
    """
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
    student_id, err = _resolve_student_id()
    if err:
        return err[0], err[1]
    c = Competition.query.get_or_404(competition_id)
    visibility = (c.ranking_visibility or 'final').strip().lower()
    if visibility == 'final' and c.status != 'encerrada':
        return jsonify({"error": "Ranking só é exibido após o encerramento da competição"}), 403
    result = CompetitionRankingService.get_my_ranking(competition_id, student_id)
    if result is None:
        return jsonify({
            "message": "Você ainda não possui resultado nesta competição",
            "position": None,
            "total_participants": 0,
        }), 200
    return jsonify(result), 200


@bp.route('/<competition_id>/finalize', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def finalize_competition(competition_id):
    """
    Finaliza a competição manualmente: grava ranking em competition_results,
    paga moedas de ranking e define status='encerrada'.
    Só permite se expiration já passou e status é aberta/em_andamento.
    """
    from datetime import datetime
    c = Competition.query.get_or_404(competition_id)
    now_utc = datetime.utcnow()
    if c.status not in ('aberta', 'em_andamento'):
        return jsonify({
            "error": "Competição já encerrada ou não está aberta.",
            "status": c.status,
        }), 400
    if c.expiration and c.expiration > now_utc:
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
    competition = Competition.query.get_or_404(competition_id)
    include_meta = request.args.get('include_meta', '').lower() in ('1', 'true', 'yes')

    # Verificações globais da competição
    now = get_local_time()
    now_naive = now.replace(tzinfo=None) if now.tzinfo else now
    if competition.status != 'aberta' or not competition.test_id:
        if include_meta:
            return jsonify({
                "eligible": [],
                "meta": {
                    "reason": "competition_not_open_or_no_test",
                    "status": competition.status,
                    "has_test_id": bool(competition.test_id),
                },
            }), 200
        return jsonify([]), 200
    if competition.enrollment_start and now_naive < competition.enrollment_start:
        if include_meta:
            return jsonify({
                "eligible": [],
                "meta": {"reason": "before_enrollment_period", "enrollment_start": competition.enrollment_start.isoformat() if competition.enrollment_start else None},
            }), 200
        return jsonify([]), 200
    if competition.enrollment_end and now_naive > competition.enrollment_end:
        if include_meta:
            return jsonify({
                "eligible": [],
                "meta": {"reason": "after_enrollment_period", "enrollment_end": competition.enrollment_end.isoformat() if competition.enrollment_end else None},
            }), 200
        return jsonify([]), 200

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
        if CompetitionService.is_student_enrolled(competition.id, student.id):
            excluded_enrolled += 1
            continue
        if StudentTestOlimpics.query.filter_by(
            student_id=student.id,
            test_id=competition.test_id,
        ).first():
            excluded_olympics += 1
            continue
        available = CompetitionService.get_available_competitions_for_student(
            student.id,
            subject_id=competition.subject_id,
        )
        if not any(c.id == competition.id for c in available):
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
    """Detalhe de uma competição."""
    c = Competition.query.get_or_404(competition_id)
    return jsonify(_competition_to_dict(c)), 200


@bp.route('', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def create_competition():
    """Cria competição."""
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
    competition = CompetitionService.create_competition(data, user['id'])
    return jsonify(_competition_to_dict(competition)), 201


@bp.route('/<competition_id>', methods=['PUT'])
@jwt_required()
@role_required(*ROLES_EDIT)
def update_competition(competition_id):
    """Atualiza competição (apenas rascunho)."""
    c = Competition.query.get_or_404(competition_id)
    if c.status != 'rascunho':
        return jsonify({"error": "Só é possível editar competição em rascunho"}), 400
    data = request.get_json()
    if not data:
        return jsonify({"error": "Body JSON obrigatório"}), 400
    editable = ('name', 'description', 'level', 'scope', 'scope_filter', 'enrollment_start', 'enrollment_end',
                'application', 'expiration', 'timezone', 'question_mode', 'question_rules', 'reward_config',
                'ranking_criteria', 'ranking_tiebreaker', 'ranking_visibility', 'max_participants', 'recurrence',
                'template_id')
    
    # Parse todas as datas primeiro
    parsed_dates = {}
    for key in ('enrollment_start', 'enrollment_end', 'application', 'expiration'):
        if key in data:
            parsed_dates[key] = _parse_dt(data[key])
    
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
            setattr(c, key, val)

    # Se passou para auto_random com question_rules e ainda não tem prova, sorteia questões e cria o Test
    if c.question_mode == 'auto_random' and c.question_rules and not c.test_id:
        try:
            CompetitionService._create_test_with_random_questions(c)
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

    db.session.commit()
    return jsonify(_competition_to_dict(c)), 200


@bp.route('/<competition_id>', methods=['DELETE'])
@jwt_required()
@role_required(*ROLES_EDIT)
def delete_competition(competition_id):
    """Remove competição (apenas rascunho ou cancelada). Remove inscrições e dados relacionados."""
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
    competition = CompetitionService.publish_competition(competition_id)
    return jsonify(_competition_to_dict(competition)), 200


@bp.route('/<competition_id>/cancel', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def cancel_competition(competition_id):
    """Cancela competição."""
    data = request.get_json() or {}
    reason = data.get('reason')
    competition = CompetitionService.cancel_competition(competition_id, reason=reason)
    return jsonify(_competition_to_dict(competition)), 200


@bp.route('/<competition_id>/questions', methods=['POST'])
@jwt_required()
@role_required(*ROLES_EDIT)
def add_questions(competition_id):
    """Adiciona questões manualmente (question_mode = 'manual')."""
    data = request.get_json()
    if not data or 'question_ids' not in data:
        return jsonify({"error": "question_ids obrigatório"}), 400
    CompetitionService.add_questions_manually(competition_id, data['question_ids'])
    c = Competition.query.get_or_404(competition_id)
    return jsonify(_competition_to_dict(c)), 200
