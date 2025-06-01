from flask import Blueprint, request, jsonify
from app.models.student import Student
from app.models.user import User
from app.models.school import School
from app.models.user import RoleEnum
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging
from app.decorators.role_required import role_required, get_current_user_from_token
from app.utils.auth import get_current_tenant_id
from datetime import datetime
from app import db
from flask_jwt_extended import jwt_required
from werkzeug.security import generate_password_hash
from marshmallow import ValidationError
from app.models.studentClass import Class

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


@bp.route("", methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def criar_usuario_e_aluno():
    try:
        logging.info("Iniciando criação de usuário/aluno combinada")

        data = request.get_json()
        logging.info(f"Dados recebidos: {data}")

        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ["name", "email", "password", "class_id"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Tenta encontrar o usuário pelo email
        usuario = User.query.filter_by(email=data["email"]).first()

        if usuario:
            logging.info(f"Usuário existente encontrado: {usuario.email}")
            # Verificar se o usuário já é um aluno
            if Student.query.filter_by(user_id=usuario.id).first():
                logging.warning(f"Usuário {usuario.email} já é um aluno.")
                return jsonify({"error": "User is already a student"}), 400
        else:
            logging.info("Usuário não encontrado, criando novo usuário.")
            # Verificar se matrícula já existe (caso fornecida) - apenas para novo usuário
            if data.get("registration") and User.query.filter_by(registration=data["registration"]).first():
                return jsonify({"error": "Registration number already exists"}), 400

            # Criar usuário (role padrão: aluno)
            usuario = User(
                name=data["name"],
                email=data["email"],
                password_hash=generate_password_hash(data["password"]),
                registration=data.get("registration"),
                role=RoleEnum("aluno")
            )
            db.session.add(usuario)
            db.session.flush() 
            print(usuario.id)
            logging.info(f"Novo usuário criado com sucesso. ID: {usuario.id}")

        # Buscar turma
        class_obj = Class.query.get(data["class_id"])
        if not class_obj:
            # Se o usuário foi criado neste request, precisamos desfazê-lo
            if not usuario.id:
                db.session.rollback()
                return jsonify({"error": "Class not found"}), 404

        # Verificar formato da data de nascimento (se fornecida)
        birth_date = None
        if "birth_date" in data:
            try:
                birth_date = datetime.strptime(data["birth_date"], "%Y-%m-%d").date()
            except ValueError:
                # Se o usuário foi criado neste request, precisamos desfazê-lo
                if not usuario.id:
                    db.session.rollback()
                    return jsonify({"error": "Invalid birth date format. Use YYYY-MM-DD"}), 400

        # Criar aluno
        novo_aluno = Student(
            name=usuario.name,
            user_id=usuario.id,
            registration=usuario.registration,
            birth_date=birth_date,
            class_id=data["class_id"],
            grade_id=data.get("grade_id"),
            school_id=class_obj.school_id
        )
        db.session.add(novo_aluno)
        db.session.commit()

        logging.info(f"Aluno criado com sucesso para o usuário ID: {usuario.id}")

        return jsonify({
            "message": "Student and/or User created successfully!",
            "user": {
                "id": usuario.id,
                "name": usuario.name,
                "email": usuario.email,
                "registration": usuario.registration,
                "role": usuario.role.value
            },
            "student": {
                "id": novo_aluno.id,
                "name": novo_aluno.name,
                "registration": novo_aluno.registration,
                "birth_date": str(novo_aluno.birth_date) if novo_aluno.birth_date else None,
                "class_id": novo_aluno.class_id,
                "grade_id": str(novo_aluno.grade_id) if novo_aluno.grade_id else None,
                "school_id": novo_aluno.school_id
            }
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error during user/student creation: {str(e)}")
        return jsonify({"error": "Database error occurred", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Unexpected error during user/student creation: {str(e)}", exc_info=True)
        return jsonify({"error": "Unexpected error occurred", "details": str(e)}), 500


# GET - Listar alunos
@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def listar_alunos():
    try:
        user = get_current_user_from_token()

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

@bp.route('/school/<string:school_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_students_by_school(school_id):
    try:
        logging.info(f"Fetching students for school_id: {school_id}")
        
        user = get_current_user_from_token()
        if not user:
            logging.error("User not found in token")
            return jsonify({"message": "User not found"}), 404

        # Verify if the school exists
        school = School.query.filter_by(id=school_id).first()
        if not school:
            logging.error(f"School not found with id: {school_id}")
            return jsonify({"message": "School not found"}), 404

        # Check user permissions
        if user['role'] == "professor":
            # Professor can only see students from their assigned school
            if user.get('school_id') != school_id:
                logging.warning(f"Professor {user.get('id')} tried to access students from school {school_id}")
                return jsonify({"message": "You don't have permission to view students from this school"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Director and coordinator can only see students from schools in their city
            city_id = get_current_tenant_id()
            if not city_id:
                logging.error(f"City ID not found for user {user.get('id')}")
                return jsonify({"message": "City ID not available"}), 400
            if school.city_id != city_id:
                logging.warning(f"User {user.get('id')} tried to access students from school in different city")
                return jsonify({"message": "You don't have permission to view students from this school"}), 403

        # Get all students from the school
        try:
            students = Student.query.filter_by(school_id=school_id).all()
            logging.info(f"Found {len(students)} students for school {school_id}")
        except SQLAlchemyError as e:
            logging.error(f"Database error while querying students: {str(e)}")
            return jsonify({"message": "Error querying students from database"}), 500

        return jsonify([
            {
                "id": student.id,
                "name": student.name,
                "email": student.email,
                "registration": student.registration,
                "birth_date": student.birth_date.isoformat() if student.birth_date else None,
                "class_id": student.class_id,
                "grade_id": student.grade_id,
                "school_id": student.school_id,
                "created_at": student.created_at.isoformat() if student.created_at else None
            } for student in students
        ]), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while fetching students by school: {str(e)}")
        return jsonify({"message": "Internal server error while querying data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_students_by_school route: {str(e)}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred", "details": str(e)}), 500

@bp.route('/classes/<string:class_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def get_students_by_class(class_id):
    try:
        logging.info(f"Fetching students for class_id: {class_id}")

        # Check if the class exists (optional, but good practice)
        class_obj = Class.query.get(class_id)
        if not class_obj:
            logging.warning(f"Class not found with ID: {class_id}")
            return jsonify({"message": "Class not found"}), 404

        students = Student.query.filter_by(class_id=class_id).all()

        if not students:
            logging.info(f"No students found for class_id: {class_id}")
            return jsonify([]), 200  # Return empty list if no students found

        return jsonify([
            {
                "id": student.id,
                "name": student.name,
                "registration": student.registration,
                "birth_date": student.birth_date.isoformat() if student.birth_date else None,
                "class_id": student.class_id,
                "user_id": student.user_id,
                "grade_id": student.grade_id,
                "school_id": student.school_id,
                "created_at": student.created_at.isoformat() if student.created_at else None
            } for student in students
        ]), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while fetching students by class: {str(e)}")
        return jsonify({"message": "Internal server error while querying data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_students_by_class route: {str(e)}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred", "details": str(e)}), 500
