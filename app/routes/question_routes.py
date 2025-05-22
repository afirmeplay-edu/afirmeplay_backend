from flask import Blueprint, request, jsonify
from app.models.question import Question
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime
import logging

bp = Blueprint('questions', __name__, url_prefix='/questions')

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

@bp.route('/', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def create_question():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['title', 'question_type', 'subject', 'grade_level', 'created_by']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        question = Question(
            title=data.get('title'),
            description=data.get('description'),
            resource_type=data.get('resource_type'),
            resource_content=data.get('resource_content'),
            command=data.get('command'),
            question_type=data.get('question_type'),
            subject=data.get('subject'),
            grade_level=data.get('grade_level'),
            difficulty_level=data.get('difficulty_level'),
            status=data.get('status', 'active'),
            correct_answer=data.get('correct_answer'),
            tags=data.get('tags'),
            test_id=data.get('test_id'),
            alternatives=data.get('alternatives'),
            tenant_id=get_current_tenant_id(),
            created_by=data.get('created_by')
        )

        db.session.add(question)
        db.session.commit()

        return jsonify({
            "message": "Question created successfully",
            "id": question.id
        }), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating question: {str(e)}", exc_info=True)
        return jsonify({"error": "Error creating question", "details": str(e)}), 500

@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def list_questions():
    try:
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            return jsonify({"error": "Tenant ID not found"}), 400

        test_id = request.args.get('test_id')
        
        query = Question.query.filter_by(tenant_id=tenant_id)
        
        if test_id:
            query = query.filter_by(test_id=test_id)

        questions = query.all()
        
        return jsonify([{
            'id': q.id,
            'title': q.title,
            'description': q.description,
            'resource_type': q.resource_type,
            'resource_content': q.resource_content,
            'command': q.command,
            'question_type': q.question_type,
            'subject': q.subject,
            'grade_level': q.grade_level,
            'difficulty_level': q.difficulty_level,
            'status': q.status,
            'correct_answer': q.correct_answer,
            'tags': q.tags,
            'test_id': q.test_id,
            'alternatives': q.alternatives,
            'tenant_id': q.tenant_id,
            'created_at': q.created_at.isoformat() if q.created_at else None,
            'created_by': q.created_by,
            'updated_at': q.updated_at.isoformat() if q.updated_at else None
        } for q in questions]), 200

    except Exception as e:
        logging.error(f"Error listing questions: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing questions", "details": str(e)}), 500

@bp.route('/<string:question_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_question(question_id):
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({"error": "Question not found"}), 404

        return jsonify({
            'id': question.id,
            'title': question.title,
            'description': question.description,
            'resource_type': question.resource_type,
            'resource_content': question.resource_content,
            'command': question.command,
            'question_type': question.question_type,
            'subject': question.subject,
            'grade_level': question.grade_level,
            'difficulty_level': question.difficulty_level,
            'status': question.status,
            'correct_answer': question.correct_answer,
            'tags': question.tags,
            'test_id': question.test_id,
            'alternatives': question.alternatives,
            'tenant_id': question.tenant_id,
            'created_at': question.created_at.isoformat() if question.created_at else None,
            'created_by': question.created_by,
            'updated_at': question.updated_at.isoformat() if question.updated_at else None
        }), 200

    except Exception as e:
        logging.error(f"Error getting question: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting question", "details": str(e)}), 500

@bp.route('/<string:question_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def update_question(question_id):
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({"error": "Question not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        fields = [
            'title', 'description', 'resource_type', 'resource_content', 'command',
            'question_type', 'subject', 'grade_level', 'difficulty_level', 'status',
            'correct_answer', 'tags', 'test_id', 'alternatives'
        ]

        for field in fields:
            if field in data:
                setattr(question, field, data[field])

        db.session.commit()
        return jsonify({'message': 'Question updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating question: {str(e)}", exc_info=True)
        return jsonify({"error": "Error updating question", "details": str(e)}), 500

@bp.route('/<string:question_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def delete_question(question_id):
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({"error": "Question not found"}), 404

        db.session.delete(question)
        db.session.commit()
        return jsonify({'message': 'Question deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting question: {str(e)}", exc_info=True)
        return jsonify({"error": "Error deleting question", "details": str(e)}), 500