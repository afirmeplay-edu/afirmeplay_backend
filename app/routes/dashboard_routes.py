from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.student import Student
from app.models.school import School
from app.decorators.role_required import get_current_user_from_token, role_required
from app.decorators import requires_city_context
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
@requires_city_context
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
@requires_city_context
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
@requires_city_context
def dashboard_questoes():
    """
    Retorna lista de questões para o card do dashboard, com detalhes ricos:
    quantidade de respostas, taxa de acerto, quantidade de avaliações,
    última utilização, disciplina, ano, autor, dificuldade, tipo.
    Query params: limit (default 20), offset (default 0).
    
    Filtra questões por escopo:
    - GLOBAL: Todos podem ver
    - CITY: Apenas usuários do mesmo município
    - PRIVATE: Apenas o criador
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
@requires_city_context
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


@bp.route("/dashboard/ranking-turmas", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
@requires_city_context
def ranking_turmas():
    """
    Retorna ranking de turmas para o card: turma, série, média, acerto,
    conclusão, alunos, avaliações. Respeita o escopo do usuário (município ou escola).
    Query params: limit (default 20), offset (default 0).
    """
    try:
        from flask import request
        user = get_current_user_from_token()
        scope = DashboardService._resolve_scope(user)
        limit = min(int(request.args.get("limit", 20)), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
        data = DashboardService.get_class_ranking_card(scope, limit=limit, offset=offset)
        return jsonify(data), 200
    except ValueError:
        return jsonify({"error": "Parâmetros limit e offset devem ser números"}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar ranking de turmas", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar ranking de turmas", "details": str(e)}), 500


@bp.route("/dashboard/ranking-alunos", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")
@requires_city_context
def ranking_alunos():
    """
    Retorna o top de alunos (ranking) por turma, escola ou município.
    Ordenado por média de proficiência.

    Aluno: pode ver turma, escola ou município. Sem scope na query, default = município (ver tudo).
    Outros roles: default = turma.

    Query params:
      - scope=turma   → ranking da turma (aluno: sua turma; outros: class_id se informado)
      - scope=escola  → ranking da escola (aluno: sua escola; outros: school_id se informado)
      - scope=municipio → ranking completo do município (todos os alunos da cidade)
      - limit (default 20, máx. 50)
    """
    try:
        from flask import request
        user = get_current_user_from_token()
        limit = min(max(1, int(request.args.get("limit", 20))), 50)
        # Aluno: default = município (ver tudo). Outros roles: default = turma.
        default_scope = "municipio" if user.get("role") == "aluno" else "turma"
        scope_type = request.args.get("scope", "").strip().lower() or default_scope
        class_id = request.args.get("class_id", "").strip() or None
        school_id = request.args.get("school_id", "").strip() or None
        city_id = request.args.get("city_id", "").strip() or None

        # Aluno: pode ver turma, escola ou município (ranking completo do município = "ver tudo")
        if user.get("role") == "aluno":
            student = Student.query.filter_by(user_id=user["id"]).first()
            if not student:
                return jsonify({"ranking": [], "total": 0}), 200
            # Resolver city_id do aluno (usado em municipio e como fallback)
            city_id_aluno = user.get("city_id") or user.get("tenant_id")
            if student.school_id:
                school = School.query.get(student.school_id)
                if school:
                    city_id_aluno = city_id_aluno or str(getattr(school, "city_id", "") or "")
            if scope_type == "turma":
                if not student.class_id:
                    return jsonify({"ranking": [], "total": 0}), 200
                scope = {
                    "scope": "turma",
                    "class_id": str(student.class_id),
                    "user": user,
                    "school_ids": None,
                    "city_id": None,
                }
            elif scope_type == "escola":
                if not student.school_id:
                    return jsonify({"ranking": [], "total": 0}), 200
                scope = {
                    "scope": "escola",
                    "user": user,
                    "school_ids": [str(student.school_id)],
                    "city_id": city_id_aluno,
                }
            else:
                # municipio = ranking completo (todos os alunos do município)
                if not city_id_aluno:
                    return jsonify({"ranking": [], "total": 0}), 200
                scope = {
                    "scope": "municipio",
                    "city_id": str(city_id_aluno),
                    "user": user,
                    "school_ids": None,
                }
        else:
            # Escopo explícito só quando vier o ID correspondente; senão usa escopo do usuário
            if scope_type == "turma" and class_id:
                scope = DashboardService._resolve_explicit_ranking_scope(user, "turma", class_id)
            elif scope_type == "escola" and school_id:
                scope = DashboardService._resolve_explicit_ranking_scope(user, "escola", school_id)
            elif scope_type == "municipio" and city_id:
                scope = DashboardService._resolve_explicit_ranking_scope(user, "municipio", city_id)
            else:
                scope = DashboardService._resolve_scope(user)

            # Se escopo explícito inválido (id inexistente ou sem permissão), fallback para escopo do usuário
            if scope is None:
                scope = DashboardService._resolve_scope(user)
            if scope is None:
                return jsonify({"error": "Sem permissão para este escopo ou escopo inválido"}), 403

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

