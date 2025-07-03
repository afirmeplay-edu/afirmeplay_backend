from flask import Blueprint, jsonify, request
from app.models.game import Game
from app.models.subject import Subject
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
import logging
from app import db

bp = Blueprint('games', __name__, url_prefix='/games')

def validate_subject(subject_name):
    """Valida se a disciplina existe no sistema"""
    subject = Subject.query.filter_by(name=subject_name).first()
    return subject is not None

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def create_game():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400

        # Campos obrigatórios
        required_fields = ["url", "title", "iframeHtml", "subject"]
        for field in required_fields:
            if field not in data:
                return jsonify({"erro": f"Campo obrigatório ausente: {field}"}), 400

        # Validar disciplina
        if not validate_subject(data["subject"]):
            return jsonify({"erro": "Disciplina inválida"}), 400

        # Obter usuário autenticado
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401

        # Criar novo jogo
        novo_jogo = Game(
            url=data["url"],
            title=data["title"],
            iframeHtml=data["iframeHtml"],
            thumbnail=data.get("thumbnail"),
            author=data.get("author"),
            provider="wordwall",  # Valor fixo
            subject=data["subject"],
            userId=current_user["id"]
        )

        db.session.add(novo_jogo)
        db.session.commit()

        return jsonify({
            "mensagem": "Jogo criado com sucesso!",
            "jogo": {
                "id": novo_jogo.id,
                "url": novo_jogo.url,
                "title": novo_jogo.title,
                "iframeHtml": novo_jogo.iframeHtml,
                "thumbnail": novo_jogo.thumbnail,
                "author": novo_jogo.author,
                "provider": novo_jogo.provider,
                "subject": novo_jogo.subject,
                "userId": novo_jogo.userId,
                "createdAt": novo_jogo.createdAt.isoformat() if novo_jogo.createdAt else None,
                "updatedAt": novo_jogo.updatedAt.isoformat() if novo_jogo.updatedAt else None
            }
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar jogo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao criar jogo", "detalhes": str(e)}), 500

@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def list_games():
    try:
        games = Game.query.all()
        
        return jsonify({
            "jogos": [{
                "id": game.id,
                "url": game.url,
                "title": game.title,
                "iframeHtml": game.iframeHtml,
                "thumbnail": game.thumbnail,
                "author": game.author,
                "provider": game.provider,
                "subject": game.subject,
                "userId": game.userId,
                "createdAt": game.createdAt.isoformat() if game.createdAt else None,
                "updatedAt": game.updatedAt.isoformat() if game.updatedAt else None
            } for game in games]
        }), 200

    except Exception as e:
        logging.error(f"Erro ao listar jogos: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao listar jogos", "detalhes": str(e)}), 500

@bp.route('/<string:game_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def get_game_by_id(game_id):
    try:
        game = Game.query.get(game_id)
        
        if not game:
            return jsonify({"erro": "Jogo não encontrado"}), 404

        return jsonify({
            "id": game.id,
            "url": game.url,
            "title": game.title,
            "iframeHtml": game.iframeHtml,
            "thumbnail": game.thumbnail,
            "author": game.author,
            "provider": game.provider,
            "subject": game.subject,
            "userId": game.userId,
            "createdAt": game.createdAt.isoformat() if game.createdAt else None,
            "updatedAt": game.updatedAt.isoformat() if game.updatedAt else None
        }), 200

    except Exception as e:
        logging.error(f"Erro ao buscar jogo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao buscar jogo", "detalhes": str(e)}), 500

@bp.route('/<string:game_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def update_game(game_id):
    try:
        game = Game.query.get(game_id)
        
        if not game:
            return jsonify({"erro": "Jogo não encontrado"}), 404

        # Verificar se o usuário é o criador ou admin
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401

        if game.userId != current_user["id"] and current_user["role"] not in ["admin", "tecadm"]:
            return jsonify({"erro": "Sem permissão para editar este jogo"}), 403

        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400

        # Validar disciplina se fornecida
        if "subject" in data and not validate_subject(data["subject"]):
            return jsonify({"erro": "Disciplina inválida"}), 400

        # Atualizar campos
        if "url" in data:
            game.url = data["url"]
        if "title" in data:
            game.title = data["title"]
        if "iframeHtml" in data:
            game.iframeHtml = data["iframeHtml"]
        if "thumbnail" in data:
            game.thumbnail = data["thumbnail"]
        if "author" in data:
            game.author = data["author"]
        if "subject" in data:
            game.subject = data["subject"]

        db.session.commit()

        return jsonify({
            "mensagem": "Jogo atualizado com sucesso!",
            "jogo": {
                "id": game.id,
                "url": game.url,
                "title": game.title,
                "iframeHtml": game.iframeHtml,
                "thumbnail": game.thumbnail,
                "author": game.author,
                "provider": game.provider,
                "subject": game.subject,
                "userId": game.userId,
                "createdAt": game.createdAt.isoformat() if game.createdAt else None,
                "updatedAt": game.updatedAt.isoformat() if game.updatedAt else None
            }
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao atualizar jogo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao atualizar jogo", "detalhes": str(e)}), 500

@bp.route('/<string:game_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def delete_game(game_id):
    try:
        game = Game.query.get(game_id)
        
        if not game:
            return jsonify({"erro": "Jogo não encontrado"}), 404

        # Verificar se o usuário é o criador ou admin
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401

        if game.userId != current_user["id"] and current_user["role"] not in ["admin", "tecadm"]:
            return jsonify({"erro": "Sem permissão para excluir este jogo"}), 403

        db.session.delete(game)
        db.session.commit()

        return jsonify({"mensagem": "Jogo excluído com sucesso!"}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao excluir jogo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao excluir jogo", "detalhes": str(e)}), 500 