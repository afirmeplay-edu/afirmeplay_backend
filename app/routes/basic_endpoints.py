"""
Endpoints básicos para filtros e dropdowns do frontend
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from app.decorators import requires_city_context, get_current_tenant_context
from app.models.educationStage import EducationStage
from app.models.subject import Subject
from app.models.studentClass import Class
from app.models.school import School
from app.models.grades import Grade
from app.models.test import Test
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
from app import db
from sqlalchemy import func, cast, String, text
from datetime import datetime, timedelta
import logging
from app.models.question import Question
from app.models.classTest import ClassTest
from app.models.schoolTeacher import SchoolTeacher
from app.decorators.role_required import get_current_tenant_id
from app.decorators.role_required import get_current_user_from_token

bp = Blueprint('basic_endpoints', __name__)


@bp.errorhandler(Exception)
def handle_error(error):
    """Tratamento global de erros para este blueprint"""
    logging.error(f"Erro em basic_endpoints: {str(error)}", exc_info=True)
    return jsonify({
        "error": "Erro interno no servidor",
        "details": str(error)
    }), 500


@bp.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint de health check para verificar se o servidor está funcionando
    
    Returns:
        {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00",
            "version": "1.0.0",
            "database": "connected"
        }
    """
    try:
        # Testar conexão com banco de dados
        db.session.execute('SELECT 1')
        database_status = "connected"
    except Exception as e:
        database_status = f"error: {str(e)}"
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "database": database_status
    }), 200


