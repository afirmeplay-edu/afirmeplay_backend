# -*- coding: utf-8 -*-
"""
Rotas para o sistema de competições
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.decorators.role_required import role_required, get_current_user_from_token
from app.competicoes.models import Competition, CompetitionEnrollment, CompetitionResult
from app.models.testSession import TestSession
from app.models.studentAnswer import StudentAnswer
from app.models.student import Student
from app.models.question import Question
from app.models.testQuestion import TestQuestion
from app.models.classTest import ClassTest
from app.models.skill import Skill
from app.models.subject import Subject
from app.models.studentClass import Class
from app.models.school import School
from app.models.manager import Manager
from app.models.teacher import Teacher
from app.models.teacherClass import TeacherClass
from app.models.schoolTeacher import SchoolTeacher
from app.services.evaluation_result_service import EvaluationResultService
from app.services.evaluation_calculator import EvaluationCalculator
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload
from sqlalchemy import desc, cast, or_
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
import logging
from typing import Dict, Any, List, Optional

bp = Blueprint('competitions', __name__, url_prefix='/competitions')

# Error handlers seguindo padrão do app
@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"erro": "Erro no banco de dados", "detalhes": str(error)}), 500

@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error(f"Integrity error: {str(error)}")
    return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(error)}), 400

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"erro": "Erro interno do servidor", "detalhes": str(error)}), 500


# ==================== CRUD DE COMPETIÇÕES ====================

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def criar_competicao():
    """Cria uma nova competição"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Campos obrigatórios
        required_fields = ['title']
        for field in required_fields:
            if field not in data:
                return jsonify({"erro": f"Campo obrigatório ausente: {field}"}), 400
        
        # Criar competição
        competition = Competition(
            title=data.get('title'),
            description=data.get('description'),
            instrucoes=data.get('instrucoes'),
            recompensas=data.get('recompensas'),  # {ouro: 100, prata: 50, bronze: 25, participacao: 10}
            modo_selecao=data.get('modo_selecao', 'manual'),
            icone=data.get('icone'),
            cor=data.get('cor'),
            dificuldade=data.get('dificuldade'),  # ['facil', 'medio', 'dificil']
            type=data.get('type'),
            max_score=data.get('max_score'),
            time_limit=datetime.fromisoformat(data.get('time_limit')) if data.get('time_limit') else None,
            end_time=datetime.fromisoformat(data.get('end_time')) if data.get('end_time') else None,
            duration=data.get('duration'),
            evaluation_mode=data.get('evaluation_mode', 'virtual'),
            created_by=user['id'],
            subject=data.get('subject'),
            grade_id=data.get('grade') or data.get('grade_id'),
            municipalities=data.get('municipalities'),
            schools=data.get('schools'),
            classes=data.get('classes'),
            course=data.get('course'),
            model=data.get('model'),
            subjects_info=data.get('subjects_info'),
            status=data.get('status', 'agendada'),
            max_participantes=data.get('max_participantes')
        )
        
        db.session.add(competition)
        db.session.flush()
        
        # Adicionar questões se fornecidas (reutiliza TestQuestion)
        if 'questions' in data and isinstance(data['questions'], list):
            for index, question_id in enumerate(data['questions']):
                test_question = TestQuestion(
                    test_id=competition.id,
                    question_id=question_id if isinstance(question_id, str) else question_id.get('id'),
                    order=index + 1
                )
                db.session.add(test_question)
        
        # Adicionar turmas se fornecidas (reutiliza ClassTest)
        if 'classes' in data and isinstance(data['classes'], list):
            for class_id in data['classes']:
                class_test = ClassTest(
                    class_id=class_id if isinstance(class_id, str) else class_id.get('id'),
                    test_id=competition.id,
                    status='agendada',
                    application=data.get('time_limit', ''),
                    expiration=data.get('end_time', '')
                )
                db.session.add(class_test)
        
        db.session.commit()
        
        return jsonify({
            "mensagem": "Competição criada com sucesso",
            "data": {
                "id": competition.id,
                "title": competition.title
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar competição: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao criar competição", "detalhes": str(e)}), 500


@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "student", "aluno")
def listar_competicoes():
    """Lista competições com filtros"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Filtros
        status = request.args.get('status')
        subject_id = request.args.get('subject_id')
        school_id = request.args.get('school_id')
        
        query = Competition.query
        
        # Aplicar filtros
        if status:
            query = query.filter(Competition.status == status)
        if subject_id:
            query = query.filter(Competition.subject == subject_id)
        
        # Filtros de permissão por role
        if user['role'] == 'tecadm':
            city_id = user.get('tenant_id') or user.get('city_id')
            if city_id:
                # Filtrar por escolas da cidade usando operador PostgreSQL @>
                school_ids = [s.id for s in School.query.filter_by(city_id=city_id).all()]
                if school_ids:
                    filters = []
                    for school_id in school_ids:
                        filters.append(cast(Competition.schools, JSONB).op('@>')([school_id]))
                    if filters:
                        query = query.filter(or_(*filters))
        elif user['role'] in ['diretor', 'coordenador']:
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if manager and manager.school_id:
                query = query.filter(cast(Competition.schools, JSONB).op('@>')([manager.school_id]))
        elif user['role'] == 'professor':
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                school_ids = [ts.school_id for ts in teacher_schools]
                if school_ids:
                    filters = []
                    for school_id in school_ids:
                        filters.append(cast(Competition.schools, JSONB).op('@>')([school_id]))
                    if filters:
                        query = query.filter(or_(*filters))
        elif user['role'] in ['student', 'aluno']:
            student = Student.query.filter_by(user_id=user['id']).first()
            if student and student.class_id:
                # Filtrar por competições que têm a turma do aluno
                class_test_ids = [ct.test_id for ct in ClassTest.query.filter_by(class_id=student.class_id).all()]
                if class_test_ids:
                    query = query.filter(Competition.id.in_(class_test_ids))
                else:
                    query = query.filter(False)  # Não tem acesso
        
        competitions = query.all()
        
        result = []
        for comp in competitions:
            result.append({
                "id": comp.id,
                "title": comp.title,
                "description": comp.description,
                "status": comp.status,
                "participantes_atual": comp.participantes_atual,
                "max_participantes": comp.max_participantes,
                "time_limit": comp.time_limit.isoformat() if comp.time_limit else None,
                "end_time": comp.end_time.isoformat() if comp.end_time else None,
                "recompensas": comp.recompensas,
                "icone": comp.icone,
                "cor": comp.cor
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar competições: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao listar competições", "detalhes": str(e)}), 500


@bp.route('/<string:competition_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "student", "aluno")
def obter_competicao(competition_id):
    """Obtém detalhes de uma competição"""
    try:
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"erro": "Competição não encontrada"}), 404
        
        # Buscar questões (usando query direta pois relacionamento é viewonly)
        questions = []
        test_questions = TestQuestion.query.filter_by(test_id=competition.id).order_by(TestQuestion.order).all()
        for tq in test_questions:
            if tq.question:
                questions.append({
                    "id": tq.question.id,
                    "number": tq.order,
                    "text": tq.question.text
                })
        
        return jsonify({
            "id": competition.id,
            "title": competition.title,
            "description": competition.description,
            "instrucoes": competition.instrucoes,
            "status": competition.status,
            "recompensas": competition.recompensas,
            "modo_selecao": competition.modo_selecao,
            "icone": competition.icone,
            "cor": competition.cor,
            "dificuldade": competition.dificuldade,
            "participantes_atual": competition.participantes_atual,
            "max_participantes": competition.max_participantes,
            "time_limit": competition.time_limit.isoformat() if competition.time_limit else None,
            "end_time": competition.end_time.isoformat() if competition.end_time else None,
            "duration": competition.duration,
            "questions": questions
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter competição: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao obter competição", "detalhes": str(e)}), 500


@bp.route('/<string:competition_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def atualizar_competicao(competition_id):
    """Atualiza uma competição"""
    try:
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"erro": "Competição não encontrada"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        # Atualizar campos permitidos
        if 'title' in data:
            competition.title = data['title']
        if 'description' in data:
            competition.description = data['description']
        if 'instrucoes' in data:
            competition.instrucoes = data['instrucoes']
        if 'recompensas' in data:
            competition.recompensas = data['recompensas']
        if 'status' in data:
            competition.status = data['status']
        if 'time_limit' in data:
            competition.time_limit = datetime.fromisoformat(data['time_limit']) if data['time_limit'] else None
        if 'end_time' in data:
            competition.end_time = datetime.fromisoformat(data['end_time']) if data['end_time'] else None
        
        db.session.commit()
        
        return jsonify({
            "mensagem": "Competição atualizada com sucesso",
            "data": {"id": competition.id}
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao atualizar competição: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao atualizar competição", "detalhes": str(e)}), 500


@bp.route('/<string:competition_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def excluir_competicao(competition_id):
    """Exclui uma competição"""
    try:
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"erro": "Competição não encontrada"}), 404
        
        db.session.delete(competition)
        db.session.commit()
        
        return jsonify({"mensagem": "Competição excluída com sucesso"}), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao excluir competição: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao excluir competição", "detalhes": str(e)}), 500


# ==================== INSCRIÇÃO ====================

@bp.route('/available', methods=['GET'])
@jwt_required()
@role_required("student", "aluno", "admin", "professor")
def listar_competicoes_disponiveis():
    """Lista competições disponíveis para o aluno se inscrever"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"erro": "Dados do aluno não encontrados"}), 404
        
        # Buscar competições onde o aluno pode se inscrever
        # Status 'aberta' ou 'em_andamento'
        # Não excedeu max_participantes
        # Aluno pertence a uma das turmas selecionadas
        now = datetime.utcnow()
        
        query = Competition.query.filter(
            Competition.status.in_(['aberta', 'em_andamento'])
        )
        
        # Filtrar por data de início (se time_limit existe, deve ter passado)
        query = query.filter(
            or_(
                Competition.time_limit.is_(None),
                Competition.time_limit <= now
            )
        )
        
        # Filtrar por data de término (se end_time existe, não deve ter passado)
        query = query.filter(
            or_(
                Competition.end_time.is_(None),
                Competition.end_time >= now
            )
        )
        
        # Filtrar por turmas do aluno
        class_tests = ClassTest.query.filter_by(class_id=student.class_id).all()
        competition_ids = [ct.test_id for ct in class_tests]
        query = query.filter(Competition.id.in_(competition_ids))
        
        # Filtrar por limite de participantes
        query = query.filter(
            db.or_(
                Competition.max_participantes.is_(None),
                Competition.participantes_atual < Competition.max_participantes
            )
        )
        
        competitions = query.all()
        
        result = []
        for comp in competitions:
            # Verificar se já está inscrito
            enrollment = CompetitionEnrollment.query.filter_by(
                competition_id=comp.id,
                student_id=student.id
            ).first()
            
            result.append({
                "id": comp.id,
                "title": comp.title,
                "description": comp.description,
                "status": comp.status,
                "participantes_atual": comp.participantes_atual,
                "max_participantes": comp.max_participantes,
                "time_limit": comp.time_limit.isoformat() if comp.time_limit else None,
                "end_time": comp.end_time.isoformat() if comp.end_time else None,
                "recompensas": comp.recompensas,
                "inscrito": enrollment is not None,
                "enrollment_status": enrollment.status if enrollment else None
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar competições disponíveis: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao listar competições disponíveis", "detalhes": str(e)}), 500


@bp.route('/<string:competition_id>/enroll', methods=['POST'])
@jwt_required()
@role_required("student", "aluno", "admin", "professor")
def inscrever_em_competicao(competition_id):
    """Inscreve o aluno em uma competição"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"erro": "Dados do aluno não encontrados"}), 404
        
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"erro": "Competição não encontrada"}), 404
        
        # Verificar se pode se inscrever
        if competition.status not in ['aberta', 'em_andamento']:
            return jsonify({"erro": "Competição não está aberta para inscrições"}), 400
        
        if competition.max_participantes and competition.participantes_atual >= competition.max_participantes:
            return jsonify({"erro": "Competição atingiu o limite de participantes"}), 400
        
        # Verificar se aluno pertence a uma das turmas
        class_test = ClassTest.query.filter_by(
            test_id=competition_id,
            class_id=student.class_id
        ).first()
        if not class_test:
            return jsonify({"erro": "Você não pertence a uma turma elegível para esta competição"}), 403
        
        # Verificar se já está inscrito
        existing_enrollment = CompetitionEnrollment.query.filter_by(
            competition_id=competition_id,
            student_id=student.id
        ).first()
        
        if existing_enrollment:
            return jsonify({
                "mensagem": "Aluno já está inscrito",
                "data": {"enrollment_id": existing_enrollment.id}
            }), 200
        
        # Criar inscrição
        enrollment = CompetitionEnrollment(
            competition_id=competition_id,
            student_id=student.id,
            status='inscrito'
        )
        
        db.session.add(enrollment)
        
        # Incrementar participantes_atual
        competition.participantes_atual = (competition.participantes_atual or 0) + 1
        
        db.session.commit()
        
        return jsonify({
            "mensagem": "Inscrição realizada com sucesso",
            "data": {"enrollment_id": enrollment.id}
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "Aluno já está inscrito nesta competição"}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao inscrever em competição: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao inscrever em competição", "detalhes": str(e)}), 500


@bp.route('/<string:competition_id>/enrollment-status', methods=['GET'])
@jwt_required()
@role_required("student", "aluno", "admin", "professor")
def obter_status_inscricao(competition_id):
    """Obtém o status da inscrição do aluno"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"erro": "Dados do aluno não encontrados"}), 404
        
        enrollment = CompetitionEnrollment.query.filter_by(
            competition_id=competition_id,
            student_id=student.id
        ).first()
        
        if not enrollment:
            return jsonify({
                "inscrito": False,
                "status": None
            }), 200
        
        return jsonify({
            "inscrito": True,
            "status": enrollment.status,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter status de inscrição: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao obter status de inscrição", "detalhes": str(e)}), 500


# ==================== EXECUÇÃO ====================

@bp.route('/<string:competition_id>/can-start', methods=['GET'])
@jwt_required()
@role_required("student", "aluno", "admin", "professor")
def pode_iniciar_competicao(competition_id):
    """Verifica se o aluno pode iniciar a competição"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"erro": "Dados do aluno não encontrados"}), 404
        
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"erro": "Competição não encontrada"}), 404
        
        # Verificar se está inscrito
        enrollment = CompetitionEnrollment.query.filter_by(
            competition_id=competition_id,
            student_id=student.id
        ).first()
        
        if not enrollment:
            return jsonify({
                "pode_iniciar": False,
                "motivo": "Aluno não está inscrito na competição"
            }), 200
        
        # Verificar se já iniciou/finalizou
        if enrollment.status == 'finalizado':
            return jsonify({
                "pode_iniciar": False,
                "motivo": "Competição já foi finalizada"
            }), 200
        
        # Verificar data de início
        now = datetime.utcnow()
        if competition.time_limit and now < competition.time_limit:
            return jsonify({
                "pode_iniciar": False,
                "motivo": "Competição ainda não iniciou"
            }), 200
        
        # Verificar se não expirou
        if competition.end_time and now > competition.end_time:
            return jsonify({
                "pode_iniciar": False,
                "motivo": "Competição já expirou"
            }), 200
        
        return jsonify({
            "pode_iniciar": True
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao verificar se pode iniciar: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao verificar se pode iniciar", "detalhes": str(e)}), 500


@bp.route('/<string:competition_id>/start', methods=['POST'])
@jwt_required()
@role_required("student", "aluno", "admin", "professor")
def iniciar_competicao(competition_id):
    """Inicia a competição para o aluno (cria TestSession)"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"erro": "Dados do aluno não encontrados"}), 404
        
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"erro": "Competição não encontrada"}), 404
        
        # Verificar se está inscrito
        enrollment = CompetitionEnrollment.query.filter_by(
            competition_id=competition_id,
            student_id=student.id
        ).first()
        
        if not enrollment:
            return jsonify({"erro": "Aluno não está inscrito na competição"}), 400
        
        # Verificar se já tem sessão ativa
        existing_session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=competition_id,
            status='em_andamento'
        ).first()
        
        if existing_session:
            return jsonify({
                "mensagem": "Sessão já iniciada",
                "data": {
                    "session_id": existing_session.id,
                    "started_at": existing_session.started_at.isoformat() if existing_session.started_at else None
                }
            }), 200
        
        # Criar TestSession (reutiliza modelo existente)
        session = TestSession(
            student_id=student.id,
            test_id=competition_id,
            time_limit_minutes=competition.duration,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        session.start_session()
        
        # Atualizar status da inscrição
        enrollment.status = 'iniciado'
        
        db.session.add(session)
        db.session.commit()
        
        # Buscar questões (embaralhadas se necessário)
        questions = []
        test_questions = TestQuestion.query.filter_by(test_id=competition_id).order_by(TestQuestion.order).all()
        
        for tq in test_questions:
            question = tq.question
            questions.append({
                "id": question.id,
                "number": tq.order,
                "text": question.text,
                "formatted_text": question.formatted_text,
                "alternatives": question.alternatives,
                "question_type": question.question_type,
                "images": question.images
            })
        
        return jsonify({
            "mensagem": "Competição iniciada com sucesso",
            "data": {
                "session_id": session.id,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "time_limit_minutes": session.time_limit_minutes,
                "questions": questions
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao iniciar competição: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao iniciar competição", "detalhes": str(e)}), 500


@bp.route('/submit', methods=['POST'])
@jwt_required()
@role_required("student", "aluno", "admin", "professor")
def submeter_competicao():
    """Submete as respostas da competição"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({"erro": "session_id é obrigatório"}), 400
        
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({"erro": "Sessão não encontrada"}), 404
        
        competition = Competition.query.get(session.test_id)
        if not competition:
            return jsonify({"erro": "Competição não encontrada"}), 404
        
        # Salvar respostas (reutiliza StudentAnswer)
        answers = data.get('answers', [])
        for ans_data in answers:
            question_id = ans_data.get('question_id')
            answer = ans_data.get('answer')
            
            if not question_id or answer is None:
                continue
            
            existing_answer = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id,
                question_id=question_id
            ).first()
            
            if existing_answer:
                existing_answer.answer = str(answer)
                existing_answer.answered_at = datetime.utcnow()
            else:
                student_answer = StudentAnswer(
                    student_id=session.student_id,
                    test_id=session.test_id,
                    question_id=question_id,
                    answer=str(answer)
                )
                db.session.add(student_answer)
        
        # Calcular resultados usando EvaluationResultService
        from app.models.testQuestion import TestQuestion
        test_questions = TestQuestion.query.filter_by(test_id=competition.id).all()
        questions = [tq.question for tq in test_questions]
        
        student_answers = StudentAnswer.query.filter_by(
            student_id=session.student_id,
            test_id=competition.id
        ).all()
        
        # Calcular resultado
        result = EvaluationResultService.calculate_and_save_result(
            test_id=competition.id,
            student_id=session.student_id,
            session_id=session_id,
            questions=questions,
            answers=student_answers
        )
        
        # Criar CompetitionResult
        competition_result = CompetitionResult(
            competition_id=competition.id,
            student_id=session.student_id,
            session_id=session_id,
            correct_answers=result['correct_answers'],
            total_questions=result['total_questions'],
            score_percentage=result['score_percentage'],
            grade=result['grade'],
            proficiency=result['proficiency'],
            classification=result['classification'],
            acertos=result['correct_answers'],
            erros=result['total_questions'] - result['correct_answers'],
            em_branco=0  # Será calculado depois
        )
        
        # Calcular tempo gasto
        if session.started_at:
            tempo_gasto = (datetime.utcnow() - session.started_at).total_seconds()
            competition_result.tempo_gasto = int(tempo_gasto)
        
        db.session.add(competition_result)
        
        # Finalizar sessão
        session.finalize_session(
            correct_answers=result['correct_answers'],
            total_questions=result['total_questions']
        )
        
        # Atualizar status da inscrição
        enrollment = CompetitionEnrollment.query.filter_by(
            competition_id=competition.id,
            student_id=session.student_id
        ).first()
        if enrollment:
            enrollment.status = 'finalizado'
        
        db.session.commit()
        
        # Calcular ranking e posição (será feito depois quando todos submeterem)
        # Por enquanto, retornar resultado sem posição
        
        return jsonify({
            "mensagem": "Competição submetida com sucesso",
            "data": {
                "result_id": competition_result.id,
                "grade": competition_result.grade,
                "proficiency": competition_result.proficiency,
                "classification": competition_result.classification,
                "correct_answers": competition_result.correct_answers,
                "total_questions": competition_result.total_questions
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao submeter competição: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao submeter competição", "detalhes": str(e)}), 500


# ==================== RESULTADOS ====================

def _calcular_moedas_ganhas(posicao: int, recompensas: Dict) -> int:
    """Calcula moedas ganhas baseado na posição"""
    if not recompensas:
        return 0
    
    participacao = recompensas.get('participacao', 0)
    
    if posicao == 1:
        return recompensas.get('ouro', 0) + participacao
    elif posicao == 2:
        return recompensas.get('prata', 0) + participacao
    elif posicao == 3:
        return recompensas.get('bronze', 0) + participacao
    else:
        return participacao


def _gerar_tabela_detalhada_competicao(competition_id: str) -> Dict[str, Any]:
    """
    Gera tabela detalhada de resultados da competição
    Baseado em _gerar_tabela_detalhada_por_disciplina, adaptado para competições
    """
    try:
        competition = Competition.query.get(competition_id)
        if not competition:
            return {"disciplinas": [], "geral": {"alunos": []}}
        
        # Buscar questões da competição
        questoes_por_disciplina = {}
        test_questions = TestQuestion.query.filter_by(
            test_id=competition_id
        ).join(Question).options(
            joinedload(TestQuestion.question).joinedload(Question.subject)
        ).order_by(TestQuestion.order).all()
        
        # Buscar habilidades
        skill_ids = set()
        for test_question in test_questions:
            if test_question.question.skill:
                clean_skill_id = test_question.question.skill.replace('{', '').replace('}', '')
                skill_ids.add(clean_skill_id)
        
        skills_dict = {}
        if skill_ids:
            skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
            skills_dict = {str(skill.id): skill for skill in skills}
        
        for test_question in test_questions:
            question = test_question.question
            subject_id = str(question.subject_id) if question.subject_id else 'sem_disciplina'
            subject_name = question.subject.name if question.subject else 'Sem Disciplina'
            
            skill_code = "N/A"
            skill_description = "N/A"
            if question.skill:
                clean_skill_id = question.skill.replace('{', '').replace('}', '')
                skill_obj = skills_dict.get(clean_skill_id)
                if skill_obj:
                    skill_code = skill_obj.code
                    skill_description = skill_obj.description
                else:
                    skill_code = clean_skill_id
                    skill_description = "Habilidade não encontrada"
            
            if subject_id not in questoes_por_disciplina:
                questoes_por_disciplina[subject_id] = {
                    "id": subject_id,
                    "nome": subject_name,
                    "questoes": [],
                    "alunos": []
                }
            
            questoes_por_disciplina[subject_id]["questoes"].append({
                "numero": test_question.order or 1,
                "habilidade": skill_description,
                "codigo_habilidade": skill_code,
                "question_id": question.id
            })
        
        # Buscar todos os alunos inscritos
        enrollments = CompetitionEnrollment.query.filter_by(
            competition_id=competition_id
        ).all()
        
        student_ids = [e.student_id for e in enrollments]
        if not student_ids:
            return {"disciplinas": list(questoes_por_disciplina.values()), "geral": {"alunos": []}}
        
        all_students = Student.query.filter(Student.id.in_(student_ids)).all()
        
        # Buscar resultados
        competition_results = CompetitionResult.query.filter_by(
            competition_id=competition_id
        ).all()
        results_dict = {cr.student_id: cr for cr in competition_results}
        
        # Buscar respostas
        all_student_answers = StudentAnswer.query.filter(
            StudentAnswer.test_id == competition_id,
            StudentAnswer.student_id.in_(student_ids)
        ).all()
        
        respostas_por_aluno = {}
        for resposta in all_student_answers:
            if resposta.student_id not in respostas_por_aluno:
                respostas_por_aluno[resposta.student_id] = {}
            respostas_por_aluno[resposta.student_id][resposta.question_id] = resposta
        
        # Processar cada disciplina
        for subject_id, disciplina_data in questoes_por_disciplina.items():
            alunos_disciplina = []
            
            for student in all_students:
                turma_nome = "N/A"
                serie_nome = "N/A"
                escola_nome = "N/A"
                
                if student.class_:
                    turma_nome = student.class_.name or "N/A"
                    if student.class_.grade:
                        serie_nome = student.class_.grade.name or "N/A"
                    if student.class_.school:
                        escola_nome = student.class_.school.name or "N/A"
                
                competition_result = results_dict.get(student.id)
                
                respostas_por_questao = []
                total_acertos = 0
                total_erros = 0
                total_respondidas = 0
                
                for questao_info in disciplina_data["questoes"]:
                    question_id = questao_info["question_id"]
                    question = Question.query.get(question_id)
                    
                    if question:
                        resposta_aluno = respostas_por_aluno.get(student.id, {}).get(question.id)
                        
                        if resposta_aluno:
                            total_respondidas += 1
                            
                            acertou = False
                            if question.question_type == 'multiple_choice':
                                acertou = EvaluationResultService.check_multiple_choice_answer(
                                    resposta_aluno.answer, question.correct_answer
                                )
                            else:
                                acertou = str(resposta_aluno.answer).strip().lower() == str(question.correct_answer).strip().lower()
                            
                            if acertou:
                                total_acertos += 1
                            else:
                                total_erros += 1
                            
                            respostas_por_questao.append({
                                "questao": questao_info["numero"],
                                "acertou": acertou,
                                "respondeu": True,
                                "resposta": resposta_aluno.answer
                            })
                        else:
                            respostas_por_questao.append({
                                "questao": questao_info["numero"],
                                "acertou": False,
                                "respondeu": False,
                                "resposta": None
                            })
                
                # Calcular nota e proficiência
                disciplina_nota = 0.0
                disciplina_proficiencia = 0.0
                disciplina_classificacao = None
                
                if total_respondidas > 0:
                    course_name = "Anos Iniciais"
                    if competition.course:
                        try:
                            from app.models.educationStage import EducationStage
                            import uuid
                            course_uuid = uuid.UUID(competition.course)
                            course_obj = EducationStage.query.get(course_uuid)
                            if course_obj:
                                course_name = course_obj.name
                        except:
                            pass
                    
                    result = EvaluationCalculator.calculate_complete_evaluation(
                        correct_answers=total_acertos,
                        total_questions=total_respondidas,
                        course_name=course_name,
                        subject_name=disciplina_data['nome']
                    )
                    
                    disciplina_nota = result['grade']
                    disciplina_proficiencia = result['proficiency']
                    disciplina_classificacao = result['classification']
                
                # Buscar resultado da competição para obter posição e moedas
                posicao = None
                moedas_ganhas = 0
                tempo_gasto = None
                
                if competition_result:
                    posicao = competition_result.posicao
                    moedas_ganhas = competition_result.moedas_ganhas
                    tempo_gasto = competition_result.tempo_gasto
                
                status = "concluida" if total_respondidas > 0 else "pendente"
                
                aluno_disciplina = {
                    "id": student.id,
                    "nome": student.name,
                    "escola": escola_nome,
                    "serie": serie_nome,
                    "turma": turma_nome,
                    "respostas_por_questao": respostas_por_questao,
                    "total_acertos": total_acertos,
                    "total_erros": total_erros,
                    "total_respondidas": total_respondidas,
                    "total_questoes_disciplina": len(disciplina_data["questoes"]),
                    "total_em_branco": len(disciplina_data["questoes"]) - total_respondidas,
                    "nivel_proficiencia": disciplina_classificacao,
                    "nota": disciplina_nota,
                    "proficiencia": disciplina_proficiencia,
                    "status": status,
                    "percentual_acertos": round((total_acertos / total_respondidas * 100), 2) if total_respondidas > 0 else 0.0,
                    "posicao": posicao,
                    "moedas_ganhas": moedas_ganhas,
                    "tempo_gasto": tempo_gasto
                }
                
                alunos_disciplina.append(aluno_disciplina)
            
            disciplina_data["alunos"] = alunos_disciplina
        
        # Calcular dados gerais (similar a _calcular_dados_gerais_alunos)
        course_name = "Anos Iniciais"
        if competition.course:
            try:
                from app.models.educationStage import EducationStage
                import uuid
                course_uuid = uuid.UUID(competition.course)
                course_obj = EducationStage.query.get(course_uuid)
                if course_obj:
                    course_name = course_obj.name
            except:
                pass
        
        dados_gerais = _calcular_dados_gerais_competicao(questoes_por_disciplina, course_name, competition_id)
        
        return {
            "disciplinas": list(questoes_por_disciplina.values()),
            "geral": dados_gerais
        }
        
    except Exception as e:
        logging.error(f"Erro ao gerar tabela detalhada de competição: {str(e)}", exc_info=True)
        return {"disciplinas": [], "geral": {"alunos": []}, "erro": str(e)}


def _calcular_dados_gerais_competicao(questoes_por_disciplina: dict, course_name: str, competition_id: str) -> dict:
    """Calcula dados gerais (média) para cada aluno na competição"""
    try:
        dados_alunos = {}
        
        for disciplina_id, disciplina_data in questoes_por_disciplina.items():
            for aluno_data in disciplina_data.get("alunos", []):
                aluno_id = aluno_data["id"]
                
                if aluno_id not in dados_alunos:
                    dados_alunos[aluno_id] = {
                        "id": aluno_id,
                        "nome": aluno_data["nome"],
                        "escola": aluno_data["escola"],
                        "serie": aluno_data["serie"],
                        "turma": aluno_data["turma"],
                        "notas_disciplinas": [],
                        "proficiencias_disciplinas": [],
                        "total_acertos_geral": 0,
                        "total_questoes_geral": 0,
                        "total_respondidas_geral": 0,
                        "posicao": aluno_data.get("posicao"),
                        "moedas_ganhas": aluno_data.get("moedas_ganhas", 0),
                        "tempo_gasto": aluno_data.get("tempo_gasto")
                    }
                
                dados_alunos[aluno_id]["notas_disciplinas"].append(aluno_data["nota"])
                dados_alunos[aluno_id]["proficiencias_disciplinas"].append(aluno_data["proficiencia"])
                dados_alunos[aluno_id]["total_acertos_geral"] += aluno_data["total_acertos"]
                dados_alunos[aluno_id]["total_questoes_geral"] += aluno_data["total_questoes_disciplina"]
                dados_alunos[aluno_id]["total_respondidas_geral"] += aluno_data["total_respondidas"]
        
        alunos_gerais = []
        for aluno_id, dados in dados_alunos.items():
            if dados["notas_disciplinas"]:
                nota_geral = sum(dados["notas_disciplinas"]) / len(dados["notas_disciplinas"])
                proficiencia_geral = sum(dados["proficiencias_disciplinas"]) / len(dados["proficiencias_disciplinas"])
            else:
                nota_geral = 0.0
                proficiencia_geral = 0.0
            
            if dados["total_questoes_geral"] > 0:
                percentual_acertos_geral = (dados["total_acertos_geral"] / dados["total_questoes_geral"]) * 100
            else:
                percentual_acertos_geral = 0.0
            
            # Classificação geral (mesma lógica de avaliações)
            nivel_proficiencia_geral = None
            if dados["notas_disciplinas"] and dados["proficiencias_disciplinas"]:
                proficiencia_media = sum(dados["proficiencias_disciplinas"]) / len(dados["proficiencias_disciplinas"])
                
                if "finais" in course_name.lower() or "médio" in course_name.lower() or "medio" in course_name.lower():
                    if proficiencia_media >= 340:
                        nivel_proficiencia_geral = "Avançado"
                    elif proficiencia_media >= 290:
                        nivel_proficiencia_geral = "Adequado"
                    elif proficiencia_media >= 212.50:
                        nivel_proficiencia_geral = "Básico"
                    else:
                        nivel_proficiencia_geral = "Abaixo do Básico"
                else:
                    if proficiencia_media >= 263:
                        nivel_proficiencia_geral = "Avançado"
                    elif proficiencia_media >= 213:
                        nivel_proficiencia_geral = "Adequado"
                    elif proficiencia_media >= 163:
                        nivel_proficiencia_geral = "Básico"
                    else:
                        nivel_proficiencia_geral = "Abaixo do Básico"
            
            status_geral = "concluida" if dados["total_respondidas_geral"] > 0 else "pendente"
            
            aluno_geral = {
                "id": dados["id"],
                "nome": dados["nome"],
                "escola": dados["escola"],
                "serie": dados["serie"],
                "turma": dados["turma"],
                "nota_geral": round(nota_geral, 2),
                "proficiencia_geral": round(proficiencia_geral, 2),
                "nivel_proficiencia_geral": nivel_proficiencia_geral,
                "total_acertos_geral": dados["total_acertos_geral"],
                "total_questoes_geral": dados["total_questoes_geral"],
                "total_respondidas_geral": dados["total_respondidas_geral"],
                "total_em_branco_geral": dados["total_questoes_geral"] - dados["total_respondidas_geral"],
                "percentual_acertos_geral": round(percentual_acertos_geral, 2),
                "status_geral": status_geral,
                "posicao": dados["posicao"],
                "moedas_ganhas": dados["moedas_ganhas"],
                "tempo_gasto": dados["tempo_gasto"]
            }
            
            alunos_gerais.append(aluno_geral)
        
        # Ordenar por posição (ranking)
        alunos_gerais.sort(key=lambda x: (x["posicao"] is None, x["posicao"] or 0))
        
        return {"alunos": alunos_gerais}
        
    except Exception as e:
        logging.error(f"Erro ao calcular dados gerais da competição: {str(e)}")
        return {"alunos": []}


@bp.route('/<string:competition_id>/results', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_resultados(competition_id):
    """Obtém resultados completos da competição com estrutura detalhada"""
    try:
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"erro": "Competição não encontrada"}), 404
        
        # Calcular rankings e posições se ainda não calculados
        _calcular_rankings_competicao(competition_id)
        
        # Gerar tabela detalhada
        tabela_detalhada = _gerar_tabela_detalhada_competicao(competition_id)
        
        return jsonify(tabela_detalhada), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter resultados: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao obter resultados", "detalhes": str(e)}), 500


def _calcular_rankings_competicao(competition_id: str):
    """Calcula rankings e atualiza posições e moedas"""
    try:
        # Buscar todos os resultados
        results = CompetitionResult.query.filter_by(
            competition_id=competition_id
        ).order_by(
            desc(CompetitionResult.grade),
            CompetitionResult.tempo_gasto.asc()  # Em caso de empate, menor tempo ganha
        ).all()
        
        competition = Competition.query.get(competition_id)
        recompensas = competition.recompensas if competition else {}
        
        # Atualizar posições e moedas
        for index, result in enumerate(results):
            posicao = index + 1
            result.posicao = posicao
            result.moedas_ganhas = _calcular_moedas_ganhas(posicao, recompensas)
        
        db.session.commit()
        
    except Exception as e:
        logging.error(f"Erro ao calcular rankings: {str(e)}", exc_info=True)
        db.session.rollback()


@bp.route('/<string:competition_id>/my-result', methods=['GET'])
@jwt_required()
@role_required("student", "aluno", "admin", "professor")
def obter_meu_resultado(competition_id):
    """Obtém resultado individual do aluno"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"erro": "Dados do aluno não encontrados"}), 404
        
        result = CompetitionResult.query.filter_by(
            competition_id=competition_id,
            student_id=student.id
        ).first()
        
        if not result:
            return jsonify({
                "mensagem": "Resultado não encontrado",
                "data": None
            }), 200
        
        return jsonify({
            "mensagem": "Resultado obtido com sucesso",
            "data": result.to_dict()
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter meu resultado: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao obter meu resultado", "detalhes": str(e)}), 500

