from flask import Blueprint, request, jsonify
from app.models.student import Student
from app.models.user import User
from app.models.user import RoleEnum
from app.models.teacher import Teacher
from app.models.school import School
from app.models.schoolTeacher import SchoolTeacher
from werkzeug.security import generate_password_hash
from datetime import datetime
from app import db
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
        if user['role'] == "professor":
            # Professor só pode ver professores da sua própria escola
            if not any(st.school_id == school_id for st in SchoolTeacher.query.filter_by(teacher_id=user.get('teacher_id')).all()):
                return jsonify({"erro": "Você não tem permissão para ver professores desta escola"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem ver escolas do seu município
            if not user.get('city_id'):
                return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400
            if escola.city_id != user['city_id']:
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
@role_required("admin", "diretor", "coordenador", "tecadm")
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

        # Filtrar por município baseado na role
        if user['role'] == "admin":
            # Admin vê todos os professores
            pass
        elif user['role'] in ["diretor", "coordenador", "tecadm"]:
            # Diretor, coordenador e tecadmin veem apenas professores do mesmo município
            if not user.get('city_id'):
                return jsonify({"erro": "Usuário não tem city_id atribuído"}), 400
            
            # Filtrar professores pelo city_id do usuário
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
            from app.models.teacherClass import TeacherClass
            turmas_professor = TeacherClass.query.filter_by(teacher_id=professor.id).all()
            
            turmas = []
            for turma_vinculo in turmas_professor:
                # Buscar dados da turma
                from app.models.studentClass import Class
                from app.models.grades import Grade
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
            from app.models.city import City
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
            from app.models.city import City
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
            from app.models.city import City
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
@role_required("admin", "diretor")
def criar_diretor():
    try:
        logging.info("Iniciando criação de diretor")
        
        dados = request.get_json()
        logging.info(f"Dados recebidos: {dados}")

        if not dados:
            return jsonify({"erro": "Nenhum dado fornecido"}), 400

        campos_obrigatorios = ["nome", "email", "senha", "matricula"]
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
            # Diretor usa seu próprio city_id
            city_id = current_user.get("city_id")
            if not city_id:
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
            # Verificar se matrícula já existe
            if User.query.filter_by(registration=dados["matricula"]).first():
                return jsonify({"erro": "Matrícula já cadastrada"}), 400

            # Criar usuário (role: diretor)
            usuario = User(
                name=dados["nome"],
                email=dados["email"],
                password_hash=generate_password_hash(dados["senha"]),
                registration=dados["matricula"],
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
@role_required("admin", "diretor")
def criar_coordenador():
    try:
        logging.info("Iniciando criação de coordenador")
        
        dados = request.get_json()
        logging.info(f"Dados recebidos: {dados}")

        if not dados:
            return jsonify({"erro": "Nenhum dado fornecido"}), 400

        campos_obrigatorios = ["nome", "email", "senha", "matricula"]
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
                return jsonify({"erro": "city_id é obrigatório para admin criando coordenadores"}), 400
        else:
            # Diretor usa seu próprio city_id
            city_id = current_user.get("city_id")
            if not city_id:
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
            # Verificar se matrícula já existe
            if User.query.filter_by(registration=dados["matricula"]).first():
                return jsonify({"erro": "Matrícula já cadastrada"}), 400

            # Criar usuário (role: coordenador)
            usuario = User(
                name=dados["nome"],
                email=dados["email"],
                password_hash=generate_password_hash(dados["senha"]),
                registration=dados["matricula"],
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

        campos_obrigatorios = ["nome", "email", "senha", "matricula", "city_id"]
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
            # Verificar se matrícula já existe
            if User.query.filter_by(registration=dados["matricula"]).first():
                return jsonify({"erro": "Matrícula já cadastrada"}), 400

            # Criar usuário (role: tecadm)
            usuario = User(
                name=dados["nome"],
                email=dados["email"],
                password_hash=generate_password_hash(dados["senha"]),
                registration=dados["matricula"],
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
