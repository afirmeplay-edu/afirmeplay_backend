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

@bp.route('/sessions/start', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def start_test_session():
    """
    Inicia uma nova sessão de prova para o aluno logado
    
    Body:
    {
        "test_id": "uuid",
        "time_limit_minutes": 60
    }
    
    O student_id é obtido automaticamente do JWT token do usuário logado.
    """
    try:
        data = request.get_json()
        test_id = data.get('test_id')
        time_limit_minutes = data.get('time_limit_minutes')
        
        # Obter user_id do JWT token
        current_user_id = get_jwt_identity()
        
        if not test_id:
            return jsonify({'error': 'test_id é obrigatório'}), 400
        
        # Buscar estudante pelo user_id
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404
            
        test = Test.query.get(test_id)
        if not test:
            return jsonify({'error': 'Teste não encontrado'}), 404
        
        # Verificar se já existe sessão ativa para este aluno/teste
        existing_session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id,
            status='em_andamento'
        ).first()
        
        if existing_session:
            return jsonify({
                'message': 'Sessão já iniciada',
                'session_id': existing_session.id,
                'started_at': existing_session.started_at.isoformat() if existing_session.started_at else None,
                'time_limit_minutes': existing_session.time_limit_minutes
            }), 200
        
        # Criar nova sessão (sem iniciar cronômetro ainda)
        session = TestSession(
            student_id=student.id,
            test_id=test_id,
            time_limit_minutes=time_limit_minutes,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            'message': 'Sessão criada com sucesso. Use /start-timer para iniciar o cronômetro.',
            'session_id': session.id,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'time_limit_minutes': session.time_limit_minutes
        }), 201
        
    except Exception as e:
        logging.error(f"Erro ao iniciar sessão: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao iniciar sessão", "details": str(e)}), 500


