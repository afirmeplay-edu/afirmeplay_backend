# -*- coding: utf-8 -*-
"""
Sistema completo de submissão de respostas de alunos
- Controle de sessões de prova
- Validação de tempo
- Cálculo automático de notas
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app.models.test import Test
from app.models.question import Question
from app.models.student import Student
from app.models.testQuestion import TestQuestion
from app.decorators.role_required import role_required
from datetime import datetime, timedelta
import logging

bp = Blueprint('student_answer', __name__, url_prefix='/student-answers')




@bp.errorhandler(Exception)
def handle_error(error):
    """Tratamento global de erros"""
    logging.error(f"Erro em student_answer_routes: {str(error)}", exc_info=True)
    return jsonify({
        "error": "Erro interno no servidor",
        "details": str(error)
    }), 500


# ==================== CONTROLE DE SESSÕES ====================

@bp.route('/sessions/<session_id>/status', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno", "tecadm")
def get_session_status(session_id):
    """
    Retorna o status atual da sessão
    """
    try:
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Calcular tempo decorrido e restante
        elapsed_minutes = 0
        remaining_minutes = session.time_limit_minutes
        is_expired = False
        
        if session.started_at and session.time_limit_minutes:
            from datetime import datetime
            elapsed_minutes = int((datetime.utcnow() - session.started_at).total_seconds() / 60)
            remaining_minutes = max(0, session.time_limit_minutes - elapsed_minutes)
            is_expired = remaining_minutes <= 0
        elif session.time_limit_minutes is None:
            # Se não há limite de tempo, não está expirada
            is_expired = False
        
        return jsonify({
            'session_id': session.id,
            'status': session.status,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'time_limit_minutes': session.time_limit_minutes,
            'elapsed_minutes': elapsed_minutes,
            'remaining_minutes': remaining_minutes,
            'is_expired': is_expired,
            'total_questions': session.total_questions,
            'correct_answers': session.correct_answers,
            'score': session.score,
            'grade': session.grade
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter status da sessão: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter status", "details": str(e)}), 500


@bp.route('/sessions/<session_id>/end', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno", "tecadm")
def end_test_session(session_id):
    """
    Encerra uma sessão de prova
    
    Body:
    {
        "reason": "finished" // opcional: finished, timeout, manual
    }
    """
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'finished')
        
        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Verificar se a sessão já foi finalizada
        if session.status in ['finalizada', 'expirada']:
            return jsonify({
                'message': f'Sessão já foi {session.status}',
                'session_id': session.id,
                'status': session.status,
                'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
                'duration_minutes': session.duration_minutes,
                'total_questions': session.total_questions,
                'correct_answers': session.correct_answers,
                'score': session.score,
                'grade': session.grade
            }), 200
        
        # Verificar se a sessão está ativa
        if session.status != 'em_andamento':
            return jsonify({
                'error': f'Sessão não está ativa. Status atual: {session.status}'
            }), 400
        
        # Encerrar sessão
        session.submitted_at = datetime.utcnow()
        session.status = 'finalizada'
        
        # Se não há respostas salvas, calcular com 0 acertos
        if session.total_questions is None:
            session.total_questions = 0
        if session.correct_answers is None:
            session.correct_answers = 0
        if session.score is None:
            session.score = 0.0
        
        db.session.commit()
        
        return jsonify({
            'message': 'Sessão encerrada com sucesso',
            'session_id': session.id,
            'status': session.status,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'duration_minutes': session.duration_minutes,
            'total_questions': session.total_questions,
            'correct_answers': session.correct_answers,
            'score': session.score,
            'grade': session.grade
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao encerrar sessão: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao encerrar sessão", "details": str(e)}), 500


@bp.route('/sessions/<session_id>/timer', methods=['PATCH'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def update_session_timer(session_id):
    """
    Atualiza o tempo decorrido e o tempo restante da sessão de prova.
    Body:
    {
        "elapsed_minutes": 10,
        "remaining_minutes": 50
    }
    """
    try:
        data = request.get_json()
        elapsed_minutes = data.get('elapsed_minutes')
        remaining_minutes = data.get('remaining_minutes')
        
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Atualizar campos na sessão
        if elapsed_minutes is not None:
            session.elapsed_minutes = elapsed_minutes
        if remaining_minutes is not None:
            session.remaining_minutes = remaining_minutes
        db.session.commit()
        
        return jsonify({
            'message': 'Tempo da sessão atualizado com sucesso',
            'session_id': session.id,
            'elapsed_minutes': session.elapsed_minutes,
            'remaining_minutes': session.remaining_minutes
        }), 200
    except Exception as e:
        logging.error(f"Erro ao atualizar timer da sessão: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao atualizar timer da sessão", "details": str(e)}), 500


# ==================== SUBMISSÃO DE RESPOSTAS ====================

@bp.route('/submit', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def submit_answers():
    """
    Submete as respostas do aluno com validação de tempo e cálculo automático
    
    Body:
    {
        "session_id": "uuid",
        "answers": [
            {
                "question_id": "uuid",
                "answer": "resposta_do_aluno"
            }
        ]
    }
    """
    try:
        data = request.get_json()
        
        # Validação básica dos dados JSON
        if not data:
            return jsonify({'error': 'Dados JSON são obrigatórios'}), 400
        
        session_id = data.get('session_id')
        answers = data.get('answers')
        
        if not session_id:
            return jsonify({'error': 'session_id é obrigatório'}), 400
        
        # Verificar se answers está presente no JSON (pode ser lista vazia)
        if 'answers' not in data:
            return jsonify({'error': 'Campo answers é obrigatório'}), 400
        
        # Garantir que answers seja uma lista (pode ser vazia)
        if not isinstance(answers, list):
            return jsonify({'error': 'Lista de respostas deve ser um array'}), 400
        
        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Verificar se a avaliação não expirou
        from app.models.classTest import ClassTest
        class_test = ClassTest.query.filter_by(
            test_id=session.test_id
        ).first()
        
        if class_test and class_test.expiration:
            current_time = datetime.utcnow()
            # Garantir que ambas as datas estejam em UTC para comparação
            expiration_utc = class_test.expiration.replace(tzinfo=None) if class_test.expiration.tzinfo else class_test.expiration
            current_utc = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time
            if current_utc > expiration_utc:
                session.status = 'expirada'
                db.session.commit()
                return jsonify({
                    'error': 'Avaliação expirada. Não é possível submeter respostas.'
                }), 410
        
        # Validar se sessão ainda está ativa
        if session.status != 'em_andamento':
            return jsonify({
                'error': f'Sessão não está ativa. Status atual: {session.status}'
            }), 400
        
        # Validar tempo limite (cálculo no frontend, mas validação adicional aqui)
        if session.started_at and session.time_limit_minutes:
            from app.utils.timezone_utils import get_brazil_time
            current_time = get_brazil_time()
            elapsed_minutes = int((current_time - session.started_at).total_seconds() / 60)
            if elapsed_minutes > session.time_limit_minutes:
                session.status = 'expirada'
                db.session.commit()
                return jsonify({
                    'error': 'Tempo limite excedido. Sessão expirada.'
                }), 410  # 410 Gone
        
        # Buscar questões do teste através da tabela de associação
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=session.test_id).order_by(TestQuestion.order).all()]
        test_questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
        questions_dict = {q.id: q for q in test_questions}
        
        correct_count = 0
        saved_answers = []
        
        # Processar cada resposta
        for ans_data in answers:
            question_id = ans_data.get('question_id')
            answer = ans_data.get('answer')
            
            if not question_id or answer is None:
                continue
            
            # Verificar se a questão existe e pertence ao teste
            if question_id not in questions_dict:
                logging.warning(f"Questão {question_id} não encontrada no teste {session.test_id}")
                continue
            
            # Verificar se já existe resposta para esta questão nesta sessão
            existing_answer = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id,
                question_id=question_id
            ).first()
            
            if existing_answer:
                # Atualizar resposta existente
                existing_answer.answer = str(answer)
                existing_answer.answered_at = datetime.utcnow()
                student_answer = existing_answer
            else:
                # Criar nova resposta
                student_answer = StudentAnswer(
                    student_id=session.student_id,
                    test_id=session.test_id,
                    question_id=question_id,
                    answer=str(answer)
                )
                db.session.add(student_answer)
            
            saved_answers.append({
                'question_id': question_id,
                'answer': str(answer),
                'answered_at': student_answer.answered_at.isoformat() if student_answer.answered_at else None
            })
            
            # Verificar se a resposta está correta (correção automática)
            question = questions_dict[question_id]
            if question.question_type == 'multipleChoice':
                # Verificar usando alternatives para questões de múltipla escolha
                from app.services.evaluation_result_service import EvaluationResultService
                is_correct = EvaluationResultService.check_multiple_choice_answer(answer, question.alternatives)
                if is_correct:
                    correct_count += 1
            elif question.correct_answer:
                # Para outros tipos de questão que usam correct_answer
                if str(answer).strip().lower() == str(question.correct_answer).strip().lower():
                    correct_count += 1
        
        # Finalizar sessão e calcular nota
        total_questions = len(test_questions)
        session.finalize_session(
            correct_answers=correct_count,
            total_questions=total_questions
        )
        
        # ✅ NOVO: Calcular resultado completo e salvar
        from app.services.evaluation_result_service import EvaluationResultService
        
        evaluation_result = EvaluationResultService.calculate_and_save_result(
            test_id=session.test_id,
            student_id=session.student_id,
            session_id=session.id
        )
        
        # Não alterar o status global da avaliação
        # Cada aluno tem seu próprio status individual
        db.session.commit()
        
        # ✅ NOVO: Retornar resultados completos calculados
        if evaluation_result:
            results = {
                'session_id': session.id,
                'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
                'status': 'finalizada',
                'total_questions': total_questions,
                'correct_answers': correct_count,
                'score_percentage': evaluation_result['score_percentage'],
                'grade': evaluation_result['grade'],
                'proficiency': evaluation_result['proficiency'],
                'classification': evaluation_result['classification'],
                'duration_minutes': session.duration_minutes,
                'message': 'Avaliação enviada com sucesso!'
            }
        else:
            # Fallback para cálculo básico se houver erro no cálculo completo
            results = {
                'session_id': session.id,
                'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
                'status': 'finalizada',
                'total_questions': total_questions,
                'correct_answers': correct_count,
                'score_percentage': round((correct_count / total_questions) * 100, 2) if total_questions > 0 else 0,
                'grade': session.grade,
                'duration_minutes': session.duration_minutes,
                'message': 'Avaliação enviada com sucesso! (Cálculo básico)'
            }
        
        return jsonify(results), 201
        
    except Exception as e:
        logging.error(f"Erro ao submeter respostas: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao submeter respostas", "details": str(e)}), 500


@bp.route('/save-partial', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def save_partial_answers():
    """
    Salva respostas parciais sem finalizar a sessão
    
    Body:
    {
        "session_id": "uuid",
        "answers": [
            {
                "question_id": "uuid",
                "answer": "resposta_do_aluno"
            }
        ]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Dados JSON são obrigatórios'}), 400
        
        session_id = data.get('session_id')
        answers = data.get('answers', [])
        
        if not session_id:
            return jsonify({'error': 'session_id é obrigatório'}), 400
        
        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Verificar se a avaliação não expirou
        from app.models.classTest import ClassTest
        class_test = ClassTest.query.filter_by(
            test_id=session.test_id
        ).first()
        
        if class_test and class_test.expiration:
            current_time = datetime.utcnow()
            # Garantir que ambas as datas estejam em UTC para comparação
            expiration_utc = class_test.expiration.replace(tzinfo=None) if class_test.expiration.tzinfo else class_test.expiration
            current_utc = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time
            if current_utc > expiration_utc:
                session.status = 'expirada'
                db.session.commit()
                return jsonify({
                    'error': 'Avaliação expirada. Não é possível salvar respostas.'
                }), 410
        
        # Validar se sessão ainda está ativa
        if session.status != 'em_andamento':
            return jsonify({
                'error': f'Sessão não está ativa. Status atual: {session.status}'
            }), 400
        
        # Validar tempo limite (cálculo no frontend, mas validação adicional aqui)
        if session.started_at and session.time_limit_minutes:
            from app.utils.timezone_utils import get_brazil_time
            current_time = get_brazil_time()
            elapsed_minutes = int((current_time - session.started_at).total_seconds() / 60)
            if elapsed_minutes > session.time_limit_minutes:
                session.status = 'expirada'
                db.session.commit()
                return jsonify({
                    'error': 'Tempo limite excedido. Sessão expirada.'
                }), 410  # 410 Gone
        
        # Buscar questões do teste através da tabela de associação
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=session.test_id).order_by(TestQuestion.order).all()]
        test_questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
        questions_dict = {q.id: q for q in test_questions}
        
        saved_answers = []
        
        # Processar cada resposta
        for ans_data in answers:
            question_id = ans_data.get('question_id')
            answer = ans_data.get('answer')
            
            if not question_id or answer is None:
                continue
            
            # Verificar se a questão existe e pertence ao teste
            if question_id not in questions_dict:
                logging.warning(f"Questão {question_id} não encontrada no teste {session.test_id}")
                continue
            
            # Verificar se já existe resposta para esta questão nesta sessão
            existing_answer = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id,
                question_id=question_id
            ).first()
            
            if existing_answer:
                # Atualizar resposta existente
                existing_answer.answer = str(answer)
                existing_answer.answered_at = datetime.utcnow()
                student_answer = existing_answer
            else:
                # Criar nova resposta
                student_answer = StudentAnswer(
                    student_id=session.student_id,
                    test_id=session.test_id,
                    question_id=question_id,
                    answer=str(answer)
                )
                db.session.add(student_answer)
            
            saved_answers.append({
                'question_id': question_id,
                'answer': str(answer),
                'answered_at': student_answer.answered_at.isoformat() if student_answer.answered_at else None
            })
        
        db.session.commit()
        
        return jsonify({
            'message': 'Respostas parciais salvas com sucesso',
            'session_id': session.id,
            'answers_saved': len(saved_answers),
            'answers': saved_answers
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao salvar respostas parciais: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao salvar respostas parciais", "details": str(e)}), 500


@bp.route('/active-session/<string:test_id>', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def get_active_session(test_id):
    """
    Retorna a sessão ativa para um teste específico
    """
    try:
        from app.models.student import Student
        
        # Obter user_id do JWT token
        current_user_id = get_jwt_identity()
        
        # Buscar estudante pelo user_id
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404
        
        # Buscar sessão ativa para este aluno/teste
        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id,
            status='em_andamento'
        ).first()
        
        if not session:
            return jsonify({
                'message': 'Nenhuma sessão ativa encontrada para este teste',
                'test_id': test_id,
                'student_id': student.id,
                'session_exists': False
            }), 404
        
        # Calcular tempo decorrido e restante
        elapsed_minutes = 0
        remaining_minutes = session.time_limit_minutes
        is_expired = False
        
        if session.started_at and session.time_limit_minutes:
            from datetime import datetime
            elapsed_minutes = int((datetime.utcnow() - session.started_at).total_seconds() / 60)
            remaining_minutes = max(0, session.time_limit_minutes - elapsed_minutes)
            is_expired = remaining_minutes <= 0
        elif session.time_limit_minutes is None:
            # Se não há limite de tempo, não está expirada
            is_expired = False
        
        # Se expirou, atualizar status
        if is_expired and session.status == 'em_andamento':
            session.status = 'expirada'
            db.session.commit()
            return jsonify({
                'message': 'Sessão expirada',
                'test_id': test_id,
                'session_id': session.id,
                'status': session.status,
                'is_expired': True
            }), 410
        
        return jsonify({
            'session_id': session.id,
            'test_id': session.test_id,
            'student_id': session.student_id,
            'status': session.status,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'time_limit_minutes': session.time_limit_minutes,
            'elapsed_minutes': elapsed_minutes,
            'remaining_minutes': remaining_minutes,
            'is_expired': is_expired,
            'total_questions': session.total_questions,
            'correct_answers': session.correct_answers,
            'score': session.score,
            'grade': session.grade,
            'session_exists': True
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar sessão ativa: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar sessão ativa", "details": str(e)}), 500


# ==================== VERIFICAÇÃO DE STATUS POR ALUNO ====================

@bp.route('/student/<string:test_id>/status', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def get_student_test_status(test_id):
    """
    Verifica o status de uma avaliação específica para o aluno autenticado
    
    Returns:
    {
        "test_id": "uuid",
        "student_id": "uuid", 
        "has_completed": true/false,
        "session_status": "em_andamento/finalizada/expirada/nao_iniciada",
        "completed_at": "2024-01-01T10:00:00Z",
        "score": 85.5,
        "grade": 8.5,
        "total_questions": 20,
        "correct_answers": 17
    }
    """
    try:
        from app.models.student import Student
        
        # Obter user_id do JWT token
        current_user_id = get_jwt_identity()
        
        # Buscar estudante pelo user_id
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404
        
        # Verificar se o teste existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({'error': 'Teste não encontrado'}), 404
        
        # Buscar sessão do aluno para este teste
        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id
        ).first()
        
        if not session:
            return jsonify({
                'test_id': test_id,
                'student_id': student.id,
                'has_completed': False,
                'session_status': 'nao_iniciada',
                'completed_at': None,
                'score': None,
                'grade': None,
                'total_questions': None,
                'correct_answers': None,
                'can_start': True
            }), 200
        
        # Verificar se há respostas salvas
        has_answers = StudentAnswer.query.filter_by(
            student_id=student.id,
            test_id=test_id
        ).first() is not None
        
        response = {
            'test_id': test_id,
            'student_id': student.id,
            'has_completed': session.status in ['finalizada', 'expirada', 'corrigida', 'revisada'],
            'session_status': session.status,
            'completed_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'score': session.score,
            'grade': session.grade,
            'total_questions': session.total_questions,
            'correct_answers': session.correct_answers,
            'has_answers': has_answers,
            'can_start': session.status == 'nao_iniciada' or (session.status == 'em_andamento' and not has_answers)
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logging.error(f"Erro ao verificar status do teste para aluno: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar status do teste", "details": str(e)}), 500


@bp.route('/student/tests/status', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def get_student_all_tests_status():
    """
    Verifica o status de todas as avaliações disponíveis para o aluno autenticado
    
    Query Parameters:
    - class_id: ID da classe (opcional, se não fornecido usa a classe do aluno)
    
    Returns:
    {
        "student_id": "uuid",
        "tests_status": [
            {
                "test_id": "uuid",
                "has_completed": true/false,
                "session_status": "em_andamento/finalizada/expirada/nao_iniciada",
                "completed_at": "2024-01-01T10:00:00Z",
                "score": 85.5,
                "grade": 8.5,
                "can_start": true/false
            }
        ]
    }
    """
    try:
        from app.models.student import Student
        from app.models.classTest import ClassTest
        
        # Obter user_id do JWT token
        current_user_id = get_jwt_identity()
        
        # Buscar estudante pelo user_id
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404
        
        # Determinar classe (parâmetro ou classe do aluno)
        class_id = request.args.get('class_id', student.class_id)
        if not class_id:
            return jsonify({'error': 'Aluno não está matriculado em nenhuma classe'}), 400
        
        # Buscar todas as avaliações aplicadas na classe
        class_tests = ClassTest.query.filter_by(class_id=class_id).all()
        if not class_tests:
            return jsonify({
                'student_id': student.id,
                'class_id': class_id,
                'tests_status': []
            }), 200
        
        # Buscar todas as sessões do aluno para estas avaliações
        test_ids = [ct.test_id for ct in class_tests]
        sessions = TestSession.query.filter_by(student_id=student.id).filter(
            TestSession.test_id.in_(test_ids)
        ).all()
        
        # Criar dicionário de sessões por test_id
        sessions_dict = {session.test_id: session for session in sessions}
        
        # Preparar resposta
        tests_status = []
        for class_test in class_tests:
            session = sessions_dict.get(class_test.test_id)
            
            if session:
                # Verificar se há respostas salvas
                has_answers = StudentAnswer.query.filter_by(
                    student_id=student.id,
                    test_id=class_test.test_id
                ).first() is not None
                
                test_status = {
                    'test_id': class_test.test_id,
                    'class_test_id': class_test.id,
                    'has_completed': session.status in ['finalizada', 'expirada', 'corrigida', 'revisada'],
                    'session_status': session.status,
                    'completed_at': session.submitted_at.isoformat() if session.submitted_at else None,
                    'score': session.score,
                    'grade': session.grade,
                    'total_questions': session.total_questions,
                    'correct_answers': session.correct_answers,
                    'has_answers': has_answers,
                    'can_start': session.status == 'nao_iniciada' or (session.status == 'em_andamento' and not has_answers)
                }
            else:
                test_status = {
                    'test_id': class_test.test_id,
                    'class_test_id': class_test.id,
                    'has_completed': False,
                    'session_status': 'nao_iniciada',
                    'completed_at': None,
                    'score': None,
                    'grade': None,
                    'total_questions': None,
                    'correct_answers': None,
                    'has_answers': False,
                    'can_start': True
                }
            
            tests_status.append(test_status)
        
        return jsonify({
            'student_id': student.id,
            'class_id': class_id,
            'tests_status': tests_status
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao verificar status dos testes para aluno: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar status dos testes", "details": str(e)}), 500


# ==================== CONSULTAS E RELATÓRIOS ====================

@bp.route('/session/<session_id>/answers', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def get_session_answers(session_id):
    """
    Retorna todas as respostas de uma sessão específica
    """
    try:
        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Buscar respostas
        answers = StudentAnswer.query.filter_by(
            student_id=session.student_id,
            test_id=session.test_id
        ).all()
        
        answers_data = []
        for answer in answers:
            answers_data.append({
                'question_id': answer.question_id,
                'answer': answer.answer,
                'answered_at': answer.answered_at.isoformat() if answer.answered_at else None,
                'is_correct': answer.is_correct,
                'manual_points': answer.manual_points,
                'feedback': answer.feedback
            })
        
        return jsonify({
            'session_id': session_id,
            'total_answers': len(answers_data),
            'answers': answers_data
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar respostas da sessão: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar respostas", "details": str(e)}), 500


@bp.route('/student/sessions', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def get_student_sessions():
    """
    Retorna todas as sessões do aluno logado
    """
    try:
        from app.models.student import Student
        
        # Obter user_id do JWT token
        current_user_id = get_jwt_identity()
        
        # Buscar estudante pelo user_id
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404
        
        # Buscar todas as sessões do aluno
        sessions = TestSession.query.filter_by(student_id=student.id).all()
        
        sessions_data = []
        for session in sessions:
            # Calcular tempo decorrido e restante
            elapsed_minutes = 0
            remaining_minutes = session.time_limit_minutes
            is_expired = False
            
            if session.started_at and session.time_limit_minutes:
                from datetime import datetime
                elapsed_minutes = int((datetime.utcnow() - session.started_at).total_seconds() / 60)
                remaining_minutes = max(0, session.time_limit_minutes - elapsed_minutes)
                is_expired = remaining_minutes <= 0
            elif session.time_limit_minutes is None:
                # Se não há limite de tempo, não está expirada
                is_expired = False
            
            sessions_data.append({
                'session_id': session.id,
                'test_id': session.test_id,
                'status': session.status,
                'started_at': session.started_at.isoformat() if session.started_at else None,
                'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
                'time_limit_minutes': session.time_limit_minutes,
                'elapsed_minutes': elapsed_minutes,
                'remaining_minutes': remaining_minutes,
                'is_expired': is_expired,
                'duration_minutes': session.duration_minutes,
                'total_questions': session.total_questions,
                'correct_answers': session.correct_answers,
                'score': session.score,
                'grade': session.grade
            })
        
        return jsonify({
            'student_id': student.id,
            'total_sessions': len(sessions_data),
            'sessions': sessions_data
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar sessões do aluno: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar sessões", "details": str(e)}), 500


@bp.route('/student/<string:test_id>/can-start', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def can_student_start_test(test_id):
    """
    Verifica se um aluno pode iniciar uma avaliação específica
    
    Returns:
    {
        "can_start": true/false,
        "reason": "string explicando o motivo",
        "test_info": {
            "id": "uuid",
            "title": "string",
            "status": "string"
        },
        "student_info": {
            "id": "uuid",
            "session_status": "string",
            "has_completed": true/false
        }
    }
    """
    try:
        from app.models.student import Student
        from app.models.classTest import ClassTest
        from datetime import datetime
        
        # Obter user_id do JWT token
        current_user_id = get_jwt_identity()
        
        # Buscar estudante pelo user_id
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404
        
        # Verificar se o teste existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({'error': 'Teste não encontrado'}), 404
        
        # Verificar se o teste está aplicado na classe do aluno
        class_test = ClassTest.query.filter_by(
            class_id=student.class_id,
            test_id=test_id
        ).first()
        
        if not class_test:
            return jsonify({
                'can_start': False,
                'reason': 'Avaliação não está aplicada na sua classe',
                'test_info': {
                    'id': test_id,
                    'title': test.title,
                    'status': test.status
                },
                'student_info': {
                    'id': student.id,
                    'session_status': 'nao_aplicada',
                    'has_completed': False
                }
            }), 200
        
        # ✅ CORRIGIDO: Verificar se já completou, se a avaliação está disponível E se não expirou
        can_start = False  # Por padrão, não pode iniciar
        reason = "Verificando disponibilidade..."
        
        # Buscar sessão do aluno (sempre buscar, independente da expiração)
        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id
        ).first()
        
        # Buscar sessão do aluno (sempre buscar, independente da expiração)
        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id
        ).first()
        
        # Verificar se a avaliação está disponível (data de aplicação) e não expirou (data de expiração)
        from app.utils.timezone_utils import get_brazil_time, convert_to_brazil_time
        current_time = get_brazil_time()
        
        # Verificar se já passou da data de aplicação
        if class_test.application and class_test.application is not None:
            try:
                # Converter data de aplicação para fuso horário do Brasil
                application_brazil = convert_to_brazil_time(class_test.application)
                current_brazil = current_time
                
                # Log de debug para verificar as datas
                import logging
                logging.info(f"DEBUG CAN-START DATES - Test: {test_id}, Application: {class_test.application}, Application Brazil: {application_brazil}, Current: {current_time}")
                
                # Comparar datas com timezone - só disponível se já passou da data de aplicação
                time_diff = current_brazil - application_brazil
                if time_diff.total_seconds() < 0:
                    can_start = False
                    reason = "Avaliação ainda não está disponível"
                    logging.info(f"DEBUG CAN-START TIME DIFF - Test: {test_id}, Time Difference: {time_diff}, Total Seconds: {time_diff.total_seconds()}, Can Start: {can_start}")
                else:
                    # Verificar se a avaliação não expirou
                    if class_test.expiration and class_test.expiration is not None:
                        try:
                            # Converter data de expiração para fuso horário do Brasil
                            expiration_brazil = convert_to_brazil_time(class_test.expiration)
                            current_brazil = current_time
                            
                            # Log de debug para verificar as datas de expiração
                            logging.info(f"DEBUG CAN-START EXPIRATION - Test: {test_id}, Expiration: {class_test.expiration}, Expiration Brazil: {expiration_brazil}, Current: {current_time}")
                            
                            # Comparar datas com timezone usando diferença de tempo
                            time_diff = current_brazil - expiration_brazil
                            if time_diff.total_seconds() > 0:
                                can_start = False
                                reason = "Avaliação expirada"
                                logging.info(f"DEBUG CAN-START EXPIRATION TIME DIFF - Test: {test_id}, Time Difference: {time_diff}, Total Seconds: {time_diff.total_seconds()}, Can Start: {can_start}")
                        except Exception as e:
                            # Se houver erro na conversão, não expirada
                            logging.error(f"Erro ao converter data de expiração para teste {test_id}: {str(e)}")
                    
                    # Se chegou até aqui, a avaliação está disponível e não expirou
                    can_start = True
                    reason = "Avaliação disponível"
                    
                    # Verificar se o aluno já completou
                    if session:
                        if session.status in ['finalizada', 'expirada', 'corrigida', 'revisada']:
                            can_start = False
                            reason = "Você já completou esta avaliação"
                        elif session.status == 'em_andamento':
                            # Verificar se há respostas salvas
                            has_answers = StudentAnswer.query.filter_by(
                                student_id=student.id,
                                test_id=test_id
                            ).first() is not None
                            
                            if has_answers:
                                can_start = False
                                reason = "Você já iniciou esta avaliação"
            except Exception as e:
                # Se houver erro na conversão, não disponível
                logging.error(f"Erro ao converter data de aplicação para teste {test_id}: {str(e)}")
                can_start = False
                reason = "Erro ao verificar disponibilidade da avaliação"
        else:
            # Se não há data de aplicação definida, não está disponível
            can_start = False
            reason = "Avaliação não tem data de aplicação definida"
        
        # Log de debug para o resultado final
        logging.info(f"DEBUG CAN-START FINAL - Test: {test_id}, Can Start: {can_start}, Reason: {reason}")
        
        return jsonify({
            'can_start': can_start,
            'reason': reason,
            'test_info': {
                'id': test_id,
                'title': test.title,
                'status': test.status,
                'application': class_test.application.isoformat() if class_test.application else None,
                'expiration': class_test.expiration.isoformat() if class_test.expiration else None
            },
            'student_info': {
                'id': student.id,
                'session_status': session.status if session else 'nao_iniciada',
                'has_completed': session.status in ['finalizada', 'expirada', 'corrigida', 'revisada'] if session else False
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao verificar se aluno pode iniciar teste: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar permissão", "details": str(e)}), 500


# ==================== ENDPOINT LEGADO (COMPATIBILIDADE) ====================

# Endpoint legado removido - usar /submit em vez de POST raiz 

@bp.route('/student/<string:test_id>/submission-status', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def get_student_submission_status(test_id):
    """
    Retorna apenas se a avaliação foi enviada (sem mostrar resultados)
    
    Returns:
    {
        "test_id": "uuid",
        "student_id": "uuid",
        "is_submitted": true/false,
        "submitted_at": "2024-01-01T10:00:00Z" ou null,
        "session_status": "finalizada/expirada/em_andamento/nao_iniciada"
    }
    """
    try:
        from app.models.student import Student
        
        # Obter user_id do JWT token
        current_user_id = get_jwt_identity()
        
        # Buscar estudante pelo user_id
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404
        
        # Verificar se o teste existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({'error': 'Teste não encontrado'}), 404
        
        # Buscar sessão do aluno para este teste
        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id
        ).first()
        
        if not session:
            return jsonify({
                'test_id': test_id,
                'student_id': student.id,
                'is_submitted': False,
                'submitted_at': None,
                'session_status': 'nao_iniciada'
            }), 200
        
        # Verificar se foi enviada (status finalizada, expirada, corrigida, revisada)
        is_submitted = session.status in ['finalizada', 'expirada', 'corrigida', 'revisada']
        
        return jsonify({
            'test_id': test_id,
            'student_id': student.id,
            'is_submitted': is_submitted,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'session_status': session.status
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao verificar status de submissão do teste para aluno: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar status de submissão", "details": str(e)}), 500 