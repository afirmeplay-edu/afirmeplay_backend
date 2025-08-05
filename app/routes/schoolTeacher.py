from flask import Blueprint, request, jsonify
from app.models.schoolTeacher import SchoolTeacher
from app.decorators.role_required import role_required
from app import db
import uuid
from flask_jwt_extended import jwt_required

school_teacher_bp = Blueprint('school_teacher', __name__)

@school_teacher_bp.route('/school-teacher', methods=['POST'])
@jwt_required()
@role_required('admin', 'tecadm')
def create_school_teacher():
    data = request.get_json()
    
    try:
        school_teacher = SchoolTeacher(
            registration=data.get('registration'),
            school_id=data.get('school_id'),
            teacher_id=data.get('teacher_id')
        )
        
        db.session.add(school_teacher)
        db.session.commit()
        
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
        return jsonify({'error': str(e)}), 400

@school_teacher_bp.route('/school-teacher/<string:id>', methods=['DELETE'])
@jwt_required()
@role_required('admin', 'tecadm')
def delete_school_teacher(id):
    try:
        school_teacher = SchoolTeacher.query.get(id)
        if not school_teacher:
            return jsonify({'error': 'Vínculo não encontrado'}), 404
            
        db.session.delete(school_teacher)
        db.session.commit()
        
        return jsonify({'message': 'Vínculo removido com sucesso'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400 