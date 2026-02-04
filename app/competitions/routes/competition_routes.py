# -*- coding: utf-8 -*-
"""
Rotas CRUD e ações de competições.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.permissions import role_required, get_current_user_from_token
from app.competitions.models import (
    Competition,
    CompetitionEnrollment,
    CompetitionRankingPayout,
    CompetitionResult,
    CompetitionReward,
)
from app.competitions.services import CompetitionService, ValidationError, validate_reward_config
from app.models.student import Student
from app.models.testQuestion import TestQuestion
from app.competitions.constants import is_valid_level, LEVEL_OPTIONS
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
    """Como _competition_to_dict mas adiciona is_enrolled."""
    d = _competition_to_dict(c)
    d["is_enrolled"] = CompetitionService.is_student_enrolled(c.id, student_id) if student_id else False
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
    if val is None or isinstance(val, datetime):
        return val
    if isinstance(val, str):
        return datetime.fromisoformat(val.replace('Z', '+00:00'))
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
    for key in editable:
        if key in data:
            val = data[key]
            if key in ('enrollment_start', 'enrollment_end', 'application', 'expiration'):
                val = _parse_dt(val)
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
    c = Competition.query.get_or_404(competition_id)
    if c.status not in ('rascunho', 'cancelada'):
        return jsonify({
            "error": "Só é possível excluir competição em rascunho ou cancelada. Cancele a competição antes de excluir."
        }), 400

    # Tabelas com FK sem ON DELETE CASCADE precisam ser apagadas antes
    CompetitionRankingPayout.query.filter_by(competition_id=c.id).delete()
    # Inscrições, recompensas e resultados têm CASCADE no banco; removemos em código para controle
    CompetitionResult.query.filter_by(competition_id=c.id).delete()
    CompetitionReward.query.filter_by(competition_id=c.id).delete()
    CompetitionEnrollment.query.filter_by(competition_id=c.id).delete()

    db.session.delete(c)
    db.session.commit()
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
