from flask import Blueprint, request, jsonify
from app.models.student import Student
from app.models.user import User, RoleEnum
from app.models.school import School
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.evaluationResult import EvaluationResult
from app.models.test import Test
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, case, desc
from sqlalchemy.orm import joinedload
import logging
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from app import db
from typing import Dict, List, Optional, Any

bp = Blueprint('student_grades', __name__, url_prefix="/students")

@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"error": "Database error occurred", "details": str(error)}), 500

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"error": "An unexpected error occurred", "details": str(error)}), 500

def _get_classification_from_proficiency(proficiency: float) -> str:
    """Determina a classificação baseada na proficiência"""
    if proficiency < 200:
        return "Abaixo do Básico"
    elif proficiency < 250:
        return "Básico"
    elif proficiency < 300:
        return "Adequado"
    else:
        return "Avançado"

def _get_student_general_stats(student_id: str) -> Dict[str, Any]:
    """Calcula estatísticas gerais do aluno baseadas em todas as avaliações"""
    try:
        # Buscar todos os resultados do aluno
        results = EvaluationResult.query.filter_by(student_id=student_id).all()
        
        if not results:
            return {
                "total_evaluations": 0,
                "general_proficiency": 0.0,
                "general_grade": 0.0,
                "general_classification": "Sem avaliações",
                "total_correct_answers": 0,
                "total_questions_answered": 0
            }
        
        # Calcular médias
        total_proficiency = sum(r.proficiency for r in results)
        total_grade = sum(r.grade for r in results)
        total_correct = sum(r.correct_answers for r in results)
        total_questions = sum(r.total_questions for r in results)
        
        avg_proficiency = total_proficiency / len(results)
        avg_grade = total_grade / len(results)
        
        classification = _get_classification_from_proficiency(avg_proficiency)
        
        return {
            "total_evaluations": len(results),
            "general_proficiency": round(avg_proficiency, 2),
            "general_grade": round(avg_grade, 2),
            "general_classification": classification,
            "total_correct_answers": total_correct,
            "total_questions_answered": total_questions
        }
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas gerais do aluno {student_id}: {str(e)}")
        return {}

