from flask import Blueprint, request, jsonify
from app.models.question import Question
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime
import logging
import base64
import uuid
import os
from PIL import Image
import io

bp = Blueprint('questions', __name__, url_prefix='/questions')

def process_image(image_data, image_type):
    """
    Processa uma imagem em base64 e retorna um dicionário com suas informações
    """
    try:
        # Remove o cabeçalho do base64 se existir
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Decodifica o base64
        image_bytes = base64.b64decode(image_data)
        
        # Abre a imagem com PIL para processamento
        image = Image.open(io.BytesIO(image_bytes))
        
        # Gera um ID único para a imagem
        image_id = str(uuid.uuid4())
        
        # Obtém informações da imagem
        image_info = {
            "id": image_id,
            "type": image_type,
            "size": len(image_bytes),
            "width": image.width,
            "height": image.height,
            "data": image_data  # Mantém o base64 para armazenamento
        }
        
        return image_info
    except Exception as e:
        logging.error(f"Error processing image: {str(e)}")
        raise

def extract_images_from_html(html_content):
    """
    Extrai imagens em base64 do conteúdo HTML
    """
    import re
    images = []
    
    # Procura por tags img com src em base64
    img_pattern = r'<img[^>]+src="(data:image/[^;]+;base64,[^"]+)"[^>]*>'
    matches = re.finditer(img_pattern, html_content)
    
    for match in matches:
        base64_data = match.group(1)
        image_type = base64_data.split(';')[0].split(':')[1]
        image_info = process_image(base64_data, image_type)
        images.append(image_info)
    
    return images

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

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def create_question():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['text', 'question_type', 'subject_id', 'grade_level', 'created_by']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Processa imagens do texto formatado
        images = []
        if data.get('formattedText'):
            images.extend(extract_images_from_html(data['formattedText']))
        
        # Processa imagens da solução formatada
        if data.get('formattedSolution'):
            images.extend(extract_images_from_html(data['formattedSolution']))

        # Validações específicas por tipo de questão
        if data['question_type'] == 'multipleChoice':
            if not data.get('alternatives') or not isinstance(data['alternatives'], list):
                return jsonify({"error": "Multiple choice questions must have alternatives"}), 400
            if not any(alt.get('isCorrect') for alt in data['alternatives']):
                return jsonify({"error": "At least one alternative must be marked as correct"}), 400

        question = Question(
            number=data.get('number'),
            text=data.get('text'),
            formatted_text=data.get('formattedText'),
            images=images,
            subject_id=data.get('subjectId'),
            title=data.get('title'),
            description=data.get('description'),
            command=data.get('command'),
            subtitle=data.get('subtitle'),
            alternatives=data.get('options'),
            skill=data.get('skills'),
            grade_level=data.get('grade'),
            difficulty_level=data.get('difficulty'),
            correct_answer=data.get('solution'),
            formatted_solution=data.get('formattedSolution'),
            test_id=data.get('test_id'),
            question_type=data.get('type'),
            value=data.get('value'),
            topics=data.get('topics'),
            version=data.get('version', 1),
            created_by=data.get('created_by'),
            last_modified_by=data.get('lastModifiedBy')
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
        question_type = request.args.get('type')
        subject_id = request.args.get('subject_id')
        
        query = Question.query.filter_by(tenant_id=tenant_id)
        
        if test_id:
            query = query.filter_by(test_id=test_id)
        if question_type:
            query = query.filter_by(question_type=question_type)
        if subject_id:
            query = query.filter_by(subject_id=subject_id)

        questions = query.all()
        
        return jsonify([{
            'id': q.id,
            'number': q.number,
            'text': q.text,
            'formattedText': q.formatted_text,
            'subjectId': q.subject_id,
            'title': q.title,
            'description': q.description,
            'command': q.command,
            'subtitle': q.subtitle,
            'options': q.alternatives,
            'skills': q.skill,
            'grade': q.grade_level,
            'difficulty': q.difficulty_level,
            'solution': q.correct_answer,
            'formattedSolution': q.formatted_solution,
            'test_id': q.test_id,
            'type': q.question_type,
            'value': q.value,
            'topics': q.topics,
            'version': q.version,
            'created_at': q.created_at.isoformat() if q.created_at else None,
            'created_by': q.created_by,
            'updated_at': q.updated_at.isoformat() if q.updated_at else None,
            'lastModifiedBy': q.last_modified_by
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
            'number': question.number,
            'text': question.text,
            'formattedText': question.formatted_text,
            'subjectId': question.subject_id,
            'title': question.title,
            'description': question.description,
            'command': question.command,
            'subtitle': question.subtitle,
            'options': question.alternatives,
            'skills': question.skill,
            'grade': question.grade_level,
            'difficulty': question.difficulty_level,
            'solution': question.correct_answer,
            'formattedSolution': question.formatted_solution,
            'test_id': question.test_id,
            'type': question.question_type,
            'value': question.value,
            'topics': question.topics,
            'version': question.version,
            'created_at': question.created_at.isoformat() if question.created_at else None,
            'created_by': question.created_by,
            'updated_at': question.updated_at.isoformat() if question.updated_at else None,
            'lastModifiedBy': question.last_modified_by
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
            'number', 'text', 'formattedText', 'subject_id', 'title', 'description',
            'command', 'subtitle', 'alternatives', 'skill', 'grade_level',
            'difficulty_level', 'correct_answer', 'formatted_solution', 'test_id',
            'question_type', 'value', 'topics', 'version'
        ]

        for field in fields:
            if field in data:
                if field == 'formattedText':
                    setattr(question, 'formatted_text', data[field])
                elif field == 'alternatives':
                    setattr(question, 'alternatives', data[field])
                else:
                    setattr(question, field, data[field])

        question.last_modified_by = data.get('lastModifiedBy')
        question.version += 1

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