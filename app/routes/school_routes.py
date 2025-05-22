from flask import Blueprint, request, jsonify
from app.models.school import School
from app import db
from app.decorators.role_required import role_required, get_current_user_from_cookie
from flask_jwt_extended import jwt_required
from app.utils.auth import get_current_tenant_id
from sqlalchemy.exc import SQLAlchemyError
import logging


import uuid

bp = Blueprint('school', __name__, url_prefix='/school')

# POST - Criar escola
@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "diretor")
def criar_escola():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
            
        # Validação dos campos obrigatórios
        required_fields = ['name', 'city_id']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                "erro": "Campos obrigatórios faltando",
                "campos_faltantes": missing_fields
            }), 400

        # Validação do formato dos dados
        if not isinstance(data['name'], str) or len(data['name'].strip()) == 0:
            return jsonify({"erro": "Nome da escola inválido"}), 400
            
        if not isinstance(data['city_id'], str):
            return jsonify({"erro": "ID da cidade inválido"}), 400

        nova_escola = School(
            name=data['name'],
            domain=data.get('domain'),
            address=data.get('address'),
            city_id=data['city_id']
        )

        try:
            db.session.add(nova_escola)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao criar escola no banco de dados: {str(e)}")
            return jsonify({
                "erro": "Erro ao salvar escola no banco de dados",
                "detalhes": str(e)
            }), 500

        return jsonify({
            "mensagem": "Escola criada com sucesso!", 
            "id": nova_escola.id
        }), 201

    except Exception as e:
        logging.error(f"Erro inesperado ao criar escola: {str(e)}", exc_info=True)
        return jsonify({
            "erro": "Erro interno do servidor",
            "detalhes": str(e)
        }), 500

# GET - Listar escolas
@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def listar_escolas():
    try:
        user = get_current_user_from_cookie()

        if not user:
            return jsonify({"message": "Usuário não encontrado"}), 404

        schools = []
        if user['role'] == "admin":
            # Admin pode ver todas as escolas
            schools = School.query.all()
        elif user['role'] == "professor":
            # Professor só vê a escola onde está alocado
            schools = School.query.filter_by(id=user.get('school_id')).all()
        else:
            # Diretor e coordenador veem escolas da mesma cidade
            city_id = get_current_tenant_id()
            if not city_id:
                return jsonify({"message": "ID da cidade não disponível para este usuário"}), 400
            schools = School.query.filter_by(city_id=city_id).all()

        return jsonify([
            {
                "id": e.id,
                "name": e.name,
                "domain": e.domain,
                "address": e.address,
                "city_id": e.city_id,
                "created_at": e.created_at.isoformat() if e.created_at else None
            } for e in schools
        ]), 200

    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao listar escolas: {e}")
        return jsonify({"message": "Erro interno do servidor ao consultar dados", "details": str(e)}), 500
    except AttributeError as e:
        logging.error(f"Erro de atributo ao processar usuário ou papel: {e}")
        return jsonify({"message": "Erro ao processar dados do usuário", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro inesperado na rota listar_escolas: {e}", exc_info=True)
        return jsonify({"message": "Ocorreu um erro inesperado no servidor"}), 500

   
# PUT - Atualizar escola
@bp.route('/<string:escola_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "diretor")
def atualizar_escola(escola_id):
    try:
        # Validação do ID
        if not escola_id:
            return jsonify({"erro": "ID da escola não fornecido"}), 400

        escola = School.query.get(escola_id)
        if not escola:
            return jsonify({"erro": "Escola não encontrada"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400

        # Validação dos campos
        if 'name' in data and (not isinstance(data['name'], str) or len(data['name'].strip()) == 0):
            return jsonify({"erro": "Nome da escola inválido"}), 400

        if 'city_id' in data and not isinstance(data['city_id'], str):
            return jsonify({"erro": "ID da cidade inválido"}), 400

        # Atualização dos campos
        try:
            escola.name = data.get('name', escola.name)
            escola.domain = data.get('domain', escola.domain)
            escola.address = data.get('address', escola.address)
            escola.city_id = data.get('city_id', escola.city_id)

            db.session.commit()
            return jsonify({
                "mensagem": "Escola atualizada com sucesso",
                "id": escola.id
            }), 200

        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao atualizar escola no banco de dados: {str(e)}")
            return jsonify({
                "erro": "Erro ao atualizar escola no banco de dados",
                "detalhes": str(e)
            }), 500

    except Exception as e:
        logging.error(f"Erro inesperado ao atualizar escola: {str(e)}", exc_info=True)
        return jsonify({
            "erro": "Erro interno do servidor",
            "detalhes": str(e)
        }), 500

# DELETE - Excluir escola
@bp.route('/<string:escola_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin")
def deletar_escola(escola_id):
    try:
        # Validação do ID
        if not escola_id:
            return jsonify({"erro": "ID da escola não fornecido"}), 400

        escola = School.query.get(escola_id)
        if not escola:
            return jsonify({"erro": "Escola não encontrada"}), 404

        try:
            db.session.delete(escola)
            db.session.commit()
            return jsonify({
                "mensagem": "Escola deletada com sucesso",
                "id": escola_id
            }), 200

        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao deletar escola no banco de dados: {str(e)}")
            return jsonify({
                "erro": "Erro ao deletar escola no banco de dados",
                "detalhes": str(e)
            }), 500

    except Exception as e:
        logging.error(f"Erro inesperado ao deletar escola: {str(e)}", exc_info=True)
        return jsonify({
            "erro": "Erro interno do servidor",
            "detalhes": str(e)
        }), 500
