from flask import Blueprint, request, jsonify
from app.models.teacherClass import TeacherClass
from app.models.teacher import Teacher
from app.models.user import User
from app import db
import uuid
import logging
from app.decorators.role_required import role_required
from flask_jwt_extended import jwt_required

teacher_class_bp = Blueprint('teacher_class', __name__)

@teacher_class_bp.route('/teacher-class', methods=['POST'])
@jwt_required()
@role_required('admin', 'tecadm')
def create_teacher_class():
    data = request.get_json()
    logging.info(f"Dados recebidos para vincular professor à turma: {data}")
    
    try:
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
        class_id = data.get('class_id')
        logging.info(f"Vincular professor {teacher_id} à turma {class_id}")
        
        # Verificar se já existe o vínculo
        existing_vinculo = TeacherClass.query.filter_by(
            teacher_id=teacher_id,
            class_id=class_id
        ).first()
        
        if existing_vinculo:
            logging.warning(f"Vínculo já existe: professor {teacher_id} já está vinculado à turma {class_id}")
            return jsonify({
                "erro": "Professor já está vinculado a esta turma",
                "teacher_class": {
                    'id': existing_vinculo.id,
                    'teacher_id': str(existing_vinculo.teacher_id),
                    'class_id': existing_vinculo.class_id
                }
            }), 400
        
        teacher_class = TeacherClass(
            teacher_id=teacher_id,  # Usar o teacher_id correto
            class_id=class_id
        )
        
        logging.info(f"Criando vínculo: teacher_id={teacher_id}, class_id={class_id}")
        db.session.add(teacher_class)
        db.session.commit()
        logging.info(f"Vínculo criado com sucesso. ID: {teacher_class.id}")
        
        return jsonify({
            'message': 'Professor vinculado à turma com sucesso',
            'teacher_class': {
                'id': teacher_class.id,
                'teacher_id': str(teacher_class.teacher_id),
                'class_id': teacher_class.class_id
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao vincular professor à turma: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 400

@teacher_class_bp.route('/teacher-class', methods=['GET'])
@jwt_required()
@role_required('admin', 'tecadm')
def get_teacher_classes():
    try:
        # Buscar todos os vínculos professor-turma
        vinculos = TeacherClass.query.all()
        
        resultado = []
        for vinculo in vinculos:
            # Buscar dados do professor
            teacher = Teacher.query.get(vinculo.teacher_id)
            user = User.query.get(teacher.user_id) if teacher else None
            
            # Buscar dados da turma
            from app.models.studentClass import Class
            class_obj = Class.query.get(vinculo.class_id)
            
            resultado.append({
                'id': vinculo.id,
                'teacher_id': str(vinculo.teacher_id),
                'class_id': vinculo.class_id,
                'created_at': str(vinculo.created_at) if vinculo.created_at else None,
                'updated_at': str(vinculo.updated_at) if vinculo.updated_at else None,
                'professor': {
                    'id': teacher.id,
                    'name': teacher.name,
                    'email': user.email if user else None
                } if teacher else None,
                'turma': {
                    'id': class_obj.id,
                    'name': class_obj.name
                } if class_obj else None
            })
        
        return jsonify({
            'message': 'Vínculos professor-turma encontrados',
            'vinculos': resultado,
            'total': len(resultado)
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar vínculos professor-turma: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 400

@teacher_class_bp.route('/teacher-class/<string:id>', methods=['DELETE'])
@jwt_required()
@role_required('admin', 'tecadm')
def delete_teacher_class(id):
    try:
        teacher_class = TeacherClass.query.get(id)
        if not teacher_class:
            return jsonify({'error': 'Vínculo não encontrado'}), 404
            
        db.session.delete(teacher_class)
        db.session.commit()
        
        return jsonify({'message': 'Vínculo removido com sucesso'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400 