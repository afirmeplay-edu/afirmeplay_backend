from flask import Blueprint, request, jsonify
from app.models.school import School
from app import db
from app.decorators.role_required import role_required, get_current_user_from_token
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
from flask_jwt_extended import jwt_required
from app.decorators.role_required import get_current_tenant_id
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
import logging
from app.models.city import City
from app.models.studentClass import Class
from app.models.student import Student
from app.models.schoolTeacher import SchoolTeacher
from app.models.educationStage import EducationStage
from app.models.grades import Grade
from app.models.schoolCourse import SchoolCourse

import uuid

bp = Blueprint('school', __name__, url_prefix='/school')

# POST - Criar escola
@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin",  "diretor", "coordenador","tecadm")
def criar_escola():
    try:
        data = request.get_json()
        
        if not data:
            logging.error("Dados não fornecidos na requisição")
            return jsonify({"erro": "Dados não fornecidos"}), 400
            
        # Validação dos campos obrigatórios
        required_fields = ['name', 'city_id']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                "erro": "Campos obrigatórios faltando",
                "campos_faltantes": missing_fields
            }), 400

        # Validação do formato dos dados
        if not isinstance(data['name'], str) or len(data['name'].strip()) == 0:
            return jsonify({"erro": "Nome da escola inválido"}), 400
            
        if not isinstance(data['city_id'], str) or not data['city_id'].strip():
            return jsonify({"erro": "ID da cidade inválido"}), 400

        cidade = City.query.get(data['city_id'])
        if not cidade:
            return jsonify({"erro": "city_id não encontrado"}), 400

        nova_escola = School(
            name=data['name'],
            domain=data.get('domain'),
            address=data.get('address'),
            city_id=data['city_id']
        )

        try:
            db.session.add(nova_escola)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao criar escola no banco de dados: {str(e)}")
            return jsonify({
                "erro": "Erro ao salvar escola no banco de dados",
                "detalhes": str(e)
            }), 500

        return jsonify({
            "mensagem": "Escola criada com sucesso!", 
            "id": nova_escola.id
        }), 201

    except Exception as e:
        logging.error(f"Erro inesperado ao criar escola: {str(e)}", exc_info=True)
        return jsonify({
            "erro": "Erro interno do servidor",
            "detalhes": str(e)
        }), 500

# GET - Listar escolas
@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def listar_escolas():
    try:
        user = get_current_user_from_token()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Base query with explicit joins
        query = db.session.query(
            School,
            City,
            db.func.count(Student.id).label('students_count'),
            db.func.count(Class.id).label('classes_count')
        ).join(
            City, School.city_id == City.id
        ).outerjoin(
            Student, School.id == Student.school_id
        ).outerjoin(
            Class, cast(School.id, PostgresUUID) == Class.school_id
        ).group_by(
            School.id, City.id
        )

        schools = []
        if user['role'] == "admin":
            # Admin pode ver todas as escolas
            schools = query.all()
        elif user['role'] == "professor":
            # Professor: buscar primeiro na tabela teacher e depois suas escolas vinculadas
            from app.models.teacher import Teacher
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            
            if not teacher:
                return jsonify({"error": "Professor não encontrado na tabela teacher"}), 404
            
            # Buscar escolas onde o professor está vinculado
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            school_ids = [ts.school_id for ts in teacher_schools]
            
            if school_ids:
                schools = query.filter(School.id.in_(school_ids)).all()
            else:
                return jsonify({"message": "Professor não está alocado em nenhuma escola"}), 404
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador veem apenas sua escola
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            
            if not manager:
                return jsonify({"error": "Diretor/Coordenador não encontrado na tabela manager"}), 404
            
            # Buscar a escola do diretor/coordenador
            if not manager.school_id:
                return jsonify({"error": "Diretor/Coordenador não está vinculado a nenhuma escola"}), 400
            
            # ✅ CORRIGIDO: School.id é VARCHAR, converter manager.school_id para string
            from app.utils.uuid_helpers import uuid_to_str
            school_id_str = uuid_to_str(manager.school_id)
            schools = query.filter(School.id == school_id_str).all() if school_id_str else []
        else:
            # TecAdmin vê escolas do município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return jsonify({"error": "City ID not available for this user"}), 400
            schools = query.filter(School.city_id == city_id).all()

        return jsonify([{
            "id": school.id,
            "name": school.name,
            "domain": school.domain,
            "address": school.address,
            "city_id": school.city_id,
            "created_at": school.created_at.isoformat() if school.created_at else None,
            "students_count": students_count,
            "classes_count": classes_count,
            "city": {
                "id": city.id,
                "name": city.name,
                "state": city.state,
                "created_at": city.created_at.isoformat() if city.created_at else None
            } if city else None
        } for school, city, students_count, classes_count in schools]), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while listing schools: {e}")
        return jsonify({"error": "Internal server error while querying data", "details": str(e)}), 500
    except AttributeError as e:
        logging.error(f"Attribute error while processing user or role: {e}")
        return jsonify({"error": "Error processing user data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in list_schools route: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred on the server"}), 500

   
