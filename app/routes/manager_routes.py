from flask import Blueprint, request, jsonify, g
from app.models.manager import Manager
from app.models.user import User, RoleEnum
from app.models.school import School
from app.models.city import City
from app.decorators.role_required import role_required, get_current_user_from_token
from app import db
from flask_jwt_extended import jwt_required
from app.utils.auth import hash_password
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import text
import logging
from datetime import datetime
from app.utils.tenant_middleware import (
    city_id_to_schema_name,
    set_search_path,
    get_current_tenant_context,
)

bp = Blueprint('managers', __name__, url_prefix="/managers")

@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"error": "Database error occurred", "details": str(error)}), 500

@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error(f"Integrity error: {str(error)}")
    return jsonify({"error": "Data integrity error", "details": str(error)}), 400

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"error": "An unexpected error occurred", "details": str(error)}), 500


def _schema_for_school_id(school_id):
    """
    Encontra o schema (city_xxx) que contém a escola com o id dado.
    Necessário quando o request não tem contexto de tenant (ex.: admin sem X-City-ID).
    Retorna o nome do schema ou None se não encontrar.
    """
    try:
        rp = db.session.execute(
            text("""
                SELECT n.nspname
                FROM pg_namespace n
                JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = 'school'
                WHERE n.nspname LIKE 'city_%'
                ORDER BY n.nspname
            """)
        )
        schemas = [row[0] for row in rp.fetchall()]
        for schema in schemas:
            try:
                r = db.session.execute(
                    text('SELECT 1 FROM "{}".school WHERE id = :sid'.format(schema)),
                    {"sid": school_id},
                )
                if r.fetchone():
                    return schema
            except Exception:
                continue
        return None
    except Exception as e:
        logging.warning("Erro ao descobrir schema da escola: %s", e)
        return None


