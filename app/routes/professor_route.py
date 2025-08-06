from flask import Blueprint, request, jsonify
from app.models.student import Student
from app.models.user import User
from app.models.user import RoleEnum
from app.models.teacher import Teacher
from app.models.school import School
from app.models.schoolTeacher import SchoolTeacher
from app.utils.auth import get_current_tenant_id
from werkzeug.security import generate_password_hash
from datetime import datetime
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
import logging
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload

bp = Blueprint('teacher', __name__, url_prefix="/teacher")

@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Erro no banco de dados: {str(error)}")
    return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(error)}), 500

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Erro inesperado: {str(error)}", exc_info=True)
    return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(error)}), 500

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "diretor")
def criar_professor():
    try:
        logging.info("Iniciando criação de usuário/professor combinada")
        
        dados = request.get_json()
        logging.info(f"Dados recebidos: {dados}")

        if not dados:
            return jsonify({"erro": "Nenhum dado fornecido"}), 400

        campos_obrigatorios = ["nome", "email", "senha", "matricula"]
        for campo in campos_obrigatorios:
            if campo not in dados:
                return jsonify({"erro": f"Campo obrigatório ausente: {campo}"}), 400

        # Obter usuário atual para determinar city_id
        from app.decorators.role_required import get_current_user_from_token
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Determinar city_id baseado na role do usuário atual
        city_id = None
        if current_user['role'] == "admin":
            # Admin pode escolher qualquer city_id
            city_id = dados.get("city_id")
            if not city_id:
                return jsonify({"erro": "city_id é obrigatório para admin criando professores"}), 400
        else:
            # Diretor usa seu próprio city_id
            city_id = current_user.get("city_id")
            if not city_id:
                return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400

        # Verificar se usuário já existe
        usuario = User.query.filter_by(email=dados["email"]).first()

        if usuario:
            logging.info(f"Usuário existente encontrado: {usuario.email}")
            # Verificar se o usuário já é um professor
            if Teacher.query.filter_by(user_id=usuario.id).first():
                logging.warning(f"Usuário {usuario.email} já é um professor.")
                return jsonify({"erro": "Usuário já é um professor"}), 400
        else:
            logging.info("Usuário não encontrado, criando novo usuário.")
            # Verificar se matrícula já existe
            if User.query.filter_by(registration=dados["matricula"]).first():
                return jsonify({"erro": "Matrícula já cadastrada"}), 400

            # Criar usuário (role: professor)
            usuario = User(
                name=dados["nome"],  # Corrigido: nome -> name
                email=dados["email"],
                password_hash=generate_password_hash(dados["senha"]),  # Corrigido: senha -> password
                registration=dados["matricula"],  # Corrigido: matricula -> registration
                role=RoleEnum("professor"),
                city_id=city_id  # Adicionando city_id
            )
            db.session.add(usuario)
            db.session.flush()
            logging.info(f"Novo usuário criado com sucesso. ID: {usuario.id}")

        # Converter data de nascimento
        data_nascimento = None
        if "birth_date" in dados:
            try:
                data_nascimento = datetime.strptime(dados["birth_date"], "%Y-%m-%d").date()
            except ValueError:
                if not usuario.id:
                    db.session.rollback()
                return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD"}), 400

        # Criar professor
        professor = Teacher(
            name=usuario.name,  # Corrigido: nome -> name
            registration=usuario.registration,  # Corrigido: matricula -> registration
            birth_date=data_nascimento,
            user_id=usuario.id  # Corrigido: usuario_id -> user_id
        )
        db.session.add(professor)
        db.session.flush()

        # Vincular professor às escolas
        escolas_ids = dados.get("escolas_ids", [])
        if escolas_ids:
            escolas = School.query.filter(School.id.in_(escolas_ids), School.city_id == city_id).all()
            if len(escolas) != len(escolas_ids):
                db.session.rollback()
                return jsonify({"erro": "Uma ou mais escolas não encontradas ou não pertencem ao município"}), 400
            
            # Criar vínculos com as escolas
            for escola in escolas:
                school_teacher = SchoolTeacher(
                    registration=professor.registration,  # Corrigido: matricula -> registration
                    school_id=escola.id,
                    teacher_id=professor.id
                )
                db.session.add(school_teacher)

        db.session.commit()
        logging.info(f"Professor criado com sucesso para o usuário ID: {usuario.id}")

        return jsonify({
            "mensagem": "Professor criado com sucesso",
            "usuario": {
                "id": usuario.id,
                "name": usuario.name,  # Corrigido: nome -> name
                "email": usuario.email,
                "registration": usuario.registration,  # Corrigido: matricula -> registration
                "role": usuario.role.value,
                "city_id": usuario.city_id
            },
            "professor": {
                "id": professor.id,
                "name": professor.name,  # Corrigido: nome -> name
                "registration": professor.registration,  # Corrigido: matricula -> registration
                "birth_date": str(professor.birth_date) if professor.birth_date else None,
                "user_id": professor.user_id,
                "escolas_ids": escolas_ids
            }
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados durante a criação do usuário/professor: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado durante a criação do usuário/professor: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500

@bp.route('/school/<string:school_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def listar_professores_por_escola(school_id):
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Verificar se a escola existe
        escola = School.query.get(school_id)
        if not escola:
            return jsonify({"erro": "Escola não encontrada"}), 404

        # Verificar permissões
        tenant_id = get_current_tenant_id()
        if user['role'] == "professor":
            # Professor só pode ver professores da sua própria escola
            if not any(st.school_id == school_id for st in SchoolTeacher.query.filter_by(teacher_id=user.get('teacher_id')).all()):
                return jsonify({"erro": "Você não tem permissão para ver professores desta escola"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem ver escolas do seu município
            if escola.city_id != tenant_id:
                return jsonify({"erro": "Você não tem permissão para ver professores desta escola"}), 403

        # Buscar professores da escola
        professores = db.session.query(
            Teacher,
            User,
            SchoolTeacher
        ).join(
            User, Teacher.user_id == User.id
        ).join(
            SchoolTeacher, Teacher.id == SchoolTeacher.teacher_id
        ).filter(
            SchoolTeacher.school_id == school_id
        ).all()

        resultado = []
        for professor, usuario, vinculo in professores:
            resultado.append({
                "professor": {
                    "id": professor.id,
                    "name": professor.name,
                    "email": professor.email,
                    "registration": professor.registration,
                    "birth_date": str(professor.birth_date) if professor.birth_date else None,
                    "tenant_id": professor.tenant_id
                },
                "usuario": {
                    "id": usuario.id,
                    "name": usuario.name,
                    "email": usuario.email,
                    "registration": usuario.registration,
                    "role": usuario.role.value
                },
                "vinculo_escola": {
                    "registration": vinculo.registration,
                    "school_id": vinculo.school_id
                }
            })

        return jsonify({
            "mensagem": "Professores encontrados com sucesso",
            "escola": {
                "id": escola.id,
                "name": escola.name
            },
            "professores": resultado
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao listar professores: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado ao listar professores: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500

@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador")
def listar_professores():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Obter tenant_id (município) do contexto do token
        tenant_id = get_current_tenant_id()

        # Base query com joins
        query = db.session.query(
            Teacher,
            User,
            SchoolTeacher
        ).join(
            User, Teacher.user_id == User.id
        ).join(
            SchoolTeacher, Teacher.id == SchoolTeacher.teacher_id
        )

        # Filtrar por município ou escola baseado na role
        if user['role'] == "admin":
            # Admin vê todos os professores
            pass
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador veem apenas professores de sua escola
            from app.models.schoolTeacher import SchoolTeacher
            
            # Buscar a escola do diretor/coordenador
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"erro": "Diretor/Coordenador não encontrado"}), 404
            
            teacher_school = SchoolTeacher.query.filter_by(teacher_id=teacher.id).first()
            if not teacher_school:
                return jsonify({"erro": "Diretor/Coordenador não está vinculado a nenhuma escola"}), 400
            
            # Buscar professores da mesma escola
            school_teachers = SchoolTeacher.query.filter_by(school_id=teacher_school.school_id).all()
            teacher_ids = [st.teacher_id for st in school_teachers]
            
            if teacher_ids:
                query = query.filter(Teacher.id.in_(teacher_ids))
            else:
                return jsonify({"erro": "Nenhum professor encontrado nesta escola"}), 404
        else:
            # TecAdmin vê professores do município
            query = query.filter(Teacher.tenant_id == tenant_id)

        # Executar query
        professores = query.all()

        # Organizar resultados
        resultado = []
        for professor, usuario, vinculo in professores:
            resultado.append({
                "professor": {
                    "id": professor.id,
                    "name": professor.name,
                    "email": professor.email,
                    "registration": professor.registration,
                    "birth_date": str(professor.birth_date) if professor.birth_date else None,
                    "tenant_id": professor.tenant_id
                },
                "usuario": {
                    "id": usuario.id,
                    "name": usuario.name,
                    "email": usuario.email,
                    "registration": usuario.registration,
                    "role": usuario.role.value
                },
                "vinculo_escola": {
                    "registration": vinculo.registration,
                    "school_id": vinculo.school_id
                }
            })

        return jsonify({
            "mensagem": "Professores encontrados com sucesso",
            "professores": resultado
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao listar professores: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado ao listar professores: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500
