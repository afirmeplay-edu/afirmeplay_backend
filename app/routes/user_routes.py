from flask import Blueprint, jsonify, request
from app.decorators.role_required import get_current_tenant_id
from app.models.user import User, RoleEnum
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models.student import Student
from app.models.school import School
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.teacher import Teacher
from app.models.manager import Manager
from app.models.studentPasswordLog import StudentPasswordLog
from sqlalchemy.orm import joinedload
from app.utils.email_service import EmailService
from datetime import datetime, timedelta, date
from flask import current_app
import csv
import io
import uuid
from werkzeug.utils import secure_filename
import os
from openpyxl import load_workbook
from xlrd import open_workbook

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
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def list_users():
    try:
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Base query
        query = User.query

        # Filtragem baseada no papel do usuário
        if current_user['role'] == "admin":
            # Admin vê todos os usuários do sistema
            pass
        elif current_user['role'] == "tecadm":
            # Tecadm vê apenas usuários do seu município
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            query = query.filter_by(city_id=city_id)
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador vêem apenas usuários da sua escola
            from app.models.manager import Manager
            from app.models.school import School
            
            # Buscar o manager vinculado ao usuário atual
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or not manager.school_id:
                return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
            
            # Buscar a escola do manager
            school = School.query.get(manager.school_id)
            if not school:
                return jsonify({"erro": "Escola não encontrada"}), 400
            
            # Filtrar usuários por city_id da escola
            query = query.filter_by(city_id=school.city_id)
        elif current_user['role'] == "professor":
            # Professor vê apenas usuários do seu município
            city_id = current_user.get('city_id')
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

        if user.role == RoleEnum.ALUNO:
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
        
        # Exclusão em cascata - deletar registros relacionados primeiro
        deleted_relations = []
        
        # Verificar e deletar se é um estudante
        student = Student.query.filter_by(user_id=user_id).first()
        if student:
            db.session.delete(student)
            deleted_relations.append("estudante")
            logging.info(f"Deletando registro de estudante para usuário {user_id}")
        
        # Verificar e deletar se é um professor
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        if teacher:
            db.session.delete(teacher)
            deleted_relations.append("professor")
            logging.info(f"Deletando registro de professor para usuário {user_id}")
        
        # Verificar e deletar se é um diretor/coordenador/tecadm
        manager = Manager.query.filter_by(user_id=user_id).first()
        if manager:
            db.session.delete(manager)
            deleted_relations.append("manager")
            logging.info(f"Deletando registro de manager para usuário {user_id}")
        
        # Verificar e deletar vínculos com escolas (SchoolTeacher)
        from app.models.schoolTeacher import SchoolTeacher
        school_teachers = SchoolTeacher.query.filter_by(teacher_id=user_id).all()
        if school_teachers:
            for school_teacher in school_teachers:
                db.session.delete(school_teacher)
            deleted_relations.append(f"{len(school_teachers)} vínculos escolares")
            logging.info(f"Deletando {len(school_teachers)} vínculos escolares para usuário {user_id}")
        
        # Verificar e deletar vínculos com turmas (TeacherClass)
        from app.models.teacherClass import TeacherClass
        teacher_classes = TeacherClass.query.filter_by(teacher_id=user_id).all()
        if teacher_classes:
            for teacher_class in teacher_classes:
                db.session.delete(teacher_class)
            deleted_relations.append(f"{len(teacher_classes)} vínculos com turmas")
            logging.info(f"Deletando {len(teacher_classes)} vínculos com turmas para usuário {user_id}")
        
        # Verificar e deletar UserQuickLinks
        from app.models.userQuickLinks import UserQuickLinks
        user_quick_links = UserQuickLinks.query.filter_by(user_id=user_id).first()
        if user_quick_links:
            db.session.delete(user_quick_links)
            deleted_relations.append("atalhos rápidos")
            logging.info(f"Deletando atalhos rápidos para usuário {user_id}")
        
        # Deletar usuário
        db.session.delete(user_to_delete)
        db.session.commit()
        
        logging.info(f"Usuário {user_to_delete.email} deletado por {current_user['email']}")
        
        # Preparar mensagem de resposta
        if deleted_relations:
            relations_text = ", ".join(deleted_relations)
            message = f"Usuário deletado com sucesso. Registros relacionados também deletados: {relations_text}"
        else:
            message = "Usuário deletado com sucesso"
        
        return jsonify({
            "mensagem": message,
            "deleted_relations": deleted_relations
        }), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao deletar usuário: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao deletar usuário: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor"}), 500 