# POST - Criar manager (diretor, coordenador, tecadm, admin)
@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def create_manager():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ["name", "email", "password", "role"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Validar role (roles válidas para criação nesta rota)
        valid_roles = ["diretor", "coordenador", "tecadm", "admin"]
        if data["role"] not in valid_roles:
            return jsonify({"error": f"Invalid role. Must be one of: {valid_roles}"}), 400

        # Obter usuário atual para verificar permissões
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"error": "User not found"}), 404

        # Validar permissões baseadas na role do usuário atual
        current_role = current_user['role']
        role_to_create = data["role"]
        
        if current_role == "diretor" or current_role == "coordenador":
            # Diretor e Coordenador só podem criar diretores e coordenadores
            if role_to_create not in ["diretor", "coordenador"]:
                return jsonify({
                    "error": f"{current_role.capitalize()} can only create diretor or coordenador roles"
                }), 403
        elif current_role == "tecadm":
            # Tecadm pode criar diretores, coordenadores e outros tecadms
            if role_to_create not in ["diretor", "coordenador", "tecadm"]:
                return jsonify({
                    "error": "tecadm can only create diretor, coordenador or tecadm roles"
                }), 403
        elif current_role == "admin":
            # Admin pode criar todos os roles
            pass
        else:
            return jsonify({"error": "Unauthorized role"}), 403

        # Verificar se email já existe
        if User.query.filter_by(email=data["email"]).first():
            return jsonify({"error": "Email already exists"}), 400

        # Verificar se registration já existe
        if data.get("registration") and User.query.filter_by(registration=data["registration"]).first():
            return jsonify({"error": "Registration number already exists"}), 400

        # Determinar city_id baseado na role do usuário atual
        city_id = None
        if current_user['role'] == "admin":
            # Admin pode escolher qualquer city_id
            city_id = data.get("city_id")
            if not city_id:
                return jsonify({"error": "city_id is required for admin creating managers"}), 400
        else:
            # Tecadm, Diretor e Coordenador usam seu próprio city_id
            city_id = current_user.get("city_id")
            
            # Verificação adicional: buscar city_id diretamente do banco
            if not city_id:
                user_from_db = User.query.get(current_user['id'])
                if user_from_db and user_from_db.city_id:
                    city_id = user_from_db.city_id
                    logging.info(f"City_id recuperado do banco para usuário {current_user['id']}: {city_id}")
                else:
                    return jsonify({"error": "User does not have city_id assigned"}), 400

        # Criar usuário
        novo_usuario = User(
            name=data["name"],
            email=data["email"],
            password_hash=hash_password(data["password"]),
            registration=data.get("registration"),
            role=RoleEnum(data["role"]),
            city_id=city_id
        )
        db.session.add(novo_usuario)
        db.session.flush()

        # Converter data de nascimento
        birth_date = None
        if data.get("birth_date"):
            try:
                birth_date = datetime.strptime(data["birth_date"], "%Y-%m-%d").date()
            except ValueError:
                db.session.rollback()
                return jsonify({"error": "Invalid birth date format. Use YYYY-MM-DD"}), 400

        # Criar manager
        novo_manager = Manager(
            name=data["name"],
            registration=data.get("registration"),
            birth_date=birth_date,
            profile_picture=data.get("profile_picture"),
            user_id=novo_usuario.id,
            city_id=city_id  # Para tecadm
        )
        db.session.add(novo_manager)
        db.session.commit()

        return jsonify({
            "message": f"{data['role'].capitalize()} created successfully!",
            "user": {
                "id": novo_usuario.id,
                "name": novo_usuario.name,
                "email": novo_usuario.email,
                "registration": novo_usuario.registration,
                "role": novo_usuario.role.value,
                "city_id": novo_usuario.city_id
            },
            "manager": {
                "id": novo_manager.id,
                "name": novo_manager.name,
                "registration": novo_manager.registration,
                "birth_date": str(novo_manager.birth_date) if novo_manager.birth_date else None,
                "school_id": novo_manager.school_id,
                "city_id": novo_manager.city_id
            }
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error during manager creation: {str(e)}")
        return jsonify({"error": "Database error occurred", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Unexpected error during manager creation: {str(e)}", exc_info=True)
        return jsonify({"error": "Unexpected error occurred", "details": str(e)}), 500

# POST - Vincular diretor/coordenador à escola
@bp.route('/link-to-school', methods=['POST'])
@bp.route('/school-link', methods=['POST'])  # Rota antiga para compatibilidade
@jwt_required()
@role_required("admin", "tecadm")
def link_manager_to_school():
    try:
        data = request.get_json()
        print(data)
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ["user_id", "school_id"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Verificar se usuário existe e é diretor ou coordenador
        user = User.query.get(data["user_id"])
        if not user:
            return jsonify({"error": "User not found"}), 404

        if user.role not in [RoleEnum.DIRETOR, RoleEnum.COORDENADOR]:
            return jsonify({"error": "User must be a diretor or coordenador"}), 400

        # Verificar se manager existe
        manager = Manager.query.filter_by(user_id=data["user_id"]).first()
        if not manager:
            return jsonify({"error": "Manager not found"}), 404

        # Verificar se escola existe
        school = School.query.get(data["school_id"])
        if not school:
            return jsonify({"error": "School not found"}), 404

        # Verificar se já está vinculado a uma escola
        if manager.school_id:
            return jsonify({"error": "Manager is already linked to a school"}), 400

        # Vincular à escola
        manager.school_id = data["school_id"]
        db.session.commit()

        return jsonify({
            "message": f"{user.role.value.capitalize()} linked to school successfully!",
            "manager": {
                "id": manager.id,
                "name": manager.name,
                "school_id": manager.school_id,
                "school_name": school.name
            }
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error occurred", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": "Unexpected error occurred", "details": str(e)}), 500

# DELETE - Desvincular diretor/coordenador da escola
@bp.route('/unlink-from-school/<string:user_id>', methods=['DELETE'])
@bp.route('/school-link/<string:user_id>', methods=['DELETE'])  # Rota antiga para compatibilidade
@jwt_required()
@role_required("admin", "tecadm")
def unlink_manager_from_school(user_id):
    try:
        # Verificar se usuário existe
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        if user.role not in [RoleEnum.DIRETOR, RoleEnum.COORDENADOR]:
            return jsonify({"error": "User must be a diretor or coordenador"}), 400

        # Verificar se manager existe
        manager = Manager.query.filter_by(user_id=user_id).first()
        if not manager:
            return jsonify({"error": "Manager not found"}), 404

        if not manager.school_id:
            return jsonify({"error": "Manager is not linked to any school"}), 400

        # Desvincular da escola
        manager.school_id = None
        db.session.commit()

        return jsonify({
            "message": f"{user.role.value.capitalize()} unlinked from school successfully!"
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error occurred", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": "Unexpected error occurred", "details": str(e)}), 500



# GET - Listar diretores/coordenadores por cidade
@bp.route('/city/<string:city_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm")
def get_managers_by_city(city_id):
    try:
        # Buscar managers da cidade (que estão vinculados a escolas da cidade)
        managers = db.session.query(
            Manager,
            User,
            School
        ).join(
            User, Manager.user_id == User.id
        ).join(
            School, Manager.school_id == School.id
        ).filter(
            School.city_id == city_id,
            User.role.in_([RoleEnum.DIRETOR, RoleEnum.COORDENADOR])
        ).all()

        resultado = []
        for manager, user, school in managers:
            resultado.append({
                "manager": {
                    "id": manager.id,
                    "name": manager.name,
                    "registration": manager.registration,
                    "birth_date": str(manager.birth_date) if manager.birth_date else None,
                    "profile_picture": manager.profile_picture,
                    "school_id": manager.school_id
                },
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "registration": user.registration,
                    "role": user.role.value
                },
                "school": {
                    "id": school.id,
                    "name": school.name
                }
            })

        return jsonify({
            "message": "Managers found successfully",
            "city_id": city_id,
            "managers": resultado,
            "total": len(resultado)
        }), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error occurred", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": "Unexpected error occurred", "details": str(e)}), 500

# GET - Listar todos os managers
@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm")
def list_all_managers():
    try:
        managers = db.session.query(
            Manager,
            User,
            School,
            City
        ).join(
            User, Manager.user_id == User.id
        ).outerjoin(
            School, Manager.school_id == School.id
        ).outerjoin(
            City, Manager.city_id == City.id
        ).filter(
            User.role.in_([RoleEnum.DIRETOR, RoleEnum.COORDENADOR, RoleEnum.TECADM])
        ).all()

        resultado = []
        for manager, user, school, city in managers:
            resultado.append({
                "manager": {
                    "id": manager.id,
                    "name": manager.name,
                    "registration": manager.registration,
                    "birth_date": str(manager.birth_date) if manager.birth_date else None,
                    "profile_picture": manager.profile_picture,
                    "school_id": manager.school_id,
                    "city_id": manager.city_id
                },
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "registration": user.registration,
                    "role": user.role.value
                },
                "school": {
                    "id": school.id,
                    "name": school.name
                } if school else None,
                "city": {
                    "id": city.id,
                    "name": city.name
                } if city else None
            })

        return jsonify({
            "message": "All managers found successfully",
            "managers": resultado,
            "total": len(resultado)
        }), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error occurred", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": "Unexpected error occurred", "details": str(e)}), 500

