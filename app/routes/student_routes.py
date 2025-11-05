from flask import Blueprint, request, jsonify, Response
from app.models.student import Student
from app.models.user import User, RoleEnum
from app.models.school import School
from app.models.studentPasswordLog import StudentPasswordLog
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging
from app.decorators.role_required import role_required, get_current_user_from_token
from app.decorators.role_required import get_current_tenant_id
from datetime import datetime
from app import db
from flask_jwt_extended import jwt_required
from werkzeug.security import generate_password_hash
from marshmallow import ValidationError
from app.models.studentAnswer import StudentAnswer
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.classTest import ClassTest
from app.models.city import City
from app.models.manager import Manager
from app.models.teacher import Teacher
from app.models.schoolTeacher import SchoolTeacher
from app.models.teacherClass import TeacherClass
from sqlalchemy.orm import joinedload
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO

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
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
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

        # Buscar turma para determinar city_id (necessário tanto para usuário novo quanto existente)
        class_obj = Class.query.get(data["class_id"])
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404
        
        # Buscar escola da turma
        school = School.query.get(class_obj.school_id)
        if not school:
            return jsonify({"error": "School not found for the specified class"}), 404
        
        # Determinar city_id baseado na escola
        city_id = school.city_id

        # Tenta encontrar o usuário pelo email
        usuario = User.query.filter_by(email=data["email"]).first()
        usuario_foi_criado_agora = False  # Flag para saber se criamos o usuário agora

        if usuario:
            logging.info(f"Usuário existente encontrado: {usuario.email}")
            # Verificar se o usuário já é um aluno
            if Student.query.filter_by(user_id=usuario.id).first():
                logging.warning(f"Usuário {usuario.email} já é um aluno.") 
                return jsonify({"error": "User is already a student"}), 400
        else:
            logging.info("Usuário não encontrado, criando novo usuário.")
            usuario_foi_criado_agora = True  # Marcar que vamos criar o usuário agora
            # Verificar se matrícula já existe (caso fornecida) - apenas para novo usuário
            if data.get("registration") and User.query.filter_by(registration=data["registration"]).first():
                return jsonify({"error": "Registration number already exists"}), 400
            
            # Criar usuário (role padrão: aluno) com city_id da escola
            usuario = User(
                name=data["name"],
                email=data["email"],
                password_hash=generate_password_hash(data["password"]),
                registration=data.get("registration"),
                role=RoleEnum("aluno"),
                city_id=city_id
            )
            db.session.add(usuario)
            db.session.flush() 
            print(usuario.id)
            logging.info(f"Novo usuário criado com sucesso. ID: {usuario.id}")

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
        db.session.flush()  # Flush para obter o ID do aluno
        
        # Salvar senha em texto plano na tabela de log apenas se criamos um novo usuário
        # (quando o usuário já existe, não temos a senha original em texto plano)
        if usuario_foi_criado_agora:
            password_log = StudentPasswordLog(
                student_name=data["name"],
                email=data["email"],
                password=data["password"],  # Senha em texto plano
                registration=data.get("registration"),
                user_id=usuario.id,
                student_id=novo_aluno.id,
                class_id=data["class_id"],
                grade_id=data.get("grade_id"),
                school_id=class_obj.school_id,
                city_id=city_id
            )
            db.session.add(password_log)
        
        db.session.commit()

        logging.info(f"Aluno criado com sucesso para o usuário ID: {usuario.id}")

        return jsonify({
            "message": "Student and/or User created successfully!",
            "user": {
                "id": usuario.id,
                "name": usuario.name,
                "email": usuario.email,
                "registration": usuario.registration,
                "role": usuario.role.value,
                "city_id": usuario.city_id
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


# Helper function to format student data with related details
def format_student_details(student, user=None, school=None, class_obj=None, grade=None):
    user_details = None
    if user:
        user_details = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "registration": user.registration,
            "role": user.role.value,
            "city_id": user.city_id,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }

    school_details = None
    if school:
        school_details = {
            "id": school.id,
            "name": school.name,
            "domain": school.domain,
            "address": school.address,
            "city_id": school.city_id,
            "created_at": school.created_at.isoformat() if school.created_at else None
        }

    class_details = None
    if class_obj:
        class_details = {
            "id": class_obj.id,
            "name": class_obj.name,
            "school_id": class_obj.school_id,
            "grade_id": str(class_obj.grade_id) if class_obj.grade_id else None
        }

    grade_details = None
    if grade:
        grade_details = {
            "id": grade.id,
            "name": grade.name
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
        "user": user_details,
        "school": school_details,
        "class": class_details,
        "grade": grade_details
    }

# GET - Listar alunos
@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def listar_alunos():
    try:
        user = get_current_user_from_token()

        if not user:
            return jsonify({"message": "Usuário não encontrado"}), 404

        # Base query with joins - usando LEFT JOIN para incluir alunos sem escola
        query = db.session.query(
            Student,
            User,
            School,
            Class,
            Grade
        ).join(
            User, Student.user_id == User.id
        ).outerjoin(
            School, Student.school_id == School.id
        ).outerjoin(
            Class, Student.class_id == Class.id
        ).outerjoin(
            Grade, Student.grade_id == Grade.id
        )

        students = []
        if user['role'] == "admin":
            # Admin pode ver todos os alunos
            students = query.all()
        elif user['role'] == "professor":
            # Professor só vê alunos das escolas onde está vinculado
            from app.models.teacher import Teacher
            from app.models.schoolTeacher import SchoolTeacher
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"message": "Professor não encontrado"}), 404
            
            # Buscar escolas onde o professor está vinculado
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            school_ids = [ts.school_id for ts in teacher_schools]
            
            if school_ids:
                students = query.filter(Student.school_id.in_(school_ids)).all()
            else:
                return jsonify({"message": "Professor não está alocado em nenhuma escola"}), 400
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador veem alunos apenas de sua escola
            # Precisamos buscar a escola do usuário
            from app.models.teacher import Teacher
            from app.models.schoolTeacher import SchoolTeacher
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"message": "Usuário não encontrado como professor/diretor/coordenador"}), 404
            
            # Buscar a escola do diretor/coordenador
            teacher_school = SchoolTeacher.query.filter_by(teacher_id=teacher.id).first()
            if not teacher_school:
                return jsonify({"message": "Diretor/Coordenador não está vinculado a nenhuma escola"}), 400
            
            students = query.filter(Student.school_id == teacher_school.school_id).all()
        else:
            # TecAdmin vê alunos de todas as escolas do município + alunos sem escola mas com city_id
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return jsonify({"message": "ID da cidade não disponível para este usuário"}), 400

            # Busca todas as escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).all()
            school_ids = [school.id for school in schools_in_city]

            # Busca alunos das escolas da cidade OU alunos sem escola mas com city_id correto
            students = query.filter(
                db.or_(
                    Student.school_id.in_(school_ids),
                    db.and_(Student.school_id.is_(None), User.city_id == city_id)
                )
            ).all()

        return jsonify([format_student_details(student, user, school, class_obj, grade) 
                       for student, user, school, class_obj, grade in students]), 200

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

        # Atualizar city_id do usuário se o aluno foi movido para outra escola
        if aluno.school_id:
            school = School.query.get(aluno.school_id)
            if school and school.city_id != usuario.city_id:
                usuario.city_id = school.city_id
                logging.info(f"Atualizando city_id do aluno {usuario.id} para {school.city_id}")

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