@bp.route('/bulk-upload-students', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def bulk_upload_students():
    """
    Rota para upload em massa de alunos via arquivo CSV ou Excel
    """
    try:
        # Verificar se há arquivo no request
        if 'file' not in request.files:
            return jsonify({"erro": "Nenhum arquivo enviado"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"erro": "Nenhum arquivo selecionado"}), 400
        
        # Verificar extensão do arquivo
        allowed_extensions = {'csv', 'xlsx', 'xls'}
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_extension not in allowed_extensions:
            return jsonify({"erro": "Formato de arquivo não suportado. Use CSV, XLSX ou XLS"}), 400
        
        # Obter usuário atual para verificar permissões
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Ler o arquivo
        try:
            if file_extension == 'csv':
                # Para CSV, tentar diferentes encodings
                try:
                    content = file.read().decode('utf-8')
                except UnicodeDecodeError:
                    file.seek(0)
                    content = file.read().decode('latin-1')
                
                # Processar CSV
                csv_reader = csv.DictReader(io.StringIO(content))
                rows = list(csv_reader)
            else:
                # Para Excel
                if file_extension == 'xlsx':
                    workbook = load_workbook(file, data_only=True)
                    sheet = workbook.active
                else:  # xls
                    workbook = open_workbook(file_contents=file.read())
                    sheet = workbook.sheet_by_index(0)
                
                # Converter para lista de dicionários
                rows = []
                if file_extension == 'xlsx':
                    headers = [cell.value for cell in sheet[1]]
                    for row in sheet.iter_rows(min_row=2):
                        row_data = {}
                        for i, cell in enumerate(row):
                            if i < len(headers) and headers[i]:
                                row_data[headers[i]] = cell.value
                        if any(row_data.values()):  # Ignorar linhas vazias
                            rows.append(row_data)
                else:  # xls
                    headers = [sheet.cell_value(0, i) for i in range(sheet.ncols)]
                    for row_idx in range(1, sheet.nrows):
                        row_data = {}
                        for col_idx in range(sheet.ncols):
                            if col_idx < len(headers) and headers[col_idx]:
                                row_data[headers[col_idx]] = sheet.cell_value(row_idx, col_idx)
                        if any(row_data.values()):  # Ignorar linhas vazias
                            rows.append(row_data)
        except Exception as e:
            return jsonify({"erro": f"Erro ao ler arquivo: {str(e)}"}), 400
        
        # Verificar colunas obrigatórias
        required_columns = ['nome', 'email', 'data_nascimento', 'escola', 'endereco_escola', 'estado_escola', 'municipio_escola', 'serie', 'turma']
        if rows:
            missing_columns = [col for col in required_columns if col not in rows[0].keys()]
        else:
            missing_columns = required_columns
        
        if missing_columns:
            return jsonify({
                "erro": f"Colunas obrigatórias ausentes: {', '.join(missing_columns)}",
                "colunas_encontradas": list(rows[0].keys()) if rows else [],
                "colunas_obrigatorias": required_columns
            }), 400
        
        # Limpar dados
        rows = [row for row in rows if all(str(row.get(col, '')).strip() for col in ['nome', 'email', 'escola', 'endereco_escola', 'estado_escola', 'municipio_escola', 'serie', 'turma'])]
        
        # Converter data de nascimento
        def parse_date(date_value):
            # Se o valor for None ou vazio, retornar None
            if not date_value:
                return None
            
            # Se o valor já for um objeto date, retornar diretamente
            if isinstance(date_value, date):
                return date_value
            
            # Se o valor for um objeto datetime.datetime, converter para date
            if isinstance(date_value, datetime):
                return date_value.date()
            
            # Se for string, fazer o parse como antes
            try:
                date_str = str(date_value).strip()
                if not date_str:
                    return None
                
                # Tentar diferentes formatos de data
                for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y', '%d-%m-%y']:
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except:
                        continue
                
                # Se nenhum formato funcionar, tentar parse automático com YYYY-MM-DD
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return None
        
        # Processar cada linha para adicionar data parseada
        for row in rows:
            row['data_nascimento_parsed'] = parse_date(row.get('data_nascimento'))
        
        # Validar dados e processar
        results = {
            "total_linhas": len(rows),
            "sucessos": 0,
            "erros": [],
            "alunos_criados": []
        }
        
        # Verificar permissões baseadas no papel do usuário
        allowed_schools = []
        if current_user['role'] == "admin":
            # Admin pode criar alunos em qualquer escola
            allowed_schools = [school.id for school in School.query.all()]
        elif current_user['role'] == "tecadm":
            # Tecadm pode criar alunos em escolas da sua cidade
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if city_id:
                allowed_schools = [school.id for school in School.query.filter_by(city_id=city_id).all()]
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador podem criar alunos apenas na sua escola
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if manager and manager.school_id:
                allowed_schools = [manager.school_id]
        
        if not allowed_schools:
            return jsonify({"erro": "Usuário não tem permissão para criar alunos em nenhuma escola"}), 403
        
        # Processar cada linha
        for index, row in enumerate(rows):
            try:
                # Validar email
                email = str(row.get('email', '')).strip().lower()
                if not email or '@' not in email:
                    results["erros"].append({
                        "linha": index + 2,  # +2 porque index começa em 0 e há cabeçalho
                        "campo": "email",
                        "valor": email,
                        "erro": "Email inválido"
                    })
                    continue
                
                # Verificar se email já existe
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    # Verificar se o usuário já é um aluno
                    existing_student = Student.query.filter_by(user_id=existing_user.id).first()
                    if existing_student:
                        results["erros"].append({
                            "linha": index + 2,
                            "campo": "email",
                            "valor": email,
                            "erro": "Aluno já cadastrado no sistema"
                        })
                        continue
                    else:
                        results["erros"].append({
                            "linha": index + 2,
                            "campo": "email",
                            "valor": email,
                            "erro": "Email já cadastrado para outro tipo de usuário"
                        })
                        continue
                
                # Validar matrícula se fornecida (opcional)
                matricula_raw = row.get('matricula', '')
                # Normalizar matrícula: tratar None, "None", "null", "", etc. como vazio
                if matricula_raw is None:
                    matricula = None
                else:
                    matricula = str(matricula_raw).strip()
                    # Se após strip for vazio ou valores como "None", "null", etc., tratar como None
                    if not matricula or matricula.lower() in ['none', 'null', 'nulo', '']:
                        matricula = None
                
                # Verificar se matrícula já existe (apenas se foi fornecida)
                if matricula and User.query.filter_by(registration=matricula).first():
                    results["erros"].append({
                        "linha": index + 2,
                        "campo": "matricula",
                        "valor": matricula,
                        "erro": "Matrícula já cadastrada"
                    })
                    continue
                
                # Buscar escola existente (busca exata case-insensitive)
                escola_nome = str(row.get('escola', '')).strip()
                escola_nome_normalizado = escola_nome.lower()
                escola = School.query.filter(func.lower(School.name) == escola_nome_normalizado).first()
                
                if not escola:
                    results["erros"].append({
                        "linha": index + 2,
                        "campo": "escola",
                        "valor": escola_nome,
                        "erro": "Escola não encontrada"
                    })
                    continue
                
                # Verificar se usuário tem permissão para esta escola
                if escola.id not in allowed_schools:
                    results["erros"].append({
                        "linha": index + 2,
                        "campo": "escola",
                        "valor": escola_nome,
                        "erro": "Sem permissão para criar alunos nesta escola"
                    })
                    continue
                
                # Buscar série existente (busca exata case-insensitive)
                serie_nome = str(row.get('serie', '')).strip()
                serie_nome_normalizado = serie_nome.lower()
                serie = Grade.query.filter(func.lower(Grade.name) == serie_nome_normalizado).first()
                if not serie:
                    results["erros"].append({
                        "linha": index + 2,
                        "campo": "serie",
                        "valor": serie_nome,
                        "erro": "Série não encontrada"
                    })
                    continue
                
                # Buscar turma existente (busca exata case-insensitive)
                turma_nome = str(row.get('turma', '')).strip()
                turma_nome_normalizado = turma_nome.lower()
                turma = Class.query.filter(
                    func.lower(Class.name) == turma_nome_normalizado,
                    Class.school_id == escola.id,
                    Class.grade_id == serie.id
                ).first()
                if not turma:
                    results["erros"].append({
                        "linha": index + 2,
                        "campo": "turma",
                        "valor": turma_nome,
                        "erro": f"Turma não encontrada na escola {escola_nome} e série {serie_nome}"
                    })
                    continue
                
                # Verificar se já existe aluno na mesma turma (por matrícula, se fornecida)
                if matricula:
                    existing_student_in_class = Student.query.filter_by(
                        class_id=turma.id,
                        registration=matricula
                    ).first()
                    if existing_student_in_class:
                        results["erros"].append({
                            "linha": index + 2,
                            "campo": "matricula",
                            "valor": matricula,
                            "erro": f"Aluno com esta matrícula já está cadastrado na turma {turma_nome}"
                        })
                        continue
                
                # Validar data de nascimento
                data_nascimento = row.get('data_nascimento_parsed')
                if not data_nascimento:
                    results["erros"].append({
                        "linha": index + 2,
                        "campo": "data_nascimento",
                        "valor": row.get('data_nascimento', ''),
                        "erro": "Data de nascimento inválida"
                    })
                    continue
                
                # Gerar senha aleatória antes de criptografar
                senha_gerada = str(uuid.uuid4())
                
                # Criar usuário
                novo_usuario = User(
                    id=str(uuid.uuid4()),
                    name=str(row.get('nome', '')).strip(),
                    email=email,
                    password_hash=generate_password_hash(senha_gerada),  # Senha aleatória criptografada
                    registration=matricula if matricula else None,
                    role=RoleEnum.ALUNO,
                    city_id=escola.city_id
                )
                db.session.add(novo_usuario)
                db.session.flush()  # Flush para obter o ID do usuário
                
                # Criar estudante
                novo_aluno = Student(
                    id=str(uuid.uuid4()),
                    name=str(row.get('nome', '')).strip(),
                    registration=matricula if matricula else None,
                    birth_date=data_nascimento,
                    profile_picture=str(row.get('foto_perfil', '')).strip() if row.get('foto_perfil') else None,
                    user_id=novo_usuario.id,
                    school_id=escola.id,
                    grade_id=serie.id,
                    class_id=turma.id
                )
                db.session.add(novo_aluno)
                db.session.flush()  # Flush para obter o ID do aluno
                
                # Salvar senha em texto plano na tabela de log
                password_log = StudentPasswordLog(
                    student_name=str(row.get('nome', '')).strip(),
                    email=email,
                    password=senha_gerada,  # Senha em texto plano (antes de criptografar)
                    registration=matricula if matricula else None,
                    user_id=novo_usuario.id,
                    student_id=novo_aluno.id,
                    class_id=turma.id,
                    grade_id=serie.id,
                    school_id=escola.id,
                    city_id=escola.city_id
                )
                db.session.add(password_log)
                
                # Commit para esta linha
                db.session.commit()
                
                results["sucessos"] += 1
                results["alunos_criados"].append({
                    "nome": novo_aluno.name,
                    "email": novo_usuario.email,
                    "matricula": novo_aluno.registration,
                    "escola": escola.name,
                    "serie": serie.name,
                    "turma": turma.name
                })
                
                logging.info(f"Aluno criado com sucesso: {novo_aluno.name} ({novo_usuario.email})")
                
            except Exception as e:
                db.session.rollback()
                results["erros"].append({
                    "linha": index + 2,
                    "campo": "geral",
                    "valor": "",
                    "erro": f"Erro inesperado: {str(e)}"
                })
                logging.error(f"Erro ao processar linha {index + 2}: {str(e)}")
                continue
        
        # Preparar resposta
        if results["sucessos"] > 0:
            message = f"Upload concluído! {results['sucessos']} alunos criados com sucesso."
            if results["erros"]:
                message += f" {len(results['erros'])} erros encontrados."
        else:
            message = "Nenhum aluno foi criado. Verifique os erros abaixo."
        
        return jsonify({
            "mensagem": message,
            "resumo": {
                "total_linhas": results["total_linhas"],
                "sucessos": results["sucessos"],
                "erros": len(results["erros"])
            },
            "alunos_criados": results["alunos_criados"],
            "erros": results["erros"]
        }), 200 if results["sucessos"] > 0 else 400
        
    except Exception as e:
        logging.error(f"Erro inesperado no upload em massa: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro interno do servidor", "detalhes": str(e)}), 500 