"""
Rotas de preferências do aluno (tema da loja, etc.).
Espelham a lógica de /users/user-settings/<user_id> para o path /student/me/preferences
usado pelo frontend quando o aluno está logado.
UserSettings é sempre lido/escrito em public para persistir entre sessões (multi-tenant).
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import logging

from app import db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.decorators.role_required import role_required, get_current_user_from_token

bp = Blueprint("student_preferences", __name__, url_prefix="/student")


def _user_settings_in_public(fn):
    """UserSettings usa ``schema=\"public\"`` no modelo."""
    return fn()


def _format_settings(settings_instance):
    if not settings_instance:
        return {
            "theme": None,
            "fontFamily": None,
            "fontSize": None,
            "sidebar_theme_id": None,
            "frame_id": None,
            "stamp_id": None,
        }
    return {
        "theme": settings_instance.theme,
        "fontFamily": settings_instance.font_family,
        "fontSize": settings_instance.font_size,
        "sidebar_theme_id": settings_instance.sidebar_theme_id,
        "frame_id": settings_instance.frame_id,
        "stamp_id": settings_instance.stamp_id,
    }


@bp.route("/me/preferences", methods=["GET", "OPTIONS"])
@jwt_required()
@role_required("aluno")
def get_my_preferences():
    """GET /student/me/preferences — retorna preferências do aluno (tema, fonte, etc.)."""
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        user_id = current_user["id"]

        def _get():
            user_settings = UserSettings.query.filter_by(user_id=user_id).first()
            return jsonify({"settings": _format_settings(user_settings)}), 200

        return _user_settings_in_public(_get)
    except Exception as e:
        logging.error(f"Erro ao buscar preferências do aluno: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao buscar preferências", "detalhes": str(e)}), 500


@bp.route("/me/preferences", methods=["POST", "PUT", "PATCH"])
@jwt_required()
@role_required("aluno")
def save_my_preferences():
    """POST/PUT/PATCH /student/me/preferences — salva preferências do aluno (tema da loja, etc.)."""
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        user_id = current_user["id"]
        user = User.query.get(user_id)
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        payload = request.get_json()
        if not payload or "settings" not in payload:
            return jsonify({"erro": "Objeto settings é obrigatório"}), 400

        settings_data = payload.get("settings")
        if not isinstance(settings_data, dict):
            return jsonify({"erro": "Objeto settings deve ser um dicionário"}), 400

        def _parse_font_size(val):
            """Aceita int, '110' ou '110%' e retorna int (110) ou None."""
            if val is None:
                return None
            if isinstance(val, int):
                return val
            s = str(val).strip().rstrip("%")
            if not s:
                return None
            try:
                return int(s)
            except ValueError:
                return None

        if "fontSize" in settings_data and settings_data["fontSize"] is not None:
            if _parse_font_size(settings_data["fontSize"]) is None:
                return jsonify({"erro": "fontSize deve ser um número inteiro ou percentual (ex: 110 ou 110%)"}), 400

        def _save():
            user_settings = UserSettings.query.filter_by(user_id=user_id).first()
            if not user_settings:
                user_settings = UserSettings(user_id=user_id)
                db.session.add(user_settings)

            # Atualização parcial: só altera os campos enviados no body
            if "theme" in settings_data:
                user_settings.theme = settings_data.get("theme")
            if "fontFamily" in settings_data:
                user_settings.font_family = settings_data.get("fontFamily")
            if "fontSize" in settings_data:
                user_settings.font_size = _parse_font_size(settings_data["fontSize"])
            if "sidebar_theme_id" in settings_data:
                user_settings.sidebar_theme_id = settings_data.get("sidebar_theme_id")
            if "frame_id" in settings_data:
                user_settings.frame_id = settings_data.get("frame_id")
            if "stamp_id" in settings_data:
                user_settings.stamp_id = settings_data.get("stamp_id")

            db.session.commit()
            return jsonify({"settings": _format_settings(user_settings)}), 200

        return _user_settings_in_public(_save)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao salvar preferências do aluno: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao salvar preferências", "detalhes": str(e)}), 500