@bp.route('/available', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def get_available_students():
    """
    Lista alunos que não estão vinculados a nenhuma escola (disponíveis para alocação)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"message": "Usuário não encontrado"}), 404

        # Buscar TODOS os usuários com role aluno (disponíveis para alocação)
        # Isso inclui tanto usuários sem registro Student quanto com Student mas sem school_id
        all_users_with_aluno_role = db.session.query(
            User
        ).filter(
            User.role == RoleEnum.ALUNO
        ).all()
        
        logging.info(f"Todos os usuários com role aluno: {[(u.id, u.name, u.city_id) for u in all_users_with_aluno_role]}")
        
        # Filtrar apenas os que são realmente "disponíveis" (sem escola)
        available_students = []
        
        for user_obj in all_users_with_aluno_role:
            # Verificar se tem registro na tabela Student
            student_record = Student.query.filter_by(user_id=user_obj.id).first()
            
            if student_record:
                # Se tem registro Student, só é disponível se school_id for NULL
                if student_record.school_id is None:
                    available_students.append((student_record, user_obj))
                    logging.info(f"Aluno disponível (com Student, sem escola): {user_obj.name} (city_id: {user_obj.city_id})")
            else:
                # Se não tem registro Student, é disponível
                available_students.append((None, user_obj))
                logging.info(f"Aluno disponível (sem Student): {user_obj.name} (city_id: {user_obj.city_id})")
        
        students = available_students
        logging.info(f"Total de alunos disponíveis: {len(students)}")

        # Filtrar por permissões
        logging.info(f"Verificando permissões para role: {user['role']}")
        
        if user['role'] == "admin":
            # Admin vê todos os alunos disponíveis
            logging.info("Admin - permitindo acesso a todos os alunos disponíveis")
            pass
        elif user['role'] == "tecadm":
            # Tecadm vê apenas alunos do seu município
            city_id = user.get('tenant_id') or user.get('city_id')
            logging.info(f"Tecadm - city_id: {city_id}")
            if not city_id:
                return jsonify({"message": "ID da cidade não disponível para este usuário"}), 400
            
            # Log antes do filtro
            print(f"Alunos antes do filtro por city_id: {[(s[0].id if s[0] else 'None', s[1].id, s[1].name, s[1].city_id) for s in students]}")
            logging.info(f"Alunos antes do filtro por city_id: {[(s[0].id if s[0] else 'None', s[1].id, s[1].name, s[1].city_id) for s in students]}")
            
            # Filtro com verificação detalhada
            filtered_students = []
            for s in students:
                user_city_id = s[1].city_id
                logging.info(f"Comparando: user_city_id={user_city_id} (tipo: {type(user_city_id)}) vs city_id={city_id} (tipo: {type(city_id)})")
                if user_city_id == city_id:
                    filtered_students.append(s)
                    logging.info(f"Match encontrado para usuário {s[1].name} (city_id: {user_city_id})")
                else:
                    logging.info(f"Não match para usuário {s[1].name} (city_id: {user_city_id})")
            
            students = filtered_students
            logging.info(f"Tecadm - {len(students)} alunos filtrados por city_id")
            
            # Log após o filtro
            logging.info(f"Alunos após filtro por city_id: {[(s[0].id if s[0] else 'None', s[1].id, s[1].name, s[1].city_id) for s in students]}")
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador podem ver alunos disponíveis do seu município
            city_id = user.get('tenant_id') or user.get('city_id')
            logging.info(f"{user['role'].title()} - city_id: {city_id}")
            if not city_id:
                return jsonify({"message": "ID da cidade não disponível para este usuário"}), 400
            
            # Log antes do filtro
            print(f"Alunos antes do filtro por city_id: {[(s[0].id if s[0] else 'None', s[1].id, s[1].name, s[1].city_id) for s in students]}")
            logging.info(f"Alunos antes do filtro por city_id: {[(s[0].id if s[0] else 'None', s[1].id, s[1].name, s[1].city_id) for s in students]}")
            
            # Filtro com verificação detalhada
            filtered_students = []
            for s in students:
                user_city_id = s[1].city_id
                logging.info(f"Comparando: user_city_id={user_city_id} (tipo: {type(user_city_id)}) vs city_id={city_id} (tipo: {type(city_id)})")
                if user_city_id == city_id:
                    filtered_students.append(s)
                    logging.info(f"Match encontrado para usuário {s[1].name} (city_id: {user_city_id})")
                else:
                    logging.info(f"Não match para usuário {s[1].name} (city_id: {user_city_id})")
            
            students = filtered_students
            print(f"Alunos após filtro por city_id: {[(s[0].id if s[0] else 'None', s[1].id, s[1].name, s[1].city_id) for s in students]}")
            logging.info(f"{user['role'].title()} - {len(students)} alunos filtrados por city_id")
            
            # Log após o filtro
            print(f"Alunos após filtro por city_id: {[(s[0].id if s[0] else 'None', s[1].id, s[1].name, s[1].city_id) for s in students]}")
            logging.info(f"Alunos após filtro por city_id: {[(s[0].id if s[0] else 'None', s[1].id, s[1].name, s[1].city_id) for s in students]}")
        elif user['role'] == "professor":
            # Professor não pode ver alunos disponíveis
            logging.info(f"Role {user['role']} - negando acesso")
            return jsonify({"message": "Você não tem permissão para visualizar alunos disponíveis"}), 403

        result = []
        for student, user_obj in students:
            # Se student é None, usar dados do user_obj
            if student is None:
                result.append({
                    "id": None,  # Não tem ID de student
                    "name": user_obj.name,
                    "registration": user_obj.registration,
                    "birth_date": None,  # Não tem birth_date no user
                    "user": {
                        "id": user_obj.id,
                        "name": user_obj.name,
                        "email": user_obj.email,
                        "registration": user_obj.registration,
                        "role": user_obj.role.value,
                        "city_id": user_obj.city_id
                    }
                })
            else:
                result.append({
                    "id": student.id,
                    "name": student.name,
                    "registration": student.registration,
                    "birth_date": student.birth_date.isoformat() if student.birth_date else None,
                    "user": {
                        "id": user_obj.id,
                        "name": user_obj.name,
                        "email": user_obj.email,
                        "registration": user_obj.registration,
                        "role": user_obj.role.value,
                        "city_id": user_obj.city_id
                    }
                })

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Erro ao listar alunos disponíveis: {str(e)}", exc_info=True)
        return jsonify({"message": "Erro ao listar alunos disponíveis", "details": str(e)}), 500

@bp.route('/school/<string:school_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
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
        if user['role'] == "admin":
            # Admin can access any school
            pass
        elif user['role'] == "professor":
            # Professor can only see students from their assigned schools
            from app.models.teacher import Teacher
            from app.models.schoolTeacher import SchoolTeacher
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"message": "Professor não encontrado"}), 404
            
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            teacher_school_ids = [ts.school_id for ts in teacher_schools]
            
            if school_id not in teacher_school_ids:
                logging.warning(f"Professor {user.get('id')} tried to access students from school {school_id}")
                return jsonify({"message": "You don't have permission to view students from this school"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Director and coordinator can only see students from their school
            from app.models.manager import Manager
            
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if not manager:
                return jsonify({"message": "Diretor/Coordenador não encontrado na tabela manager"}), 404
            
            if not manager.school_id or manager.school_id != school_id:
                logging.warning(f"User {user.get('id')} tried to access students from school {school_id}")
                return jsonify({"message": "You don't have permission to view students from this school"}), 403
        else:
            # TecAdmin can access schools in their municipality
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id or school.city_id != city_id:
                logging.warning(f"User {user.get('id')} tried to access students from school in different city")
                return jsonify({"message": "You don't have permission to view students from this school"}), 403

        # Get all students from the school with related data using joins
        try:
            students = db.session.query(
                Student,
                User,
                School,
                Class,
                Grade
            ).join(
                User, Student.user_id == User.id
            ).join(
                School, Student.school_id == School.id
            ).join(
                Class, Student.class_id == Class.id
            ).outerjoin(
                Grade, Student.grade_id == Grade.id
            ).filter(
                Student.school_id == school_id
            ).all()
            
            logging.info(f"Found {len(students)} students for school {school_id}")
        except SQLAlchemyError as e:
            logging.error(f"Database error while querying students: {str(e)}")
            return jsonify({"message": "Error querying students from database"}), 500

        return jsonify([format_student_details(student, user, school, class_obj, grade) 
                       for student, user, school, class_obj, grade in students]), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while fetching students by school: {str(e)}")
        return jsonify({"message": "Internal server error while querying data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_students_by_school route: {str(e)}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred", "details": str(e)}), 500

@bp.route('/classes/<string:class_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor","tecadm")
def get_students_by_class(class_id):
    try:
        logging.info(f"Fetching students for class_id: {class_id}")

        # Check if the class exists (optional, but good practice)
        class_obj = Class.query.get(class_id)
        if not class_obj:
            logging.warning(f"Class not found with ID: {class_id}")
            return jsonify({"message": "Class not found"}), 404

        # Query with explicit joins to get all related data
        students = db.session.query(
            Student,
            User,
            School,
            Class,
            Grade
        ).join(
            User, Student.user_id == User.id
        ).join(
            School, Student.school_id == School.id
        ).join(
            Class, Student.class_id == Class.id
        ).outerjoin(
            Grade, Student.grade_id == Grade.id
        ).filter(
            Student.class_id == class_id
        ).all()

        if not students:
            logging.info(f"No students found for class_id: {class_id}")
            return jsonify([]), 200  # Return empty list if no students found

        return jsonify([format_student_details(student, user, school, class_obj, grade) 
                       for student, user, school, class_obj, grade in students]), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while fetching students by class: {str(e)}")
        return jsonify({"message": "Internal server error while querying data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_students_by_class route: {str(e)}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred", "details": str(e)}), 500

@bp.route('/school/<string:school_id>/class/<string:class_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor","tecadm")
def get_students_by_school_and_class(school_id, class_id):
    try:
        logging.info(f"Fetching students for school_id: {school_id} and class_id: {class_id}")

        # Primeiro validar se escola e turma existem
        school = School.query.get(school_id)
        if not school:
            logging.warning(f"School not found with id: {school_id}")
            return jsonify({"error": "School not found"}), 404

        class_obj = Class.query.get(class_id)
        if not class_obj:
            logging.warning(f"Class not found with id: {class_id}")
            return jsonify({"error": "Class not found"}), 404

        # Validar se a turma pertence à escola especificada
        if class_obj.school_id != school_id:
            logging.warning(f"Class {class_id} does not belong to school {school_id}")
            return jsonify({"error": "Class does not belong to the specified school"}), 400

        # Agora buscar os alunos com validação correta
        # Primeiro buscar apenas os alunos para garantir que todos sejam retornados
        students = Student.query.filter_by(
            school_id=school_id,
            class_id=class_id
        ).all()
        
        if not students:
            logging.info(f"No students found for school_id: {school_id} and class_id: {class_id}")
            return jsonify([]), 200  # Return empty list if no students found
        
        # Agora buscar os dados relacionados para cada aluno
        formatted_students = []
        for student in students:
            user = User.query.get(student.user_id)
            school = School.query.get(student.school_id)
            class_obj = Class.query.get(student.class_id)
            grade = Grade.query.get(student.grade_id) if student.grade_id else None
            
            formatted_students.append(format_student_details(student, user, school, class_obj, grade))
        
        return jsonify(formatted_students), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while fetching students by school and class: {str(e)}")
        return jsonify({"message": "Internal server error while querying data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_students_by_school_and_class route: {str(e)}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred", "details": str(e)}), 500

@bp.route('/<string:student_id>/class', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "aluno")
def get_student_class(student_id):
    try:
        logging.info(f"Fetching class for user_id: {student_id}")

        # Buscar o aluno com suas relações
        student = db.session.query(
            Student,
            User,
            School,
            Class,
            Grade
        ).join(
            User, Student.user_id == User.id
        ).join(
            School, Student.school_id == School.id
        ).join(
            Class, Student.class_id == Class.id
        ).join(
            Grade, Student.grade_id == Grade.id
        ).filter(
            Student.user_id == student_id
        ).first()

        if not student:
            logging.warning(f"Student not found with user_id: {student_id}")
            return jsonify({"message": "Student not found"}), 404

        student_obj, user, school, class_obj, grade = student

        # Verificar permissões do usuário
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"message": "User not found"}), 404

        if current_user['role'] == "professor":
            # Professor só pode ver alunos da escola onde está alocado
            if current_user.get('school_id') != student_obj.school_id:
                logging.warning(f"Professor {current_user.get('id')} tried to access student from different school")
                return jsonify({"message": "You don't have permission to view this student's class"}), 403
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem ver alunos de escolas da sua cidade
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"message": "City ID not available"}), 400
            if school.city_id != city_id:
                logging.warning(f"User {current_user.get('id')} tried to access student from different city")
                return jsonify({"message": "You don't have permission to view this student's class"}), 403

        # Buscar avaliações aplicadas à classe usando o relacionamento class_tests
        class_tests = ClassTest.query.filter_by(class_id=class_obj.id).all()
        applied_test_ids = [ct.test_id for ct in class_tests]

        # Formatar resposta com detalhes da classe
        class_details = {
            "id": class_obj.id,
            "name": class_obj.name,
            "school_id": class_obj.school_id,
            "grade_id": str(class_obj.grade_id) if class_obj.grade_id else None,
            "school": {
                "id": school.id,
                "name": school.name,
                "domain": school.domain,
                "address": school.address,
                "city_id": school.city_id
            },
            "grade": {
                "id": grade.id,
                "name": grade.name
            } if grade else None,
            "student": {
                "id": student_obj.id,
                "name": student_obj.name,
                "registration": student_obj.registration,
                "birth_date": student_obj.birth_date.isoformat() if student_obj.birth_date else None,
                "user_id": student_obj.user_id
            },
            "applied_tests": {
                "total": len(applied_test_ids),
                "test_ids": applied_test_ids
            }
        }

        return jsonify(class_details), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while fetching student class: {str(e)}")
        return jsonify({"message": "Internal server error while querying data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_student_class route: {str(e)}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred", "details": str(e)}), 500

@bp.route('/me', methods=['GET'])
@jwt_required()
@role_required("aluno")
def get_current_student():
    """
    Retorna os dados do aluno atual baseado no token JWT
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Buscar aluno pelo user_id
        student = db.session.query(
            Student,
            User,
            School,
            Class,
            Grade
        ).join(
            User, Student.user_id == User.id
        ).join(
            School, Student.school_id == School.id
        ).join(
            Class, Student.class_id == Class.id
        ).outerjoin(
            Grade, Student.grade_id == Grade.id
        ).filter(
            Student.user_id == user['id']
        ).first()

        if not student:
            return jsonify({"error": "Dados do aluno não encontrados"}), 404

        student_obj, user_obj, school, class_obj, grade = student

        return jsonify(format_student_details(student_obj, user_obj, school, class_obj, grade)), 200

    except Exception as e:
        logging.error(f"Erro ao obter dados do aluno atual: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter dados do aluno", "details": str(e)}), 500

