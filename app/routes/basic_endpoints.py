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
from app.models.test import Test
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta
import logging
from app.models.question import Question

bp = Blueprint('basic_endpoints', __name__)


@bp.errorhandler(Exception)
def handle_error(error):
    """Tratamento global de erros para este blueprint"""
    logging.error(f"Erro em basic_endpoints: {str(error)}", exc_info=True)
    return jsonify({
        "error": "Erro interno no servidor",
        "details": str(error)
    }), 500


@bp.route('/dashboard/stats', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def dashboard_stats():
    """
    Retorna estatísticas do dashboard
    
    Returns:
        {
            "total_evaluations": int,
            "active_evaluations": int,
            "completed_evaluations": int,
            "total_students": int,
            "average_completion": float,
            "last_sync": string
        }
    """
    try:
        # Buscar estatísticas de avaliações
        total_evaluations = Test.query.count()
        active_evaluations = Test.query.filter(Test.status.in_(['agendada', 'em_andamento'])).count()
        completed_evaluations = Test.query.filter(Test.status == 'concluida').count()
        
        # Buscar estatísticas de estudantes
        total_students = Student.query.count()
        
        # Calcular taxa de conclusão média
        # Buscar todas as sessões de teste dos últimos 30 dias
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_sessions = TestSession.query.filter(
            TestSession.started_at >= thirty_days_ago
        ).all()
        
        if recent_sessions:
            # Calcular porcentagem de sessões concluídas
            completed_sessions = [s for s in recent_sessions if s.submitted_at is not None]
            average_completion = (len(completed_sessions) / len(recent_sessions)) * 100
        else:
            average_completion = 0.0
        
        return jsonify({
            "total_evaluations": total_evaluations,
            "active_evaluations": active_evaluations,
            "completed_evaluations": completed_evaluations,
            "total_students": total_students,
            "average_completion": round(average_completion, 2),
            "last_sync": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar estatísticas do dashboard: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao buscar estatísticas do dashboard",
            "details": str(e)
        }), 500


@bp.route('/evaluations/stats', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def evaluations_stats():
    """
    Retorna estatísticas específicas de avaliações de forma robusta
    
    Returns:
        {
            "total": int,
            "this_month": int,
            "total_questions": int,
            "average_questions": float,
            "virtual_evaluations": int,
            "physical_evaluations": int,
            "by_type": {...},
            "by_model": {...},
            "by_status": {...}
        }
    """
    try:
        logging.info("📊 Iniciando cálculo de estatísticas de avaliações")
        
        # Estatísticas básicas - versão mais segura
        logging.info("🔢 Contando total de avaliações...")
        total_evaluations = Test.query.count()
        logging.info(f"✅ Total de avaliações: {total_evaluations}")
        
        # Avaliações deste mês
        logging.info("📅 Contando avaliações deste mês...")
        this_month_evaluations = 0
        try:
            current_month = datetime.now().month
            current_year = datetime.now().year
            
            # Versão mais compatível sem extract
            from sqlalchemy import and_
            this_month_evaluations = Test.query.filter(
                and_(
                    Test.created_at >= datetime(current_year, current_month, 1),
                    Test.created_at < datetime(current_year, current_month + 1, 1) if current_month < 12 else datetime(current_year + 1, 1, 1)
                )
            ).count()
            logging.info(f"✅ Avaliações deste mês: {this_month_evaluations}")
        except Exception as e:
            logging.error(f"❌ Erro ao contar avaliações deste mês: {e}")
            this_month_evaluations = 0
        
        # Total de questões 
        logging.info("❓ Contando total de questões...")
        total_questions_result = 0
        try:
            total_questions_result = Question.query.count()
            logging.info(f"✅ Total de questões: {total_questions_result}")
        except Exception as e:
            logging.error(f"❌ Erro ao contar questões: {e}")
            total_questions_result = 0
        
        # Média de questões por avaliação - versão simples
        logging.info("📊 Calculando média de questões por avaliação...")
        questions_per_evaluation = 0
        try:
            # Buscar todas as avaliações e contar questões
            evaluations = Test.query.all()
            if evaluations:
                total_questions_in_evaluations = 0
                evaluations_with_questions = 0
                
                for evaluation in evaluations:
                    if hasattr(evaluation, 'questions') and evaluation.questions:
                        if isinstance(evaluation.questions, list):
                            total_questions_in_evaluations += len(evaluation.questions)
                            evaluations_with_questions += 1
                
                questions_per_evaluation = total_questions_in_evaluations / evaluations_with_questions if evaluations_with_questions > 0 else 0
            
            logging.info(f"✅ Média de questões por avaliação: {questions_per_evaluation}")
        except Exception as e:
            logging.error(f"❌ Erro ao calcular média de questões: {e}")
            questions_per_evaluation = 0
        
        # Estatísticas por tipo de avaliação
        logging.info("📊 Calculando estatísticas por tipo...")
        by_type = {}
        try:
            evaluations_by_type = db.session.query(Test.type, db.func.count(Test.id)).group_by(Test.type).all()
            by_type = {item[0]: item[1] for item in evaluations_by_type if item[0]}
            logging.info(f"✅ Estatísticas por tipo: {by_type}")
        except Exception as e:
            logging.error(f"❌ Erro ao calcular estatísticas por tipo: {e}")
            by_type = {}
        
        # Estatísticas por modelo
        logging.info("📊 Calculando estatísticas por modelo...")
        by_model = {}
        try:
            evaluations_by_model = db.session.query(Test.model, db.func.count(Test.id)).group_by(Test.model).all()
            by_model = {item[0]: item[1] for item in evaluations_by_model if item[0]}
            logging.info(f"✅ Estatísticas por modelo: {by_model}")
        except Exception as e:
            logging.error(f"❌ Erro ao calcular estatísticas por modelo: {e}")
            by_model = {}
        
        # Estatísticas por status
        logging.info("📊 Calculando estatísticas por status...")
        by_status = {}
        try:
            evaluations_by_status = db.session.query(Test.status, db.func.count(Test.id)).group_by(Test.status).all()
            by_status = {item[0]: item[1] for item in evaluations_by_status if item[0]}
            logging.info(f"✅ Estatísticas por status: {by_status}")
        except Exception as e:
            logging.error(f"❌ Erro ao calcular estatísticas por status: {e}")
            by_status = {}
        
        # Estatísticas por modo de avaliação
        logging.info("📊 Calculando estatísticas por modo...")
        virtual_evaluations = 0
        physical_evaluations = 0
        try:
            virtual_evaluations = Test.query.filter(Test.evaluation_mode == 'virtual').count()
            physical_evaluations = Test.query.filter(Test.evaluation_mode == 'physical').count()
            logging.info(f"✅ Virtuais: {virtual_evaluations}, Físicas: {physical_evaluations}")
        except Exception as e:
            logging.error(f"❌ Erro ao calcular estatísticas por modo: {e}")
            virtual_evaluations = 0
            physical_evaluations = 0
        
        result = {
            "total": total_evaluations,
            "this_month": this_month_evaluations,
            "total_questions": total_questions_result,
            "average_questions": round(float(questions_per_evaluation), 2),
            "virtual_evaluations": virtual_evaluations,
            "physical_evaluations": physical_evaluations,
            "by_type": by_type,
            "by_model": by_model,
            "by_status": by_status,
            "last_sync": datetime.now().isoformat()
        }
        
        logging.info(f"🎉 Estatísticas calculadas com sucesso!")
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"💥 Erro geral ao buscar estatísticas de avaliações: {str(e)}", exc_info=True)
        # Retornar dados padrão em caso de erro
        return jsonify({
            "total": 0,
            "this_month": 0,
            "total_questions": 0,
            "average_questions": 0.0,
            "virtual_evaluations": 0,
            "physical_evaluations": 0,
            "by_type": {},
            "by_model": {},
            "by_status": {},
            "last_sync": datetime.now().isoformat(),
            "error": "Erro ao buscar estatísticas de avaliações",
            "details": str(e)
        }), 200  # Retorna 200 mesmo com erro para não quebrar o frontend


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