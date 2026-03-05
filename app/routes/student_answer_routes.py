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
from app.decorators import requires_city_context
from datetime import datetime, timedelta
import logging
import dateutil.parser

bp = Blueprint('student_answer', __name__, url_prefix='/student-answers')


def _expired_session_response(session, test_id):
    """Monta o corpo da resposta 410 (sessão expirada) incluindo sempre as respostas salvas."""
    sid = getattr(session, 'student_id', None) or session.student_id
    tid = getattr(session, 'test_id', None) or session.test_id
    answers_exp = StudentAnswer.query.filter_by(student_id=sid, test_id=tid).all()
    answers_data = [
        {
            'question_id': a.question_id,
            'answer': a.answer,
            'answered_at': a.answered_at.isoformat() if a.answered_at else None,
            'is_correct': a.is_correct,
            'manual_points': getattr(a, 'manual_score', None),
            'feedback': a.feedback
        }
        for a in answers_exp
    ]
    return {
        'message': 'Sessão expirada',
        'test_id': test_id,
        'session_id': session.id,
        'status': getattr(session, 'status', 'expirada'),
        'is_expired': True,
        'total_answers': len(answers_data),
        'answers': answers_data
    }


def _effective_time_limit_minutes(session):
    """Retorna time_limit_minutes da sessão ou, se None, a duração da prova (test.duration)."""
    if getattr(session, 'time_limit_minutes', None) is not None:
        return int(session.time_limit_minutes)
    test = Test.query.get(session.test_id)
    if test and getattr(test, 'duration', None) is not None:
        return int(test.duration)
    return None


