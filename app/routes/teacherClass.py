from flask import Blueprint, request, jsonify
from app.models.teacherClass import TeacherClass
from app import db
import uuid
from app.decorators.role_required import role_required
from flask_jwt_extended import jwt_required

teacher_class_bp = Blueprint('teacher_class', __name__)

@teacher_class_bp.route('/teacher-class', methods=['POST'])
@jwt_required()
@role_required('admin', 'tecadm')
def create_teacher_class():
    data = request.get_json()
    
    try:
        teacher_class = TeacherClass(
            teacher_id=data.get('teacher_id'),
            class_id=data.get('class_id')
        )
        
        db.session.add(teacher_class)
        db.session.commit()
        
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