from flask import Blueprint, jsonify, request
from app.models.userQuickLinks import UserQuickLinks
from app.models.user import User
from app.decorators.role_required import get_current_user_from_token
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
import logging
from app import db

bp = Blueprint('userQuickLinks', __name__, url_prefix='/user-quick-links')


@bp.route('/<string:user_id>', methods=['GET'])
@jwt_required()
def get_user_quick_links(user_id):
    """Buscar os atalhos de um usuário específico"""
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Verificar se o usuário está tentando acessar seus próprios atalhos
        if current_user['id'] != user_id:
            return jsonify({"erro": "Não autorizado a acessar atalhos de outro usuário"}), 403

        quick_links = UserQuickLinks.query.filter_by(user_id=user_id).first()
        
        if not quick_links:
            return jsonify({"quickLinks": []}), 200

        return jsonify({
            "id": quick_links.id,
            "user_id": quick_links.user_id,
            "quickLinks": quick_links.quickLinks,
            "created_at": quick_links.created_at.isoformat() if quick_links.created_at else None,
            "updated_at": quick_links.updated_at.isoformat() if quick_links.updated_at else None
        }), 200

    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao buscar atalhos do usuário: {e}")
        return jsonify({"erro": "Erro ao consultar atalhos", "detalhes": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao buscar atalhos do usuário: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500


@bp.route('/<string:user_id>', methods=['POST'])
@jwt_required()
def create_or_update_user_quick_links(user_id):
    """Criar ou atualizar os atalhos de um usuário"""
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Verificar se o usuário está tentando modificar seus próprios atalhos
        if current_user['id'] != user_id:
            return jsonify({"erro": "Não autorizado a modificar atalhos de outro usuário"}), 403

        data = request.get_json()
        if not data or 'quickLinks' not in data:
            return jsonify({"erro": "Dados inválidos. Campo 'quickLinks' é obrigatório"}), 400

        # Verificar se o usuário existe
        user = User.query.get(user_id)
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Verificar se já existem atalhos para este usuário
        existing_quick_links = UserQuickLinks.query.filter_by(user_id=user_id).first()
        
        if existing_quick_links:
            # Atualizar atalhos existentes
            existing_quick_links.quickLinks = data['quickLinks']
            db.session.commit()
            
            return jsonify({
                "mensagem": "Atalhos atualizados com sucesso!",
                "id": existing_quick_links.id,
                "user_id": existing_quick_links.user_id,
                "quickLinks": existing_quick_links.quickLinks,
                "updated_at": existing_quick_links.updated_at.isoformat() if existing_quick_links.updated_at else None
            }), 200
        else:
            # Criar novos atalhos
            new_quick_links = UserQuickLinks(
                user_id=user_id,
                quickLinks=data['quickLinks']
            )
            db.session.add(new_quick_links)
            db.session.commit()
            
            return jsonify({
                "mensagem": "Atalhos criados com sucesso!",
                "id": new_quick_links.id,
                "user_id": new_quick_links.user_id,
                "quickLinks": new_quick_links.quickLinks,
                "created_at": new_quick_links.created_at.isoformat() if new_quick_links.created_at else None
            }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao salvar atalhos: {e}")
        return jsonify({"erro": "Erro ao salvar atalhos", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado ao salvar atalhos: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500


@bp.route('/<string:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user_quick_links(user_id):
    """Deletar os atalhos de um usuário"""
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Verificar se o usuário está tentando deletar seus próprios atalhos
        if current_user['id'] != user_id:
            return jsonify({"erro": "Não autorizado a deletar atalhos de outro usuário"}), 403

        quick_links = UserQuickLinks.query.filter_by(user_id=user_id).first()
        
        if not quick_links:
            return jsonify({"erro": "Atalhos não encontrados"}), 404

        db.session.delete(quick_links)
        db.session.commit()
        
        return jsonify({"mensagem": "Atalhos deletados com sucesso!"}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao deletar atalhos: {e}")
        return jsonify({"erro": "Erro ao deletar atalhos", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado ao deletar atalhos: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500 