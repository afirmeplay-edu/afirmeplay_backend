from flask import Blueprint, request, jsonify
from app.models.schoolTeacher import SchoolTeacher
from app.models.teacher import Teacher
from app.models.user import User
from app.models.manager import Manager
from app.models.school import School
from app.decorators.role_required import role_required, get_current_user_from_token
from app import db
import uuid
import logging
from flask_jwt_extended import jwt_required, get_jwt_identity

school_teacher_bp = Blueprint('school_teacher', __name__)

@school_teacher_bp.route('/school-teacher', methods=['POST'])
@jwt_required()
@role_required('admin', 'tecadm', 'diretor', 'coordenador',"professor")
def create_school_teacher():
    data = request.get_json()
    logging.info(f"Dados recebidos para vincular professor à escola: {data}")
    
    try:
        # Obter usuário atual
        current_user = get_current_user_from_token()
        
        # Verificar permissões baseadas no role
        school_id = data.get('school_id')
        
        if current_user['role'] == 'tecadm':
            # Tecadm só pode vincular professores a escolas do seu município
            school = School.query.get(school_id)
            if not school or school.city_id != current_user['city_id']:
                return jsonify({"erro": "Você só pode vincular professores a escolas do seu município"}), 403
        elif current_user['role'] in ['diretor', 'coordenador']:
            # Diretor/coordenador só pode vincular professores à sua escola
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or manager.school_id != school_id:
                return jsonify({"erro": "Você só pode vincular professores à sua escola"}), 403
        
        # Verificar se o professor existe
        teacher = None
        user = User.query.get(data.get('teacher_id'))
        logging.info(f"Buscando usuário com ID: {data.get('teacher_id')}")
        
        if user:
            logging.info(f"Usuário encontrado: {user.name} ({user.email})")
            # Se encontrou um usuário, buscar o professor correspondente
            teacher = Teacher.query.filter_by(user_id=user.id).first()
            if not teacher:
                logging.error(f"Usuário {user.email} não é um professor")
                return jsonify({"erro": "Usuário encontrado, mas não é um professor"}), 404
            logging.info(f"Professor encontrado: {teacher.name} (ID: {teacher.id})")
        else:
            logging.info(f"Usuário não encontrado, tentando buscar como teacher_id")
            # Se não encontrou usuário, tentar buscar diretamente como teacher_id
            teacher = Teacher.query.get(data.get('teacher_id'))
            if not teacher:
                logging.error(f"Professor não encontrado com ID: {data.get('teacher_id')}")
                return jsonify({"erro": "Professor não encontrado"}), 404
            logging.info(f"Professor encontrado diretamente: {teacher.name} (ID: {teacher.id})")

        # Usar o teacher.id correto
        teacher_id = teacher.id
        registration = data.get('registration')
        logging.info(f"Vincular professor {teacher_id} à escola {school_id}")
        
        # Verificar se já existe o vínculo
        existing_vinculo = SchoolTeacher.query.filter_by(
            teacher_id=teacher_id,
            school_id=school_id
        ).first()
        
        if existing_vinculo:
            logging.warning(f"Vínculo já existe: professor {teacher_id} já está vinculado à escola {school_id}")
            return jsonify({
                "erro": "Professor já está vinculado a esta escola",
                "school_teacher": {
                    'id': existing_vinculo.id,
                    'teacher_id': str(existing_vinculo.teacher_id),
                    'school_id': existing_vinculo.school_id
                }
            }), 400
        
        school_teacher = SchoolTeacher(
            registration=registration,
            school_id=school_id,
            teacher_id=teacher_id  # Usar o teacher_id correto
        )
        
        logging.info(f"Criando vínculo: teacher_id={teacher_id}, school_id={school_id}, registration={registration}")
        db.session.add(school_teacher)
        db.session.commit()
        logging.info(f"Vínculo criado com sucesso. ID: {school_teacher.id}")
        
        return jsonify({
            'message': 'Professor vinculado à escola com sucesso',
            'school_teacher': {
                'id': school_teacher.id,
                'registration': school_teacher.registration,
                'school_id': school_teacher.school_id,
                'teacher_id': str(school_teacher.teacher_id)
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao vincular professor à escola: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 400

@school_teacher_bp.route('/school-teacher', methods=['GET'])
@jwt_required()
@role_required('admin', 'tecadm', 'diretor', 'coordenador',"professor")
def get_school_teachers():
    try:
        # Obter usuário atual
        current_user = get_current_user_from_token()
        
        # Aplicar filtros baseados no role
        if current_user['role'] == 'admin':
            # Admin vê todos os vínculos
            vinculos = SchoolTeacher.query.all()
        elif current_user['role'] == 'tecadm':
            # Tecadm vê vínculos de escolas do seu município
            school_ids = db.session.query(School.id).filter(School.city_id == current_user['city_id']).all()
            school_ids = [sid[0] for sid in school_ids]
            vinculos = SchoolTeacher.query.filter(SchoolTeacher.school_id.in_(school_ids)).all()
        elif current_user['role'] in ['diretor', 'coordenador']:
            # Diretor/coordenador vê vínculos da sua escola
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager:
                return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 403
            vinculos = SchoolTeacher.query.filter_by(school_id=manager.school_id).all()
        elif current_user['role'] == 'professor':
            # Professor vê apenas o seu próprio vínculo
            teacher = Teacher.query.filter_by(user_id=current_user['id']).first()
            if not teacher:
                return jsonify({"erro": "Usuário não está vinculado como professor"}), 403
            vinculos = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
        else:
            # Role não reconhecido
            return jsonify({"erro": "Role não autorizado para esta operação"}), 403
        
        # Verificar se vinculos foi definido
        if 'vinculos' not in locals():
            return jsonify({"erro": "Erro interno: role não processado corretamente"}), 500
        
        resultado = []
        for vinculo in vinculos:
            # Buscar dados do professor
            teacher = Teacher.query.get(vinculo.teacher_id)
            user = User.query.get(teacher.user_id) if teacher else None
            
            # Buscar dados da escola
            school = School.query.get(vinculo.school_id)
            
            resultado.append({
                'id': vinculo.id,
                'teacher_id': str(vinculo.teacher_id),
                'school_id': vinculo.school_id,
                'registration': vinculo.registration,
                'created_at': str(vinculo.created_at) if vinculo.created_at else None,
                'updated_at': str(vinculo.updated_at) if vinculo.updated_at else None,
                'professor': {
                    'id': teacher.id,
                    'name': teacher.name,
                    'email': user.email if user else None
                } if teacher else None,
                'escola': {
                    'id': school.id,
                    'name': school.name
                } if school else None
            })
        
        return jsonify({
            'message': 'Vínculos professor-escola encontrados',
            'vinculos': resultado,
            'total': len(resultado)
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar vínculos professor-escola: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 400

@school_teacher_bp.route('/school-teacher/<string:id>', methods=['DELETE'])
@jwt_required()
@role_required('admin', 'tecadm', 'diretor', 'coordenador')
def delete_school_teacher(id):
    try:
        # Obter usuário atual
        current_user = get_current_user_from_token()
        
        school_teacher = SchoolTeacher.query.get(id)
        if not school_teacher:
            return jsonify({'error': 'Vínculo não encontrado'}), 404
        
        # Verificar permissões baseadas no role
        if current_user['role'] == 'tecadm':
            # Tecadm só pode deletar vínculos de escolas do seu município
            school = School.query.get(school_teacher.school_id)
            if not school or school.city_id != current_user['city_id']:
                return jsonify({"erro": "Você só pode deletar vínculos de escolas do seu município"}), 403
        elif current_user['role'] in ['diretor', 'coordenador']:
            # Diretor/coordenador só pode deletar vínculos da sua escola
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or manager.school_id != school_teacher.school_id:
                return jsonify({"erro": "Você só pode deletar vínculos da sua escola"}), 403
            
        db.session.delete(school_teacher)
        db.session.commit()
        
        return jsonify({'message': 'Vínculo removido com sucesso'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400 