# PUT - Atualizar escola
@bp.route('/<string:escola_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "diretor")
def atualizar_escola(escola_id):
    try:
        # Validação do ID
        if not escola_id:
            return jsonify({"erro": "ID da escola não fornecido"}), 400

        escola = School.query.get(escola_id)
        if not escola:
            return jsonify({"erro": "Escola não encontrada"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400

        # Validação dos campos
        if 'name' in data and (not isinstance(data['name'], str) or len(data['name'].strip()) == 0):
            return jsonify({"erro": "Nome da escola inválido"}), 400

        if 'city_id' in data and not isinstance(data['city_id'], str):
            return jsonify({"erro": "ID da cidade inválido"}), 400

        # Atualização dos campos
        try:
            escola.name = data.get('name', escola.name)
            escola.domain = data.get('domain', escola.domain)
            escola.address = data.get('address', escola.address)
            escola.city_id = data.get('city_id', escola.city_id)

            db.session.commit()
            return jsonify({
                "mensagem": "Escola atualizada com sucesso",
                "id": escola.id
            }), 200

        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao atualizar escola no banco de dados: {str(e)}")
            return jsonify({
                "erro": "Erro ao atualizar escola no banco de dados",
                "detalhes": str(e)
            }), 500

    except Exception as e:
        logging.error(f"Erro inesperado ao atualizar escola: {str(e)}", exc_info=True)
        return jsonify({
            "erro": "Erro interno do servidor",
            "detalhes": str(e)
        }), 500

# DELETE - Excluir escola
@bp.route('/<string:escola_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin")
def deletar_escola(escola_id):
    try:
        # Validação do ID
        if not escola_id:
            return jsonify({"erro": "ID da escola não fornecido"}), 400

        escola = School.query.get(escola_id)
        if not escola:
            return jsonify({"erro": "Escola não encontrada"}), 404

        try:
            db.session.delete(escola)
            db.session.commit()
            return jsonify({
                "mensagem": "Escola deletada com sucesso",
                "id": escola_id
            }), 200

        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao deletar escola no banco de dados: {str(e)}")
            return jsonify({
                "erro": "Erro ao deletar escola no banco de dados",
                "detalhes": str(e)
            }), 500

    except Exception as e:
        logging.error(f"Erro inesperado ao deletar escola: {str(e)}", exc_info=True)
        return jsonify({
            "erro": "Erro interno do servidor",
            "detalhes": str(e)
        }), 500

# GET - Buscar escola específica
@bp.route('/<string:escola_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def buscar_escola(escola_id):
    try:
        user = get_current_user_from_token()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Query with explicit joins
        result = db.session.query(
            School,
            City,
            db.func.count(Student.id).label('students_count'),
            db.func.count(Class.id).label('classes_count')
        ).join(
            City, School.city_id == City.id
        ).outerjoin(
            Student, School.id == Student.school_id
        ).outerjoin(
            Class, cast(School.id, PostgresUUID) == Class.school_id
        ).filter(
            School.id == escola_id
        ).group_by(
            School.id, City.id
        ).first()

        if not result:
            return jsonify({"error": "School not found"}), 404

        school, city, students_count, classes_count = result

        # Verifica permissões
        if user['role'] == "admin":
            # Admin pode ver qualquer escola
            pass
        elif user['role'] == "professor":
            # Professor: buscar primeiro na tabela teacher e depois verificar se está vinculado à escola
            from app.models.teacher import Teacher
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            
            if not teacher:
                return jsonify({"error": "Professor não encontrado na tabela teacher"}), 404
            
            # Verificar se o professor está vinculado à escola específica
            teacher_school = SchoolTeacher.query.filter_by(
                teacher_id=teacher.id,
                school_id=school.id
            ).first()
            if not teacher_school:
                return jsonify({"error": "You don't have permission to view this school"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem ver sua escola
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            
            if not manager:
                return jsonify({"error": "Diretor/Coordenador não encontrado na tabela manager"}), 404
            
            if not manager.school_id or manager.school_id != school.id:
                return jsonify({"error": "You don't have permission to view this school"}), 403
        else:
            # TecAdmin só pode ver escolas do seu município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id or school.city_id != city_id:
                return jsonify({"error": "You don't have permission to view this school"}), 403

        return jsonify({
            "id": school.id,
            "name": school.name,
            "domain": school.domain,
            "address": school.address,
            "city_id": school.city_id,
            "created_at": school.created_at.isoformat() if school.created_at else None,
            "students_count": students_count,
            "classes_count": classes_count,
            "city": {
                "id": city.id,
                "name": city.name,
                "state": city.state,
                "created_at": city.created_at.isoformat() if city.created_at else None
            } if city else None
        }), 200

    except SQLAlchemyError as e:
        logging.error(f"Database error while fetching school: {e}")
        return jsonify({"error": "Internal server error while querying data", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_school route: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred on the server"}), 500

# GET - Buscar escolas por cidade
@bp.route('/city/<string:city_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def buscar_escolas_por_cidade(city_id):
    try:
        user = get_current_user_from_token()

        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Query com joins explícitos
        query = db.session.query(
            School,
            City,
            db.func.count(Student.id).label('students_count'),
            db.func.count(Class.id).label('classes_count')
        ).join(
            City, School.city_id == City.id
        ).outerjoin(
            Student, School.id == Student.school_id
        ).outerjoin(
            Class, cast(School.id, PostgresUUID) == Class.school_id
        ).filter(
            School.city_id == city_id
        ).group_by(
            School.id, City.id
        )

        # Verifica permissões
        if user['role'] == "admin":
            # Admin pode ver todas as escolas
            schools = query.all()
        elif user['role'] == "professor":
            # Professor: buscar primeiro na tabela teacher e depois suas escolas vinculadas
            from app.models.teacher import Teacher
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            
            if not teacher:
                return jsonify({"error": "Professor não encontrado na tabela teacher"}), 404
            
            # Buscar escolas onde o professor está vinculado
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            school_ids = [ts.school_id for ts in teacher_schools]
            
            if school_ids:
                schools = query.filter(School.id.in_(school_ids)).all()
            else:
                return jsonify({"message": "Professor não está alocado em nenhuma escola"}), 404
        else:
            # Diretor e coordenador só podem ver escolas da mesma cidade
            current_city_id = user.get('tenant_id') or user.get('city_id')
            if city_id != current_city_id:
                return jsonify({"error": "Você não tem permissão para visualizar escolas desta cidade"}), 403
            schools = query.all()

        if not schools:
            return jsonify({"message": "Nenhuma escola encontrada para esta cidade"}), 404

        return jsonify([{
            "id": school.id,
            "name": school.name,
            "domain": school.domain,
            "address": school.address,
            "city_id": school.city_id,
            "created_at": school.created_at.isoformat() if school.created_at else None,
            "students_count": students_count,
            "classes_count": classes_count,
            "city": {
                "id": city.id,
                "name": city.name,
                "state": city.state,
                "created_at": city.created_at.isoformat() if city.created_at else None
            } if city else None
        } for school, city, students_count, classes_count in schools]), 200

    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao buscar escolas por cidade: {e}")
        return jsonify({"error": "Erro interno do servidor ao consultar dados", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro inesperado na rota de busca de escolas por cidade: {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado no servidor"}), 500

# GET - Buscar escolas por série/grade
@bp.route('/by-grade/<string:grade_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def buscar_escolas_por_serie(grade_id):
    try:
        user = get_current_user_from_token()

        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Validação do ID da série
        if not grade_id:
            return jsonify({"erro": "ID da série não fornecido"}), 400

        # Obter parâmetros de query opcionais para filtrar por estado e município
        state = request.args.get('state')
        city_id = request.args.get('city_id')

        # Verificar se a série existe
        from app.models.grades import Grade
        grade = Grade.query.get(grade_id)
        if not grade:
            return jsonify({"erro": "Série não encontrada"}), 404

        # Query com joins para buscar escolas que têm turmas da série específica
        query = db.session.query(
            School,
            City,
            db.func.count(db.distinct(Student.id)).label('students_count'),
            db.func.count(db.distinct(Class.id)).label('classes_count')
        ).join(
            City, School.city_id == City.id
        ).join(
            Class, cast(School.id, PostgresUUID) == Class.school_id
        ).outerjoin(
            Student, School.id == Student.school_id
        ).filter(
            Class.grade_id == grade_id
        )

        # Aplicar filtro por estado se fornecido
        if state:
            query = query.filter(City.state == state)

        # Aplicar filtro por município se fornecido
        if city_id:
            query = query.filter(School.city_id == city_id)

        # Agrupar resultados
        query = query.group_by(School.id, City.id)

        # Aplicar filtros de permissão baseados na role
        if user['role'] == "admin":
            # Admin pode ver todas as escolas
            schools = query.all()
        elif user['role'] == "professor":
            # Professor: buscar escolas onde está vinculado
            from app.models.teacher import Teacher
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            
            if not teacher:
                return jsonify({"error": "Professor não encontrado na tabela teacher"}), 404
            
            # Buscar escolas onde o professor está vinculado
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            school_ids = [ts.school_id for ts in teacher_schools]
            
            if school_ids:
                schools = query.filter(School.id.in_(school_ids)).all()
            else:
                return jsonify({"message": "Professor não está alocado em nenhuma escola"}), 404
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador veem apenas sua escola
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            
            if not manager:
                return jsonify({"error": "Diretor/Coordenador não encontrado na tabela manager"}), 404
            
            if not manager.school_id:
                return jsonify({"error": "Diretor/Coordenador não está vinculado a nenhuma escola"}), 400
            
            # ✅ CORRIGIDO: School.id é VARCHAR, converter manager.school_id para string
            from app.utils.uuid_helpers import uuid_to_str
            school_id_str = uuid_to_str(manager.school_id)
            schools = query.filter(School.id == school_id_str).all() if school_id_str else []
        else:
            # TecAdmin vê escolas do município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return jsonify({"error": "City ID not available for this user"}), 400
            schools = query.filter(School.city_id == city_id).all()

        if not schools:
            return jsonify({
                "message": f"Nenhuma escola encontrada com turmas da série {grade.name}"
            }), 404

        return jsonify({
            "grade": {
                "id": str(grade.id),
                "name": grade.name
            },
            "schools": [{
                "id": school.id,
                "name": school.name,
                "domain": school.domain,
                "address": school.address,
                "city_id": school.city_id,
                "created_at": school.created_at.isoformat() if school.created_at else None,
                "students_count": students_count,
                "classes_count": classes_count,
                "city": {
                    "id": city.id,
                    "name": city.name,
                    "state": city.state,
                    "created_at": city.created_at.isoformat() if city.created_at else None
                } if city else None
            } for school, city, students_count, classes_count in schools]
        }), 200

    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao buscar escolas por série: {e}")
        return jsonify({"error": "Erro interno do servidor ao consultar dados", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro inesperado na rota de busca de escolas por série: {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado no servidor"}), 500

# POST - Adicionar professor a escola(s)
@bp.route('/add-teacher', methods=['POST'])
@jwt_required()
@role_required("admin", "diretor")
def adicionar_professor_escola():
    try:
        data = request.get_json()
        
        if not data:
            logging.error("Dados não fornecidos na requisição")
            return jsonify({"erro": "Dados não fornecidos"}), 400
            
        # Validação dos campos obrigatórios
        required_fields = ['teacher_id', 'school_ids']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                "erro": "Campos obrigatórios faltando",
                "campos_faltantes": missing_fields
            }), 400

        # Validação do formato dos dados
        if not isinstance(data['teacher_id'], str):
            return jsonify({"erro": "ID do professor inválido"}), 400
            
        if not isinstance(data['school_ids'], list) or len(data['school_ids']) == 0:
            return jsonify({"erro": "Lista de IDs das escolas inválida ou vazia"}), 400

        # Verificar se todos os IDs das escolas são strings válidas
        for school_id in data['school_ids']:
            if not isinstance(school_id, str):
                return jsonify({"erro": "ID da escola inválido na lista"}), 400

        # Verificar se o professor existe
        from app.models.teacher import Teacher
        from app.models.user import User
        
        # Primeiro, verificar se é um user_id ou teacher_id
        teacher = None
        user = User.query.get(data['teacher_id'])
        
        if user:
            # Se encontrou um usuário, buscar o professor correspondente
            teacher = Teacher.query.filter_by(user_id=user.id).first()
            if not teacher:
                return jsonify({"erro": "Usuário encontrado, mas não é um professor"}), 404
        else:
            # Se não encontrou usuário, tentar buscar diretamente como teacher_id
            teacher = Teacher.query.get(data['teacher_id'])
            if not teacher:
                return jsonify({"erro": "Professor não encontrado"}), 404

        # Usar o teacher.id correto para as operações
        teacher_id = teacher.id

        # Verificar se as escolas existem
        schools = School.query.filter(School.id.in_(data['school_ids'])).all()
        if len(schools) != len(data['school_ids']):
            found_ids = [school.id for school in schools]
            missing_ids = [school_id for school_id in data['school_ids'] if school_id not in found_ids]
            return jsonify({
                "erro": "Algumas escolas não foram encontradas",
                "escolas_nao_encontradas": missing_ids
            }), 404

        # Verificar permissões (diretor só pode adicionar professores a escolas da sua cidade)
        user = get_current_user_from_token()
        if user['role'] == "diretor":
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return jsonify({"error": "City ID not available for this user"}), 400
            
            # Verificar se todas as escolas pertencem à cidade do diretor
            for school in schools:
                if school.city_id != city_id:
                    return jsonify({
                        "erro": "Você não tem permissão para adicionar professores a escolas de outras cidades"
                    }), 403

        # Verificar se já existem associações
        existing_associations = SchoolTeacher.query.filter_by(teacher_id=teacher_id).all()
        existing_school_ids = [assoc.school_id for assoc in existing_associations]
        
        # Filtrar apenas escolas que ainda não estão associadas
        new_school_ids = [school_id for school_id in data['school_ids'] if school_id not in existing_school_ids]
        
        if not new_school_ids:
            return jsonify({
                "mensagem": "Professor já está associado a todas as escolas especificadas",
                "associacoes_existentes": existing_school_ids
            }), 200

        # Criar novas associações
        novas_associacoes = []
        for school_id in new_school_ids:
            nova_associacao = SchoolTeacher(
                teacher_id=teacher_id,  # Usar o teacher_id correto
                school_id=school_id
            )
            novas_associacoes.append(nova_associacao)

        try:
            db.session.add_all(novas_associacoes)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao adicionar professor às escolas no banco de dados: {str(e)}")
            return jsonify({
                "erro": "Erro ao salvar associações no banco de dados",
                "detalhes": str(e)
            }), 500

        return jsonify({
            "mensagem": "Professor adicionado às escolas com sucesso!",
            "professor_id": teacher_id,  # Usar o teacher_id correto
            "escolas_adicionadas": new_school_ids,
            "associacoes_existentes": existing_school_ids if existing_school_ids else None
        }), 201

    except Exception as e:
        logging.error(f"Erro inesperado ao adicionar professor às escolas: {str(e)}", exc_info=True)
        return jsonify({
            "erro": "Erro interno do servidor",
            "detalhes": str(e)
        }), 500

# GET - Buscar cursos (education stages) vinculados a uma escola específica
@bp.route('/<string:school_id>/courses', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def buscar_cursos_por_escola(school_id):
    """
    Retorna todos os cursos (education stages) vinculados a uma escola específica.
    
    Args:
        school_id: ID da escola
        
    Returns:
        Lista de cursos (education stages) que têm grades com classes na escola
    """
    try:
        user = get_current_user_from_token()
        
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        # Verificar se a escola existe
        school = School.query.get(school_id)
        if not school:
            return jsonify({"error": "Escola não encontrada"}), 404
        
        # Verificar permissões para acessar a escola
        if user['role'] == "admin":
            # Admin pode ver qualquer escola
            pass
        elif user['role'] == "professor":
            # Professor: verificar se está vinculado à escola
            from app.models.teacher import Teacher
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            
            if not teacher:
                return jsonify({"error": "Professor não encontrado"}), 404
            
            teacher_school = SchoolTeacher.query.filter_by(
                teacher_id=teacher.id,
                school_id=school.id
            ).first()
            
            if not teacher_school:
                return jsonify({"error": "Você não tem permissão para acessar esta escola"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem ver sua escola
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            
            if not manager:
                return jsonify({"error": "Diretor/Coordenador não encontrado"}), 404
            
            if not manager.school_id or manager.school_id != school.id:
                return jsonify({"error": "Você não tem permissão para acessar esta escola"}), 403
        else:
            # TecAdmin só pode ver escolas do seu município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id or school.city_id != city_id:
                return jsonify({"error": "Você não tem permissão para acessar esta escola"}), 403
        
        # Buscar cursos vinculados diretamente à escola via school_course
        school_courses = SchoolCourse.query.filter_by(school_id=school_id).all()
        courses = [sc.education_stage for sc in school_courses]
        result = [{"id": str(c.id), "name": c.name} for c in courses]
        
        return jsonify({
            "school_id": school.id,
            "school_name": school.name,
            "courses": result
        }), 200
        
    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao buscar cursos da escola: {e}")
        return jsonify({"error": "Erro interno do servidor ao consultar dados", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro inesperado na rota de busca de cursos por escola: {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado no servidor"}), 500

# POST - Vincular curso(s) (education stage) a uma escola
@bp.route('/<string:school_id>/courses', methods=['POST'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "tecadm")
def vincular_curso_escola(school_id):
    """
    Vincula um ou mais cursos (education stage) a uma escola específica.
    
    Body:
    {
        "education_stage_ids": ["uuid1", "uuid2", "uuid3"]  // Array de IDs
    }
    
    Ou (compatibilidade com versão anterior):
    {
        "education_stage_id": "uuid"  // ID único (será convertido para array)
    }
    
    Permissões:
    - Admin: pode vincular curso a qualquer escola
    - Tecadm: pode vincular curso a escolas do município
    - Diretor/Coordenador: pode vincular curso apenas à sua escola
    """
    try:
        user = get_current_user_from_token()
        
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Aceitar tanto array quanto ID único (compatibilidade)
        education_stage_ids = data.get('education_stage_ids')
        if not education_stage_ids:
            # Se não forneceu array, verificar se forneceu ID único
            single_id = data.get('education_stage_id')
            if single_id:
                education_stage_ids = [single_id]
            else:
                return jsonify({"error": "education_stage_ids (array) ou education_stage_id é obrigatório"}), 400
        
        # Garantir que é uma lista
        if not isinstance(education_stage_ids, list):
            return jsonify({"error": "education_stage_ids deve ser um array"}), 400
        
        if len(education_stage_ids) == 0:
            return jsonify({"error": "education_stage_ids não pode ser um array vazio"}), 400
        
        # Verificar se a escola existe
        school = School.query.get(school_id)
        if not school:
            return jsonify({"error": "Escola não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == "admin":
            # Admin pode vincular curso a qualquer escola
            pass
        elif user['role'] == "tecadm":
            # TecAdmin só pode vincular cursos a escolas do município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id or school.city_id != city_id:
                return jsonify({"error": "Você não tem permissão para vincular cursos a esta escola"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem vincular cursos à sua escola
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            
            if not manager:
                return jsonify({"error": "Diretor/Coordenador não encontrado"}), 404
            
            if not manager.school_id or manager.school_id != school.id:
                return jsonify({"error": "Você não tem permissão para vincular cursos a esta escola"}), 403
        
        # Verificar se todos os cursos existem
        education_stages = EducationStage.query.filter(EducationStage.id.in_(education_stage_ids)).all()
        found_ids = [str(es.id) for es in education_stages]
        missing_ids = [eid for eid in education_stage_ids if eid not in found_ids]
        
        if missing_ids:
            return jsonify({
                "error": "Alguns cursos não foram encontrados",
                "missing_course_ids": missing_ids
            }), 404
        
        # Verificar vínculos existentes e criar novos
        existing_links = SchoolCourse.query.filter_by(school_id=school_id).filter(
            SchoolCourse.education_stage_id.in_(education_stage_ids)
        ).all()
        
        existing_ids = [str(sc.education_stage_id) for sc in existing_links]
        new_ids = [eid for eid in education_stage_ids if eid not in existing_ids]
        
        # Criar novos vínculos
        new_links = []
        for education_stage_id in new_ids:
            school_course = SchoolCourse(
                school_id=school_id,
                education_stage_id=education_stage_id
            )
            new_links.append(school_course)
        
        try:
            if new_links:
                db.session.add_all(new_links)
                db.session.commit()
            
            # Preparar resposta
            all_courses = {str(es.id): es for es in education_stages}
            linked_courses = []
            already_linked_courses = []
            
            for eid in education_stage_ids:
                course = all_courses.get(eid)
                if course:
                    course_info = {
                        "course_id": str(course.id),
                        "course_name": course.name
                    }
                    if eid in existing_ids:
                        already_linked_courses.append(course_info)
                    else:
                        linked_courses.append(course_info)
            
            response = {
                "message": f"{len(linked_courses)} curso(s) vinculado(s) com sucesso" if linked_courses else "Nenhum curso novo para vincular",
                "school_id": school.id,
                "school_name": school.name,
                "linked_courses": linked_courses,
            }
            
            if already_linked_courses:
                response["already_linked_courses"] = already_linked_courses
                response["message"] += f", {len(already_linked_courses)} curso(s) já estava(m) vinculado(s)"
            
            return jsonify(response), 201 if new_links else 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao vincular curso à escola: {e}")
            return jsonify({"error": "Erro ao salvar vínculo no banco de dados", "details": str(e)}), 500
        
    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao vincular curso à escola: {e}")
        return jsonify({"error": "Erro interno do servidor ao consultar dados", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro inesperado na rota de vincular curso à escola: {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado no servidor"}), 500

# DELETE - Desvincular curso (education stage) de uma escola
@bp.route('/<string:school_id>/courses/<string:education_stage_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "tecadm")
def desvincular_curso_escola(school_id, education_stage_id):
    """
    Desvincula um curso (education stage) de uma escola específica.
    
    Permissões:
    - Admin: pode desvincular curso de qualquer escola
    - Tecadm: pode desvincular curso de escolas do município
    - Diretor/Coordenador: pode desvincular curso apenas da sua escola
    """
    try:
        user = get_current_user_from_token()
        
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        # Verificar se a escola existe
        school = School.query.get(school_id)
        if not school:
            return jsonify({"error": "Escola não encontrada"}), 404
        
        # Verificar se o curso existe
        education_stage = EducationStage.query.get(education_stage_id)
        if not education_stage:
            return jsonify({"error": "Curso não encontrado"}), 404
        
        # Verificar permissões
        if user['role'] == "admin":
            # Admin pode desvincular curso de qualquer escola
            pass
        elif user['role'] == "tecadm":
            # TecAdmin só pode desvincular cursos de escolas do município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id or school.city_id != city_id:
                return jsonify({"error": "Você não tem permissão para desvincular cursos desta escola"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem desvincular cursos da sua escola
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            
            if not manager:
                return jsonify({"error": "Diretor/Coordenador não encontrado"}), 404
            
            if not manager.school_id or manager.school_id != school.id:
                return jsonify({"error": "Você não tem permissão para desvincular cursos desta escola"}), 403
        
        # Buscar vínculo
        school_course = SchoolCourse.query.filter_by(
            school_id=school_id,
            education_stage_id=education_stage_id
        ).first()
        
        if not school_course:
            return jsonify({"error": "Curso não está vinculado a esta escola"}), 404
        
        # Verificar se há turmas usando este curso (através de grades)
        # Se houver turmas vinculadas a grades deste curso, não permitir desvincular
        classes_with_course = db.session.query(Class).join(
            Grade, Class.grade_id == Grade.id
        ).filter(
            Grade.education_stage_id == education_stage_id,
            Class.school_id == school_id
        ).first()
        
        if classes_with_course:
            return jsonify({
                "error": "Não é possível desvincular curso que possui turmas vinculadas",
                "details": "Existem turmas que usam este curso através de suas séries"
            }), 400
        
        try:
            db.session.delete(school_course)
            db.session.commit()
            
            return jsonify({
                "message": "Curso desvinculado da escola com sucesso",
                "school_id": school.id,
                "school_name": school.name,
                "course_id": str(education_stage.id),
                "course_name": education_stage.name
            }), 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao desvincular curso da escola: {e}")
            return jsonify({"error": "Erro ao remover vínculo do banco de dados", "details": str(e)}), 500
        
    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados ao desvincular curso da escola: {e}")
        return jsonify({"error": "Erro interno do servidor ao consultar dados", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro inesperado na rota de desvincular curso da escola: {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado no servidor"}), 500
