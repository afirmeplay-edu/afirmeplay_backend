from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
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
    try:
        user = get_current_user_from_token()
        data = DashboardService.get_admin_dashboard(user)
        return jsonify(data), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500


@bp.route("/dashboard/tecadm", methods=["GET"])
@jwt_required()
@role_required("tecadm")
def dashboard_tecadm():
    try:
        user = get_current_user_from_token()
        data = DashboardService.get_tecadm_dashboard(user)
        return jsonify(data), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500


@bp.route("/dashboard/diretor", methods=["GET"])
@jwt_required()
@role_required("diretor")
def dashboard_diretor():
    try:
        user = get_current_user_from_token()
        data = DashboardService.get_school_dashboard(user)
        return jsonify(data), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500


@bp.route("/dashboard/coordenador", methods=["GET"])
@jwt_required()
@role_required("coordenador")
def dashboard_coordenador():
    try:
        user = get_current_user_from_token()
        data = DashboardService.get_school_dashboard(user)
        return jsonify(data), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500


@bp.route("/dashboard/professor", methods=["GET"])
@jwt_required()
@role_required("professor")
def dashboard_professor():
    try:
        user = get_current_user_from_token()
        data = DashboardService.get_professor_dashboard(user)
        return jsonify(data), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar dados do dashboard", "details": str(e)}), 500


@bp.route("/dashboard/avisos/quantidade", methods=["GET"])
@jwt_required()
def avisos_quantidade():
    """
    Retorna a quantidade de avisos no escopo do usuário logado.
    """
    try:
        user = get_current_user_from_token()
        scope = DashboardService._resolve_scope(user)
        quantidade = DashboardService._count_notices(scope)
        return jsonify({"quantidade": quantidade}), 200
    except Exception as e:
        return jsonify({"error": "Erro ao buscar quantidade de avisos", "details": str(e)}), 500


@bp.route("/dashboard/analise-sistema", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm")
def analise_sistema():
    """
    Retorna dados para o modal de análise do sistema: métricas gerais, dados
    técnicos, dados por escopo (geral, estado, município, escola) e séries
    para gráficos (evolução, distribuição, taxas de conclusão).
    """
    try:
        data = DashboardService.get_analise_sistema()
        return jsonify(data), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar análise do sistema", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar análise do sistema", "details": str(e)}), 500


@bp.route("/dashboard/questoes", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def dashboard_questoes():
    """
    Retorna lista de questões para o card do dashboard, com detalhes ricos:
    quantidade de respostas, taxa de acerto, quantidade de avaliações,
    última utilização, disciplina, ano, autor, dificuldade, tipo.
    Query params: limit (default 20), offset (default 0).
    """
    try:
        from flask import request
        user = get_current_user_from_token()
        scope = DashboardService._resolve_scope(user)
        limit = min(max(1, int(request.args.get("limit", 20))), 50)
        offset = max(0, int(request.args.get("offset", 0)))
        data = DashboardService.get_questoes_dashboard(scope, limit=limit, offset=offset)
        return jsonify(data), 200
    except ValueError:
        return jsonify({"error": "Parâmetros limit e offset devem ser números"}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar questões", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar questões", "details": str(e)}), 500


@bp.route("/dashboard/avaliacoes-recentes", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def avaliacoes_recentes():
    """
    Retorna avaliações recentes (type AVALIACAO) com: quantidade de alunos que
    fizeram, que vão fazer, prazo, progresso, status, disciplina, escola(s).
    Query param: limit (default 10).
    """
    try:
        from flask import request
        user = get_current_user_from_token()
        scope = DashboardService._resolve_scope(user)
        limit = min(int(request.args.get("limit", 10)), 50)
        data = DashboardService.get_recent_evaluations_avaliacao(scope, limit=limit)
        return jsonify({"avaliacoes": data}), 200
    except ValueError:
        return jsonify({"error": "Parâmetro limit deve ser um número"}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar avaliações recentes", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar avaliações recentes", "details": str(e)}), 500


@bp.route("/dashboard/ranking-escolas", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def ranking_escolas():
    """
    Retorna ranking de escolas para card: média, quantidade de alunos,
    taxa de conclusão por avaliações, total de turmas e provas entregues.
    Respeita o escopo do usuário (município ou escola).
    Query params: limit (default 20), offset (default 0).
    """
    try:
        from flask import request
        user = get_current_user_from_token()
        scope = DashboardService._resolve_scope(user)
        limit = min(int(request.args.get("limit", 20)), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
        data = DashboardService.get_school_ranking_card(scope, limit=limit, offset=offset)
        return jsonify(data), 200
    except ValueError:
        return jsonify({"error": "Parâmetros limit e offset devem ser números"}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar ranking de escolas", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar ranking de escolas", "details": str(e)}), 500


@bp.route("/dashboard/ranking-alunos", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def ranking_alunos():
    """
    Retorna o top de alunos (ranking) do servidor para o dashboard.
    Ordenado por média de notas. Respeita o escopo do usuário.
    Query param: limit (default 20, máx. 50).
    """
    try:
        from flask import request
        user = get_current_user_from_token()
        scope = DashboardService._resolve_scope(user)
        limit = min(max(1, int(request.args.get("limit", 20))), 50)
        data = DashboardService.get_ranking_alunos(scope, limit=limit)
        return jsonify(data), 200
    except ValueError:
        return jsonify({"error": "Parâmetro limit deve ser um número"}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar ranking de alunos", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar ranking de alunos", "details": str(e)}), 500