# GET - Listar managers por escola
@bp.route('/school/<string:school_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm", "aluno")
def get_managers_by_school(school_id):
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Garantir search_path no schema do tenant: tabela school existe em city_xxx, não em public
        ctx = get_current_tenant_context()
        if ctx and ctx.has_tenant_context and ctx.schema and ctx.schema != "public":
            set_search_path(ctx.schema)
        else:
            # Admin sem X-City-ID ou request sem tenant: descobrir schema onde está a escola
            schema = _schema_for_school_id(school_id)
            if not schema:
                return jsonify({"error": "Escola não encontrada"}), 404
            set_search_path(schema)

        # Verificar se a escola existe
        school = School.query.get(school_id)
        if not school:
            return jsonify({"error": "Escola não encontrada"}), 404

        # Importar modelos necessários
        from app.models.teacher import Teacher
        from app.models.schoolTeacher import SchoolTeacher
        from app.models.manager import Manager
        from app.models.student import Student
        
        # Verificar permissões
        if user['role'] == "admin":
            # Admin pode ver managers de qualquer escola
            pass
        elif user['role'] == "aluno":
            # Aluno só pode ver managers da sua própria escola
            student = Student.query.filter_by(user_id=user['id']).first()
            if not student:
                return jsonify({"error": "Aluno não encontrado"}), 404
            
            if not student.school_id or student.school_id != school_id:
                return jsonify({"error": "Você não tem permissão para visualizar managers desta escola"}), 403
        elif user['role'] == "professor":
            # Professor só pode ver managers da sua escola
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Professor não encontrado"}), 404
            
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            teacher_school_ids = [ts.school_id for ts in teacher_schools]
            
            if school_id not in teacher_school_ids:
                return jsonify({"error": "Você não tem permissão para visualizar managers desta escola"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem ver managers da sua escola
            
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if not manager:
                return jsonify({"error": "Diretor/Coordenador não encontrado na tabela manager"}), 404
            
            if not manager.school_id or manager.school_id != school_id:
                return jsonify({"error": "Você não tem permissão para visualizar managers desta escola"}), 403
        else:
            # TecAdmin só pode ver escolas do seu município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id or school.city_id != city_id:
                return jsonify({"error": "Você não tem permissão para visualizar managers desta escola"}), 403

        # Buscar managers da escola
        managers = db.session.query(
            Manager,
            User,
            School
        ).join(
            User, Manager.user_id == User.id
        ).join(
            School, Manager.school_id == School.id
        ).filter(
            Manager.school_id == school_id,
            User.role.in_([RoleEnum.DIRETOR, RoleEnum.COORDENADOR])
        ).all()

        resultado = []
        for manager_obj, user_obj, school_obj in managers:
            resultado.append({
                "manager": {
                    "id": manager_obj.id,
                    "name": manager_obj.name,
                    "registration": manager_obj.registration,
                    "birth_date": str(manager_obj.birth_date) if manager_obj.birth_date else None,
                    "profile_picture": manager_obj.profile_picture,
                    "school_id": manager_obj.school_id
                },
                "user": {
                    "id": user_obj.id,
                    "name": user_obj.name,
                    "email": user_obj.email,
                    "registration": user_obj.registration,
                    "role": user_obj.role.value
                },
                "school": {
                    "id": school_obj.id,
                    "name": school_obj.name
                }
            })

        return jsonify({
            "message": "Managers found successfully",
            "school": {
                "id": school.id,
                "name": school.name
            },
            "managers": resultado,
            "total": len(resultado)
        }), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error occurred", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": "Unexpected error occurred", "details": str(e)}), 500