def _effective_elapsed_seconds(session, now=None):
    """
    Tempo efetivo de prova em segundos (desconsidera tempo com aba fechada / pausado).
    Usa started_at, paused_at e total_paused_seconds do TestSession.
    """
    if not session or not getattr(session, 'started_at', None):
        return 0
    now = now or datetime.utcnow()
    if session.started_at.tzinfo:
        from datetime import timezone
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
    raw = (now - session.started_at).total_seconds()
    total_paused = getattr(session, 'total_paused_seconds', 0) or 0
    paused_at = getattr(session, 'paused_at', None)
    if paused_at:
        current_pause = (now - paused_at).total_seconds()
        return max(0, int(raw - total_paused - current_pause))
    return max(0, int(raw - total_paused))


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
        
        time_limit_minutes = _effective_time_limit_minutes(session)
        elapsed_seconds = _effective_elapsed_seconds(session)
        elapsed_minutes = elapsed_seconds // 60
        remaining_minutes = time_limit_minutes
        is_expired = False
        if time_limit_minutes is not None:
            remaining_minutes = max(0, time_limit_minutes - elapsed_minutes)
            is_expired = remaining_minutes <= 0
        
        return jsonify({
            'session_id': session.id,
            'status': session.status,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'time_limit_minutes': time_limit_minutes,
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

        # Etapa 4: recompensa de participação em competição (moedas)
        coins_earned = 0
        try:
            from app.competitions.services import CompetitionService
            coins_earned = CompetitionService.process_participation_reward(
                test_id=session.test_id,
                student_id=session.student_id,
                test_session_id=session.id,
            )
        except Exception as coins_err:
            logging.error(f"Erro ao processar recompensa de competição: {str(coins_err)}", exc_info=True)
        
        response_payload = {
            'message': 'Sessão encerrada com sucesso',
            'session_id': session.id,
            'status': session.status,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'duration_minutes': session.duration_minutes,
            'total_questions': session.total_questions,
            'correct_answers': session.correct_answers,
            'score': session.score,
            'grade': session.grade
        }
        if coins_earned > 0:
            response_payload['coins_earned'] = coins_earned
        return jsonify(response_payload), 200
        
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
        
        # Verificar se a avaliação não expirou (turma e/ou olimpíada)
        # Ambos funcionam simultaneamente - não há exclusão mútua
        from app.models.classTest import ClassTest
        from app.models.studentTestOlimpics import StudentTestOlimpics
        from sqlalchemy.exc import SQLAlchemyError
        student = session.student
        class_test = ClassTest.query.filter_by(
            class_id=student.class_id,
            test_id=session.test_id
        ).first() if student and student.class_id else None
        olympics = None
        if student:
            try:
                olympics = StudentTestOlimpics.query.filter_by(
                    student_id=session.student_id,
                    test_id=session.test_id
                ).first()
            except (SQLAlchemyError, Exception) as e:
                # Se a tabela não existir, continuar apenas com ClassTest
                error_str = str(e).lower()
                if 'student_test_olimpics' in error_str or 'does not exist' in error_str or 'undefinedtable' in error_str:
                    logging.warning(f"Tabela student_test_olimpics não encontrada, continuando apenas com ClassTest: {str(e)}")
                    olympics = None
                else:
                    logging.warning(f"Erro ao buscar StudentTestOlimpics, continuando apenas com ClassTest: {str(e)}")
                    olympics = None
        # Priorizar StudentTestOlimpics se ambos existirem (mais específico para o aluno)
        # Ambos funcionam simultaneamente - não há exclusão mútua
        app_record = olympics if olympics else class_test

        # Para competição (StudentTestOlimpics): se a sessão já está em_andamento, permitir submissão
        # mesmo após o horário de expiração da competição (o aluno já começou e deve poder entregar).
        is_competition_session = app_record is olympics
        if app_record and app_record.expiration and not is_competition_session:
            current_time = datetime.utcnow()
            import dateutil.parser
            from datetime import timezone as tz
            expiration_dt = dateutil.parser.parse(app_record.expiration)
            if expiration_dt.tzinfo:
                expiration_utc = expiration_dt.astimezone(tz.utc).replace(tzinfo=None)
            else:
                expiration_utc = expiration_dt
            current_utc = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time
            if current_utc > expiration_utc:
                session.status = 'expirada'
                db.session.commit()
                return jsonify({
                    'error': 'Avaliação expirada. Não é possível submeter respostas.'
                }), 410

        # Validar se sessão ainda está ativa
        if session.status != 'em_andamento':
            # Sessão expirada/finalizada: retornar 410 com respostas salvas para o front exibir
            body = {
                'error': f'Sessão não está ativa. Status atual: {session.status}',
                'session_id': str(session.id),
                'test_id': str(session.test_id),
                'status': session.status,
                'is_expired': session.status == 'expirada'
            }
            answers_saved = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id
            ).all()
            body['answers'] = [
                {
                    'question_id': str(a.question_id),
                    'answer': a.answer,
                    'answered_at': a.answered_at.isoformat() if a.answered_at else None,
                }
                for a in answers_saved
            ]
            body['total_answers'] = len(body['answers'])
            return jsonify(body), 410

        # Validar tempo limite (cálculo no frontend, mas validação adicional aqui)
        if session.started_at and session.time_limit_minutes:
            from app.utils.timezone_utils import get_local_time
            from datetime import timezone
            current_time = get_local_time()
            
            # Converter started_at para timezone local para comparação
            started_at_dt = session.started_at
            if started_at_dt.tzinfo is None:
                # Se não tem timezone, assumir UTC e converter para local
                started_at_dt = started_at_dt.replace(tzinfo=timezone.utc)
            
            # Converter para timezone local para comparação
            started_at_local = started_at_dt.astimezone(current_time.tzinfo)
            
            elapsed_minutes = int((current_time - started_at_local).total_seconds() / 60)
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
            if question.question_type == 'multiple_choice':
                # Verificar usando correct_answer para questões de múltipla escolha
                from app.services.evaluation_result_service import EvaluationResultService
                is_correct = EvaluationResultService.check_multiple_choice_answer(answer, question.correct_answer)
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
        
        try:
            evaluation_result = EvaluationResultService.calculate_and_save_result(
                test_id=session.test_id,
                student_id=session.student_id,
                session_id=session.id
            )
        except Exception as calc_error:
            logging.error(f"Erro ao calcular resultado: {str(calc_error)}", exc_info=True)
            evaluation_result = None
        
        # Não alterar o status global da avaliação
        # Cada aluno tem seu próprio status individual
        try:
            db.session.commit()
        except Exception as commit_error:
            logging.error(f"Erro no commit: {str(commit_error)}", exc_info=True)
            raise

        # Etapa 4: recompensa de participação em competição (moedas)
        coins_earned = 0
        try:
            from app.competitions.services import CompetitionService
            coins_earned = CompetitionService.process_participation_reward(
                test_id=session.test_id,
                student_id=session.student_id,
                test_session_id=session.id,
            )
        except Exception as coins_err:
            logging.error(f"Erro ao processar recompensa de competição: {str(coins_err)}", exc_info=True)

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
        if coins_earned > 0:
            results['coins_earned'] = coins_earned
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

        # Validar que o aluno autenticado é o dono da sessão (evita salvar em sessão de outro)
        current_user_id = get_jwt_identity()
        current_student = Student.query.filter_by(user_id=current_user_id).first()
        if not current_student or str(current_student.id) != str(session.student_id):
            return jsonify({'error': 'Você não tem permissão para salvar respostas nesta sessão'}), 403
        
        # Verificar se a avaliação não expirou (turma e/ou olimpíada)
        # Ambos funcionam simultaneamente - não há exclusão mútua
        from app.models.classTest import ClassTest
        from app.models.studentTestOlimpics import StudentTestOlimpics
        from sqlalchemy.exc import SQLAlchemyError
        student = session.student
        class_test = ClassTest.query.filter_by(
            class_id=student.class_id,
            test_id=session.test_id
        ).first() if student and student.class_id else None
        olympics = None
        if student:
            try:
                olympics = StudentTestOlimpics.query.filter_by(
                    student_id=session.student_id,
                    test_id=session.test_id
                ).first()
            except (SQLAlchemyError, Exception) as e:
                # Se a tabela não existir, continuar apenas com ClassTest
                error_str = str(e).lower()
                if 'student_test_olimpics' in error_str or 'does not exist' in error_str or 'undefinedtable' in error_str:
                    logging.warning(f"Tabela student_test_olimpics não encontrada, continuando apenas com ClassTest: {str(e)}")
                    olympics = None
                else:
                    logging.warning(f"Erro ao buscar StudentTestOlimpics, continuando apenas com ClassTest: {str(e)}")
                    olympics = None
        # Priorizar StudentTestOlimpics se ambos existirem (mais específico para o aluno)
        app_record = olympics if olympics else class_test
        is_competition_session = app_record is olympics

        if app_record and app_record.expiration and not is_competition_session:
            current_time = datetime.utcnow()
            import dateutil.parser
            from datetime import timezone as tz
            expiration_dt = dateutil.parser.parse(app_record.expiration)
            if expiration_dt.tzinfo:
                expiration_utc = expiration_dt.astimezone(tz.utc).replace(tzinfo=None)
            else:
                expiration_utc = expiration_dt
            current_utc = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time
            if current_utc > expiration_utc:
                session.status = 'expirada'
                db.session.commit()
                return jsonify({
                    'error': 'Avaliação expirada. Não é possível salvar respostas.'
                }), 410

        # Validar se sessão ainda está ativa
        if session.status != 'em_andamento':
            body = {
                'error': f'Sessão não está ativa. Status atual: {session.status}',
                'session_id': str(session.id),
                'test_id': str(session.test_id),
                'status': session.status,
                'is_expired': session.status == 'expirada',
            }
            answers_saved = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id
            ).all()
            body['answers'] = [
                {'question_id': str(a.question_id), 'answer': a.answer, 'answered_at': a.answered_at.isoformat() if a.answered_at else None}
                for a in answers_saved
            ]
            body['total_answers'] = len(body['answers'])
            return jsonify(body), 410

        # Validar tempo limite (cálculo no frontend, mas validação adicional aqui)
        if session.started_at and session.time_limit_minutes:
            from app.utils.timezone_utils import get_local_time
            from datetime import timezone
            current_time = get_local_time()
            
            # Converter started_at para timezone local para comparação
            started_at_dt = session.started_at
            if started_at_dt.tzinfo is None:
                # Se não tem timezone, assumir UTC e converter para local
                started_at_dt = started_at_dt.replace(tzinfo=timezone.utc)
            
            # Converter para timezone local para comparação
            started_at_local = started_at_dt.astimezone(current_time.tzinfo)
            
            elapsed_minutes = int((current_time - started_at_local).total_seconds() / 60)
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
@requires_city_context
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
        
        # Tempo limite = duração da prova (não a janela application/expiration)
        time_limit_minutes = _effective_time_limit_minutes(session)
        # Calcular tempo decorrido e restante (considera pausa quando aba fechada)
        elapsed_seconds = _effective_elapsed_seconds(session)
        elapsed_minutes = elapsed_seconds // 60
        remaining_minutes = time_limit_minutes
        is_expired = False
        if time_limit_minutes is not None:
            remaining_minutes = max(0, time_limit_minutes - elapsed_minutes)
            is_expired = remaining_minutes <= 0
        elif time_limit_minutes is None:
            is_expired = False
        
        # Se expirou, atualizar status
        if is_expired and session.status == 'em_andamento':
            session.status = 'expirada'
            db.session.commit()
            return jsonify(_expired_session_response(session, test_id)), 410

        return jsonify({
            'session_id': session.id,
            'test_id': session.test_id,
            'student_id': session.student_id,
            'status': session.status,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'time_limit_minutes': time_limit_minutes,
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


@bp.route('/active-session/<string:test_id>/with-answers', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
@requires_city_context
def get_active_session_with_answers(test_id):
    """
    Retorna a sessão ativa + respostas já salvas em uma única chamada.
    Use este endpoint ao retomar uma prova para evitar 2 round-trips (active-session + session/answers).
    """
    try:
        current_user_id = get_jwt_identity()
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404

        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id,
            status='em_andamento'
        ).first()

        if not session:
            # Pode ser que a sessão já tenha sido marcada como expirada (ex.: em outra aba).
            # Devolver última sessão (expirada/finalizada) + respostas para o front exibir o que foi salvo.
            last_session = (
                TestSession.query.filter_by(student_id=student.id, test_id=test_id)
                .filter(TestSession.status.in_(['expirada', 'finalizada']))
                .order_by(TestSession.started_at.desc())
                .first()
            )
            if last_session:
                answers_last = StudentAnswer.query.filter_by(
                    student_id=student.id,
                    test_id=test_id
                ).all()
                answers_data_last = [
                    {
                        'question_id': a.question_id,
                        'answer': a.answer,
                        'answered_at': a.answered_at.isoformat() if a.answered_at else None,
                        'is_correct': a.is_correct,
                        'manual_points': getattr(a, 'manual_score', None),
                        'feedback': a.feedback
                    }
                    for a in answers_last
                ]
                return jsonify({
                    'message': 'Nenhuma sessão ativa; exibindo respostas da última sessão.',
                    'test_id': test_id,
                    'session_id': last_session.id,
                    'status': last_session.status,
                    'session_exists': False,
                    'is_expired': last_session.status == 'expirada',
                    'total_answers': len(answers_data_last),
                    'answers': answers_data_last,
                    'started_at': last_session.started_at.isoformat() if last_session.started_at else None,
                    'submitted_at': last_session.submitted_at.isoformat() if last_session.submitted_at else None,
                }), 200
            return jsonify({
                'message': 'Nenhuma sessão ativa encontrada para este teste',
                'test_id': test_id,
                'session_exists': False
            }), 404

        time_limit_minutes = _effective_time_limit_minutes(session)
        elapsed_seconds = _effective_elapsed_seconds(session)
        elapsed_minutes = elapsed_seconds // 60
        remaining_minutes = time_limit_minutes
        is_expired = False
        if time_limit_minutes is not None:
            remaining_minutes = max(0, time_limit_minutes - elapsed_minutes)
            is_expired = remaining_minutes <= 0
        elif time_limit_minutes is None:
            is_expired = False

        if is_expired and session.status == 'em_andamento':
            session.status = 'expirada'
            db.session.commit()
            return jsonify(_expired_session_response(session, test_id)), 410

        answers = StudentAnswer.query.filter_by(
            student_id=session.student_id,
            test_id=session.test_id
        ).all()
        answers_data = [
            {
                'question_id': a.question_id,
                'answer': a.answer,
                'answered_at': a.answered_at.isoformat() if a.answered_at else None,
                'is_correct': a.is_correct,
                'manual_points': getattr(a, 'manual_score', None),  # modelo usa manual_score
                'feedback': a.feedback
            }
            for a in answers
        ]

        return jsonify({
            'session_id': session.id,
            'test_id': session.test_id,
            'student_id': session.student_id,
            'status': session.status,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
            'time_limit_minutes': time_limit_minutes,
            'elapsed_minutes': elapsed_minutes,
            'remaining_minutes': remaining_minutes,
            'is_expired': is_expired,
            'total_questions': session.total_questions,
            'correct_answers': session.correct_answers,
            'score': session.score,
            'grade': session.grade,
            'session_exists': True,
            'total_answers': len(answers_data),
            'answers': answers_data
        }), 200

    except Exception as e:
        logging.error(f"Erro ao buscar sessão ativa com respostas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar sessão com respostas", "details": str(e)}), 500


@bp.route('/active-session/<string:test_id>/pause', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
@requires_city_context
def pause_session(test_id):
    """
    Pausa o timer da prova (ex.: aluno fechou a aba).
    O tempo enquanto pausado não conta para o limite. Chamar ao detectar visibility hidden.
    """
    try:
        current_user_id = get_jwt_identity()
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado'}), 404
        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id,
            status='em_andamento'
        ).first()
        if not session:
            return jsonify({'error': 'Nenhuma sessão ativa para este teste'}), 404
        if getattr(session, 'paused_at', None):
            return jsonify({'message': 'Sessão já está pausada', 'session_id': session.id}), 200
        session.paused_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            'message': 'Timer pausado',
            'session_id': session.id,
            'paused_at': session.paused_at.isoformat() if session.paused_at else None
        }), 200
    except Exception as e:
        logging.error(f"Erro ao pausar sessão: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao pausar sessão", "details": str(e)}), 500


