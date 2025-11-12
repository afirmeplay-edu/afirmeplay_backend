from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app.decorators.role_required import get_current_user_from_token, role_required
from app.services.dashboard_service import DashboardService

bp = Blueprint("dashboard_routes", __name__)


@bp.errorhandler(Exception)
def handle_dashboard_error(error):
    return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(error)}), 500


@bp.route("/dashboard/admin", methods=["GET"])
@jwt_required()
@role_required("admin")
def dashboard_admin():
    user = get_current_user_from_token()
    data = DashboardService.get_admin_dashboard(user)
    return jsonify(data), 200


@bp.route("/dashboard/tecadm", methods=["GET"])
@jwt_required()
@role_required("tecadm")
def dashboard_tecadm():
    user = get_current_user_from_token()
    data = DashboardService.get_tecadm_dashboard(user)
    return jsonify(data), 200


@bp.route("/dashboard/diretor", methods=["GET"])
@jwt_required()
@role_required("diretor")
def dashboard_diretor():
    user = get_current_user_from_token()
    data = DashboardService.get_school_dashboard(user)
    return jsonify(data), 200


@bp.route("/dashboard/coordenador", methods=["GET"])
@jwt_required()
@role_required("coordenador")
def dashboard_coordenador():
    user = get_current_user_from_token()
    data = DashboardService.get_school_dashboard(user)
    return jsonify(data), 200


@bp.route("/dashboard/professor", methods=["GET"])
@jwt_required()
@role_required("professor")
def dashboard_professor():
    user = get_current_user_from_token()
    data = DashboardService.get_professor_dashboard(user)
    return jsonify(data), 200

