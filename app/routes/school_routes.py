from flask import Blueprint, request, jsonify
from app.models.school import School
from app import db
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from app.utils.auth import get_current_tenant_id
from sqlalchemy.exc import SQLAlchemyError
import logging
from app.models.city import City
from app.models.studentClass import Class
from app.models.student import Student

import uuid

bp = Blueprint('school', __name__, url_prefix='/school')

# POST - Criar escola
@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin",  "diretor", "coordenador",)
def criar_escola():
    try:
        data = request.get_json()
        
        if not data:
            logging.error("Dados não fornecidos na requisição")
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
        user = get_current_user_from_token()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Base query with explicit joins
        query = db.session.query(
            School,
            City,
            db.func.count(Student.id).label('students_count'),
            db.func.count(Class.id).label('classes_count')
        ).join(
            City, School.city_id == City.id
        ).outerjoin(
            Student, School.id == Student.school_id
        ).outerjoin(
            Class, School.id == Class.school_id
        ).group_by(
            School.id, City.id
        )

        schools = []
        if user['role'] == "admin":
            # Admin pode ver todas as escolas
            schools = query.all()
        elif user['role'] == "professor":
            # Professor vê todas as escolas onde está alocado
            from app.models.schoolTeacher import TeacherSchool
            teacher_schools = TeacherSchool.query.filter_by(teacher_id=user['id']).all()
            school_ids = [ts.school_id for ts in teacher_schools]
            if school_ids:
                schools = query.filter(School.id.in_(school_ids)).all()
            else:
                return jsonify({"message": "Professor não está alocado em nenhuma escola"}), 404
        else:
            # Diretor e coordenador veem escolas da mesma cidade
            city_id = get_current_tenant_id()
            if not city_id:
                return jsonify({"error": "City ID not available for this user"}), 400
            schools = query.filter(School.city_id == city_id).all()

        return jsonify([{
            "id": school.id,
            "name": school.name,
            "domain": school.domain,
            "address": school.address,
            "city_id": school.city_id,
            "created_at": school.created_at.isoformat() if school.created_at else None,
            "students_count": students_count,
            "classes_count": classes_count,
            "city": {
                "id": city.id,
                "name": city.name,
                "state": city.state,
                "created_at": city.created_at.isoformat() if city.created_at else None
            } if city else None
        } for school, city, students_count, classes_count in schools]), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while listing schools: {e}")
        return jsonify({"error": "Internal server error while querying data", "details": str(e)}), 500
    except AttributeError as e:
        logging.error(f"Attribute error while processing user or role: {e}")
        return jsonify({"error": "Error processing user data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in list_schools route: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred on the server"}), 500

   
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

# GET - Buscar escola específica
@bp.route('/<string:escola_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def buscar_escola(escola_id):
    try:
        user = get_current_user_from_token()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Query with explicit joins
        result = db.session.query(
            School,
            City,
            db.func.count(Student.id).label('students_count'),
            db.func.count(Class.id).label('classes_count')
        ).join(
            City, School.city_id == City.id
        ).outerjoin(
            Student, School.id == Student.school_id
        ).outerjoin(
            Class, School.id == Class.school_id
        ).filter(
            School.id == escola_id
        ).group_by(
            School.id, City.id
        ).first()

        if not result:
            return jsonify({"error": "School not found"}), 404

        school, city, students_count, classes_count = result

        # Verifica permissões
        if user['role'] == "admin":
            # Admin pode ver qualquer escola
            pass
        elif user['role'] == "professor":
            # Professor só pode ver escolas onde está alocado
            from app.models.schoolTeacher import TeacherSchool
            teacher_school = TeacherSchool.query.filter_by(
                teacher_id=user['id'],
                school_id=school.id
            ).first()
            if not teacher_school:
                return jsonify({"error": "You don't have permission to view this school"}), 403
        else:
            # Diretor e coordenador só podem ver escolas da mesma cidade
            if school.city_id != get_current_tenant_id():
                return jsonify({"error": "You don't have permission to view this school"}), 403

        return jsonify({
            "id": school.id,
            "name": school.name,
            "domain": school.domain,
            "address": school.address,
            "city_id": school.city_id,
            "created_at": school.created_at.isoformat() if school.created_at else None,
            "students_count": students_count,
            "classes_count": classes_count,
            "city": {
                "id": city.id,
                "name": city.name,
                "state": city.state,
                "created_at": city.created_at.isoformat() if city.created_at else None
            } if city else None
        }), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while fetching school: {e}")
        return jsonify({"error": "Internal server error while querying data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_school route: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred on the server"}), 500