@bp.route('/sessions/<session_id>/status', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
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


@bp.route('/sessions/<session_id>/start-timer', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def start_session_timer(session_id):
    """
    Inicia efetivamente o cronômetro de uma sessão de prova
    
    Este endpoint deve ser chamado quando o aluno efetivamente começar a responder
    a avaliação, não apenas quando acessar a página.
    """
    try:
        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Verificar se a sessão está ativa
        if session.status != 'em_andamento':
            return jsonify({
                'error': f'Sessão não está ativa. Status atual: {session.status}'
            }), 400
        
        # Verificar se o cronômetro já foi iniciado
        if session.started_at:
            return jsonify({
                'message': 'Cronômetro já foi iniciado',
                'session_id': session.id,
                'started_at': session.started_at.isoformat() if session.started_at else None,
                'time_limit_minutes': session.time_limit_minutes
            }), 200
        
        # Iniciar cronômetro
        session.start_session()
        db.session.commit()
        
        return jsonify({
            'message': 'Cronômetro iniciado com sucesso',
            'session_id': session.id,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'time_limit_minutes': session.time_limit_minutes
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao iniciar cronômetro: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao iniciar cronômetro", "details": str(e)}), 500


@bp.route('/sessions/<session_id>/end', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
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
        
        # Validar se sessão ainda está ativa
        if session.status != 'em_andamento':
            return jsonify({
                'error': f'Sessão não está ativa. Status atual: {session.status}'
            }), 400
        
        # Validar tempo limite (cálculo no frontend, mas validação adicional aqui)
        if session.started_at and session.time_limit_minutes:
            from datetime import datetime
            elapsed_minutes = int((datetime.utcnow() - session.started_at).total_seconds() / 60)
            if elapsed_minutes > session.time_limit_minutes:
                session.status = 'expirada'
                db.session.commit()
                return jsonify({
                    'error': 'Tempo limite excedido. Sessão expirada.'
                }), 410  # 410 Gone
        
        # Buscar questões do teste para validação e correção
        test_questions = Question.query.filter_by(test_id=session.test_id).all()
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
            if question.correct_answer and str(answer).strip().lower() == str(question.correct_answer).strip().lower():
                correct_count += 1
        
        # Finalizar sessão e calcular nota
        total_questions = len(test_questions)
        session.finalize_session(
            correct_answers=correct_count,
            total_questions=total_questions
        )
        
        # Alterar status da avaliação para "concluida"
        from app.models.test import Test
        test = Test.query.get(session.test_id)
        if test:
            test.status = 'concluida'
        
        db.session.commit()
        
        return jsonify({
            'message': 'Respostas salvas e sessão finalizada com sucesso',
            'session_id': session.id,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'duration_minutes': session.duration_minutes,
            'results': {
                'total_questions': session.total_questions,
                'correct_answers': session.correct_answers,
                'score_percentage': session.score,
                'grade': session.grade,
                'answers_saved': len(saved_answers)
            },
            'answers': saved_answers
        }), 201
        
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
        
        # Validar se sessão ainda está ativa
        if session.status != 'em_andamento':
            return jsonify({
                'error': f'Sessão não está ativa. Status atual: {session.status}'
            }), 400
        
        # Validar tempo limite (cálculo no frontend, mas validação adicional aqui)
        if session.started_at and session.time_limit_minutes:
            from datetime import datetime
            elapsed_minutes = int((datetime.utcnow() - session.started_at).total_seconds() / 60)
            if elapsed_minutes > session.time_limit_minutes:
                session.status = 'expirada'
                db.session.commit()
                return jsonify({
                    'error': 'Tempo limite excedido. Sessão expirada.'
                }), 410  # 410 Gone
        
        # Buscar questões do teste
        test_questions = Question.query.filter_by(test_id=session.test_id).all()
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


# ==================== CONSULTAS E RELATÓRIOS ====================

@bp.route('/test/<string:test_id>/session', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def get_test_session(test_id):
    """
    Retorna a sessão de teste ativa para o usuário logado e teste específico
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
        logging.error(f"Erro ao buscar sessão do teste: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar sessão", "details": str(e)}), 500


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


# ==================== ENDPOINT LEGADO (COMPATIBILIDADE) ====================

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def submit_answers_legacy():
    """
    Endpoint legado para compatibilidade - redireciona para o sistema de sessões
    """
    try:
        data = request.get_json()
        test_id = data.get('test_id')
        answers = data.get('answers', [])
        time_limit_minutes = data.get('time_limit_minutes', 60)  # padrão 60 minutos
        
        # Obter user_id do JWT token
        current_user_id = get_jwt_identity()
        
        if not test_id or not answers:
            return jsonify({'error': 'test_id e answers são obrigatórios'}), 400
        
        # Buscar estudante pelo user_id
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404
        
        # Verificar se já existe sessão ativa
        existing_session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id,
            status='em_andamento'
        ).first()
        
        if not existing_session:
            # Criar nova sessão
            session = TestSession(
                student_id=student.id,
                test_id=test_id,
                time_limit_minutes=time_limit_minutes,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            db.session.add(session)
            db.session.flush()  # Para obter o ID
        else:
            session = existing_session
        
        # Processar respostas e finalizar sessão
        test_questions = Question.query.filter_by(test_id=test_id).all()
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
                logging.warning(f"Questão {question_id} não encontrada no teste {test_id}")
                continue
            
            # Verificar se já existe resposta para esta questão nesta sessão
            existing_answer = StudentAnswer.query.filter_by(
                student_id=student.id,
                test_id=test_id,
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
                    student_id=student.id,
                    test_id=test_id,
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
            if question.correct_answer and str(answer).strip().lower() == str(question.correct_answer).strip().lower():
                correct_count += 1
        
        # Finalizar sessão e calcular nota
        total_questions = len(test_questions)
        session.finalize_session(
            correct_answers=correct_count,
            total_questions=total_questions
        )
        
        # Alterar status da avaliação para "concluida"
        from app.models.test import Test
        test = Test.query.get(session.test_id)
        if test:
            test.status = 'concluida'
        
        db.session.commit()
        
        return jsonify({
            'message': 'Respostas enviadas com sucesso (modo legado)',
            'session_id': session.id,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'duration_minutes': session.duration_minutes,
            'results': {
                'total_questions': session.total_questions,
                'correct_answers': session.correct_answers,
                'score_percentage': session.score,
                'grade': session.grade,
                'answers_saved': len(saved_answers)
            },
            'answers': saved_answers
        }), 201
        
    except Exception as e:
        logging.error(f"Erro ao submeter respostas (legado): {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao submeter respostas", "details": str(e)}), 500 