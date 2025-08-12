from flask import Blueprint, jsonify, request
from app.decorators.role_required import get_current_tenant_id
from app.models.user import User, RoleEnum
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models.student import Student
from app.models.school import School
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.teacher import Teacher
from app.models.manager import Manager
from sqlalchemy.orm import joinedload
from app.utils.email_service import EmailService
from datetime import datetime, timedelta
from flask import current_app

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
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
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

        # Obter usuário atual
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"error": "User not found"}), 404

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

        # Determinar city_id baseado na role do usuário atual
        city_id = None
        if current_user['role'] == "admin":
            # Admin pode escolher qualquer city_id
            city_id = data.get("city_id")
            if not city_id:
                return jsonify({"error": "city_id is required for admin creating users"}), 400
        else:
            # TecAdmin, Diretor, Coordenador, Professor usam seu próprio city_id
            city_id = current_user.get("city_id")
            if not city_id:
                return jsonify({"error": "User does not have a city_id assigned"}), 400

        # Para alunos, não definir city_id diretamente (será herdado da escola)
        if data.get("role") == "aluno":
            city_id = None

        # Para tecadm, city_id é obrigatório
        if data.get("role") == "tecadm":
            city_id = data.get("city_id")
            if not city_id:
                return jsonify({"error": "city_id is required for tecadm"}), 400

        # Create user
        novo_usuario = User(
            name=data["name"],
            email=data["email"],
            password_hash=generate_password_hash(data["password"]),
            registration=data.get("registration"),
            role=RoleEnum(data.get("role")),
            city_id=city_id  # Adicionando city_id
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
                "role": novo_usuario.role.value,
                "city_id": novo_usuario.city_id
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

@bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Solicita redefinição de senha"""
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({"erro": "Email é obrigatório"}), 400
        
        email = data['email'].strip().lower()
        
        # Buscar usuário pelo email
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Por segurança, não revelar se o email existe ou não
            return jsonify({
                "mensagem": "Se o email estiver cadastrado em nossa base, você receberá um link para redefinir sua senha."
            }), 200
        
        # Gerar token de reset
        email_service = EmailService()
        reset_token = email_service.generate_reset_token()
        
        # Calcular expiração (1 hora)
        expiry_time = datetime.utcnow() + timedelta(seconds=current_app.config.get('PASSWORD_RESET_TOKEN_EXPIRY', 3600))
        
        # Salvar token no banco
        user.reset_token = reset_token
        user.reset_token_expires = expiry_time
        db.session.commit()
        
        # Enviar email
        email_sent = email_service.send_password_reset_email(
            user_email=user.email,
            user_name=user.name,
            reset_token=reset_token
        )
        
        if email_sent:
            return jsonify({
                "mensagem": "Se o email estiver cadastrado em nossa base, você receberá um link para redefinir sua senha."
            }), 200
        else:
            # Se falhou ao enviar email, limpar token
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            
            return jsonify({
                "erro": "Erro ao enviar email. Tente novamente mais tarde."
            }), 500
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao solicitar reset de senha: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao solicitar reset de senha: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Redefine a senha usando token"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        required_fields = ["token", "new_password"]
        for field in required_fields:
            if field not in data:
                return jsonify({"erro": f"Campo obrigatório: {field}"}), 400
        
        token = data['token']
        new_password = data['new_password']
        
        # Validar senha
        if len(new_password) < 6:
            return jsonify({"erro": "A senha deve ter pelo menos 6 caracteres"}), 400
        
        # Buscar usuário pelo token
        user = User.query.filter_by(reset_token=token).first()
        
        if not user:
            return jsonify({"erro": "Token inválido"}), 400
        
        # Verificar se o token expirou
        if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
            # Limpar token expirado
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            return jsonify({"erro": "Token expirado. Solicite um novo link de redefinição."}), 400
        
        # Atualizar senha
        user.password_hash = generate_password_hash(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Enviar email de confirmação
        email_service = EmailService()
        email_service.send_password_changed_email(user.email, user.name)
        
        return jsonify({
            "mensagem": "Senha redefinida com sucesso!"
        }), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao redefinir senha: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao redefinir senha: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Altera a senha do usuário logado"""
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        required_fields = ["current_password", "new_password"]
        for field in required_fields:
            if field not in data:
                return jsonify({"erro": f"Campo obrigatório: {field}"}), 400
        
        current_password = data['current_password']
        new_password = data['new_password']
        
        # Validar senha
        if len(new_password) < 6:
            return jsonify({"erro": "A senha deve ter pelo menos 6 caracteres"}), 400
        
        # Buscar usuário
        user = User.query.get(current_user['id'])
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Verificar senha atual
        if not check_password_hash(user.password_hash, current_password):
            return jsonify({"erro": "Senha atual incorreta"}), 400
        
        # Verificar se a nova senha é diferente da atual
        if check_password_hash(user.password_hash, new_password):
            return jsonify({"erro": "A nova senha deve ser diferente da senha atual"}), 400
        
        # Atualizar senha
        user.password_hash = generate_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Enviar email de confirmação
        email_service = EmailService()
        email_service.send_password_changed_email(user.email, user.name)
        
        return jsonify({
            "mensagem": "Senha alterada com sucesso!"
        }), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao alterar senha: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao alterar senha: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp.route('/validate-reset-token', methods=['POST'])
def validate_reset_token():
    """Valida se um token de reset é válido"""
    try:
        data = request.get_json()
        if not data or 'token' not in data:
            return jsonify({"erro": "Token é obrigatório"}), 400
        
        token = data['token']
        
        # Buscar usuário pelo token
        user = User.query.filter_by(reset_token=token).first()
        
        if not user:
            return jsonify({"valido": False, "mensagem": "Token inválido"}), 200
        
        # Verificar se o token expirou
        if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
            # Limpar token expirado
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            return jsonify({"valido": False, "mensagem": "Token expirado"}), 200
        
        return jsonify({
            "valido": True,
            "mensagem": "Token válido",
            "email": user.email
        }), 200
        
    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao validar token: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao validar token: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500 

@bp.route('/<string:user_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "tecadm")
def delete_user(user_id):
    """Deleta um usuário específico"""
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Verificar se o usuário está tentando deletar a si mesmo
        if current_user['id'] == user_id:
            return jsonify({"erro": "Não é possível deletar o próprio usuário"}), 400
        
        # Buscar usuário a ser deletado
        user_to_delete = User.query.get(user_id)
        if not user_to_delete:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Verificar se o usuário atual tem permissão para deletar o usuário alvo
        # Tecadm só pode deletar usuários da mesma cidade
        if current_user['role'] == "tecadm":
            current_city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if user_to_delete.city_id != current_city_id:
                return jsonify({"erro": "Sem permissão para deletar usuário de outra cidade"}), 403
        
        # Verificar se há relacionamentos que impedem a exclusão
        # Verificar se é um estudante
        student = Student.query.filter_by(user_id=user_id).first()
        if student:
            return jsonify({"erro": "Não é possível deletar usuário que é estudante. Delete o estudante primeiro."}), 400
        
        # Verificar se é um professor
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        if teacher:
            return jsonify({"erro": "Não é possível deletar usuário que é professor. Delete o professor primeiro."}), 400
        
        # Verificar se é um diretor/coordenador
        manager = Manager.query.filter_by(user_id=user_id).first()
        if manager:
            return jsonify({"erro": "Não é possível deletar usuário que é diretor/coordenador. Delete o cargo primeiro."}), 400
        
        # Deletar usuário
        db.session.delete(user_to_delete)
        db.session.commit()
        
        logging.info(f"Usuário {user_to_delete.email} deletado por {current_user['email']}")
        
        return jsonify({"mensagem": "Usuário deletado com sucesso"}), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao deletar usuário: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao deletar usuário: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500 