def _calculate_student_rankings(student_id: str, evaluation_id: Optional[str] = None) -> Dict[str, Any]:
    """Calcula ranking do aluno na escola, turma e município"""
    try:
        # Buscar dados do aluno
        student = Student.query.get(student_id)
        
        if not student:
            return {}
        
        rankings = {}
        
        # Ranking na escola
        if student.school_id:
            school_students = Student.query.filter_by(school_id=student.school_id).all()
            school_student_ids = [s.id for s in school_students]
            
            if evaluation_id:
                # Ranking específico da avaliação na escola
                school_results = db.session.query(
                    EvaluationResult.student_id,
                    EvaluationResult.proficiency,
                    Student.name
                ).join(
                    Student, EvaluationResult.student_id == Student.id
                ).filter(
                    EvaluationResult.student_id.in_(school_student_ids),
                    EvaluationResult.test_id == evaluation_id
                ).order_by(desc(EvaluationResult.proficiency)).all()
            else:
                # Ranking geral na escola (média de proficiências)
                school_results = db.session.query(
                    EvaluationResult.student_id,
                    func.avg(EvaluationResult.proficiency).label('avg_proficiency'),
                    Student.name
                ).join(
                    Student, EvaluationResult.student_id == Student.id
                ).filter(
                    EvaluationResult.student_id.in_(school_student_ids)
                ).group_by(EvaluationResult.student_id, Student.name).order_by(
                    desc('avg_proficiency')
                ).all()
            
            # Encontrar posição do aluno e montar ranking completo
            position = 1
            ranking_list = []
            for result in school_results:
                ranking_list.append({
                    "position": position,
                    "student_id": result.student_id,
                    "student_name": result.name,
                    "proficiency": result.proficiency if evaluation_id else result.avg_proficiency
                })
                if result.student_id == student_id:
                    student_position = position
                position += 1
            
            rankings["school"] = {
                "position": student_position,
                "total_students": len(school_results),
                "ranking": ranking_list
            }
        
        # Ranking na turma
        if student.class_id:
            class_students = Student.query.filter_by(class_id=student.class_id).all()
            class_student_ids = [s.id for s in class_students]
            
            if evaluation_id:
                # Ranking específico da avaliação na turma
                class_results = db.session.query(
                    EvaluationResult.student_id,
                    EvaluationResult.proficiency,
                    Student.name
                ).join(
                    Student, EvaluationResult.student_id == Student.id
                ).filter(
                    EvaluationResult.student_id.in_(class_student_ids),
                    EvaluationResult.test_id == evaluation_id
                ).order_by(desc(EvaluationResult.proficiency)).all()
            else:
                # Ranking geral na turma (média de proficiências)
                class_results = db.session.query(
                    EvaluationResult.student_id,
                    func.avg(EvaluationResult.proficiency).label('avg_proficiency'),
                    Student.name
                ).join(
                    Student, EvaluationResult.student_id == Student.id
                ).filter(
                    EvaluationResult.student_id.in_(class_student_ids)
                ).group_by(EvaluationResult.student_id, Student.name).order_by(
                    desc('avg_proficiency')
                ).all()
            
            # Encontrar posição do aluno e montar ranking completo
            position = 1
            ranking_list = []
            for result in class_results:
                ranking_list.append({
                    "position": position,
                    "student_id": result.student_id,
                    "student_name": result.name,
                    "proficiency": result.proficiency if evaluation_id else result.avg_proficiency
                })
                if result.student_id == student_id:
                    student_position = position
                position += 1
            
            rankings["class"] = {
                "position": student_position,
                "total_students": len(class_results),
                "ranking": ranking_list
            }
        
        # Ranking no município
        school = School.query.get(student.school_id) if student.school_id else None
        if school and school.city_id:
            # Buscar todas as escolas do município
            municipality_schools = School.query.filter_by(city_id=school.city_id).all()
            municipality_school_ids = [s.id for s in municipality_schools]
            
            # Buscar todos os alunos do município
            municipality_students = Student.query.filter(
                Student.school_id.in_(municipality_school_ids)
            ).all()
            municipality_student_ids = [s.id for s in municipality_students]
            
            if evaluation_id:
                # Ranking específico da avaliação no município
                municipality_results = db.session.query(
                    EvaluationResult.student_id,
                    EvaluationResult.proficiency,
                    Student.name
                ).join(
                    Student, EvaluationResult.student_id == Student.id
                ).filter(
                    EvaluationResult.student_id.in_(municipality_student_ids),
                    EvaluationResult.test_id == evaluation_id
                ).order_by(desc(EvaluationResult.proficiency)).all()
            else:
                # Ranking geral no município (média de proficiências)
                municipality_results = db.session.query(
                    EvaluationResult.student_id,
                    func.avg(EvaluationResult.proficiency).label('avg_proficiency'),
                    Student.name
                ).join(
                    Student, EvaluationResult.student_id == Student.id
                ).filter(
                    EvaluationResult.student_id.in_(municipality_student_ids)
                ).group_by(EvaluationResult.student_id, Student.name).order_by(
                    desc('avg_proficiency')
                ).all()
            
            # Encontrar posição do aluno e montar ranking completo
            position = 1
            ranking_list = []
            for result in municipality_results:
                ranking_list.append({
                    "position": position,
                    "student_id": result.student_id,
                    "student_name": result.name,
                    "proficiency": result.proficiency if evaluation_id else result.avg_proficiency
                })
                if result.student_id == student_id:
                    student_position = position
                position += 1
            
            rankings["municipality"] = {
                "position": student_position,
                "total_students": len(municipality_results),
                "ranking": ranking_list
            }
        
        return rankings
        
    except Exception as e:
        logging.error(f"Erro ao calcular rankings do aluno {student_id}: {str(e)}")
        return {}

def _get_evaluation_specific_stats(student_id: str, evaluation_id: str) -> Dict[str, Any]:
    """Busca estatísticas específicas de uma avaliação"""
    try:
        # Buscar resultado específico da avaliação
        result = EvaluationResult.query.filter_by(
            student_id=student_id,
            test_id=evaluation_id
        ).first()
        
        if not result:
            return {}
        
        return {
            "evaluation_id": evaluation_id,
            "proficiency": result.proficiency,
            "grade": result.grade,
            "classification": result.classification,
            "correct_answers": result.correct_answers,
            "total_questions": result.total_questions,
            "score_percentage": result.score_percentage,
            "calculated_at": result.calculated_at.isoformat() if result.calculated_at else None
        }
        
    except Exception as e:
        logging.error(f"Erro ao buscar estatísticas específicas do aluno {student_id} na avaliação {evaluation_id}: {str(e)}")
        return {}