@bp.route('/active-session/<string:test_id>/resume', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
@requires_city_context
def resume_session(test_id):
    """
    Retoma o timer da prova (ex.: aluno reabriu a aba).
    Acumula o tempo que ficou pausado em total_paused_seconds.
    """
    try:
        current_user_id = get_jwt_identity()
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado'}), 404
        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id,
            status='em_andamento'
        ).first()
        if not session:
            return jsonify({'error': 'Nenhuma sessão ativa para este teste'}), 404
        paused_at = getattr(session, 'paused_at', None)
        if not paused_at:
            return jsonify({'message': 'Sessão não estava pausada', 'session_id': session.id}), 200
        now = datetime.utcnow()
        extra_paused = int((now - paused_at).total_seconds())
        total_paused = getattr(session, 'total_paused_seconds', 0) or 0
        session.total_paused_seconds = total_paused + extra_paused
        session.paused_at = None
        db.session.commit()
        return jsonify({
            'message': 'Timer retomado',
            'session_id': session.id,
            'total_paused_seconds': session.total_paused_seconds
        }), 200
    except Exception as e:
        logging.error(f"Erro ao retomar sessão: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao retomar sessão", "details": str(e)}), 500


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
        from app.models.studentTestOlimpics import StudentTestOlimpics

        current_user_id = get_jwt_identity()
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404

        class_id = request.args.get('class_id', student.class_id)
        class_tests = ClassTest.query.filter_by(class_id=class_id).all() if class_id else []
        olympics = []
        try:
            from sqlalchemy.exc import SQLAlchemyError
            olympics = StudentTestOlimpics.query.filter_by(student_id=student.id).all()
        except (SQLAlchemyError, Exception) as e:
            # Se a tabela não existir, continuar apenas com ClassTest
            error_str = str(e).lower()
            if 'student_test_olimpics' in error_str or 'does not exist' in error_str or 'undefinedtable' in error_str:
                logging.warning(f"Tabela student_test_olimpics não encontrada, continuando apenas com ClassTest: {str(e)}")
                olympics = []
            else:
                logging.warning(f"Erro ao buscar StudentTestOlimpics, continuando apenas com ClassTest: {str(e)}")
                olympics = []

        class_test_map = {ct.test_id: ct for ct in class_tests}
        olympics_map = {o.test_id: o for o in olympics}
        all_test_ids = list(set(class_test_map.keys()) | set(olympics_map.keys()))

        if not all_test_ids:
            return jsonify({
                'student_id': student.id,
                'class_id': class_id,
                'tests_status': []
            }), 200

        sessions = TestSession.query.filter_by(student_id=student.id).filter(
            TestSession.test_id.in_(all_test_ids)
        ).all()
        sessions_dict = {s.test_id: s for s in sessions}

        tests_status = []
        for tid in all_test_ids:
            ct = class_test_map.get(tid)
            o = olympics_map.get(tid)
            session = sessions_dict.get(tid)

            class_test_id = ct.id if ct else None
            student_test_olimpics_id = o.id if o else None

            if session:
                has_answers = StudentAnswer.query.filter_by(
                    student_id=student.id,
                    test_id=tid
                ).first() is not None
                test_status = {
                    'test_id': tid,
                    'class_test_id': class_test_id,
                    'student_test_olimpics_id': student_test_olimpics_id,
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
                    'test_id': tid,
                    'class_test_id': class_test_id,
                    'student_test_olimpics_id': student_test_olimpics_id,
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
@requires_city_context
def get_session_answers(session_id):
    """
    Retorna todas as respostas de uma sessão específica.
    Apenas o dono da sessão (aluno) pode consultar.
    Para retomar prova, prefira GET /active-session/<test_id>/with-answers (1 chamada em vez de 2).
    """
    try:
        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404

        # Validar que o aluno autenticado é o dono da sessão
        current_user_id = get_jwt_identity()
        current_student = Student.query.filter_by(user_id=current_user_id).first()
        if not current_student or str(current_student.id) != str(session.student_id):
            return jsonify({'error': 'Você não tem permissão para acessar as respostas desta sessão'}), 403
        
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
                'manual_points': getattr(answer, 'manual_score', None),  # modelo usa manual_score
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
@requires_city_context
def get_student_sessions():
    """
    Retorna todas as sessões do aluno logado. Requer contexto de tenant (schema) para acessar Student.
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
        from app.models.studentTestOlimpics import StudentTestOlimpics

        current_user_id = get_jwt_identity()

        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student:
            return jsonify({'error': 'Estudante não encontrado para este usuário'}), 404

        test = Test.query.get(test_id)
        if not test:
            return jsonify({'error': 'Teste não encontrado'}), 404

        # Turma (ClassTest) e/ou olimpíada (StudentTestOlimpics)
        # Ambos funcionam simultaneamente - não há exclusão mútua
        from sqlalchemy.exc import SQLAlchemyError
        class_test = ClassTest.query.filter_by(
            class_id=student.class_id,
            test_id=test_id
        ).first()
        olympics = None
        try:
            olympics = StudentTestOlimpics.query.filter_by(
                student_id=student.id,
                test_id=str(test_id)
            ).first()
        except (SQLAlchemyError, Exception) as e:
            # Se a tabela não existir, continuar apenas com ClassTest
            error_str = str(e).lower()
            if 'student_test_olimpics' in error_str or 'does not exist' in error_str or 'undefinedtable' in error_str:
                logging.warning(f"Tabela student_test_olimpics não encontrada, continuando apenas com ClassTest: {str(e)}")
                olympics = None
            else:
                logging.warning(f"Erro ao buscar StudentTestOlimpics, continuando apenas com ClassTest: {str(e)}")
                olympics = None

        # Priorizar StudentTestOlimpics se ambos existirem (mais específico para o aluno)
        # Ambos funcionam simultaneamente - não há exclusão mútua
        app_record = olympics if olympics else class_test
        if not app_record:
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

        can_start = False
        reason = "Verificando disponibilidade..."

        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id
        ).first()

        has_completed = False
        if session:
            has_completed = session.status in ['finalizada', 'expirada', 'corrigida', 'revisada']

        if has_completed:
            can_start = False
            reason = "Avaliação já foi completada"
        else:
            is_available_now = False
            is_expired = False

            current_time = None
            if app_record.timezone:
                import pytz
                try:
                    target_tz = pytz.timezone(app_record.timezone)
                    current_time = datetime.now(target_tz)
                except pytz.exceptions.UnknownTimeZoneError:
                    from app.utils.timezone_utils import get_local_time
                    current_time = get_local_time()
            else:
                from app.utils.timezone_utils import get_local_time
                current_time = get_local_time()

            if app_record.application and app_record.application is not None:
                try:
                    if app_record.timezone:
                        import pytz
                        try:
                            target_tz = pytz.timezone(app_record.timezone)
                            application_dt = dateutil.parser.parse(app_record.application)
                            if application_dt.tzinfo is None:
                                application_dt = application_dt.replace(tzinfo=target_tz)
                            is_available_now = current_time >= application_dt
                        except pytz.exceptions.UnknownTimeZoneError:
                            logging.warning(f"Timezone inválido: {app_record.timezone}, usando fallback")
                            raise Exception(f"Timezone inválido: {app_record.timezone}")
                    else:
                        application_dt = dateutil.parser.parse(app_record.application)
                        if application_dt.tzinfo is None:
                            application_dt = application_dt.replace(tzinfo=current_time.tzinfo)
                        is_available_now = current_time >= application_dt
                except Exception as e:
                    logging.error(f"Erro ao converter data de aplicação para teste {test_id}: {str(e)}")
                    is_available_now = False
            else:
                is_available_now = False

            if app_record.expiration and app_record.expiration is not None:
                try:
                    if app_record.timezone:
                        import pytz
                        try:
                            target_tz = pytz.timezone(app_record.timezone)
                            expiration_dt = dateutil.parser.parse(app_record.expiration)
                            if expiration_dt.tzinfo is None:
                                expiration_dt = expiration_dt.replace(tzinfo=target_tz)
                            is_expired = current_time > expiration_dt
                        except pytz.exceptions.UnknownTimeZoneError:
                            logging.warning(f"Timezone inválido: {app_record.timezone}, usando fallback")
                            raise Exception(f"Timezone inválido: {app_record.timezone}")
                    else:
                        expiration_dt = dateutil.parser.parse(app_record.expiration)
                        if expiration_dt.tzinfo is None:
                            expiration_dt = expiration_dt.replace(tzinfo=current_time.tzinfo)
                        is_expired = current_time > expiration_dt
                except Exception as e:
                    logging.error(f"Erro ao converter data de expiração para teste {test_id}: {str(e)}")
                    is_expired = False

            if test.status in ['agendada', 'em_andamento']:
                if is_available_now and not is_expired:
                    can_start = True
                    reason = "Avaliação disponível para início"
                elif not is_available_now:
                    can_start = False
                    reason = "Avaliação ainda não está disponível"
                else:
                    can_start = False
                    reason = "Avaliação expirada"
            else:
                can_start = False
                reason = f"Status da avaliação não permite início: {test.status}"

        logging.info(f"DEBUG CAN-START FINAL - Test: {test_id}, Can Start: {can_start}, Reason: {reason}")

        return jsonify({
            'can_start': can_start,
            'reason': reason,
            'test_info': {
                'id': test_id,
                'title': test.title,
                'status': test.status,
                'application': app_record.application if app_record.application else None,
                'expiration': app_record.expiration if app_record.expiration else None
            },
            'student_info': {
                'id': student.id,
                'session_status': session.status if session else 'nao_iniciada',
                'has_completed': has_completed
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao verificar se aluno pode iniciar teste: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar permissão", "details": str(e)}), 500


# ==================== ENDPOINT DE DEBUG ====================

@bp.route('/debug/session/<string:session_id>', methods=['GET'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def debug_session_status(session_id):
    """
    Endpoint de debug para verificar o status detalhado de uma sessão
    """
    try:
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404

        test = Test.query.get(session.test_id)
        from app.models.classTest import ClassTest
        from app.models.studentTestOlimpics import StudentTestOlimpics
        student = session.student
        class_test = None
        if test and student and student.class_id:
            class_test = ClassTest.query.filter_by(
                class_id=student.class_id,
                test_id=session.test_id
            ).first()
        olympics = None
        if student:
            try:
                from sqlalchemy.exc import SQLAlchemyError
                olympics = StudentTestOlimpics.query.filter_by(
                    student_id=session.student_id,
                    test_id=session.test_id
                ).first()
            except (SQLAlchemyError, Exception) as e:
                # Se a tabela não existir, continuar apenas com ClassTest
                error_str = str(e).lower()
                if 'student_test_olimpics' in error_str or 'does not exist' in error_str or 'undefinedtable' in error_str:
                    logging.warning(f"Tabela student_test_olimpics não encontrada, continuando apenas com ClassTest: {str(e)}")
                    olympics = None
                else:
                    logging.warning(f"Erro ao buscar StudentTestOlimpics, continuando apenas com ClassTest: {str(e)}")
                    olympics = None
        # Priorizar StudentTestOlimpics se ambos existirem (mais específico para o aluno)
        # Ambos funcionam simultaneamente - não há exclusão mútua
        app_record = olympics if olympics else class_test

        answers = StudentAnswer.query.filter_by(
            student_id=session.student_id,
            test_id=session.test_id
        ).all()

        debug_info = {
            'session': {
                'id': session.id,
                'student_id': session.student_id,
                'test_id': session.test_id,
                'status': session.status,
                'started_at': session.started_at.isoformat() if session.started_at else None,
                'submitted_at': session.submitted_at.isoformat() if session.submitted_at else None,
                'time_limit_minutes': session.time_limit_minutes,
                'total_questions': session.total_questions,
                'correct_answers': session.correct_answers,
                'score': session.score,
                'grade': session.grade,
                'duration_minutes': session.duration_minutes
            },
            'test': {
                'id': test.id if test else None,
                'title': test.title if test else None,
                'status': test.status if test else None
            },
            'class_test': {
                'id': app_record.id if app_record else None,
                'class_test_id': class_test.id if class_test else None,
                'student_test_olimpics_id': olympics.id if olympics else None,
                'application': app_record.application if app_record else None,
                'expiration': app_record.expiration if app_record else None,
                'timezone': app_record.timezone if app_record else None
            },
            'answers': {
                'total_answers': len(answers),
                'answers_list': [
                    {
                        'question_id': answer.question_id,
                        'answer': answer.answer,
                        'answered_at': answer.answered_at.isoformat() if answer.answered_at else None
                    } for answer in answers
                ]
            }
        }

        return jsonify(debug_info), 200

    except Exception as e:
        logging.error(f"Erro no debug de sessão: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro no debug", "details": str(e)}), 500


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
