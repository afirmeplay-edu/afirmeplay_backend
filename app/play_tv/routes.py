from flask import Blueprint, request, jsonify, make_response
from app.play_tv.models import PlayTvVideo, PlayTvVideoSchool, PlayTvVideoClass
from app.models.school import School
from app.models.grades import Grade
from app.models.subject import Subject
from app.models.city import City
from app.models.studentClass import Class
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

bp = Blueprint('playtv', __name__, url_prefix='/play-tv')

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

@bp.route('/videos', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def list_videos():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Query base com joins
        query = db.session.query(PlayTvVideo).join(
            PlayTvVideoSchool, PlayTvVideo.id == PlayTvVideoSchool.video_id
        ).join(
            School, PlayTvVideoSchool.school_id == School.id
        ).join(
            City, School.city_id == City.id
        ).join(
            Grade, PlayTvVideo.grade_id == Grade.id
        ).join(
            Subject, PlayTvVideo.subject_id == Subject.id
        ).outerjoin(
            Class, (Class.school_id == School.id) & (Class.grade_id == Grade.id)
        ).distinct()
        
        # Aplicar filtros hierárquicos (query parameters)
        state = request.args.get('state')
        municipality = request.args.get('municipality') or request.args.get('municipality_id')
        school = request.args.get('school') or request.args.get('school_id')
        grade = request.args.get('grade') or request.args.get('grade_id')
        subject = request.args.get('subject') or request.args.get('subject_id')
        class_id = request.args.get('class') or request.args.get('class_id')
        
        if state:
            query = query.filter(City.state.ilike(f"%{state}%"))
        
        if municipality:
            city_obj = City.query.get(municipality)
            if city_obj:
                query = query.filter(City.id == municipality)
            else:
                query = query.filter(City.name.ilike(f"%{municipality}%"))
        
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
        
        if class_id:
            class_obj = Class.query.get(class_id)
            if class_obj:
                query = query.filter(Class.id == class_id)
        
        # Aplicar filtros de permissão por role (seguindo padrão de `grades_routes.py`)
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
                    (PlayTvVideo.grade_id == student.grade_id) &
                    (School.id == student.school_id)
                )
        
        videos = query.all()
        
        # Formatar resposta
        result = []
        for video in videos:
            result.append({
                "id": video.id,
                "url": video.url,
                "title": video.title,
                "schools": [{"id": vs.school.id, "name": vs.school.name} for vs in video.video_schools],
                "classes": [{"id": vc.class_.id, "name": vc.class_.name} for vc in video.video_classes],
                "grade": {"id": str(video.grade.id), "name": video.grade.name} if video.grade else None,
                "subject": {"id": video.subject.id, "name": video.subject.name} if video.subject else None,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "created_by": {
                    "id": video.creator.id,
                    "name": video.creator.name
                } if video.creator else None
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar vídeos: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao listar vídeos", "detalhes": str(e)}), 500

@bp.route('/videos', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "diretor", "coordenador", "tecadm")
def create_video():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        # Validações de campos obrigatórios
        required_fields = ["url", "schools", "grade", "subject"]
        for field in required_fields:
            if field not in data:
                return jsonify({"erro": f"Campo obrigatório ausente: {field}"}), 400
        
        # Validar URL
        url = data["url"].strip()
        if not url:
            return jsonify({"erro": "URL não pode estar vazia"}), 400
        
        parsed_url = urlparse(url)
        if not parsed_url.scheme or parsed_url.scheme not in ['http', 'https']:
            return jsonify({"erro": "URL inválida. Deve começar com http:// ou https://"}), 400
        
        # Validar título (se fornecido)
        title = data.get("title")
        if title and len(title) > 100:
            return jsonify({"erro": "Título não pode exceder 100 caracteres"}), 400
        
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
        
        # Validar classes (opcional)
        classes_ids = data.get("classes", [])
        classes = []
        if classes_ids:
            if not isinstance(classes_ids, list):
                return jsonify({"erro": "Classes deve ser uma lista"}), 400
            
            # Validar que as classes existem
            classes = Class.query.filter(Class.id.in_(classes_ids)).all()
            if len(classes) != len(classes_ids):
                return jsonify({"erro": "Uma ou mais classes não encontradas"}), 404
            
            # Validar que as classes pertencem às escolas selecionadas
            class_school_ids = {c.school_id for c in classes}
            school_ids_set = {s.id for s in schools}
            if not class_school_ids.issubset(school_ids_set):
                return jsonify({"erro": "Todas as classes devem pertencer às escolas selecionadas"}), 400
        
        # Obter usuário autenticado
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401
        
        # Validar permissões para criar nas escolas selecionadas
        if current_user['role'] == 'tecadm':
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if city_id:
                for school in schools:
                    if school.city_id != city_id:
                        return jsonify({"erro": f"Você não tem permissão para criar vídeos na escola {school.name}"}), 403
        elif current_user['role'] in ['diretor', 'coordenador']:
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if manager and manager.school_id:
                for school in schools:
                    if school.id != manager.school_id:
                        return jsonify({"erro": f"Você não tem permissão para criar vídeos na escola {school.name}"}), 403
        elif current_user['role'] == 'professor':
            teacher = Teacher.query.filter_by(user_id=current_user['id']).first()
            if teacher:
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                allowed_school_ids = [ts.school_id for ts in teacher_schools]
                for school in schools:
                    if school.id not in allowed_school_ids:
                        return jsonify({"erro": f"Você não tem permissão para criar vídeos na escola {school.name}"}), 403
        
        # Criar vídeo
        new_video = PlayTvVideo(
            url=url,
            title=title,
            grade_id=grade_id,
            subject_id=subject_id,
            created_by=current_user['id']
        )
        
        db.session.add(new_video)
        db.session.flush()  # Para obter o ID antes de criar associações
        
        # Criar associações com escolas
        for school in schools:
            video_school = PlayTvVideoSchool(
                video_id=new_video.id,
                school_id=school.id
            )
            db.session.add(video_school)
        
        # Criar associações com classes (se fornecidas)
        for class_obj in classes:
            video_class = PlayTvVideoClass(
                video_id=new_video.id,
                class_id=class_obj.id
            )
            db.session.add(video_class)
        
        db.session.commit()
        
        return jsonify({
            "mensagem": "Vídeo criado com sucesso!",
            "video": {
                "id": new_video.id,
                "url": new_video.url,
                "title": new_video.title,
                "schools": [{"id": s.id, "name": s.name} for s in schools],
                "classes": [{"id": c.id, "name": c.name} for c in classes] if classes else [],
                "grade": {"id": str(grade.id), "name": grade.name},
                "subject": {"id": subject.id, "name": subject.name},
                "created_at": new_video.created_at.isoformat() if new_video.created_at else None
            }
        }), 201
        
    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except IntegrityError as e:
        logging.error(f"Erro de integridade: {str(e)}")
        return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao criar vídeo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao criar vídeo", "detalhes": str(e)}), 500

@bp.route('/videos/<string:video_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def get_video(video_id):
    try:
        video = PlayTvVideo.query.get(video_id)
        
        if not video:
            return jsonify({"erro": "Vídeo não encontrado"}), 404
        
        # Verificar permissões de acesso (seguindo padrão de `school_routes.py`)
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Verificar se usuário tem acesso às escolas do vídeo
        video_school_ids = [vs.school_id for vs in video.video_schools]
        
        if user['role'] == 'tecadm':
            city_id = user.get('tenant_id') or user.get('city_id')
            if city_id:
                schools = School.query.filter(School.id.in_(video_school_ids), School.city_id == city_id).all()
                if not schools:
                    return jsonify({"erro": "Você não tem permissão para acessar este vídeo"}), 403
        elif user['role'] in ['diretor', 'coordenador']:
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if manager and manager.school_id:
                if manager.school_id not in video_school_ids:
                    return jsonify({"erro": "Você não tem permissão para acessar este vídeo"}), 403
        elif user['role'] == 'professor':
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                allowed_school_ids = [ts.school_id for ts in teacher_schools]
                if not any(sid in allowed_school_ids for sid in video_school_ids):
                    return jsonify({"erro": "Você não tem permissão para acessar este vídeo"}), 403
        elif user['role'] == 'aluno':
            student = Student.query.filter_by(user_id=user['id']).first()
            if student:
                if (video.grade_id != student.grade_id or 
                    student.school_id not in video_school_ids):
                    return jsonify({"erro": "Você não tem permissão para acessar este vídeo"}), 403
        
        return jsonify({
            "id": video.id,
            "url": video.url,
            "title": video.title,
            "schools": [{"id": vs.school.id, "name": vs.school.name} for vs in video.video_schools],
            "classes": [{"id": vc.class_.id, "name": vc.class_.name} for vc in video.video_classes],
            "grade": {"id": str(video.grade.id), "name": video.grade.name} if video.grade else None,
            "subject": {"id": video.subject.id, "name": video.subject.name} if video.subject else None,
            "created_at": video.created_at.isoformat() if video.created_at else None,
            "created_by": {
                "id": video.creator.id,
                "name": video.creator.name
            } if video.creator else None
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar vídeo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao buscar vídeo", "detalhes": str(e)}), 500

@bp.route('/videos/<string:video_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "diretor", "coordenador", "tecadm")
def delete_video(video_id):
    try:
        video = PlayTvVideo.query.get(video_id)
        
        if not video:
            return jsonify({"erro": "Vídeo não encontrado"}), 404
        
        # Verificar permissões de exclusão
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401
        
        # Admin pode deletar qualquer vídeo
        if current_user['role'] not in ['admin', 'tecadm']:
            # Verificar se é o criador
            if video.created_by != current_user['id']:
                # Verificar permissões por role
                if current_user['role'] == 'tecadm':
                    city_id = current_user.get('tenant_id') or current_user.get('city_id')
                    if city_id:
                        video_school_ids = [vs.school_id for vs in video.video_schools]
                        schools = School.query.filter(School.id.in_(video_school_ids), School.city_id == city_id).all()
                        if not schools:
                            return jsonify({"erro": "Sem permissão para excluir este vídeo"}), 403
                elif current_user['role'] in ['diretor', 'coordenador']:
                    manager = Manager.query.filter_by(user_id=current_user['id']).first()
                    if manager and manager.school_id:
                        video_school_ids = [vs.school_id for vs in video.video_schools]
                        if manager.school_id not in video_school_ids:
                            return jsonify({"erro": "Sem permissão para excluir este vídeo"}), 403
                elif current_user['role'] == 'professor':
                    # Professor só pode deletar vídeos que criou
                    return jsonify({"erro": "Sem permissão para excluir este vídeo"}), 403
        
        # Deletar vídeo (cascade deletará automaticamente os registros em play_tv_video_schools)
        db.session.delete(video)
        db.session.commit()
        
        return jsonify({"mensagem": "Vídeo excluído com sucesso!"}), 200
        
    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro ao excluir vídeo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao excluir vídeo", "detalhes": str(e)}), 500



