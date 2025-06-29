from flask import Blueprint, jsonify, request
from app.utils.auth import get_current_tenant_id
from app.models.user import User, RoleEnum
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
import logging
from werkzeug.security import generate_password_hash
from app import db
from app.models.student import Student
from app.models.school import School
from app.models.studentClass import Class
from app.models.grades import Grade
from sqlalchemy.orm import joinedload

bp = Blueprint('users', __name__, url_prefix='/users')

def format_student_details(student):
    user_details = None
    school_details = None
    if student.school:
        school_details = {
            "id": student.school.id,
            "name": student.school.name,
            "domain": student.school.domain,
            "address": student.school.address,
            "city_id": student.school.city_id,
            "created_at": student.school.created_at.isoformat() if student.school.created_at else None
        }

    class_details = None
    if student.class_:
        class_details = {
            "id": student.class_.id,
            "name": student.class_.name,
            "school_id": student.class_.school_id,
            "grade_id": str(student.class_.grade_id) if student.class_.grade_id else None
        }

    grade_details = None
    if student.grade:
        grade_details = {
            "id": student.grade.id,
            "name": student.grade.name
        }

    return {
        "id": student.id,
        "name": student.name,
        "registration": student.registration,
        "birth_date": student.birth_date.isoformat() if student.birth_date else None,
        "class_id": student.class_id,
        "grade_id": student.grade_id,
        "school_id": student.school_id,
        "created_at": student.created_at.isoformat() if student.created_at else None,
        "school": school_details,
        "class": class_details,
        "grade": grade_details
    }

@bp.route('/list', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm")
def list_users():
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Base query
        query = User.query

        # Filtra por city_id se for tecadmin
        if current_user['role'] == "tecadm":
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

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def create_user():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ["name", "email", "password"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Check if email already exists
        existing_user = User.query.filter_by(email=data["email"]).first()
        if existing_user:
            return jsonify({
                "message": "User already exists",
                "user": {
                    "id": existing_user.id,
                    "name": existing_user.name,
                    "email": existing_user.email,
                    "registration": existing_user.registration,
                    "role": existing_user.role.value
                }
            }), 200

        # Check if registration already exists
        if data.get("registration") and User.query.filter_by(registration=data["registration"]).first():
            return jsonify({"error": "Registration number already exists"}), 400

        # Create user
        novo_usuario = User(
            name=data["name"],
            email=data["email"],
            password_hash=generate_password_hash(data["password"]),
            registration=data.get("registration"),
            role=RoleEnum(data.get("role"))
        )
        db.session.add(novo_usuario)
        db.session.commit()

        return jsonify({
            "message": "User created successfully!",
            "user": {
                "id": novo_usuario.id,
                "name": novo_usuario.name,
                "email": novo_usuario.email,
                "registration": novo_usuario.registration,
                "role": novo_usuario.role.value
            }
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error occurred", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating user: {str(e)}", exc_info=True)
        return jsonify({"error": "Error creating user", "details": str(e)}), 500

@bp.route('/<string:user_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")
def get_user_by_id(user_id):
    try:
        logging.info(f"Fetching user with ID: {user_id}")

        user = User.query.get(user_id)

        if not user:
            logging.warning(f"User not found with ID: {user_id}")
            return jsonify({"message": "User not found"}), 404

        user_data = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "registration": user.registration,
            "role": user.role.value,
            "city_id": user.city_id,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }

        if user.role == RoleEnum.aluno:
            student = Student.query.options(
                joinedload(Student.school),
                joinedload(Student.class_),
                joinedload(Student.grade)
            ).filter_by(user_id=user.id).first()

            if student:
                student_details = format_student_details(student)
                user_data['student_details'] = student_details

        return jsonify(user_data), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while fetching user by ID: {str(e)}")
        return jsonify({"message": "Internal server error while querying data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_user_by_id route: {str(e)}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred", "details": str(e)}), 500 