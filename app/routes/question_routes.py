from flask import Blueprint, request, jsonify
from app.models.question import Question
from app.models.subject import Subject
from app.models.grades import Grade
from app.models.educationStage import EducationStage
from app.models.test import Test
from app.models.user import User
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime
import logging
import base64
import uuid
import os
from PIL import Image
import io
from sqlalchemy.orm import aliased, joinedload
from app.utils.response_formatters import format_question_response

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

        required_fields = ['text', 'type', 'subjectId', 'grade', 'createdBy']
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
        if data['type'] == 'multipleChoice':
            if not data.get('options') or not isinstance(data.get('options'), list):
                return jsonify({"error": "Multiple choice questions must have alternatives"}), 400
            if not any(alt.get('isCorrect') for alt in data['options']):
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
            created_by=data.get('createdBy'),
            last_modified_by=data.get('lastModifiedBy'),
            education_stage_id=data.get('educationStageId')
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
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401

        test_id = request.args.get('test_id')
        question_type = request.args.get('type')
        subject_id = request.args.get('subject_id')
        created_by = request.args.get('created_by')
        
        query = Question.query.options(
            joinedload(Question.subject),
            joinedload(Question.grade),
            joinedload(Question.education_stage),
            joinedload(Question.test),
            joinedload(Question.creator),
            joinedload(Question.last_modifier)
        )
        
        if user['role'] == 'professor':
            query = query.filter(Question.created_by == user['id'])
        elif created_by:
            query = query.filter(Question.created_by == created_by)

        if test_id:
            query = query.filter(Question.test_id == test_id)
        if question_type:
            query = query.filter(Question.question_type == question_type)
        if subject_id:
            query = query.filter(Question.subject_id == subject_id)

        questions = query.all()
        
        return jsonify([format_question_response(q) for q in questions]), 200

    except Exception as e:
        logging.error(f"Error listing questions: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing questions", "details": str(e)}), 500

@bp.route('/<string:question_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_question(question_id):
    try:
        question = Question.query.options(
            joinedload(Question.subject),
            joinedload(Question.grade),
            joinedload(Question.education_stage),
            joinedload(Question.test),
            joinedload(Question.creator),
            joinedload(Question.last_modifier)
        ).get(question_id)

        if not question:
            return jsonify({"error": "Question not found"}), 404

        return jsonify(format_question_response(question)), 200

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

        # Mapeia chaves do JSON (camelCase) para atributos do modelo (snake_case)
        field_map = {
            'number': 'number',
            'text': 'text',
            'formattedText': 'formatted_text',
            'subjectId': 'subject_id',
            'title': 'title',
            'description': 'description',
            'command': 'command',
            'subtitle': 'subtitle',
            'options': 'alternatives',
            'skills': 'skill',
            'grade': 'grade_level',
            'educationStageId': 'education_stage_id',
            'difficulty': 'difficulty_level',
            'solution': 'correct_answer',
            'formattedSolution': 'formatted_solution',
            'test_id': 'test_id',
            'type': 'question_type',
            'value': 'value',
            'topics': 'topics',
            'lastModifiedBy': 'last_modified_by'
        }

        for json_key, model_attr in field_map.items():
            if json_key in data:
                setattr(question, model_attr, data[json_key])
        
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