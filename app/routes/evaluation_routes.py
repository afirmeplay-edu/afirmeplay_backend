"""
Rotas para avaliações - compatibilidade com frontend
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app.models.test import Test
from app.models.question import Question
from app.models.student import Student
from app.decorators.role_required import role_required, get_current_user_from_token
from datetime import datetime, timedelta
import logging

bp = Blueprint('evaluations', __name__, url_prefix='/evaluations')

@bp.errorhandler(Exception)
def handle_evaluation_error(error):
    """Tratamento global de erros para evaluations"""
    logging.error(f"Erro em evaluations: {str(error)}", exc_info=True)
    return jsonify({
        "error": "Erro interno no servidor",
        "details": str(error)
    }), 500

@bp.route('/ping', methods=['GET'])
def ping_evaluations():
    """Rota de teste para verificar se o blueprint está funcionando"""
    return jsonify({"message": "Evaluations blueprint está funcionando!"}), 200

@bp.route('/<string:test_id>/answers', methods=['POST'])
@jwt_required()
@role_required("student", "admin", "professor", "aluno")
def submit_evaluation_answers(test_id):
    """
    Submete respostas para uma avaliação específica
    Funciona como proxy para o sistema de sessões de student_answer_routes
    
    Body:
    {
        "answers": [
            {
                "question_id": "uuid",
                "answer": "resposta_do_aluno"
            }
        ],
        "student_id": "uuid" (opcional, será inferido do token se não fornecido)
    }
    """
    try:
        data = request.get_json()
        answers = data.get('answers', [])
        student_id = data.get('student_id')
        
        if not answers:
            return jsonify({'error': 'Lista de respostas é obrigatória'}), 400
        
        # Verificar se o teste existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({'error': 'Teste/Avaliação não encontrado'}), 404
        
        # Obter student_id do token se não fornecido
        if not student_id:
            user = get_current_user_from_token()
            if not user:
                return jsonify({'error': 'Usuário não encontrado'}), 401
            
            # Se for um aluno, buscar o student_id
            if user['role'] == 'aluno':
                student = Student.query.filter_by(user_id=user['id']).first()
                if not student:
                    return jsonify({'error': 'Registro de estudante não encontrado'}), 404
                student_id = student.id
            else:
                return jsonify({'error': 'student_id é obrigatório para usuários não-alunos'}), 400
        
        # Verificar se já existe uma sessão ativa para este aluno/teste
        existing_session = TestSession.query.filter_by(
            student_id=student_id,
            test_id=test_id,
            status='em_andamento'
        ).first()
        
        if not existing_session:
            # Criar nova sessão automaticamente
            session = TestSession(
                student_id=student_id,
                test_id=test_id,
                time_limit_minutes=60,  # padrão 60 minutos
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            db.session.add(session)
            db.session.flush()  # Para obter o ID
        else:
            session = existing_session
        
        # Validar se a sessão não expirou
        if session.is_expired:
            session.status = 'expirada'
            db.session.commit()
            return jsonify({
                'error': 'Tempo limite excedido. Sessão expirada.'
            }), 410
        
        # Buscar questões do teste para validação e correção
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
            
            # Verificar se já existe resposta para esta questão
            existing_answer = StudentAnswer.query.filter_by(
                student_id=student_id,
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
                    student_id=student_id,
                    test_id=test_id,
                    question_id=question_id,
                    answer=str(answer)
                )
                db.session.add(student_answer)
            
            saved_answers.append({
                'question_id': question_id,
                'answer': str(answer),
                'answered_at': student_answer.answered_at.isoformat()
            })
            
            # Verificar se a resposta está correta
            question = questions_dict[question_id]
            if question.correct_answer and str(answer).strip().lower() == str(question.correct_answer).strip().lower():
                correct_count += 1
        
        # Finalizar sessão e calcular nota
        total_questions = len(test_questions)
        session.finalize_session(
            correct_answers=correct_count,
            total_questions=total_questions
        )
        
        db.session.commit()
        
        return jsonify({
            'message': 'Respostas enviadas com sucesso',
            'session_id': session.id,
            'test_id': test_id,
            'submitted_at': session.submitted_at.isoformat(),
            'results': {
                'total_questions': session.total_questions,
                'correct_answers': session.correct_answers,
                'score_percentage': session.score,
                'grade': session.grade,
                'answers_saved': len(saved_answers)
            }
        }), 201
        
    except Exception as e:
        logging.error(f"Erro ao submeter respostas da avaliação: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao submeter respostas", "details": str(e)}), 500 