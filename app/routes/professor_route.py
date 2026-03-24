from flask import Blueprint, request, jsonify
from app.models.student import Student
from app.models.user import User
from app.models.user import RoleEnum
from app.models.teacher import Teacher
from app.models.school import School
from app.models.schoolTeacher import SchoolTeacher
from app.models.teacherClass import TeacherClass
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.city import City
from werkzeug.security import generate_password_hash
from datetime import datetime
from app import db
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from sqlalchemy import cast, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
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
@role_required("admin", "diretor", "tecadm")
def criar_professor():
    try:
        logging.info("Iniciando criação de usuário/professor combinada")
        
        dados = request.get_json()
        logging.info(f"Dados recebidos: {dados}")

        if not dados:
            return jsonify({"erro": "Nenhum dado fornecido"}), 400

        campos_obrigatorios = ["nome", "email", "senha"]
        for campo in campos_obrigatorios:
            if campo not in dados:
                return jsonify({"erro": f"Campo obrigatório ausente: {campo}"}), 400

        # Obter usuário atual para determinar city_id
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
            # Verificar se matrícula já existe (apenas se for fornecida)
            if dados.get("matricula") and User.query.filter_by(registration=dados["matricula"]).first():
                return jsonify({"erro": "Matrícula já cadastrada"}), 400

            # Criar usuário (role: professor)
            usuario = User(
                name=dados["nome"],  # Corrigido: nome -> name
                email=dados["email"],
                password_hash=generate_password_hash(dados["senha"]),  # Corrigido: senha -> password
                registration=dados.get("matricula"),  # Corrigido: matricula -> registration
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
@role_required("admin", "diretor", "coordenador", "professor", "tecadm", "aluno")
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
        if user['role'] == "admin":
            # Admin pode ver professores de qualquer escola
            pass
        elif user['role'] == "aluno":
            # Aluno só pode ver professores da sua própria escola
            student = Student.query.filter_by(user_id=user['id']).first()
            
            if not student:
                return jsonify({"erro": "Aluno não encontrado"}), 404
            
            if not student.school_id or student.school_id != school_id:
                return jsonify({"erro": "Você não tem permissão para ver professores desta escola"}), 403
        elif user['role'] == "professor":
            # Professor só pode ver professores da sua própria escola
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            
            if not teacher:
                return jsonify({"erro": "Professor não encontrado na tabela teacher"}), 404
            
            # Buscar escolas onde o professor está vinculado
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            if not any(st.school_id == school_id for st in teacher_schools):
                return jsonify({"erro": "Você não tem permissão para ver professores desta escola"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem ver escolas do seu município
            if not user.get('city_id'):
                return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400
            if escola.city_id != user['city_id']:
                return jsonify({"erro": "Você não tem permissão para ver professores desta escola"}), 403
        else:
            # TecAdmin só pode ver escolas do seu município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id or escola.city_id != city_id:
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
                    "email": usuario.email,
                    "registration": professor.registration,
                    "birth_date": str(professor.birth_date) if professor.birth_date else None,
                    "city_id": usuario.city_id
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

@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "tecadm", "professor")
def listar_professores():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Base query com joins
        query = db.session.query(
            Teacher,
            User
        ).join(
            User, Teacher.user_id == User.id
        )

        # Filtrar por role: professor vê apenas a si mesmo (para relatórios/filtros da sua turma)
        if user['role'] == "admin":
            # Admin vê todos os professores
            pass
        elif user['role'] == "professor":
            # Professor vê apenas seu próprio registro (série, escola, município, estado da sua turma)
            query = query.filter(Teacher.user_id == user['id'])
        elif user['role'] in ["diretor", "coordenador", "tecadm"]:
            # Diretor, coordenador e tecadmin veem apenas professores do mesmo município
            if not user.get('city_id'):
                return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400
            query = query.filter(User.city_id == user['city_id'])

        # Executar query
        professores = query.all()

        # Organizar resultados
        resultado = []
        for professor, usuario in professores:
            # Buscar vínculos escolares do professor
            vinculos_escolares = SchoolTeacher.query.filter_by(teacher_id=professor.id).all()
            
            # Criar lista de vínculos escolares com dados da escola
            vinculos = []
            for vinculo in vinculos_escolares:
                # Buscar dados da escola
                escola = School.query.get(vinculo.school_id)
                vinculos.append({
                    "registration": vinculo.registration,
                    "school_id": vinculo.school_id,
                    "school_name": escola.name if escola else None,
                    "school_domain": escola.domain if escola else None
                })
            
            # Buscar turmas onde o professor leciona
            turmas_professor = TeacherClass.query.filter_by(teacher_id=professor.id).all()
            
            turmas = []
            for turma_vinculo in turmas_professor:
                # Buscar dados da turma
                turma = Class.query.get(turma_vinculo.class_id)
                if turma:
                    serie = Grade.query.get(turma.grade_id) if turma.grade_id else None
                    turmas.append({
                        "class_id": turma.id,
                        "class_name": turma.name,
                        "school_id": turma.school_id,
                        "grade_id": str(turma.grade_id) if turma.grade_id else None,
                        "grade_name": serie.name if serie else None
                    })
            
            resultado.append({
                "professor": {
                    "id": professor.id,
                    "name": professor.name,
                    "email": usuario.email,
                    "registration": professor.registration,
                    "birth_date": str(professor.birth_date) if professor.birth_date else None,
                    "city_id": usuario.city_id
                },
                "usuario": {
                    "id": usuario.id,
                    "name": usuario.name,
                    "email": usuario.email,
                    "registration": usuario.registration,
                    "role": usuario.role.value
                },
                "vinculos_escolares": vinculos,
                "turmas": turmas
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

@bp.route('/directors', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "tecadm")
def listar_diretores():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Base query para buscar diretores
        query = db.session.query(User).filter(User.role == RoleEnum("diretor"))

        # Filtrar por município baseado na role
        if user['role'] == "admin":
            # Admin vê todos os diretores
            pass
        elif user['role'] in ["diretor", "coordenador", "tecadm"]:
            # Diretor, coordenador e tecadm veem apenas diretores do mesmo município
            if not user.get('city_id'):
                return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400
            
            # Filtrar diretores pelo city_id do usuário
            query = query.filter(User.city_id == user['city_id'])

        # Executar query
        diretores = query.all()

        # Organizar resultados
        resultado = []
        for diretor in diretores:
            # Buscar dados do município
            municipio = None
            if diretor.city_id:
                municipio = City.query.get(diretor.city_id)
            
            resultado.append({
                "id": diretor.id,
                "name": diretor.name,
                "email": diretor.email,
                "registration": diretor.registration,
                "role": diretor.role.value,
                "city_id": diretor.city_id,
                "municipio": {
                    "id": municipio.id,
                    "name": municipio.name,
                    "state": municipio.state
                } if municipio else None,
                "created_at": str(diretor.created_at) if diretor.created_at else None,
                "updated_at": str(diretor.updated_at) if diretor.updated_at else None
            })

        return jsonify({
            "mensagem": "Diretores encontrados com sucesso",
            "diretores": resultado
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao listar diretores: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado ao listar diretores: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500

@bp.route('/coordinators', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "tecadm")
def listar_coordenadores():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Base query para buscar coordenadores
        query = db.session.query(User).filter(User.role == RoleEnum("coordenador"))

        # Filtrar por município baseado na role
        if user['role'] == "admin":
            # Admin vê todos os coordenadores
            pass
        elif user['role'] in ["diretor", "coordenador", "tecadm"]:
            # Diretor, coordenador e tecadm veem apenas coordenadores do mesmo município
            if not user.get('city_id'):
                return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400
            
            # Filtrar coordenadores pelo city_id do usuário
            query = query.filter(User.city_id == user['city_id'])

        # Executar query
        coordenadores = query.all()

        # Organizar resultados
        resultado = []
        for coordenador in coordenadores:
            # Buscar dados do município
            municipio = None
            if coordenador.city_id:
                municipio = City.query.get(coordenador.city_id)
            
            resultado.append({
                "id": coordenador.id,
                "name": coordenador.name,
                "email": coordenador.email,
                "registration": coordenador.registration,
                "role": coordenador.role.value,
                "city_id": coordenador.city_id,
                "municipio": {
                    "id": municipio.id,
                    "name": municipio.name,
                    "state": municipio.state
                } if municipio else None,
                "created_at": str(coordenador.created_at) if coordenador.created_at else None,
                "updated_at": str(coordenador.updated_at) if coordenador.updated_at else None
            })

        return jsonify({
            "mensagem": "Coordenadores encontrados com sucesso",
            "coordenadores": resultado
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao listar coordenadores: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado ao listar coordenadores: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500

@bp.route('/tecadm', methods=['GET'])
@jwt_required()
@role_required("admin")
def listar_tecadm():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Base query para buscar tecadm
        query = db.session.query(User).filter(User.role == RoleEnum("tecadm"))

        # Admin vê todos os tecadm
        tecadm_users = query.all()

        # Organizar resultados
        resultado = []
        for tecadm in tecadm_users:
            # Buscar dados do município
            municipio = None
            if tecadm.city_id:
                municipio = City.query.get(tecadm.city_id)
            
            resultado.append({
                "id": tecadm.id,
                "name": tecadm.name,
                "email": tecadm.email,
                "registration": tecadm.registration,
                "role": tecadm.role.value,
                "city_id": tecadm.city_id,
                "municipio": {
                    "id": municipio.id,
                    "name": municipio.name,
                    "state": municipio.state
                } if municipio else None,
                "created_at": str(tecadm.created_at) if tecadm.created_at else None,
                "updated_at": str(tecadm.updated_at) if tecadm.updated_at else None
            })

        return jsonify({
            "mensagem": "Tecadm encontrados com sucesso",
            "tecadm": resultado
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao listar tecadm: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado ao listar tecadm: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500


@bp.route('/directors', methods=['POST'])
@jwt_required()
@role_required("admin", "diretor", "tecadm")
def criar_diretor():
    try:
        logging.info("Iniciando criação de diretor")
        
        dados = request.get_json()
        logging.info(f"Dados recebidos: {dados}")

        if not dados:
            return jsonify({"erro": "Nenhum dado fornecido"}), 400

        campos_obrigatorios = ["nome", "email", "senha"]
        for campo in campos_obrigatorios:
            if campo not in dados:
                return jsonify({"erro": f"Campo obrigatório ausente: {campo}"}), 400

        # Obter usuário atual para determinar city_id
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Determinar city_id baseado na role do usuário atual
        city_id = None
        
        if current_user['role'] == "admin":
            # Admin pode escolher qualquer city_id
            city_id = dados.get("city_id")
            if not city_id:
                return jsonify({"erro": "city_id é obrigatório para admin criando diretores"}), 400
        else:
            # Diretor e tecadm usam seu próprio city_id
            city_id = current_user.get("city_id")
            
            # Verificação adicional: buscar city_id diretamente do banco
            if not city_id:
                user_from_db = User.query.get(current_user['id'])
                if user_from_db and user_from_db.city_id:
                    city_id = user_from_db.city_id
                    logging.info(f"City_id recuperado do banco para usuário {current_user['id']}: {city_id}")
                else:
                    return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400

        # Verificar se usuário já existe
        usuario = User.query.filter_by(email=dados["email"]).first()

        if usuario:
            logging.info(f"Usuário existente encontrado: {usuario.email}")
            if usuario.role == RoleEnum("diretor"):
                logging.warning(f"Usuário {usuario.email} já é um diretor.")
                return jsonify({"erro": "Usuário já é um diretor"}), 400
            else:
                # Atualizar role para diretor
                usuario.role = RoleEnum("diretor")
                usuario.city_id = city_id
                db.session.commit()
                logging.info(f"Usuário {usuario.email} atualizado para diretor")
        else:
            logging.info("Usuário não encontrado, criando novo usuário.")
            # Verificar se matrícula já existe (apenas se for fornecida)
            if dados.get("matricula") and User.query.filter_by(registration=dados["matricula"]).first():
                return jsonify({"erro": "Matrícula já cadastrada"}), 400

            # Criar usuário (role: diretor)
            usuario = User(
                name=dados["nome"],
                email=dados["email"],
                password_hash=generate_password_hash(dados["senha"]),
                registration=dados.get("matricula"),
                role=RoleEnum("diretor"),
                city_id=city_id
            )
            db.session.add(usuario)
            db.session.commit()
            logging.info(f"Novo diretor criado com sucesso. ID: {usuario.id}")

        return jsonify({
            "mensagem": "Diretor criado com sucesso",
            "diretor": {
                "id": usuario.id,
                "name": usuario.name,
                "email": usuario.email,
                "registration": usuario.registration,
                "role": usuario.role.value,
                "city_id": usuario.city_id,
                "created_at": str(usuario.created_at) if usuario.created_at else None,
                "updated_at": str(usuario.updated_at) if usuario.updated_at else None
            }
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados durante a criação do diretor: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado durante a criação do diretor: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500

@bp.route('/coordinators', methods=['POST'])
@jwt_required()
@role_required("admin", "diretor", "tecadm")
def criar_coordenador():
    try:
        logging.info("Iniciando criação de coordenador")
        
        dados = request.get_json()
        logging.info(f"Dados recebidos: {dados}")

        if not dados:
            return jsonify({"erro": "Nenhum dado fornecido"}), 400

        campos_obrigatorios = ["nome", "email", "senha"]
        for campo in campos_obrigatorios:
            if campo not in dados:
                return jsonify({"erro": f"Campo obrigatório ausente: {campo}"}), 400

        # Obter usuário atual para determinar city_id
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 400

        # Determinar city_id baseado na role do usuário atual
        city_id = None
        
        if current_user['role'] == "admin":
            # Admin pode escolher qualquer city_id
            city_id = dados.get("city_id")
            if not city_id:
                return jsonify({"erro": "city_id é obrigatório para admin criando coordenadores"}), 400
        else:
            # Diretor e tecadm usam seu próprio city_id
            city_id = current_user.get("city_id")
            
            # Verificação adicional: buscar city_id diretamente do banco
            if not city_id:
                user_from_db = User.query.get(current_user['id'])
                if user_from_db and user_from_db.city_id:
                    city_id = user_from_db.city_id
                    logging.info(f"City_id recuperado do banco para usuário {current_user['id']}: {city_id}")
                else:
                    return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400

        # Verificar se usuário já existe
        usuario = User.query.filter_by(email=dados["email"]).first()

        if usuario:
            logging.info(f"Usuário existente encontrado: {usuario.email}")
            if usuario.role == RoleEnum("coordenador"):
                logging.warning(f"Usuário {usuario.email} já é um coordenador.")
                return jsonify({"erro": "Usuário já é um coordenador"}), 400
            else:
                # Atualizar role para coordenador
                usuario.role = RoleEnum("coordenador")
                usuario.city_id = city_id
                db.session.commit()
                logging.info(f"Usuário {usuario.email} atualizado para coordenador")
        else:
            logging.info("Usuário não encontrado, criando novo usuário.")
            # Verificar se matrícula já existe (apenas se for fornecida)
            if dados.get("matricula") and User.query.filter_by(registration=dados["matricula"]).first():
                return jsonify({"erro": "Matrícula já cadastrada"}), 400

            # Criar usuário (role: coordenador)
            usuario = User(
                name=dados["nome"],
                email=dados["email"],
                password_hash=generate_password_hash(dados["senha"]),
                registration=dados.get("matricula"),
                role=RoleEnum("coordenador"),
                city_id=city_id
            )
            db.session.add(usuario)
            db.session.commit()
            logging.info(f"Novo coordenador criado com sucesso. ID: {usuario.id}")

        return jsonify({
            "mensagem": "Coordenador criado com sucesso",
            "coordenador": {
                "id": usuario.id,
                "name": usuario.name,
                "email": usuario.email,
                "registration": usuario.registration,
                "role": usuario.role.value,
                "city_id": usuario.city_id,
                "created_at": str(usuario.created_at) if usuario.created_at else None,
                "updated_at": str(usuario.updated_at) if usuario.updated_at else None
            }
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados durante a criação do coordenador: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado durante a criação do coordenador: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500

@bp.route('/tecadm', methods=['POST'])
@jwt_required()
@role_required("admin")
def criar_tecadm():
    try:
        logging.info("Iniciando criação de tecadm")
        
        dados = request.get_json()
        logging.info(f"Dados recebidos: {dados}")

        if not dados:
            return jsonify({"erro": "Nenhum dado fornecido"}), 400

        campos_obrigatorios = ["nome", "email", "senha", "city_id"]
        for campo in campos_obrigatorios:
            if campo not in dados:
                return jsonify({"erro": f"Campo obrigatório ausente: {campo}"}), 400

        # Verificar se usuário já existe
        usuario = User.query.filter_by(email=dados["email"]).first()

        if usuario:
            logging.info(f"Usuário existente encontrado: {usuario.email}")
            if usuario.role == RoleEnum("tecadm"):
                logging.warning(f"Usuário {usuario.email} já é um tecadm.")
                return jsonify({"erro": "Usuário já é um tecadm"}), 400
            else:
                # Atualizar role para tecadm
                usuario.role = RoleEnum("tecadm")
                usuario.city_id = dados["city_id"]
                db.session.commit()
                logging.info(f"Usuário {usuario.email} atualizado para tecadm")
        else:
            logging.info("Usuário não encontrado, criando novo usuário.")
            # Verificar se matrícula já existe (apenas se for fornecida)
            if dados.get("matricula") and User.query.filter_by(registration=dados["matricula"]).first():
                return jsonify({"erro": "Matrícula já cadastrada"}), 400

            # Criar usuário (role: tecadm)
            usuario = User(
                name=dados["nome"],
                email=dados["email"],
                password_hash=generate_password_hash(dados["senha"]),
                registration=dados.get("matricula"),
                role=RoleEnum("tecadm"),
                city_id=dados["city_id"]
            )
            db.session.add(usuario)
            db.session.commit()
            logging.info(f"Novo tecadm criado com sucesso. ID: {usuario.id}")

        return jsonify({
            "mensagem": "Tecadm criado com sucesso",
            "tecadm": {
                "id": usuario.id,
                "name": usuario.name,
                "email": usuario.email,
                "registration": usuario.registration,
                "role": usuario.role.value,
                "city_id": usuario.city_id,
                "created_at": str(usuario.created_at) if usuario.created_at else None,
                "updated_at": str(usuario.updated_at) if usuario.updated_at else None
            }
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados durante a criação do tecadm: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado durante a criação do tecadm: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500

@bp.route('/<string:user_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def get_teacher_profile(user_id):
    """
    Retorna o perfil completo de um professor específico
    """
    try:
        logging.info(f"Buscando perfil do professor com user_id: {user_id}")
        
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Buscar o usuário
        user = User.query.get(user_id)
        if not user:
            logging.warning(f"Usuário não encontrado com ID: {user_id}")
            return jsonify({"erro": "Usuário não encontrado"}), 404

        # Verificar se o usuário é realmente um professor
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        if not teacher:
            logging.warning(f"Usuário {user_id} não é um professor")
            return jsonify({"erro": "Usuário não é um professor"}), 400

        # Verificar permissões do usuário atual
        if current_user['role'] == "professor":
            # Professor só pode ver seu próprio perfil ou de colegas da mesma escola
            if current_user['id'] != user_id:
                # Verificar se ambos estão na mesma escola
                current_teacher = Teacher.query.filter_by(user_id=current_user['id']).first()
                if not current_teacher:
                    return jsonify({"erro": "Professor atual não encontrado"}), 404
                
                # Buscar escolas do professor atual
                current_schools = SchoolTeacher.query.filter_by(teacher_id=current_teacher.id).all()
                current_school_ids = [st.school_id for st in current_schools]
                
                # Buscar escolas do professor alvo
                target_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                target_school_ids = [st.school_id for st in target_schools]
                
                # Verificar se há interseção entre as escolas
                if not any(sid in current_school_ids for sid in target_school_ids):
                    return jsonify({"erro": "Você não tem permissão para ver este professor"}), 403
                    
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem ver professores do mesmo município
            if not current_user.get('city_id'):
                return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400
            if user.city_id != current_user['city_id']:
                return jsonify({"erro": "Você não tem permissão para ver este professor"}), 403
                
        elif current_user['role'] == "tecadm":
            # TecAdmin só pode ver professores do mesmo município
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            if user.city_id != city_id:
                return jsonify({"erro": "Você não tem permissão para ver este professor"}), 403

        # Buscar vínculos escolares do professor
        vinculos_escolares = db.session.query(
            SchoolTeacher,
            School
        ).join(
            School, SchoolTeacher.school_id == School.id
        ).filter(
            SchoolTeacher.teacher_id == teacher.id
        ).all()

        vinculos = []
        for vinculo, escola in vinculos_escolares:
            vinculos.append({
                "registration": vinculo.registration,
                "school_id": vinculo.school_id,
                "school_name": escola.name,
                "school_domain": escola.domain,
                "school_address": escola.address,
                "school_city_id": escola.city_id
            })

        # Buscar turmas onde o professor leciona
        turmas_professor = db.session.query(
            TeacherClass,
            Class,
            School,
            Grade
        ).join(
            Class, TeacherClass.class_id == Class.id
        ).join(
            School, School.id == cast(Class.school_id, String)
        ).outerjoin(
            Grade, Class.grade_id == Grade.id
        ).filter(
            TeacherClass.teacher_id == teacher.id
        ).all()

        turmas = []
        for turma_vinculo, turma, escola, serie in turmas_professor:
            turmas.append({
                "class_id": turma.id,
                "class_name": turma.name,
                "school_id": turma.school_id,
                "school_name": escola.name,
                "grade_id": str(turma.grade_id) if turma.grade_id else None,
                "grade_name": serie.name if serie else None
            })

        # Buscar dados do município
        municipio = None
        if user.city_id:
            municipio = City.query.get(user.city_id)

        # Formatar resposta
        perfil_professor = {
            "professor": {
                "id": teacher.id,
                "name": teacher.name,
                "registration": teacher.registration,
                "birth_date": str(teacher.birth_date) if teacher.birth_date else None,
                "user_id": teacher.user_id
            },
            "usuario": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "registration": user.registration,
                "role": user.role.value,
                "city_id": user.city_id,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            },
            "municipio": {
                "id": municipio.id,
                "name": municipio.name,
                "state": municipio.state
            } if municipio else None,
            "vinculos_escolares": vinculos,
            "turmas": turmas,
            "estatisticas": {
                "total_escolas": len(vinculos),
                "total_turmas": len(turmas)
            }
        }

        logging.info(f"Perfil do professor {user_id} retornado com sucesso")
        return jsonify(perfil_professor), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao buscar perfil do professor: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado ao buscar perfil do professor: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500
