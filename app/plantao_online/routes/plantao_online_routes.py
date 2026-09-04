from flask import Blueprint, request, jsonify, make_response
from app.plantao_online.models import PlantaoOnline, PlantaoOnlineSchool
from app.models.school import School
from app.models.grades import Grade
from app.models.subject import Subject
from app.models.city import City
from app.models.manager import Manager
from app.models.teacher import Teacher
from app.models.schoolTeacher import SchoolTeacher
from app.models.student import Student
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app import db
import logging
from urllib.parse import urlparse

bp = Blueprint('plantao_online', __name__, url_prefix='/plantao-online')

# Handler para requisições OPTIONS (preflight CORS)
@bp.before_request
def handle_options():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        return response

# Error handlers seguindo padrão (sem rollback explícito, deixar Flask-SQLAlchemy gerenciar)
@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    logging.error(f"Database error: {str(error)}")
    return jsonify({"erro": "Erro no banco de dados", "detalhes": str(error)}), 500

@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    logging.error(f"Integrity error: {str(error)}")
    return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(error)}), 400

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"erro": "Erro interno do servidor", "detalhes": str(error)}), 500

@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def list_plantoes():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Query base com joins
        query = db.session.query(PlantaoOnline).join(
            PlantaoOnlineSchool, PlantaoOnline.id == PlantaoOnlineSchool.plantao_id
        ).join(
            School, PlantaoOnlineSchool.school_id == School.id
        ).join(
            City, School.city_id == City.id
        ).join(
            Grade, PlantaoOnline.grade_id == Grade.id
        ).join(
            Subject, PlantaoOnline.subject_id == Subject.id
        ).distinct()
        
        # Aplicar filtros hierárquicos (query parameters)
        school = request.args.get('school') or request.args.get('school_id')
        grade = request.args.get('grade') or request.args.get('grade_id')
        subject = request.args.get('subject') or request.args.get('subject_id')
        
        if school:
            school_obj = School.query.get(school)
            if school_obj:
                query = query.filter(School.id == school)
            else:
                query = query.filter(School.name.ilike(f"%{school}%"))
        
        if grade:
            grade_obj = Grade.query.get(grade)
            if grade_obj:
                query = query.filter(Grade.id == grade)
            else:
                query = query.filter(Grade.name.ilike(f"%{grade}%"))
        
        if subject:
            subject_obj = Subject.query.get(subject)
            if subject_obj:
                query = query.filter(Subject.id == subject)
            else:
                query = query.filter(Subject.name.ilike(f"%{subject}%"))
        
        # Aplicar filtros de permissão por role (seguindo padrão do PlayTV)
        if user['role'] == 'tecadm':
            city_id = user.get('tenant_id') or user.get('city_id')
            if city_id:
                query = query.filter(City.id == city_id)
        elif user['role'] in ['diretor', 'coordenador']:
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if manager and manager.school_id:
                query = query.filter(School.id == manager.school_id)
        elif user['role'] == 'professor':
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                school_ids = [ts.school_id for ts in teacher_schools]
                if school_ids:
                    query = query.filter(School.id.in_(school_ids))
        elif user['role'] == 'aluno':
            student = Student.query.filter_by(user_id=user['id']).first()
            if student:
                query = query.filter(
                    (PlantaoOnline.grade_id == student.grade_id) &
                    (School.id == student.school_id)
                )
        
        plantoes = query.all()
        
        # Formatar resposta
        result = []
        for plantao in plantoes:
            result.append({
                "id": plantao.id,
                "link": plantao.link,
                "title": plantao.title,
                "schools": [{"id": ps.school.id, "name": ps.school.name} for ps in plantao.plantao_schools],
                "grade": {"id": str(plantao.grade.id), "name": plantao.grade.name} if plantao.grade else None,
                "subject": {"id": plantao.subject.id, "name": plantao.subject.name} if plantao.subject else None,
                "created_at": plantao.created_at.isoformat() if plantao.created_at else None,
                "created_by": {
                    "id": plantao.creator.id,
                    "name": plantao.creator.name
                } if plantao.creator else None
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar plantões: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao listar plantões", "detalhes": str(e)}), 500

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "diretor", "coordenador", "tecadm")
def create_plantao():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        # Validações de campos obrigatórios
        required_fields = ["link", "schools", "grade", "subject"]
        for field in required_fields:
            if field not in data:
                return jsonify({"erro": f"Campo obrigatório ausente: {field}"}), 400
        
        # Validar link (URL)
        link = data["link"].strip()
        if not link:
            return jsonify({"erro": "Link não pode estar vazio"}), 400
        
        parsed_url = urlparse(link)
        if not parsed_url.scheme or parsed_url.scheme not in ['http', 'https']:
            return jsonify({"erro": "Link inválido. Deve começar com http:// ou https://"}), 400
        
        # Validar título (se fornecido)
        title = data.get("title")
        
        # Validar escolas
        schools_ids = data["schools"]
        if not isinstance(schools_ids, list) or len(schools_ids) == 0:
            return jsonify({"erro": "Pelo menos uma escola deve ser selecionada"}), 400
        
        # Validar que as escolas existem
        schools = School.query.filter(School.id.in_(schools_ids)).all()
        if len(schools) != len(schools_ids):
            return jsonify({"erro": "Uma ou mais escolas não encontradas"}), 404
        
        # Validar série
        grade_id = data["grade"]
        grade = Grade.query.get(grade_id)
        if not grade:
            return jsonify({"erro": "Série não encontrada"}), 404
        
        # Validar disciplina
        subject_id = data["subject"]
        subject = Subject.query.get(subject_id)
        if not subject:
            return jsonify({"erro": "Disciplina não encontrada"}), 404
        
        # Obter usuário autenticado
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401
        
        # Validar permissões para criar nas escolas selecionadas (mesmas regras do PlayTV)
        if current_user['role'] == 'tecadm':
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if city_id:
                for school in schools:
                    if school.city_id != city_id:
                        return jsonify({"erro": f"Você não tem permissão para criar plantões na escola {school.name}"}), 403
        elif current_user['role'] in ['diretor', 'coordenador']:
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if manager and manager.school_id:
                for school in schools:
                    if school.id != manager.school_id:
                        return jsonify({"erro": f"Você não tem permissão para criar plantões na escola {school.name}"}), 403
        elif current_user['role'] == 'professor':
            teacher = Teacher.query.filter_by(user_id=current_user['id']).first()
            if teacher:
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                allowed_school_ids = [ts.school_id for ts in teacher_schools]
                for school in schools:
                    if school.id not in allowed_school_ids:
                        return jsonify({"erro": f"Você não tem permissão para criar plantões na escola {school.name}"}), 403
        
        # Criar plantão
        new_plantao = PlantaoOnline(
            link=link,
            title=title,
            grade_id=grade_id,
            subject_id=subject_id,
            created_by=current_user['id']
        )
        
        db.session.add(new_plantao)
        db.session.flush()  # Para obter o ID antes de criar associações
        
        # Criar associações com escolas
        for school in schools:
            plantao_school = PlantaoOnlineSchool(
                plantao_id=new_plantao.id,
                school_id=school.id
            )
            db.session.add(plantao_school)
        
        db.session.commit()
        
        return jsonify({
            "mensagem": "Plantão criado com sucesso!",
            "plantao": {
                "id": new_plantao.id,
                "link": new_plantao.link,
                "title": new_plantao.title,
                "schools": [{"id": s.id, "name": s.name} for s in schools],
                "grade": {"id": str(grade.id), "name": grade.name},
                "subject": {"id": subject.id, "name": subject.name},
                "created_at": new_plantao.created_at.isoformat() if new_plantao.created_at else None
            }
        }), 201
        
    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except IntegrityError as e:
        logging.error(f"Erro de integridade: {str(e)}")
        return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao criar plantão: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao criar plantão", "detalhes": str(e)}), 500

@bp.route('/student', methods=['GET'])
@jwt_required()
@role_required("aluno")
def list_plantoes_student():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Buscar dados do aluno
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"erro": "Aluno não encontrado"}), 404
        
        if not student.grade_id or not student.school_id:
            return jsonify({"erro": "Aluno não possui série ou escola vinculada"}), 400
        
        # Query base com joins
        query = db.session.query(PlantaoOnline).join(
            PlantaoOnlineSchool, PlantaoOnline.id == PlantaoOnlineSchool.plantao_id
        ).join(
            School, PlantaoOnlineSchool.school_id == School.id
        ).join(
            Grade, PlantaoOnline.grade_id == Grade.id
        ).join(
            Subject, PlantaoOnline.subject_id == Subject.id
        ).filter(
            (PlantaoOnline.grade_id == student.grade_id) &
            (School.id == student.school_id)
        ).distinct()
        
        # Filtro opcional por disciplina
        subject = request.args.get('subject') or request.args.get('subject_id')
        if subject:
            subject_obj = Subject.query.get(subject)
            if subject_obj:
                query = query.filter(Subject.id == subject)
            else:
                query = query.filter(Subject.name.ilike(f"%{subject}%"))
        
        plantoes = query.all()
        
        # Formatar resposta
        result = []
        for plantao in plantoes:
            result.append({
                "id": plantao.id,
                "link": plantao.link,
                "title": plantao.title,
                "schools": [{"id": ps.school.id, "name": ps.school.name} for ps in plantao.plantao_schools],
                "grade": {"id": str(plantao.grade.id), "name": plantao.grade.name} if plantao.grade else None,
                "subject": {"id": plantao.subject.id, "name": plantao.subject.name} if plantao.subject else None,
                "created_at": plantao.created_at.isoformat() if plantao.created_at else None
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar plantões para aluno: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao listar plantões", "detalhes": str(e)}), 500

@bp.route('/<string:plantao_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "diretor", "coordenador", "tecadm")
def delete_plantao(plantao_id):
    """Deleta um plantão. Valida permissões seguindo as mesmas regras do PlayTV."""
    try:
        # Verificar autenticação
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401
        
        # Verificar se o plantão existe
        plantao = PlantaoOnline.query.get(plantao_id)
        if not plantao:
            return jsonify({"erro": "Plantão não encontrado"}), 404
        
        # Verificar permissões de acesso (mesmas regras do PlayTV)
        plantao_school_ids = [ps.school_id for ps in plantao.plantao_schools]
        
        # Admin pode deletar qualquer plantão
        if current_user['role'] != 'admin':
            if current_user['role'] == 'tecadm':
                city_id = current_user.get('tenant_id') or current_user.get('city_id')
                if city_id:
                    schools = School.query.filter(School.id.in_(plantao_school_ids), School.city_id == city_id).all()
                    if not schools:
                        return jsonify({"erro": "Você não tem permissão para excluir este plantão"}), 403
            elif current_user['role'] in ['diretor', 'coordenador']:
                manager = Manager.query.filter_by(user_id=current_user['id']).first()
                if manager and manager.school_id:
                    if manager.school_id not in plantao_school_ids:
                        return jsonify({"erro": "Você não tem permissão para excluir este plantão"}), 403
            elif current_user['role'] == 'professor':
                teacher = Teacher.query.filter_by(user_id=current_user['id']).first()
                if teacher:
                    teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                    allowed_school_ids = [ts.school_id for ts in teacher_schools]
                    if not any(sid in allowed_school_ids for sid in plantao_school_ids):
                        return jsonify({"erro": "Você não tem permissão para excluir este plantão"}), 403
        
        # Deletar plantão (cascade deletará automaticamente os registros em plantao_schools)
        db.session.delete(plantao)
        db.session.commit()
        
        logging.info(f"Plantão {plantao_id} deletado por usuário {current_user['id']}")
        return jsonify({"mensagem": "Plantão excluído com sucesso!"}), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao excluir plantão: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao excluir plantão", "detalhes": str(e)}), 500