@bp.route('/password-report', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_password_report():
    """
    Retorna relatório de alunos com suas senhas em formato Excel
    
    Query Parameters:
        city_id: Filtrar por cidade (opcional)
        school_id: Filtrar por escola (opcional)
        class_id: Filtrar por turma (opcional)
        grade_id: Filtrar por série (opcional)
        date_from: Data inicial (opcional, formato: YYYY-MM-DD)
        date_to: Data final (opcional, formato: YYYY-MM-DD)
    
    Returns:
        Arquivo Excel (.xlsx) com relatório de senhas
    """
    try:
        # 1. Obter usuário atual
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # 2. Construir query base
        query = db.session.query(
            StudentPasswordLog,
            School,
            City,
            Class,
            Grade
        ).outerjoin(
            School, StudentPasswordLog.school_id == School.id
        ).outerjoin(
            City, StudentPasswordLog.city_id == City.id
        ).outerjoin(
            Class, StudentPasswordLog.class_id == Class.id
        ).outerjoin(
            Grade, StudentPasswordLog.grade_id == Grade.id
        )
        
        # 3. Aplicar filtros automáticos baseados no role
        if user['role'] == "admin":
            # Admin pode ver todos os alunos
            pass
        elif user['role'] == "tecadm":
            # Tecadm vê apenas alunos do seu município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return jsonify({"error": "ID da cidade não disponível para este usuário"}), 400
            query = query.filter(StudentPasswordLog.city_id == city_id)
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador veem apenas alunos da sua escola
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if not manager:
                return jsonify({"error": "Diretor/Coordenador não encontrado na tabela manager"}), 404
            if not manager.school_id:
                return jsonify({"error": "Diretor/Coordenador não está vinculado a nenhuma escola"}), 400
            query = query.filter(StudentPasswordLog.school_id == manager.school_id)
        elif user['role'] == "professor":
            # Professor vê apenas alunos das escolas onde está vinculado
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Professor não encontrado na tabela teacher"}), 404
            
            # Buscar escolas onde o professor está vinculado
            school_teachers = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            school_ids = [st.school_id for st in school_teachers]
            
            if not school_ids:
                return jsonify({"error": "Professor não está vinculado a nenhuma escola"}), 400
            
            # Aplicar filtro por escolas
            query = query.filter(StudentPasswordLog.school_id.in_(school_ids))
            
            # Buscar turmas onde o professor está vinculado
            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            class_ids = [tc.class_id for tc in teacher_classes]
            
            # Se professor está vinculado a turmas específicas, filtrar por elas
            # Se não houver turmas vinculadas, mostrar todas as turmas das escolas vinculadas
            if class_ids:
                query = query.filter(StudentPasswordLog.class_id.in_(class_ids))
        
        # 4. Aplicar filtros opcionais (query parameters)
        city_id_param = request.args.get('city_id')
        school_id_param = request.args.get('school_id')
        class_id_param = request.args.get('class_id')
        grade_id_param = request.args.get('grade_id')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        if city_id_param:
            query = query.filter(StudentPasswordLog.city_id == city_id_param)
        if school_id_param:
            query = query.filter(StudentPasswordLog.school_id == school_id_param)
        if class_id_param:
            query = query.filter(StudentPasswordLog.class_id == class_id_param)
        if grade_id_param:
            query = query.filter(StudentPasswordLog.grade_id == grade_id_param)
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(StudentPasswordLog.created_at >= date_from_obj)
            except ValueError:
                return jsonify({"error": "Formato de data inválido para date_from. Use YYYY-MM-DD"}), 400
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                # Adicionar 23:59:59 para incluir todo o dia
                date_to_datetime = datetime.combine(date_to_obj, datetime.max.time())
                query = query.filter(StudentPasswordLog.created_at <= date_to_datetime)
            except ValueError:
                return jsonify({"error": "Formato de data inválido para date_to. Use YYYY-MM-DD"}), 400
        
        # 5. Ordenar por data de criação (mais recentes primeiro)
        query = query.order_by(StudentPasswordLog.created_at.desc())
        
        # 6. Executar query
        results = query.all()
        
        if not results:
            return jsonify({"error": "Nenhum registro encontrado com os filtros aplicados"}), 404
        
        # 7. Gerar Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Relatório de Senhas"
        
        # Criar cabeçalho
        headers = ["Nome do Aluno", "Email", "Senha", "Matrícula", "Escola", "Cidade", "Série", "Turma", "Data de Criação"]
        ws.append(headers)
        
        # Estilizar cabeçalho
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
        
        # Adicionar dados
        for log, school, city, class_obj, grade in results:
            created_at_str = ""
            if log.created_at:
                if isinstance(log.created_at, datetime):
                    created_at_str = log.created_at.strftime("%d/%m/%Y %H:%M:%S")
                else:
                    created_at_str = str(log.created_at)
            
            ws.append([
                log.student_name or "",
                log.email or "",
                log.password,  # Senha em texto plano
                log.registration or "",
                school.name if school else "",
                city.name if city else "",
                grade.name if grade else "",
                class_obj.name if class_obj else "",
                created_at_str
            ])
        
        # Ajustar largura das colunas
        column_widths = {
            'A': 30,  # Nome do Aluno
            'B': 30,  # Email
            'C': 30,  # Senha
            'D': 15,  # Matrícula
            'E': 30,  # Escola
            'F': 25,  # Cidade
            'G': 15,  # Série
            'H': 20,  # Turma
            'I': 20   # Data de Criação
        }
        
        for column, width in column_widths.items():
            ws.column_dimensions[column].width = width
        
        # 8. Salvar em memória
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # 9. Gerar nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"relatorio_senhas_alunos_{timestamp}.xlsx"
        
        # 10. Retornar arquivo Excel
        response = Response(
            buffer.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        logging.info(f"Relatório de senhas gerado com sucesso. Total de registros: {len(results)}")
        
        return response
        
    except Exception as e:
        logging.error(f"Erro ao gerar relatório Excel de senhas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao gerar relatório", "details": str(e)}), 500