@bp.route('/dashboard/stats', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
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
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Base queries
        test_query = Test.query
        student_query = Student.query
        session_query = TestSession.query
        
        # Filtragem baseada no papel do usuário
        if current_user['role'] == "admin":
            # Admin vê todas as estatísticas do sistema
            pass
        elif current_user['role'] == "tecadm":
            # Tecadm vê apenas estatísticas do seu município
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar testes por escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                # Filtrar testes que têm turmas das escolas da cidade
                class_tests = ClassTest.query.filter(
                    ClassTest.class_id.in_(
                        Class.query.filter(Class.school_id.in_(ensure_uuid_list(school_ids))).with_entities(Class.id)
                    )
                ).with_entities(ClassTest.test_id).all()
                test_ids = [ct.test_id for ct in class_tests]
                
                if test_ids:
                    test_query = test_query.filter(Test.id.in_(test_ids))
                    session_query = session_query.filter(TestSession.test_id.in_(test_ids))
                else:
                    # Se não há testes, retornar zeros
                    return jsonify({
                        "total_evaluations": 0,
                        "active_evaluations": 0,
                        "completed_evaluations": 0,
                        "total_students": 0,
                        "average_completion": 0.0,
                        "last_sync": datetime.now().isoformat()
                    }), 200
                
                # Filtrar estudantes por escolas da cidade
                student_query = student_query.filter(Student.school_id.in_(school_ids))
            else:
                # Se não há escolas na cidade, retornar zeros
                return jsonify({
                    "total_evaluations": 0,
                    "active_evaluations": 0,
                    "completed_evaluations": 0,
                    "total_students": 0,
                    "average_completion": 0.0,
                    "last_sync": datetime.now().isoformat()
                }), 200
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador vêem apenas estatísticas da sua escola
            from app.models.manager import Manager
            
            # Buscar o manager vinculado ao usuário atual
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or not manager.school_id:
                return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
            
            # Buscar a escola do manager
            # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
            from app.utils.uuid_helpers import uuid_to_str
            school_id_str = uuid_to_str(manager.school_id)
            school = School.query.filter(School.id == school_id_str).first() if school_id_str else None
            if not school:
                return jsonify({"erro": "Escola não encontrada"}), 400
            
            # Filtrar testes que têm turmas da escola
            class_tests = ClassTest.query.filter(
                ClassTest.class_id.in_(
                    Class.query.filter_by(school_id=ensure_uuid(school.id)).with_entities(Class.id)
                )
            ).with_entities(ClassTest.test_id).all()
            test_ids = [ct.test_id for ct in class_tests]
            
            if test_ids:
                test_query = test_query.filter(Test.id.in_(test_ids))
                session_query = session_query.filter(TestSession.test_id.in_(test_ids))
            else:
                # Se não há testes, retornar zeros
                return jsonify({
                    "total_evaluations": 0,
                    "active_evaluations": 0,
                    "completed_evaluations": 0,
                    "total_students": 0,
                    "average_completion": 0.0,
                    "last_sync": datetime.now().isoformat()
                }), 200
            
            # Filtrar estudantes por escola
            student_query = student_query.filter_by(school_id=school.id)
        elif current_user['role'] == "professor":
            # Professor vê apenas estatísticas do seu município
            city_id = current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar testes por escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                # Filtrar testes que têm turmas das escolas da cidade
                class_tests = ClassTest.query.filter(
                    ClassTest.class_id.in_(
                        Class.query.filter(Class.school_id.in_(ensure_uuid_list(school_ids))).with_entities(Class.id)
                    )
                ).with_entities(ClassTest.test_id).all()
                test_ids = [ct.test_id for ct in class_tests]
                
                if test_ids:
                    test_query = test_query.filter(Test.id.in_(test_ids))
                    session_query = session_query.filter(TestSession.test_id.in_(test_ids))
                else:
                    # Se não há testes, retornar zeros
                    return jsonify({
                        "total_evaluations": 0,
                        "active_evaluations": 0,
                        "completed_evaluations": 0,
                        "total_students": 0,
                        "average_completion": 0.0,
                        "last_sync": datetime.now().isoformat()
                    }), 200
                
                # Filtrar estudantes por escolas da cidade
                student_query = student_query.filter(Student.school_id.in_(school_ids))
            else:
                # Se não há escolas na cidade, retornar zeros
                return jsonify({
                    "total_evaluations": 0,
                    "active_evaluations": 0,
                    "completed_evaluations": 0,
                    "total_students": 0,
                    "average_completion": 0.0,
                    "last_sync": datetime.now().isoformat()
                }), 200
        
        # Buscar estatísticas de avaliações
        total_evaluations = test_query.count()
        active_evaluations = test_query.filter(Test.status.in_(['agendada', 'em_andamento'])).count()
        completed_evaluations = test_query.filter(Test.status == 'concluida').count()
        
        # Buscar estatísticas de estudantes
        total_students = student_query.count()
        
        # Calcular taxa de conclusão média
        # Buscar todas as sessões de teste dos últimos 30 dias
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_sessions = session_query.filter(
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


@bp.route('/dashboard/comprehensive-stats', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def comprehensive_dashboard_stats():
    """
    Retorna estatísticas mais completas do dashboard
    
    Returns:
        {
            "students": int,
            "schools": int,
            "evaluations": int,
            "games": int,
            "users": int,
            "questions": int,
            "classes": int,
            "teachers": int,
            "last_sync": string
        }
    """
    try:
        from app.models.user import User
        from app.models.game import Game
        from app.models.question import Question
        from app.models.studentClass import Class
        from app.models.teacher import Teacher
        
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Base queries
        student_query = Student.query
        school_query = School.query
        test_query = Test.query
        game_query = Game.query
        user_query = User.query
        question_query = Question.query
        class_query = Class.query
        teacher_query = Teacher.query
        
        # Filtragem baseada no papel do usuário
        if current_user['role'] == "admin":
            # Admin vê todas as estatísticas do sistema
            pass
        elif current_user['role'] == "tecadm":
            # Tecadm vê apenas estatísticas do seu município
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar escolas por cidade
            school_query = school_query.filter_by(city_id=city_id)
            
            # Obter IDs das escolas da cidade
            schools_in_city = school_query.with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                # Filtrar estudantes por escolas da cidade
                student_query = student_query.filter(Student.school_id.in_(school_ids))
                
                # Filtrar turmas por escolas da cidade
                class_query = class_query.filter(cast(Class.school_id, String).in_(school_ids))
                
                # Filtrar professores por escolas da cidade através da tabela de associação
                teacher_query = teacher_query.join(SchoolTeacher).filter(SchoolTeacher.school_id.in_(school_ids))
                
                # Filtrar testes que têm turmas das escolas da cidade
                class_tests = ClassTest.query.filter(
                    ClassTest.class_id.in_(
                        Class.query.filter(cast(Class.school_id, String).in_(school_ids)).with_entities(Class.id)
                    )
                ).with_entities(ClassTest.test_id).all()
                test_ids = [ct.test_id for ct in class_tests]
                
                if test_ids:
                    test_query = test_query.filter(Test.id.in_(test_ids))
                else:
                    # Se não há testes, definir como 0
                    test_query = test_query.filter(Test.id.is_(None))
                
                # Filtrar usuários por cidade
                user_query = user_query.filter_by(city_id=city_id)
                
                # Filtrar jogos por cidade (se tiver city_id)
                if hasattr(Game, 'city_id'):
                    game_query = game_query.filter_by(city_id=city_id)
                
                # Filtrar questões por cidade (se tiver city_id)
                if hasattr(Question, 'city_id'):
                    question_query = question_query.filter_by(city_id=city_id)
            else:
                # Se não há escolas na cidade, retornar zeros
                return jsonify({
                    "students": 0,
                    "schools": 0,
                    "evaluations": 0,
                    "games": 0,
                    "users": 0,
                    "questions": 0,
                    "classes": 0,
                    "teachers": 0,
                    "last_sync": datetime.now().isoformat()
                }), 200
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador vêem apenas estatísticas da sua escola
            from app.models.manager import Manager
            
            # Buscar o manager vinculado ao usuário atual
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or not manager.school_id:
                return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
            
            # Buscar a escola do manager
            # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
            from app.utils.uuid_helpers import uuid_to_str
            school_id_str = uuid_to_str(manager.school_id)
            school = School.query.filter(School.id == school_id_str).first() if school_id_str else None
            if not school:
                return jsonify({"erro": "Escola não encontrada"}), 400
            
            # Filtrar escolas (apenas a escola do manager)
            school_query = school_query.filter_by(id=school.id)
            
            # Filtrar estudantes por escola
            student_query = student_query.filter_by(school_id=school.id)
            
            # Filtrar turmas por escola
            class_query = class_query.filter_by(school_id=ensure_uuid(school.id))
            
            # Filtrar professores por escola através da tabela de associação
            teacher_query = teacher_query.join(SchoolTeacher).filter(SchoolTeacher.school_id == school.id)
            
            # Filtrar testes que têm turmas da escola
            class_tests = ClassTest.query.filter(
                ClassTest.class_id.in_(
                    Class.query.filter_by(school_id=ensure_uuid(school.id)).with_entities(Class.id)
                )
            ).with_entities(ClassTest.test_id).all()
            test_ids = [ct.test_id for ct in class_tests]
            
            if test_ids:
                test_query = test_query.filter(Test.id.in_(test_ids))
            else:
                # Se não há testes, definir como 0
                test_query = test_query.filter(Test.id.is_(None))
            
            # Filtrar usuários por cidade da escola
            user_query = user_query.filter_by(city_id=school.city_id)
            
            # Filtrar jogos por cidade da escola (se tiver city_id)
            if hasattr(Game, 'city_id'):
                game_query = game_query.filter_by(city_id=school.city_id)
            
            # Filtrar questões por cidade da escola (se tiver city_id)
            if hasattr(Question, 'city_id'):
                question_query = question_query.filter_by(city_id=school.city_id)
        elif current_user['role'] == "professor":
            # Professor vê apenas estatísticas do seu município
            city_id = current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar escolas por cidade
            school_query = school_query.filter_by(city_id=city_id)
            
            # Obter IDs das escolas da cidade
            schools_in_city = school_query.with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                # Filtrar estudantes por escolas da cidade
                student_query = student_query.filter(Student.school_id.in_(school_ids))
                
                # Filtrar turmas por escolas da cidade
                class_query = class_query.filter(Class.school_id.in_(ensure_uuid_list(school_ids)))
                
                # Filtrar professores por escolas da cidade através da tabela de associação
                teacher_query = teacher_query.join(SchoolTeacher).filter(SchoolTeacher.school_id.in_(school_ids))
                
                # Filtrar testes que têm turmas das escolas da cidade
                class_tests = ClassTest.query.filter(
                    ClassTest.class_id.in_(
                        Class.query.filter(Class.school_id.in_(ensure_uuid_list(school_ids))).with_entities(Class.id)
                    )
                ).with_entities(ClassTest.test_id).all()
                test_ids = [ct.test_id for ct in class_tests]
                
                if test_ids:
                    test_query = test_query.filter(Test.id.in_(test_ids))
                else:
                    # Se não há testes, definir como 0
                    test_query = test_query.filter(Test.id.is_(None))
                
                # Filtrar usuários por cidade
                user_query = user_query.filter_by(city_id=city_id)
                
                # Filtrar jogos por cidade (se tiver city_id)
                if hasattr(Game, 'city_id'):
                    game_query = game_query.filter_by(city_id=city_id)
                
                # Filtrar questões por cidade (se tiver city_id)
                if hasattr(Question, 'city_id'):
                    question_query = question_query.filter_by(city_id=city_id)
            else:
                # Se não há escolas na cidade, retornar zeros
                return jsonify({
                    "students": 0,
                    "schools": 0,
                    "evaluations": 0,
                    "games": 0,
                    "users": 0,
                    "questions": 0,
                    "classes": 0,
                    "teachers": 0,
                    "last_sync": datetime.now().isoformat()
                }), 200
        
        # Buscar todas as estatísticas em paralelo
        stats = {
            "students": student_query.count(),
            "schools": school_query.count(),
            "evaluations": test_query.count(),
            "games": game_query.count(),
            "users": user_query.count(),
            "questions": question_query.count(),
            "classes": class_query.count(),
            "teachers": teacher_query.count(),
            "last_sync": datetime.now().isoformat()
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar estatísticas completas do dashboard: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao buscar estatísticas completas do dashboard",
            "details": str(e)
        }), 500


@bp.route('/evaluations/stats', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def evaluations_stats():
    """
    Retorna estatísticas específicas de avaliações de forma robusta

    total_questions: quantidade de questões do banco municipal (Question com
    scope_type CITY e owner_city_id = município do contexto da requisição).

    Returns:
        {
            "total": int,
            "this_month": int,
            "total_questions": int,
            "virtual_evaluations": int,
            "physical_evaluations": int,
            "by_type": {...},
            "by_model": {...},
            "by_status": {...}
        }
    """
    try:
        # Obter usuário atual para filtragem
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        tenant_ctx = get_current_tenant_context()
        ctx_city_id = getattr(tenant_ctx, "city_id", None) if tenant_ctx else None
        if not ctx_city_id:
            return jsonify({"erro": "Contexto de cidade necessário"}), 400
        city_id_str = str(ctx_city_id)

        total_questions = 0
        try:
            path_row = db.session.execute(text("SHOW search_path")).fetchone()
            path_before = (path_row[0] if path_row else "public").strip()
            db.session.execute(text("SET search_path TO public"))
            try:
                total_questions = (
                    Question.query.filter(
                        Question.scope_type == "CITY",
                        Question.owner_city_id == city_id_str,
                    ).count()
                )
            finally:
                db.session.execute(text(f"SET search_path TO {path_before}"))
        except Exception as e:
            logging.debug("total_questions (banco municipal CITY): %s", e)

        # Base queries
        test_query = Test.query
        # Filtro por tipos (ex: types=AVALIACAO,SIMULADO)
        types_param = request.args.get('types')
        if types_param:
            types_list = [t.strip() for t in types_param.split(',') if t.strip()]
            if types_list:
                test_query = test_query.filter(Test.type.in_(types_list))

        # Filtragem baseada no papel do usuário
        if current_user['role'] == "admin":
            # Admin vê todas as estatísticas do sistema
            pass
        elif current_user['role'] == "tecadm":
            # Tecadm vê apenas estatísticas do seu município
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar testes por escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                # Filtrar testes que têm turmas das escolas da cidade
                # class.school_id é VARCHAR → comparar com strings (evitar character varying = uuid)
                class_tests = ClassTest.query.filter(
                    ClassTest.class_id.in_(
                        Class.query.filter(cast(Class.school_id, String).in_(school_ids)).with_entities(Class.id)
                    )
                ).with_entities(ClassTest.test_id).all()
                test_ids = [ct.test_id for ct in class_tests]

                if test_ids:
                    test_query = test_query.filter(Test.id.in_(test_ids))
                else:
                    # Se não há testes, retornar zeros
                    return jsonify({
                        "total": 0,
                        "this_month": 0,
                        "total_questions": total_questions,
                        "virtual_evaluations": 0,
                        "physical_evaluations": 0,
                        "by_type": {},
                        "by_model": {},
                        "by_status": {},
                        "last_sync": datetime.now().isoformat()
                    }), 200

            else:
                # Se não há escolas na cidade, retornar zeros
                return jsonify({
                    "total": 0,
                    "this_month": 0,
                    "total_questions": total_questions,
                    "virtual_evaluations": 0,
                    "physical_evaluations": 0,
                    "by_type": {},
                    "by_model": {},
                    "by_status": {},
                    "last_sync": datetime.now().isoformat()
                }), 200
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador vêem apenas estatísticas da sua escola
            from app.models.manager import Manager
            
            # Buscar o manager vinculado ao usuário atual
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or not manager.school_id:
                return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
            
            # Buscar a escola do manager
            # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
            from app.utils.uuid_helpers import uuid_to_str
            school_id_str = uuid_to_str(manager.school_id)
            school = School.query.filter(School.id == school_id_str).first() if school_id_str else None
            if not school:
                return jsonify({"erro": "Escola não encontrada"}), 400
            
            # Filtrar testes que têm turmas da escola
            # class.school_id é VARCHAR; School.id é VARCHAR → comparar como string
            class_tests = ClassTest.query.filter(
                ClassTest.class_id.in_(
                    Class.query.filter_by(school_id=school.id).with_entities(Class.id)
                )
            ).with_entities(ClassTest.test_id).all()
            test_ids = [ct.test_id for ct in class_tests]

            if test_ids:
                test_query = test_query.filter(Test.id.in_(test_ids))
            else:
                # Se não há testes, retornar zeros
                return jsonify({
                    "total": 0,
                    "this_month": 0,
                    "total_questions": total_questions,
                    "virtual_evaluations": 0,
                    "physical_evaluations": 0,
                    "by_type": {},
                    "by_model": {},
                    "by_status": {},
                    "last_sync": datetime.now().isoformat()
                }), 200

        elif current_user['role'] == "professor":
            # Professor vê apenas estatísticas do seu município
            city_id = current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar testes por escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                # Filtrar testes que têm turmas das escolas da cidade
                # class.school_id é VARCHAR → comparar com strings (evitar character varying = uuid)
                class_tests = ClassTest.query.filter(
                    ClassTest.class_id.in_(
                        Class.query.filter(cast(Class.school_id, String).in_(school_ids)).with_entities(Class.id)
                    )
                ).with_entities(ClassTest.test_id).all()
                test_ids = [ct.test_id for ct in class_tests]

                if test_ids:
                    test_query = test_query.filter(Test.id.in_(test_ids))
                else:
                    # Se não há testes, retornar zeros
                    return jsonify({
                        "total": 0,
                        "this_month": 0,
                        "total_questions": total_questions,
                        "virtual_evaluations": 0,
                        "physical_evaluations": 0,
                        "by_type": {},
                        "by_model": {},
                        "by_status": {},
                        "last_sync": datetime.now().isoformat()
                    }), 200

            else:
                # Se não há escolas na cidade, retornar zeros
                return jsonify({
                    "total": 0,
                    "this_month": 0,
                    "total_questions": total_questions,
                    "virtual_evaluations": 0,
                    "physical_evaluations": 0,
                    "by_type": {},
                    "by_model": {},
                    "by_status": {},
                    "last_sync": datetime.now().isoformat()
                }), 200

        # Estatísticas básicas (sem carregar todos os testes em memória)
        test_ids_subq = test_query.with_entities(Test.id)
        total_evaluations = test_query.count()

        from sqlalchemy import and_
        current_month = datetime.now().month
        current_year = datetime.now().year
        this_month_evaluations = test_query.filter(
            and_(
                Test.created_at >= datetime(current_year, current_month, 1),
                Test.created_at < datetime(current_year, current_month + 1, 1) if current_month < 12 else datetime(current_year + 1, 1, 1)
            )
        ).count()

        by_type = {}
        try:
            evaluations_by_type = db.session.query(Test.type, db.func.count(Test.id)).filter(
                Test.id.in_(test_ids_subq)
            ).group_by(Test.type).all()
            by_type = {item[0]: item[1] for item in evaluations_by_type if item[0]}
        except Exception as e:
            logging.debug("by_type: %s", e)

        by_model = {}
        try:
            evaluations_by_model = db.session.query(Test.model, db.func.count(Test.id)).filter(
                Test.id.in_(test_ids_subq)
            ).group_by(Test.model).all()
            by_model = {item[0]: item[1] for item in evaluations_by_model if item[0]}
        except Exception as e:
            logging.debug("by_model: %s", e)

        by_status = {}
        try:
            evaluations_by_status = db.session.query(Test.status, db.func.count(Test.id)).filter(
                Test.id.in_(test_ids_subq)
            ).group_by(Test.status).all()
            by_status = {item[0]: item[1] for item in evaluations_by_status if item[0]}
        except Exception as e:
            logging.debug("by_status: %s", e)

        virtual_evaluations = 0
        physical_evaluations = 0
        try:
            virtual_evaluations = test_query.filter(Test.evaluation_mode == 'virtual').count()
            physical_evaluations = test_query.filter(Test.evaluation_mode == 'physical').count()
        except Exception as e:
            logging.debug("modo: %s", e)

        result = {
            "total": total_evaluations,
            "this_month": this_month_evaluations,
            "total_questions": total_questions,
            "virtual_evaluations": virtual_evaluations,
            "physical_evaluations": physical_evaluations,
            "by_type": by_type,
            "by_model": by_model,
            "by_status": by_status,
            "last_sync": datetime.now().isoformat()
        }
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"💥 Erro geral ao buscar estatísticas de avaliações: {str(e)}", exc_info=True)
        # Retornar dados padrão em caso de erro
        return jsonify({
            "total": 0,
            "this_month": 0,
            "total_questions": 0,
            "virtual_evaluations": 0,
            "physical_evaluations": 0,
            "by_type": {},
            "by_model": {},
            "by_status": {},
            "last_sync": datetime.now().isoformat(),
            "error": "Erro ao buscar estatísticas de avaliações",
            "details": str(e)
        }), 200  # Retorna 200 mesmo com erro para não quebrar o frontend


@bp.route('/test-sessions/submitted', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_submitted_evaluations():
    """
    Retorna avaliações enviadas pelos alunos para correção
    
    Query Parameters:
        - status: pending, correcting, corrected, reviewed
        - subject: ID da disciplina
        - grade: ID da série
        - search: busca por nome do aluno ou título da avaliação
        - page: número da página (padrão: 1)
        - per_page: itens por página (padrão: 20)
    
    Returns:
        Lista de sessões de teste enviadas com dados do aluno e avaliação
    """
    try:
        print("Iniciando busca de avaliações enviadas...")
        from app.models.testSession import TestSession
        from app.models.student import Student
        from app.models.test import Test
        from app.models.subject import Subject
        from app.models.grades import Grade
        from app.models.user import User
        from app.models.studentAnswer import StudentAnswer
        from sqlalchemy.orm import joinedload
        print("Modelos importados com sucesso")
        
        # Parâmetros de busca
        status_filter = request.args.get('status', '').strip()
        subject_filter = request.args.get('subject', '').strip()
        grade_filter = request.args.get('grade', '').strip()
        search_filter = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        print("Criando query base...")
        # Obter usuário logado
        from app.decorators.role_required import get_current_user_from_token
        user = get_current_user_from_token()
        
        # Base query - buscar sessões enviadas
        query = TestSession.query.options(
            joinedload(TestSession.student).joinedload(Student.user),
            joinedload(TestSession.test).joinedload(Test.subject_rel),
            joinedload(TestSession.test).joinedload(Test.grade)
        ).filter(
            TestSession.submitted_at.isnot(None)  # Apenas sessões enviadas
        )
        
        # Filtrar por município se for tecadm
        if user and user['role'] == "tecadm":
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar por escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                # Filtrar estudantes por escolas da cidade
                query = query.join(Student).filter(Student.school_id.in_(school_ids))
            else:
                # Se não há escolas na cidade, retornar lista vazia
                return jsonify({
                    "items": [],
                    "total": 0,
                    "pages": 0,
                    "current_page": page,
                    "per_page": per_page
                }), 200
        
        # Filtrar apenas avaliações criadas pelo usuário logado (exceto para admin e tecadm)
        if user and user['role'] not in ['admin', 'tecadm']:
            query = query.join(Test).filter(Test.created_by == user['id'])
            print(f"Filtro aplicado: apenas avaliações criadas pelo usuário {user['id']} (role: {user.get('role')})")
        else:
            # Para admin e tecadm, mostrar todas as avaliações (filtradas por cidade se for tecadm)
            query = query.join(Test)
            print(f"Filtro aplicado: todas as avaliações para usuário {user['id']} (role: {user.get('role')})")
        
        print("Query base criada com sucesso")
        
        # Aplicar filtros (modelo usa finalizada/corrigida/revisada; aceitar também equivalentes em inglês)
        if status_filter and status_filter != 'all':
            if status_filter == 'pending':
                query = query.filter(TestSession.status.in_(['finalizada', 'completed', 'submitted']))
            elif status_filter == 'correcting':
                query = query.filter(TestSession.status.in_(['correcting', 'em_correcao']))
            elif status_filter == 'corrected':
                query = query.filter(TestSession.status.in_(['corrected', 'corrigida']))
            elif status_filter == 'reviewed':
                query = query.filter(TestSession.status.in_(['reviewed', 'finalized', 'revisada']))
        
        # Filtro por disciplina (Test já foi unido acima)
        if subject_filter and subject_filter != 'all':
            query = query.filter(Test.subject == subject_filter)
        
        # Filtro por série (Test já foi unido acima)
        if grade_filter and grade_filter != 'all':
            query = query.filter(Test.grade_id == grade_filter)
        
        # Filtro de busca por nome do aluno ou título da avaliação
        if search_filter:
            if user and user.get('role') == 'tecadm':
                # tecadm já tem Student no join; só aplicar o filtro
                query = query.filter(
                    db.or_(
                        Student.name.ilike(f'%{search_filter}%'),
                        Test.title.ilike(f'%{search_filter}%')
                    )
                )
            else:
                # admin/outros: incluir join de Student só para a busca
                query = query.join(Student).filter(
                    db.or_(
                        Student.name.ilike(f'%{search_filter}%'),
                        Test.title.ilike(f'%{search_filter}%')
                    )
                )
        
        # Ordenar por data de envio (mais recentes primeiro)
        query = query.order_by(TestSession.submitted_at.desc())
        
        print("Aplicando paginação...")
        # Aplicar paginação
        paginated_sessions = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        sessions = paginated_sessions.items
        print(f"Paginação aplicada. {len(sessions)} sessões encontradas")
        
        # Transformar dados para o formato esperado pelo frontend
        result = []
        for session in sessions:
            # Buscar respostas do aluno
            answers = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id
            ).all()
            
            # Calcular tempo gasto
            from datetime import datetime
            start_time = session.started_at or session.created_at
            end_time = session.submitted_at or datetime.utcnow()
            time_spent = int((end_time - start_time).total_seconds() // 60) if start_time and end_time else 0
            
            # Calcular scores baseados nos campos existentes
            auto_score = session.score or 0
            manual_score = session.grade or 0  # grade é a nota final (0-10)
            final_score = session.grade or 0   # grade é a nota final
            percentage = session.score or 0    # score é a porcentagem
            
            session_data = {
                "id": session.id,
                "student_id": session.student_id,
                "student_name": session.student.name if session.student else 'Aluno não encontrado',
                "test_id": session.test_id,
                "test_title": session.test.title if session.test else 'Avaliação não encontrada',
                "subject_id": session.test.subject if session.test else None,
                "subject_name": session.test.subject_rel.name if session.test and session.test.subject_rel else 'Sem disciplina',
                "grade_id": session.test.grade_id if session.test else None,
                "grade_name": session.test.grade.name if session.test and session.test.grade else 'Sem série',
                "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
                "time_spent": time_spent,
                "status": session.status,
                "total_questions": session.total_questions or (len(answers) if answers else 0),
                "blank_answers": len([a for a in answers if not a.answer]),
                "auto_score": auto_score,
                "manual_score": manual_score,
                "final_score": final_score,
                "percentage": percentage,
                "corrected_by": session.corrected_by,
                "corrected_at": session.corrected_at.isoformat() if session.corrected_at else None,
                "feedback": session.feedback,
                "answers": [
                    enrich_answer_data(answer, answer.question) if answer.question else {
                        "question_id": answer.question_id,
                        "question_text": "Questão não encontrada",
                        "question_type": "multiple_choice",
                        "correct_answer": None,
                        "student_answer": answer.answer,
                        "options": [],
                        "is_correct": False,
                        "manual_points": answer.manual_score,
                        "feedback": answer.feedback
                    }
                    for answer in answers
                ]
            }
            result.append(session_data)
        
        # Formato consistente com o retorno vazio (tecadm sem escolas): items + paginação
        return jsonify({
            "items": result,
            "total": paginated_sessions.total,
            "pages": paginated_sessions.pages,
            "current_page": page,
            "per_page": per_page,
        }), 200
        
    except Exception as e:
        print(f"ERRO DETALHADO: {str(e)}")
        print(f"Tipo do erro: {type(e)}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
        logging.error(f"Erro ao buscar avaliações enviadas: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao buscar avaliações enviadas",
            "details": str(e)
        }), 500


@bp.route('/test-session/<string:session_id>/correct', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def correct_evaluation(session_id):
    """
    Salva a correção de uma avaliação (sem finalizar)
    
    Body:
        {
            "questions": [
                {
                    "question_id": "string",
                    "is_correct": boolean,
                    "manual_points": number (0 ou 1),
                    "feedback": "string"
                }
            ],
            "final_score": number,
            "percentage": number,
            "general_feedback": "string",
            "status": "corrected"
        }
    """
    try:
        from app.models.testSession import TestSession
        from app.models.studentAnswer import StudentAnswer
        from app.decorators.role_required import get_current_user_from_token
        
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({"error": "Sessão não encontrada"}), 404
        
        # Verificar se a sessão foi enviada
        if not session.submitted_at:
            return jsonify({"error": "Sessão ainda não foi enviada pelo aluno"}), 400
        
        # Obter usuário atual
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Atualizar respostas das questões
        questions_data = data.get('questions', [])
        for question_data in questions_data:
            question_id = question_data.get('question_id')
            is_correct = question_data.get('is_correct', False)
            manual_points = question_data.get('manual_points', 0)
            feedback = question_data.get('feedback', '')
            
            # Buscar resposta do aluno
            answer = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id,
                question_id=question_id
            ).first()
            
            if answer:
                answer.is_correct = is_correct
                answer.manual_score = manual_points if manual_points is not None else (1 if is_correct else 0)
                answer.feedback = feedback
        
        # Atualizar dados da sessão
        # Converter nota final (0-10) para grade e score (porcentagem)
        final_score = data.get('final_score', 0)
        percentage = data.get('percentage', 0)
        
        session.grade = final_score  # grade é a nota final (0-10)
        session.score = percentage   # score é a porcentagem
        session.feedback = data.get('general_feedback', '')
        session.status = 'corrected'
        session.corrected_by = current_user['id']
        session.corrected_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            "message": "Correção salva com sucesso",
            "session_id": session_id,
            "final_score": session.grade,
            "percentage": session.score
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao salvar correção: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao salvar correção",
            "details": str(e)
        }), 500


@bp.route('/test-session/<string:session_id>/finalize', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def finalize_evaluation(session_id):
    """
    Finaliza a correção de uma avaliação (não pode mais ser editada)
    
    Body: Mesmo formato do endpoint /correct
    """
    try:
        from app.models.testSession import TestSession
        from app.models.studentAnswer import StudentAnswer
        from app.decorators.role_required import get_current_user_from_token
        
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({"error": "Sessão não encontrada"}), 404
        
        # Verificar se a sessão foi enviada
        if not session.submitted_at:
            return jsonify({"error": "Sessão ainda não foi enviada pelo aluno"}), 400
        
        # Obter usuário atual
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Atualizar respostas das questões
        questions_data = data.get('questions', [])
        for question_data in questions_data:
            question_id = question_data.get('question_id')
            is_correct = question_data.get('is_correct', False)
            manual_points = question_data.get('manual_points', 0)
            feedback = question_data.get('feedback', '')
            
            # Buscar resposta do aluno
            answer = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id,
                question_id=question_id
            ).first()
            
            if answer:
                answer.is_correct = is_correct
                answer.manual_score = manual_points if manual_points is not None else (1 if is_correct else 0)
                answer.feedback = feedback
        
        # Atualizar dados da sessão
        # Converter nota final (0-10) para grade e score (porcentagem)
        final_score = data.get('final_score', 0)
        percentage = data.get('percentage', 0)
        
        session.grade = final_score  # grade é a nota final (0-10)
        session.score = percentage   # score é a porcentagem
        session.feedback = data.get('general_feedback', '')
        session.status = 'finalized'  # Status final
        session.corrected_by = current_user['id']
        session.corrected_at = datetime.now()
        
        # Calcular proficiência baseada na nota final
        proficiency_level = calculate_proficiency(percentage)
        
        db.session.commit()
        
        return jsonify({
            "message": "Correção finalizada com sucesso",
            "session_id": session_id,
            "final_score": session.grade,
            "percentage": session.score,
            "proficiency_level": proficiency_level,
            "status": "finalized"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao finalizar correção: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao finalizar correção",
            "details": str(e)
        }), 500


def normalize_options(alternatives):
    """
    Garante que cada alternativa é um dict com id e text
    """
    options = []
    for idx, alt in enumerate(alternatives or []):
        # Se já for dict com id/text, mantém
        if isinstance(alt, dict) and 'id' in alt and 'text' in alt:
            options.append(alt)
        # Se for só texto, cria id padrão
        elif isinstance(alt, str):
            options.append({"id": f"option-{idx+1}", "text": alt})
        # Se for dict só com texto
        elif isinstance(alt, dict) and 'text' in alt:
            options.append({"id": alt.get("id", f"option-{idx+1}"), "text": alt["text"]})
    return options


def normalize_options_with_correct(alternatives, correct_answer=None):
    """
    Garante que cada alternativa tenha id, text e isCorrect
    Com validação para múltiplas alternativas corretas
    """
    if not alternatives:
        return []
    
    # ✅ CORREÇÃO: Se alternatives já é uma lista, usar diretamente
    if isinstance(alternatives, list):
        parsed_alternatives = alternatives
    elif isinstance(alternatives, str):
        try:
            import json
            parsed_alternatives = json.loads(alternatives)
        except json.JSONDecodeError:
            logging.warning(f"NORMALIZE: Erro ao fazer parse do JSON: {alternatives[:100]}...")
            return []
    else:
        logging.warning(f"NORMALIZE: Tipo inesperado para alternatives: {type(alternatives)}")
        return []
    
    if not isinstance(parsed_alternatives, list):
        logging.warning(f"NORMALIZE: alternatives não é uma lista após parse: {type(parsed_alternatives)}")
        return []
    
    options = []
    for idx, alt in enumerate(parsed_alternatives):
        # Determinar ID e texto
        if isinstance(alt, dict):
            if alt.get('id') and alt.get('id') != 'None':
                option_id = alt.get('id')
            else:
                option_id = f"option-{idx}"
            text = alt.get('text', alt.get('answer', ''))
            is_correct = alt.get('isCorrect', alt.get('is_correct', False))
        elif isinstance(alt, str):
            option_id = f"option-{idx}"
            text = alt
            is_correct = False
        else:
            continue
        
        # Determinar se está correto baseado no correct_answer
        if correct_answer and not is_correct:
            # Comparar por ID
            if option_id == correct_answer:
                is_correct = True
            # Comparar por texto
            elif text.strip().lower() == correct_answer.strip().lower():
                is_correct = True
            # Comparar por letra (A, B, C, D...)
            elif correct_answer.strip().upper() in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
                letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
                if idx < len(letters) and letters[idx] == correct_answer.strip().upper():
                    is_correct = True
        
        options.append({
            "id": option_id,
            "text": text,
            "isCorrect": is_correct
        })
    
    # ✅ VALIDAÇÃO: Verificar se há múltiplas alternativas corretas
    correct_count = sum(1 for opt in options if opt.get('isCorrect'))
    if correct_count > 1:
        logging.warning(f"VALIDAÇÃO: Questão tem {correct_count} alternativas corretas. Mantendo apenas a primeira.")
        # Manter apenas a primeira alternativa correta
        first_correct_found = False
        for opt in options:
            if opt.get('isCorrect') and not first_correct_found:
                first_correct_found = True
            elif opt.get('isCorrect') and first_correct_found:
                opt['isCorrect'] = False
    elif correct_count == 0 and correct_answer:
        logging.warning(f"VALIDAÇÃO: Nenhuma alternativa correta encontrada. Tentando inferir baseado em correct_answer: {correct_answer}")
    
    return options


def validate_question_data(question):
    """
    Valida se a questão tem dados coerentes
    """
    if not question or not question.alternatives:
        return True  # Pode ser questão discursiva
    
    try:
        # ✅ CORREÇÃO: Parse das alternativas
        if isinstance(question.alternatives, list):
            alternatives = question.alternatives
        elif isinstance(question.alternatives, str):
            import json
            alternatives = json.loads(question.alternatives)
        else:
            logging.warning(f"VALIDAÇÃO: Questão {question.id} - alternatives não é lista nem string")
            return False
        
        if not isinstance(alternatives, list):
            logging.warning(f"VALIDAÇÃO: Questão {question.id} - alternatives não é uma lista após parse")
            return False
        
        # Verificar se tem alternativas
        if not alternatives:
            return True  # Pode ser questão discursiva
        
        # Contar alternativas corretas
        correct_count = 0
        for alt in alternatives:
            if isinstance(alt, dict):
                is_correct = alt.get('isCorrect', False) or alt.get('is_correct', False)
                if is_correct:
                    correct_count += 1
        
        # Validar quantidade de alternativas corretas
        if correct_count > 1:
            logging.warning(f"VALIDAÇÃO: Questão {question.id} tem {correct_count} alternativas corretas (deveria ter apenas 1)")
            return False
        elif correct_count == 0:
            # Verificar se há correct_answer definido
            if question.correct_answer:
                logging.info(f"VALIDAÇÃO: Questão {question.id} tem correct_answer mas nenhuma alternativa marcada como correta")
                return True  # Pode ser válido se o gabarito estiver no campo correct_answer
            else:
                logging.warning(f"VALIDAÇÃO: Questão {question.id} não tem alternativa correta nem correct_answer definido")
                return False
        
        # Verificar se todos os IDs são únicos
        ids = [alt.get('id') for alt in alternatives if isinstance(alt, dict) and alt.get('id')]
        if len(ids) != len(set(ids)):
            logging.warning(f"VALIDAÇÃO: Questão {question.id} tem IDs de alternativas duplicados")
            return False
        
        return True
        
    except Exception as e:
        logging.error(f"VALIDAÇÃO: Erro ao validar questão {question.id}: {e}")
        return False


def is_answer_correct(student_answer, correct_answer, alternatives=None):
    """
    Verifica se a resposta do aluno está correta
    """
    if not student_answer or not correct_answer:
        return False
    
    # Normalizar strings
    student_answer = str(student_answer).strip()
    correct_answer = str(correct_answer).strip()
    
    # Comparação direta
    if student_answer.lower() == correct_answer.lower():
        return True
    
    # Se temos alternativas, fazer verificação mais robusta
    if alternatives:
        # Normalizar alternativas primeiro
        normalized_alternatives = normalize_options_with_correct(alternatives, correct_answer)
        
        # Encontrar qual alternativa é a correta
        correct_option_id = None
        for alt in normalized_alternatives:
            if alt.get('isCorrect'):
                correct_option_id = alt.get('id')
                break
        
        # Se encontramos a alternativa correta, verificar se o aluno escolheu ela
        if correct_option_id:
            return student_answer == correct_option_id
        
        # Fallback: verificar por texto
        for idx, alt in enumerate(alternatives):
            if isinstance(alt, dict):
                alt_text = alt.get('text', '')
                alt_id = alt.get('id', f"option-{idx}")
                
                # Se o correct_answer é um texto, verificar se corresponde a esta alternativa
                if correct_answer.lower() == alt_text.strip().lower():
                    # Verificar se o aluno escolheu esta alternativa (por ID ou texto)
                    return (student_answer == alt_id or 
                           student_answer.lower() == alt_text.strip().lower())
            elif isinstance(alt, str):
                if correct_answer.lower() == alt.strip().lower():
                    return student_answer.lower() == alt.strip().lower()
    
    # Verificar se é uma letra (A, B, C, D...)
    if correct_answer.upper() in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
        letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        if student_answer.upper() in letters:
            return student_answer.upper() == correct_answer.upper()
        
        # Verificar se o aluno respondeu com o ID da opção correspondente à letra
        if alternatives and correct_answer.upper() in letters:
            letter_index = letters.index(correct_answer.upper())
            if letter_index < len(alternatives):
                return student_answer == f"option-{letter_index}"
    
    return False


def calculate_session_score(answers, questions_dict):
    """
    Calcular nota final automaticamente baseado nas respostas
    """
    total_score = 0
    total_questions = len(answers)
    correct_answers = 0
    
    for answer in answers:
        question = questions_dict.get(answer.question_id)
        if not question:
            continue
            
        if question.question_type == "essay" or question.question_type == "discursive":
            # Questões dissertativas: usar pontuação manual se disponível
            manual_points = getattr(answer, 'manual_score', None) or 0
            total_score += manual_points
            if manual_points > 0:
                correct_answers += 1
        else:
            # Questões objetivas: verificar se resposta está correta
            if is_answer_correct(answer.answer, question.correct_answer, question.alternatives):
                total_score += 1
                correct_answers += 1
    
    percentage = (total_score / total_questions * 100) if total_questions > 0 else 0
    
    return {
        "final_score": total_score,
        "percentage": round(percentage, 1),
        "correct_answers": correct_answers,
        "total_questions": total_questions
    }


def enrich_answer_data(answer, question):
    """
    Enriquecer dados da resposta com informações completas da questão
    Com validação robusta
    """
    if not question:
        return {
            "question_id": answer.question_id,
            "question_text": "Questão não encontrada",
            "question_type": "multiple_choice",
            "correct_answer": None,
            "student_answer": answer.answer,
            "options": [],
            "is_correct": False,
            "manual_points": getattr(answer, 'manual_score', None),
            "feedback": getattr(answer, 'feedback', None)
        }
    
    # ✅ VALIDAR questão antes de processar
    if not validate_question_data(question):
        logging.warning(f"ENRICH: Questão {question.id} falhou na validação. Processando com cuidado...")
    
    # Normalizar alternativas
    options = normalize_options_with_correct(question.alternatives, question.correct_answer)
    
    # Verificar se a resposta está correta
    is_correct = is_answer_correct(answer.answer, question.correct_answer, question.alternatives)
    
    # Determinar o correct_answer para retornar (ID da opção correta)
    correct_answer_id = None
    for option in options:
        if option.get('isCorrect'):
            correct_answer_id = option.get('id')
            break
    
    # Se não encontrou ID da opção correta, usar o campo correct_answer da questão
    if not correct_answer_id and question.correct_answer:
        correct_answer_id = question.correct_answer
    
    return {
        "question_id": answer.question_id,
        "question_text": question.text or "Texto não disponível",
        "question_type": question.question_type or "multiple_choice",
        "correct_answer": correct_answer_id,  # ✅ Retorna o ID da opção correta
        "student_answer": answer.answer,
        "options": options,                   # ✅ Sempre presente com isCorrect validado
        "is_correct": is_correct,             # ✅ Calculado automaticamente
        "manual_points": getattr(answer, 'manual_score', None),
        "feedback": getattr(answer, 'feedback', None)
    }


def get_correct_option_id(alternatives, correct_answer):
    """
    Retorna o id da alternativa correta baseado no texto
    """
    if not alternatives or not correct_answer:
        return None
    
    normalized_options = normalize_options(alternatives)
    
    for alt in normalized_options:
        if isinstance(alt, dict) and alt.get('text'):
            # Comparar textos ignorando espaços extras
            if alt.get('text').strip() == correct_answer.strip():
                return alt.get('id')
    
    return None


def calculate_proficiency(percentage):
    """
    Calcula nível de proficiência baseado na porcentagem
    Baseado na equação da página de resultados
    """
    if percentage >= 80:
        return 'Avançado'
    elif percentage >= 65:
        return 'Adequado'
    elif percentage >= 50:
        return 'Básico'
    else:
        return 'Abaixo do Básico'


@bp.route('/courses', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
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
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
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
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
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
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
        classes = Class.query.join(School, Class.school_id == cast(School.id, PostgresUUID)).join(Grade).all()
        
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
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def list_schools():
    """
    Lista escolas. Query params opcionais para filtro (escopo competição):
    - city_id: lista apenas escolas do município (útil após selecionar estado e município).
    - state: lista apenas escolas do estado (usa City.state; ex: SP, RJ).
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
        query = School.query
        city_id = request.args.get('city_id')
        state = request.args.get('state')
        if city_id:
            query = query.filter(School.city_id == city_id)
        elif state:
            from app.models.city import City
            query = query.join(City, School.city_id == City.id).filter(City.state.ilike(state))
        schools = query.all()
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


@bp.route('/schools/recent', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def recent_schools():
    """
    Retorna as escolas mais recentes com detalhes completos
    
    Returns:
        Lista de escolas com informações de cidade e estatísticas
    """
    try:
        from sqlalchemy.orm import joinedload
        from sqlalchemy import func
        
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Base query
        school_query = School.query.options(
            joinedload(School.city)
        )
        
        # Filtragem baseada no papel do usuário
        if current_user['role'] == "admin":
            # Admin vê todas as escolas do sistema
            pass
        elif current_user['role'] == "tecadm":
            # Tecadm vê apenas escolas do seu município
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            school_query = school_query.filter_by(city_id=city_id)
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador vêem apenas sua escola
            from app.models.manager import Manager
            
            # Buscar o manager vinculado ao usuário atual
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or not manager.school_id:
                return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
            
            # Buscar a escola do manager
            # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
            from app.utils.uuid_helpers import uuid_to_str
            school_id_str = uuid_to_str(manager.school_id)
            school = School.query.filter(School.id == school_id_str).first() if school_id_str else None
            if not school:
                return jsonify({"erro": "Escola não encontrada"}), 400
            
            # Filtrar apenas a escola do manager
            school_query = school_query.filter_by(id=school.id)
        elif current_user['role'] == "professor":
            # Professor vê apenas escolas do seu município
            city_id = current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            school_query = school_query.filter_by(city_id=city_id)
        
        # Buscar as 5 escolas mais recentes com relacionamentos
        recent_schools = school_query.order_by(
            School.created_at.desc()
        ).limit(5).all()
        
        schools_data = []
        for school in recent_schools:
            # Contar alunos e turmas desta escola
            students_count = Student.query.filter_by(school_id=school.id).count()
            classes_count = Class.query.filter_by(school_id=ensure_uuid(school.id)).count()
            
            school_data = {
                "id": school.id,
                "name": school.name,
                "domain": school.domain,
                "address": school.address,
                "created_at": school.created_at.isoformat() if school.created_at else None,
                "students_count": students_count,
                "classes_count": classes_count,
                "city": {
                    "id": school.city.id,
                    "name": school.city.name,
                    "state": school.city.state
                } if school.city else None
            }
            schools_data.append(school_data)
        
        return jsonify(schools_data), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar escolas recentes: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao buscar escolas recentes",
            "details": str(e)
        }), 500


@bp.route('/students/recent', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def recent_students():
    """
    Retorna os alunos mais recentes com detalhes completos
    
    Returns:
        Lista de alunos com informações de escola, turma e série
    """
    try:
        from sqlalchemy.orm import joinedload
        
        # Obter usuário atual para filtragem
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Base query
        student_query = Student.query.options(
            joinedload(Student.school),
            joinedload(Student.class_),
            joinedload(Student.grade)
        )
        
        # Filtragem baseada no papel do usuário
        if current_user['role'] == "admin":
            # Admin vê todos os estudantes do sistema
            pass
        elif current_user['role'] == "tecadm":
            # Tecadm vê apenas estudantes do seu município
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar estudantes por escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                student_query = student_query.filter(Student.school_id.in_(school_ids))
            else:
                # Se não há escolas na cidade, retornar lista vazia
                return jsonify([]), 200
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador vêem apenas estudantes da sua escola
            from app.models.manager import Manager
            
            # Buscar o manager vinculado ao usuário atual
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or not manager.school_id:
                return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
            
            # Buscar a escola do manager
            # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
            from app.utils.uuid_helpers import uuid_to_str
            school_id_str = uuid_to_str(manager.school_id)
            school = School.query.filter(School.id == school_id_str).first() if school_id_str else None
            if not school:
                return jsonify({"erro": "Escola não encontrada"}), 400
            
            # Filtrar estudantes por escola
            student_query = student_query.filter_by(school_id=school.id)
        elif current_user['role'] == "professor":
            # Professor vê apenas estudantes do seu município
            city_id = current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar estudantes por escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                student_query = student_query.filter(Student.school_id.in_(school_ids))
            else:
                # Se não há escolas na cidade, retornar lista vazia
                return jsonify([]), 200
        
        # Buscar os 5 alunos mais recentes com relacionamentos (versão mais segura)
        recent_students = student_query.order_by(
            Student.created_at.desc()
        ).limit(5).all()
        
        students_data = []
        for student in recent_students:
            # Buscar dados do usuário separadamente para evitar erros
            user_data = None
            try:
                if hasattr(student, 'user_id') and student.user_id:
                    from app.models.user import User
                    user = User.query.get(student.user_id)
                    if user:
                        user_data = {
                            "id": user.id,
                            "email": user.email,
                            "role": user.role.value
                        }
            except Exception as user_error:
                logging.warning(f"Erro ao buscar dados do usuário para aluno {student.id}: {user_error}")
            
            student_data = {
                "id": student.id,
                "name": student.name,
                "registration": student.registration,
                "created_at": student.created_at.isoformat() if student.created_at else None,
                "school": {
                    "id": student.school.id,
                    "name": student.school.name
                } if student.school else None,
                "class": {
                    "id": student.class_.id,
                    "name": student.class_.name
                } if student.class_ else None,
                "grade": {
                    "id": student.grade.id,
                    "name": student.grade.name
                } if student.grade else None,
                "user": user_data
            }
            students_data.append(student_data)
        
        return jsonify(students_data), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar alunos recentes: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao buscar alunos recentes",
            "details": str(e)
        }), 500 


@bp.route('/questions/recent', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def recent_questions():
    """
    Retorna as questões mais recentes com detalhes completos
    
    Returns:
        Lista de questões com informações de disciplina, série e criador
    """
    try:
        from sqlalchemy.orm import joinedload
        
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Base query
        question_query = Question.query.options(
            joinedload(Question.subject),
            joinedload(Question.grade),
            joinedload(Question.creator)
        )
        
        # Filtragem baseada no papel do usuário
        if current_user['role'] == "admin":
            # Admin vê todas as questões do sistema
            pass
        elif current_user['role'] == "tecadm":
            # Tecadm vê apenas questões do seu município
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar questões por cidade (se tiver city_id)
            if hasattr(Question, 'city_id'):
                question_query = question_query.filter_by(city_id=city_id)
            else:
                # Se não tiver city_id, filtrar por usuários da cidade
                from app.models.user import User
                question_query = question_query.join(User, Question.created_by == User.id).filter(User.city_id == city_id)
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador vêem apenas questões da sua escola
            from app.models.manager import Manager
            
            # Buscar o manager vinculado ao usuário atual
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or not manager.school_id:
                return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
            
            # Buscar a escola do manager
            # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
            from app.utils.uuid_helpers import uuid_to_str
            school_id_str = uuid_to_str(manager.school_id)
            school = School.query.filter(School.id == school_id_str).first() if school_id_str else None
            if not school:
                return jsonify({"erro": "Escola não encontrada"}), 400
            
            # Filtrar questões por cidade da escola (se tiver city_id)
            if hasattr(Question, 'city_id'):
                question_query = question_query.filter_by(city_id=school.city_id)
            else:
                # Se não tiver city_id, filtrar por usuários da cidade da escola
                from app.models.user import User
                question_query = question_query.join(User, Question.created_by == User.id).filter(User.city_id == school.city_id)
        elif current_user['role'] == "professor":
            # Professor vê apenas questões do seu município
            city_id = current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar questões por cidade (se tiver city_id)
            if hasattr(Question, 'city_id'):
                question_query = question_query.filter_by(city_id=city_id)
            else:
                # Se não tiver city_id, filtrar por usuários da cidade
                from app.models.user import User
                question_query = question_query.join(User, Question.created_by == User.id).filter(User.city_id == city_id)
        
        # Buscar as 5 questões mais recentes com relacionamentos
        recent_questions = question_query.order_by(
            Question.created_at.desc()
        ).limit(5).all()
        
        questions_data = []
        for question in recent_questions:
            question_data = {
                "id": question.id,
                "title": question.title,
                "text": question.text,
                "formatted_text": question.formatted_text,
                "question_type": question.question_type,
                "difficulty_level": question.difficulty_level,
                "value": question.value,
                "created_at": question.created_at.isoformat() if question.created_at else None,
                "subject": {
                    "id": question.subject.id,
                    "name": question.subject.name
                } if question.subject else None,
                "grade": {
                    "id": question.grade.id,
                    "name": question.grade.name
                } if question.grade else None,
                "creator": {
                    "id": question.creator.id,
                    "name": question.creator.name
                } if question.creator else None
            }
            questions_data.append(question_data)
        
        return jsonify(questions_data), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar questões recentes: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao buscar questões recentes",
            "details": str(e)
        }), 500 


@bp.route('/evaluation-results/stats', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_evaluation_results_stats():
    """
    Retorna estatísticas gerais dos resultados de avaliações
    
    Returns:
        {
            "completed_evaluations": int,
            "pending_results": int,
            "total_evaluations": int,
            "average_score": float,
            "total_students": int,
            "average_completion_time": int,
            "top_performance_subject": string
        }
    """
    try:
        from app.models.testSession import TestSession
        from app.models.test import Test
        from app.models.student import Student
        from app.models.subject import Subject
        from sqlalchemy import func
        
        # Obter usuário atual para filtragem
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Base queries
        test_session_query = TestSession.query
        test_query = Test.query
        student_query = Student.query
        
        # Filtragem baseada no papel do usuário
        if current_user['role'] == "admin":
            # Admin vê todas as estatísticas do sistema
            pass
        elif current_user['role'] == "tecadm":
            # Tecadm vê apenas estatísticas do seu município
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar testes por escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                # Filtrar testes que têm turmas das escolas da cidade
                class_tests = ClassTest.query.filter(
                    ClassTest.class_id.in_(
                        Class.query.filter(Class.school_id.in_(ensure_uuid_list(school_ids))).with_entities(Class.id)
                    )
                ).with_entities(ClassTest.test_id).all()
                test_ids = [ct.test_id for ct in class_tests]
                
                if test_ids:
                    test_query = test_query.filter(Test.id.in_(test_ids))
                    test_session_query = test_session_query.filter(TestSession.test_id.in_(test_ids))
                else:
                    # Se não há testes, retornar zeros
                    return jsonify({
                        "completed_evaluations": 0,
                        "pending_results": 0,
                        "total_evaluations": 0,
                        "average_score": 0.0,
                        "total_students": 0,
                        "average_completion_time": 0,
                        "top_performance_subject": "Não disponível"
                    }), 200
                
                # Filtrar estudantes por escolas da cidade
                student_query = student_query.filter(Student.school_id.in_(school_ids))
            else:
                # Se não há escolas na cidade, retornar zeros
                return jsonify({
                    "completed_evaluations": 0,
                    "pending_results": 0,
                    "total_evaluations": 0,
                    "average_score": 0.0,
                    "total_students": 0,
                    "average_completion_time": 0,
                    "top_performance_subject": "Não disponível"
                }), 200
        elif current_user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador vêem apenas estatísticas da sua escola
            from app.models.manager import Manager
            
            # Buscar o manager vinculado ao usuário atual
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if not manager or not manager.school_id:
                return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
            
            # Buscar a escola do manager
            # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
            from app.utils.uuid_helpers import uuid_to_str
            school_id_str = uuid_to_str(manager.school_id)
            school = School.query.filter(School.id == school_id_str).first() if school_id_str else None
            if not school:
                return jsonify({"erro": "Escola não encontrada"}), 400
            
            # Filtrar testes que têm turmas da escola
            class_tests = ClassTest.query.filter(
                ClassTest.class_id.in_(
                    Class.query.filter_by(school_id=ensure_uuid(school.id)).with_entities(Class.id)
                )
            ).with_entities(ClassTest.test_id).all()
            test_ids = [ct.test_id for ct in class_tests]
            
            if test_ids:
                test_query = test_query.filter(Test.id.in_(test_ids))
                test_session_query = test_session_query.filter(TestSession.test_id.in_(test_ids))
            else:
                # Se não há testes, retornar zeros
                return jsonify({
                    "completed_evaluations": 0,
                    "pending_results": 0,
                    "total_evaluations": 0,
                    "average_score": 0.0,
                    "total_students": 0,
                    "average_completion_time": 0,
                    "top_performance_subject": "Não disponível"
                }), 200
            
            # Filtrar estudantes por escola
            student_query = student_query.filter_by(school_id=school.id)
        elif current_user['role'] == "professor":
            # Professor vê apenas estatísticas do seu município
            city_id = current_user.get('city_id')
            if not city_id:
                return jsonify({"erro": "ID da cidade não disponível"}), 400
            
            # Filtrar testes por escolas da cidade
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids = [school.id for school in schools_in_city]
            
            if school_ids:
                # Filtrar testes que têm turmas das escolas da cidade
                class_tests = ClassTest.query.filter(
                    ClassTest.class_id.in_(
                        Class.query.filter(Class.school_id.in_(ensure_uuid_list(school_ids))).with_entities(Class.id)
                    )
                ).with_entities(ClassTest.test_id).all()
                test_ids = [ct.test_id for ct in class_tests]
                
                if test_ids:
                    test_query = test_query.filter(Test.id.in_(test_ids))
                    test_session_query = test_session_query.filter(TestSession.test_id.in_(test_ids))
                else:
                    # Se não há testes, retornar zeros
                    return jsonify({
                        "completed_evaluations": 0,
                        "pending_results": 0,
                        "total_evaluations": 0,
                        "average_score": 0.0,
                        "total_students": 0,
                        "average_completion_time": 0,
                        "top_performance_subject": "Não disponível"
                    }), 200
                
                # Filtrar estudantes por escolas da cidade
                student_query = student_query.filter(Student.school_id.in_(school_ids))
            else:
                # Se não há escolas na cidade, retornar zeros
                return jsonify({
                    "completed_evaluations": 0,
                    "pending_results": 0,
                    "total_evaluations": 0,
                    "average_score": 0.0,
                    "total_students": 0,
                    "average_completion_time": 0,
                    "top_performance_subject": "Não disponível"
                }), 200
        
        # Avaliações concluídas (finalizadas)
        completed_evaluations = test_session_query.filter(
            TestSession.status.in_(['finalized', 'reviewed']),
            TestSession.submitted_at.isnot(None)
        ).count()
        
        # Avaliações pendentes de correção
        pending_results = test_session_query.filter(
            TestSession.status.in_(['completed', 'submitted', 'corrected']),
            TestSession.submitted_at.isnot(None)
        ).count()
        
        # Total de avaliações no sistema
        total_evaluations = test_query.count()
        
        # Média de pontuação das avaliações finalizadas
        avg_score_result = db.session.query(func.avg(TestSession.score)).filter(
            TestSession.id.in_(test_session_query.with_entities(TestSession.id)),
            TestSession.status.in_(['finalized', 'reviewed']),
            TestSession.score.isnot(None)
        ).scalar()
        average_score = round(avg_score_result or 0, 1)
        
        # Total de estudantes que participaram
        total_students = test_session_query.filter(
            TestSession.submitted_at.isnot(None)
        ).distinct(TestSession.student_id).count()
        
        # Tempo médio de conclusão (em minutos)
        # Como time_spent não existe no modelo, calcular baseado em submitted_at - started_at
        sessions_with_time = test_session_query.filter(
            TestSession.submitted_at.isnot(None),
            TestSession.started_at.isnot(None)
        ).all()
        
        if sessions_with_time:
            total_minutes = sum([
                (session.submitted_at - session.started_at).total_seconds() / 60
                for session in sessions_with_time
            ])
            average_completion_time = round(total_minutes / len(sessions_with_time), 0)
        else:
            average_completion_time = 0
        
        # Disciplina com melhor desempenho
        subject_performance = db.session.query(
            Test.subject,
            func.avg(TestSession.score).label('avg_score')
        ).join(
            TestSession, Test.id == TestSession.test_id
        ).filter(
            TestSession.id.in_(test_session_query.with_entities(TestSession.id)),
            TestSession.status.in_(['finalized', 'reviewed']),
            TestSession.score.isnot(None),
            Test.subject.isnot(None)
        ).group_by(Test.subject).order_by(
            func.avg(TestSession.score).desc()
        ).first()
        
        top_performance_subject = 'Não disponível'
        if subject_performance:
            subject = Subject.query.get(subject_performance[0])
            top_performance_subject = subject.name if subject else 'Não disponível'
        
        return jsonify({
            "completed_evaluations": completed_evaluations,
            "pending_results": pending_results,
            "total_evaluations": total_evaluations,
            "average_score": average_score,
            "total_students": total_students,
            "average_completion_time": int(average_completion_time),
            "top_performance_subject": top_performance_subject
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar estatísticas de resultados: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao buscar estatísticas de resultados",
            "details": str(e)
        }), 500


@bp.route('/evaluation-results/list', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_evaluation_results_list():
    """
    Retorna lista de avaliações com seus resultados agregados
    
    Returns:
        Lista de avaliações com estatísticas de desempenho
    """
    try:
        from app.models.test import Test
        from app.models.testSession import TestSession
        from app.models.subject import Subject
        from app.models.grades import Grade
        from sqlalchemy import func
        from sqlalchemy.orm import joinedload
        
        # Buscar avaliações que têm sessões enviadas
        evaluations_with_sessions = db.session.query(
            Test.id,
            Test.title,
            Test.created_at,
            Test.subject,
            Test.grade_id,
            func.count(TestSession.id).label('total_students'),
            func.count(TestSession.id).filter(
                TestSession.status.in_(['finalized', 'reviewed'])
            ).label('completed_students'),
            func.avg(TestSession.score).filter(
                TestSession.status.in_(['finalized', 'reviewed'])
            ).label('average_score'),
            func.max(TestSession.corrected_at).label('last_updated')
        ).outerjoin(
            TestSession, Test.id == TestSession.test_id
        ).filter(
            TestSession.submitted_at.isnot(None)
        ).group_by(
            Test.id, Test.title, Test.created_at, Test.subject, Test.grade_id
        ).all()
        
        result = []
        for eval_data in evaluations_with_sessions:
            # Buscar nome da disciplina
            subject_name = 'Sem disciplina'
            if eval_data.subject:
                subject = Subject.query.get(eval_data.subject)
                subject_name = subject.name if subject else 'Sem disciplina'
            
            # Buscar nome da série
            grade_name = 'Sem série'
            if eval_data.grade_id:
                grade = Grade.query.get(eval_data.grade_id)
                grade_name = grade.name if grade else 'Sem série'
            
            # Determinar status baseado no progresso
            completed_students = eval_data.completed_students or 0
            total_students = eval_data.total_students or 0
            
            if completed_students == total_students and total_students > 0:
                status = 'completed'
            elif completed_students > 0:
                status = 'correcting'
            else:
                status = 'pending'
            
            evaluation_result = {
                "id": eval_data.id,
                "title": eval_data.title,
                "subject_name": subject_name,
                "grade_name": grade_name,
                "total_students": total_students,
                "completed_students": completed_students,
                "average_score": round(eval_data.average_score or 0, 1),
                "status": status,
                "created_at": eval_data.created_at.isoformat() if eval_data.created_at else None,
                "last_updated": eval_data.last_updated.isoformat() if eval_data.last_updated else eval_data.created_at.isoformat() if eval_data.created_at else None
            }
            result.append(evaluation_result)
        
        # Ordenar por última atualização (mais recentes primeiro)
        result.sort(key=lambda x: x['last_updated'] or '', reverse=True)
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar lista de resultados: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao buscar lista de resultados",
            "details": str(e)
        }), 500


@bp.route('/evaluation-results/<string:evaluation_id>/export', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def export_evaluation_results(evaluation_id):
    """
    Exporta resultados de uma avaliação específica
    """
    try:
        # Por enquanto retorna um JSON com os dados
        # Futuramente pode ser implementado para gerar Excel/PDF
        from app.models.test import Test
        from app.models.testSession import TestSession
        
        evaluation = Test.query.get(evaluation_id)
        if not evaluation:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        sessions = TestSession.query.filter_by(test_id=evaluation_id).filter(
            TestSession.submitted_at.isnot(None)
        ).all()
        
        export_data = {
            "evaluation": {
                "id": evaluation.id,
                "title": evaluation.title,
                "created_at": evaluation.created_at.isoformat() if evaluation.created_at else None
            },
            "sessions": [
                {
                    "student_name": session.student.name if session.student else 'N/A',
                    "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
                    "score": session.score,
                    "grade": session.grade,
                    "status": session.status
                }
                for session in sessions
            ]
        }
        
        return jsonify(export_data), 200
        
    except Exception as e:
        logging.error(f"Erro ao exportar resultados: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao exportar resultados",
            "details": str(e)
        }), 500


@bp.route('/evaluation-results/export-all', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def export_all_results():
    """
    Exporta todos os resultados de avaliações
    """
    try:
        # Por enquanto retorna um JSON com todos os dados
        # Futuramente pode ser implementado para gerar Excel/PDF
        from app.models.testSession import TestSession
        
        sessions = TestSession.query.filter(
            TestSession.submitted_at.isnot(None)
        ).all()
        
        export_data = {
            "export_date": datetime.now().isoformat(),
            "total_sessions": len(sessions),
            "sessions": [
                {
                    "evaluation_title": session.test.title if session.test else 'N/A',
                    "student_name": session.student.name if session.student else 'N/A',
                    "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
                    "score": session.score,
                    "grade": session.grade,
                    "status": session.status
                }
                for session in sessions
            ]
        }
        
        return jsonify(export_data), 200
        
    except Exception as e:
        logging.error(f"Erro ao exportar todos os resultados: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao exportar todos os resultados",
            "details": str(e)
        }), 500


@bp.route('/scheduler/status', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm")
def get_scheduler_status():
    """
    Retorna o status do scheduler de tarefas agendadas
    Útil para verificar se o cronjob está funcionando
    
    Returns:
        {
            "running": true/false,
            "jobs": [
                {
                    "id": "check_expired_evaluations",
                    "name": "Verificar avaliações expiradas",
                    "next_run_time": "2024-01-01T10:05:00"
                }
            ]
        }
    """
    try:
        from app.services.scheduled_tasks import get_scheduler_status
        
        status = get_scheduler_status()
        return jsonify({
            "message": "Status do scheduler obtido com sucesso",
            "scheduler": status
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter status do scheduler: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao obter status do scheduler",
            "details": str(e)
        }), 500


@bp.route('/scheduler/check-expired', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm")
def manual_check_expired():
    """
    Executa manualmente a verificação de avaliações expiradas
    Útil para testes ou execução manual
    
    Returns:
        {
            "message": "Verificação executada com sucesso",
            "updated_count": 5,
            "expired_sessions_count": 10
        }
    """
    try:
        from app.services.scheduled_tasks import check_expired_evaluations
        
        # Executar verificação
        check_expired_evaluations()
        
        return jsonify({
            "message": "Verificação de avaliações expiradas executada com sucesso"
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao executar verificação manual: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Erro ao executar verificação",
            "details": str(e)
        }), 500