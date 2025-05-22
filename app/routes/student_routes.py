from flask import Blueprint, request, jsonify
from app.models.student import Student
from app.models.user import User
from app.models.school import School
from app.models.user import RoleEnum
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging
from app.decorators.role_required import role_required, get_current_user_from_cookie
from app.utils.auth import get_current_tenant_id
from datetime import datetime
from app import db
from flask_jwt_extended import jwt_required
from werkzeug.security import generate_password_hash
from marshmallow import ValidationError

bp = Blueprint('students', __name__, url_prefix="/students")

@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"error": "Database error occurred", "details": str(error)}), 500

@bp.errorhandler(ValidationError)
def handle_validation_error(error):
    return jsonify({"error": "Validation error", "details": error.messages}), 400

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"error": "An unexpected error occurred", "details": str(error)}), 500

@bp.route("", methods=["POST"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def criar_aluno():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ["name", "email", "password", "class_id"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Criação do usuário com dados básicos
        novo_usuario = User(
            name=data["name"],
            email=data["email"],
            password_hash=generate_password_hash(data["password"]),
            registration=data.get("registration"),
            role=RoleEnum("aluno"),
        )
        db.session.add(novo_usuario)
        db.session.flush()

        # Converte a data de nascimento se enviada
        birth_date = None
        if "birth_date" in data:
            try:
                birth_date = datetime.strptime(data["birth_date"], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Invalid birth date format. Use YYYY-MM-DD"}), 400

        # Criação do aluno vinculado ao usuário
        novo_aluno = Student(
            name=data["name"],
            email=data["email"],
            password_hash=generate_password_hash(data["password"]),
            user_id=novo_usuario.id,
            registration=data.get("registration"),
            birth_date=birth_date,
            class_id=data["class_id"],
            grade_id=data.get("grade_id"),
        )
        db.session.add(novo_aluno)
        db.session.commit()

        return jsonify({"message": "Student created successfully!", "id": novo_aluno.id}), 201

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"error": "Database integrity error", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating student: {str(e)}", exc_info=True)
        return jsonify({"error": "Error creating student", "details": str(e)}), 500

# GET - Listar alunos
@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def listar_alunos():
    try:
        user = get_current_user_from_cookie()

        if not user:
            return jsonify({"message": "Usuário não encontrado"}), 404

        students = []
        if user['role'] == "admin":
            # Admin pode ver todos os alunos
            students = Student.query.all()
        elif user['role'] == "professor":
            # Professor só vê alunos da escola onde está alocado
            school_id = user.get('school_id')
            if not school_id:
                return jsonify({"message": "Professor não está alocado em nenhuma escola"}), 400
            students = Student.query.filter_by(school_id=school_id).all()
        else:
            # Diretor e coordenador veem alunos de todas as escolas da cidade
            city_id = get_current_tenant_id()
            if not city_id:
                return jsonify({"message": "ID da cidade não disponível para este usuário"}), 400
            
            # Busca todas as escolas da cidade
            schools = School.query.filter_by(city_id=city_id).all()
            school_ids = [school.id for school in schools]
            
            # Busca todos os alunos das escolas da cidade
            students = Student.query.filter(Student.school_id.in_(school_ids)).all()

        return jsonify([
            {
                "id": aluno.id,
                "name": aluno.name,
                "email": aluno.email,
                "school_id": aluno.school_id,
                "created_at": aluno.created_at.isoformat() if aluno.created_at else None
            } for aluno in students
        ]), 200

    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao listar alunos: {e}")
        return jsonify({"message": "Erro interno do servidor ao consultar dados", "details": str(e)}), 500
    except AttributeError as e:
        logging.error(f"Erro de atributo ao processar usuário ou papel: {e}")
        return jsonify({"message": "Erro ao processar dados do usuário", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro inesperado na rota listar_alunos: {e}", exc_info=True)
        return jsonify({"message": "Ocorreu um erro inesperado no servidor"}), 500 

@bp.route('/<string:student_id>/<string:class_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def atualizar_aluno(student_id, class_id):
    try:
        aluno = Student.query.filter_by(id=student_id, class_id=class_id).first()

        if not aluno:
            return jsonify({"error": "Student not found"}), 404

        dados = request.get_json()
        if not dados:
            return jsonify({"error": "No data provided"}), 400

        # Atualiza dados do usuário vinculado
        usuario = aluno.usuario
        if not usuario:
            return jsonify({"error": "Associated user not found"}), 404

        usuario.name = dados.get("name", usuario.name)
        usuario.email = dados.get("email", usuario.email)
        usuario.registration = dados.get("registration", usuario.registration)

        # Atualiza dados do aluno
        aluno.class_id = dados.get("class_id", aluno.class_id)
        aluno.grade_id = dados.get("grade_id", aluno.grade_id)

        # Atualiza data de nascimento se enviada
        if "birth_date" in dados:
            try:
                aluno.birth_date = datetime.strptime(dados["birth_date"], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

        db.session.commit()
        return jsonify({"message": "Student updated successfully"}), 200

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"error": "Database integrity error", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating student: {str(e)}", exc_info=True)
        return jsonify({"error": "Error updating student", "details": str(e)}), 500

@bp.route('/<string:aluno_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def deletar_aluno(aluno_id):
    try:
        aluno = Student.query.filter_by(id=aluno_id).first()

        if not aluno:
            return jsonify({"error": "Student not found"}), 404

        # Verifica se existe usuário associado
        if aluno.usuario:
            db.session.delete(aluno.usuario)
        
        db.session.delete(aluno)
        db.session.commit()
        return jsonify({"message": "Student deleted successfully"}), 200

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"error": "Database integrity error", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting student: {str(e)}", exc_info=True)
        return jsonify({"error": "Error deleting student", "details": str(e)}), 500
