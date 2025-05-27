from flask import Blueprint, jsonify
from app.utils.auth import get_current_tenant_id
from app.models.user import User
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
import logging

bp = Blueprint('users', __name__, url_prefix='/users')

@bp.route('/list', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadmin")
def list_users():
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Base query
        query = User.query

        # Filtra por city_id se for tecadmin
        if current_user['role'] == "tecadmin":
            city_id = get_current_tenant_id()
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            query = query.filter_by(city_id=city_id)

        users = query.all()
        
        return jsonify({
            "users": [{
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "registration": user.registration,
                "role": user.role.value,
                "city_id": user.city_id,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            } for user in users]
        }), 200

    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao listar usuários: {e}")
        return jsonify({"erro": "Erro ao consultar usuários", "detalhes": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao listar usuários: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500 