"""
Endpoints básicos para filtros e dropdowns do frontend
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from app.models.educationStage import EducationStage
from app.models.subject import Subject
from app.models.studentClass import Class
from app.models.school import School
from app.models.grades import Grade
import logging

bp = Blueprint('basic_endpoints', __name__)


@bp.errorhandler(Exception)
def handle_error(error):
    """Tratamento global de erros para este blueprint"""
    logging.error(f"Erro em basic_endpoints: {str(error)}", exc_info=True)
    return jsonify({
        "error": "Erro interno no servidor",
        "details": str(error)
    }), 500


@bp.route('/courses', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def list_courses():
    """
    Lista todos os cursos/stages educacionais
    
    Returns:
        [
            {
                "id": "string",
                "name": "string"
            }
        ]
    """
    try:
        # Buscar education stages
        stages = EducationStage.query.all()
        
        # Também incluir cursos do modelo Test (valores únicos)
        from app.models.test import Test
        test_courses = Test.query.with_entities(Test.course).distinct().filter(Test.course.isnot(None)).all()
        
        results = []
        
        # Adicionar education stages
        for stage in stages:
            results.append({
                'id': stage.id,
                'name': stage.name
            })
        
        # Adicionar cursos únicos dos testes
        for course_tuple in test_courses:
            course = course_tuple[0]
            if course and not any(r['name'] == course for r in results):
                results.append({
                    'id': course.lower().replace(' ', '_'),
                    'name': course
                })
        
        return jsonify(results), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar cursos: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar cursos", "details": str(e)}), 500


@bp.route('/subjects', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def list_subjects():
    """
    Lista todas as disciplinas
    
    Returns:
        [
            {
                "id": "string",
                "name": "string"
            }
        ]
    """
    try:
        subjects = Subject.query.all()
        
        results = []
        for subject in subjects:
            results.append({
                'id': subject.id,
                'name': subject.name
            })
        
        return jsonify(results), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar disciplinas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar disciplinas", "details": str(e)}), 500


@bp.route('/classes', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def list_classes():
    """
    Lista todas as turmas
    
    Returns:
        [
            {
                "id": "string",
                "name": "string",
                "school_id": "string",
                "school_name": "string",
                "grade_id": "string",
                "grade_name": "string"
            }
        ]
    """
    try:
        classes = Class.query.join(School).join(Grade).all()
        
        results = []
        for class_obj in classes:
            results.append({
                'id': class_obj.id,
                'name': class_obj.name,
                'school_id': class_obj.school_id,
                'school_name': class_obj.school.name if class_obj.school else None,
                'grade_id': class_obj.grade_id,
                'grade_name': class_obj.grade.name if class_obj.grade else None
            })
        
        return jsonify(results), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar turmas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar turmas", "details": str(e)}), 500


@bp.route('/schools', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def list_schools():
    """
    Lista todas as escolas
    
    Returns:
        [
            {
                "id": "string",
                "name": "string",
                "address": "string",
                "city_id": "string"
            }
        ]
    """
    try:
        schools = School.query.all()
        
        results = []
        for school in schools:
            results.append({
                'id': school.id,
                'name': school.name,
                'address': school.address,
                'city_id': school.city_id
            })
        
        return jsonify(results), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar escolas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar escolas", "details": str(e)}), 500 