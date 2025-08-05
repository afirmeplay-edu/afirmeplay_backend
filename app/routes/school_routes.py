from flask import Blueprint, request, jsonify
from app.models.school import School
from app import db
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from app.utils.auth import get_current_tenant_id
from sqlalchemy.exc import SQLAlchemyError
import logging
from app.models.city import City
from app.models.studentClass import Class
from app.models.student import Student
from app.models.schoolTeacher import SchoolTeacher

import uuid

bp = Blueprint('school', __name__, url_prefix='/school')

# POST - Criar escola
@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin",  "diretor", "coordenador",)
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
            
        if not isinstance(data['city_id'], str):
            return jsonify({"erro": "ID da cidade inválido"}), 400

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
@role_required("admin", "diretor", "coordenador", "professor")
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
            Class, School.id == Class.school_id
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
            from app.models.teacher import Teacher
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            
            if not teacher:
                return jsonify({"error": "Diretor/Coordenador não encontrado na tabela teacher"}), 404
            
            # Buscar a escola do diretor/coordenador
            teacher_school = SchoolTeacher.query.filter_by(teacher_id=teacher.id).first()
            if not teacher_school:
                return jsonify({"error": "Diretor/Coordenador não está vinculado a nenhuma escola"}), 400
            
            schools = query.filter(School.id == teacher_school.school_id).all()
        else:
            # TecAdmin vê escolas do município
            city_id = get_current_tenant_id()
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
@role_required("admin", "diretor", "coordenador", "professor")
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
            Class, School.id == Class.school_id
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
            from app.models.teacher import Teacher
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            
            if not teacher:
                return jsonify({"error": "Diretor/Coordenador não encontrado na tabela teacher"}), 404
            
            teacher_school = SchoolTeacher.query.filter_by(teacher_id=teacher.id).first()
            if not teacher_school or teacher_school.school_id != school.id:
                return jsonify({"error": "You don't have permission to view this school"}), 403
        else:
            # TecAdmin só pode ver escolas do seu município
            city_id = get_current_tenant_id()
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
@role_required("admin", "diretor", "coordenador", "professor")
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
            Class, School.id == Class.school_id
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
            if city_id != get_current_tenant_id():
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
        teacher = Teacher.query.get(data['teacher_id'])
        if not teacher:
            return jsonify({"erro": "Professor não encontrado"}), 404

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
            city_id = get_current_tenant_id()
            if not city_id:
                return jsonify({"error": "City ID not available for this user"}), 400
            
            # Verificar se todas as escolas pertencem à cidade do diretor
            for school in schools:
                if school.city_id != city_id:
                    return jsonify({
                        "erro": "Você não tem permissão para adicionar professores a escolas de outras cidades"
                    }), 403

        # Verificar se já existem associações
        existing_associations = SchoolTeacher.query.filter_by(teacher_id=data['teacher_id']).all()
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
                teacher_id=data['teacher_id'],
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
            "professor_id": data['teacher_id'],
            "escolas_adicionadas": new_school_ids,
            "associacoes_existentes": existing_school_ids if existing_school_ids else None
        }), 201

    except Exception as e:
        logging.error(f"Erro inesperado ao adicionar professor às escolas: {str(e)}", exc_info=True)
        return jsonify({
            "erro": "Erro interno do servidor",
            "detalhes": str(e)
        }), 500
