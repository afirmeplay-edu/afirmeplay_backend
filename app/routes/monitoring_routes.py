from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.permissions import get_current_user_from_token, role_required
from app.services.monitoring_service import MonitoringService, MonitoringValidationError

bp = Blueprint("monitoring_routes", __name__)


def _error_response(error: Exception, fallback: str, status: int = 500):
    if isinstance(error, MonitoringValidationError):
        return jsonify({"error": error.message}), 400
    db.session.rollback()
    return jsonify({"error": fallback, "details": str(error)}), status


@bp.route("/monitoramento/opcoes-filtros", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def monitoring_filter_options():
    try:
        user = get_current_user_from_token()
        data = MonitoringService.get_filter_options(user, request.args.to_dict())
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao carregar filtros de monitoramento")


@bp.route("/monitoramento/escolas", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def monitoring_schools():
    try:
        user = get_current_user_from_token()
        data = MonitoringService.list_schools(user, request.args.to_dict())
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao carregar agregados de monitoramento")


@bp.route("/monitoramento/turmas", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def monitoring_classes():
    try:
        user = get_current_user_from_token()
        data = MonitoringService.list_classes(user, request.args.to_dict())
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao carregar agregados por turma")


@bp.route("/monitoramento/alunos", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def monitoring_students():
    try:
        user = get_current_user_from_token()
        data = MonitoringService.list_students(user, request.args.to_dict())
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao carregar alunos de monitoramento")


@bp.route("/monitoramento/alunos/<action_id>/acao-pedagogica", methods=["PATCH"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def monitoring_update_action(action_id):
    try:
        user = get_current_user_from_token()
        payload = request.get_json(silent=True) or {}
        data = MonitoringService.update_action(user, action_id, payload)
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao salvar ação pedagógica")


@bp.route("/monitoramento/habilidade-detalhe", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def monitoring_skill_detail():
    try:
        user = get_current_user_from_token()
        data = MonitoringService.get_skill_detail(user, request.args.to_dict())
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao carregar detalhe da habilidade")


@bp.route("/monitoramento/alunos/<action_id>/historico", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def monitoring_history(action_id):
    try:
        data = MonitoringService.get_history(action_id)
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao carregar histórico")


@bp.route("/monitoramento/relatorio-dados", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def monitoring_report_data():
    try:
        user = get_current_user_from_token()
        data = MonitoringService.report_data(user, request.args.to_dict())
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao montar dados de relatório de monitoramento")