def _validate_student_access(user: dict, student_id: str) -> bool:
    """Valida se o usuário tem acesso aos dados do aluno"""
    try:
        # Admin tem acesso total
        if user['role'] == 'admin':
            return True
        
        # Aluno só pode ver seus próprios dados
        if user['role'] == 'aluno':
            # Para aluno, o student_id já é do próprio usuário
            student = Student.query.filter_by(user_id=user['id']).first()
            return student and student.id == student_id
        
        # Professor, diretor, coordenador - verificar se o aluno está em suas escolas
        if user['role'] in ['professor', 'diretor', 'coordenador']:
            student = Student.query.get(student_id)
            
            if not student or not student.school_id:
                return False
            
            if user['role'] == 'professor':
                # Professor: verificar se está alocado na escola do aluno
                from app.models.teacher import Teacher
                from app.models.schoolTeacher import SchoolTeacher
                
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if not teacher:
                    return False
                
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                teacher_school_ids = [ts.school_id for ts in teacher_schools]
                
                return student.school_id in teacher_school_ids
            
            elif user['role'] in ['diretor', 'coordenador']:
                # Diretor/Coordenador: verificar se está na mesma escola
                from app.models.manager import Manager
                
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if not manager:
                    return False
                
                return manager.school_id == student.school_id
        
        # TecAdm: verificar se o aluno está no mesmo município
        elif user['role'] == 'tecadm':
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return False
            
            student = Student.query.get(student_id)
            
            school = School.query.get(student.school_id) if student and student.school_id else None
            return student and school and school.city_id == city_id
        
        return False
        
    except Exception as e:
        logging.error(f"Erro ao validar acesso do usuário {user.get('id')} ao aluno {student_id}: {str(e)}")
        return False

@bp.route('/<string:user_id>/grades/general', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def get_student_general_grades(user_id):
    """
    Retorna as notas gerais do aluno (médias de todas as avaliações)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Buscar o aluno pelo user_id
        student = Student.query.filter_by(user_id=user_id).first()
        
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404
        
        # Validar acesso ao aluno
        if not _validate_student_access(user, student.id):
            return jsonify({"error": "Você não tem permissão para acessar os dados deste aluno"}), 403
        
        # Calcular estatísticas gerais
        general_stats = _get_student_general_stats(student.id)
        
        # Calcular rankings
        rankings = _calculate_student_rankings(student.id)
        
        # Buscar dados relacionados
        school = School.query.get(student.school_id) if student.school_id else None
        class_obj = Class.query.get(student.class_id) if student.class_id else None
        
        # Montar resposta
        response_data = {
            "user_id": user_id,
            "student_id": student.id,
            "student_name": student.name,
            "student_registration": student.registration,
            "school_name": school.name if school else None,
            "class_name": class_obj.name if class_obj else None,
            **general_stats,
            "rankings": rankings
        }
        
        return jsonify({
            "success": True,
            "data": response_data,
            "message": "Dados gerais do aluno obtidos com sucesso"
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter notas gerais do aluno {user_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter dados do aluno", "details": str(e)}), 500

@bp.route('/<string:user_id>/grades/evaluation/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def get_student_evaluation_grades(user_id, evaluation_id):
    """
    Retorna as notas do aluno em uma avaliação específica
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Buscar o aluno pelo user_id
        student = Student.query.filter_by(user_id=user_id).first()
        
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404
        
        # Validar acesso ao aluno
        if not _validate_student_access(user, student.id):
            return jsonify({"error": "Você não tem permissão para acessar os dados deste aluno"}), 403
        
        # Buscar estatísticas específicas da avaliação
        evaluation_stats = _get_evaluation_specific_stats(student.id, evaluation_id)
        
        if not evaluation_stats:
            return jsonify({
                "success": True,
                "data": {
                    "user_id": user_id,
                    "student_id": student.id,
                    "student_name": student.name,
                    "evaluation_id": evaluation_id,
                    "evaluation_name": test.title,
                    "message": "Aluno não respondeu esta avaliação"
                },
                "message": "Aluno não possui resultados para esta avaliação"
            }), 200
        
        # Calcular rankings específicos da avaliação
        rankings = _calculate_student_rankings(student.id, evaluation_id)
        
        # Buscar dados relacionados
        school = School.query.get(student.school_id) if student.school_id else None
        class_obj = Class.query.get(student.class_id) if student.class_id else None
        
        # Montar resposta
        response_data = {
            "user_id": user_id,
            "student_id": student.id,
            "student_name": student.name,
            "student_registration": student.registration,
            "school_name": school.name if school else None,
            "class_name": class_obj.name if class_obj else None,
            "evaluation_name": test.title,
            **evaluation_stats,
            "rankings": rankings
        }
        
        return jsonify({
            "success": True,
            "data": response_data,
            "message": "Dados da avaliação obtidos com sucesso"
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter notas da avaliação {evaluation_id} do aluno {user_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter dados da avaliação", "details": str(e)}), 500
