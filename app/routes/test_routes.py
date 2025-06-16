from flask import Blueprint, request, jsonify, abort
from app.models.test import Test
from app.models.question import Question
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime
import logging

bp = Blueprint('tests', __name__, url_prefix="/test")

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
def criar_avaliacao():
    try:
        data = request.get_json()
        logging.info(f"Recebendo requisição POST para criar avaliação: {data}")
        
        if not data:
            logging.error("Nenhum dado fornecido na requisição")
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['title', 'type', 'model', 'course', 'created_by']
        for field in required_fields:
            if field not in data:
                logging.error(f"Campo obrigatório ausente: {field}")
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Validação específica para cada tipo de avaliação
        if data['type'] == 'SIMULADO':
            if not data.get('subjects_info'):
                logging.error("Informações de disciplinas ausentes para tipo SIMULADO")
                return jsonify({"error": "Subjects information is required for SIMULADO type"}), 400
        elif data['type'] == 'AVALIACAO':
            if not data.get('subject'):
                logging.error("Disciplina ausente para tipo AVALIACAO")
                return jsonify({"error": "Subject is required for AVALIACAO type"}), 400

        logging.info("Criando nova avaliação com os dados fornecidos")
        print(data)
        nova_avaliacao = Test(
            title=data.get('title'),
            description=data.get('description'),
            type=data.get('type'),
            subject=data.get('subject'),
            grade_id=data.get('grade_id'),
            intructions=data.get('intructions'),
            max_score=data.get('max_score'),
            time_limit=datetime.fromisoformat(data.get('time_limit')) if data.get('time_limit') else None,
            created_by=data.get('created_by'),
            municipalities=data.get('municipalities'),
            schools=data.get('schools'),
            course=data.get('course'),
            model=data.get('model'),
            subjects_info=data.get('subjects_info')
        )

        # Adiciona questões se fornecidas
        if 'questions' in data and isinstance(data['questions'], list):
            for question_data in data['questions']:
                # Cria uma nova questão sem verificar se já existe
                question = Question(
                    number=question_data.get('number'),
                    text=question_data.get('text'),
                    formatted_text=question_data.get('formattedText'),
                    subject_id=question_data.get('subjectId'),
                    title=question_data.get('title'),
                    description=question_data.get('description'),
                    command=question_data.get('command'),
                    subtitle=question_data.get('subtitle'),
                    alternatives=question_data.get('options'),
                    skill=question_data.get('skills'),
                    grade_level=question_data.get('grade'),
                    difficulty_level=question_data.get('difficulty'),
                    correct_answer=question_data.get('solution'),
                    formatted_solution=question_data.get('formattedSolution'),
                    question_type=question_data.get('type'),
                    value=question_data.get('value'),
                    topics=question_data.get('topics'),
                    created_by=data.get('created_by')
                )
                db.session.add(question)
                nova_avaliacao.questions.append(question)

        db.session.add(nova_avaliacao)
        db.session.commit()

        return jsonify({
            "message": "Test created successfully",
            "id": nova_avaliacao.id
        }), 201

    except ValueError as e:
        return jsonify({"error": "Invalid date format", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating test: {str(e)}", exc_info=True)
        return jsonify({"error": "Error creating test", "details": str(e)}), 500

@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_avaliacoes():
    try:
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            return jsonify({"error": "Tenant ID not found"}), 400

        avaliacoes = Test.query.filter_by(tenant_id=tenant_id).all()
        
        resultado = [{
            'id': a.id,
            'title': a.title,
            'description': a.description,
            'type': a.type,
            'subject': a.subject,
            'grade_id': str(a.grade_id) if a.grade_id else None,
            'max_score': a.max_score,
            'time_limit': a.time_limit.isoformat() if a.time_limit else None,
            'created_by': a.created_by,
            'created_at': a.created_at.isoformat() if a.created_at else None,
            'updated_at': a.updated_at.isoformat() if a.updated_at else None,
            'municipalities': a.municipalities,
            'schools': a.schools,
            'course': a.course,
            'model': a.model,
            'subjects_info': a.subjects_info,
            'questions': [
                {
                    'id': q.id,
                    'title': q.title,
                    'question_type': q.question_type,
                    'command': q.command
                }
                for q in a.questions
            ]
        } for a in avaliacoes]

        return jsonify(resultado), 200

    except Exception as e:
        logging.error(f"Error listing tests: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing tests", "details": str(e)}), 500

@bp.route('/user/<string:user_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_avaliacoes_por_usuario(user_id):
    try:
        # Obtém o usuário atual do token
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Se o user_id for 'me', usa o ID do usuário atual
        if user_id == 'me':
            user_id = user['id']

        # Obtém o tenant_id apenas se não for admin
        tenant_id = None
        if user['role'] != "admin":
            tenant_id = get_current_tenant_id()
            if not tenant_id:
                return jsonify({"error": "Tenant ID not found"}), 400

        # Monta a query base
        query = Test.query
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        query = query.filter_by(created_by=user_id)
        
        avaliacoes = query.all()
        
        if not avaliacoes:
            return jsonify({"message": "Nenhuma avaliação encontrada para este usuário"}), 404

        resultado = [{
            'id': a.id,
            'title': a.title,
            'description': a.description,
            'type': a.type,
            'subject': a.subject,
            'grade_id': str(a.grade_id) if a.grade_id else None,
            'max_score': a.max_score,
            'time_limit': a.time_limit.isoformat() if a.time_limit else None,
            'created_by': a.created_by,
            'created_at': a.created_at.isoformat() if a.created_at else None,
            'updated_at': a.updated_at.isoformat() if a.updated_at else None,
            'municipalities': a.municipalities,
            'schools': a.schools,
            'course': a.course,
            'model': a.model,
            'subjects_info': a.subjects_info,
            'questions': [
                {
                    'id': q.id,
                    'title': q.title,
                    'question_type': q.question_type,
                    'command': q.command
                }
                for q in a.questions
            ]
        } for a in avaliacoes]

        return jsonify(resultado), 200

    except Exception as e:
        logging.error(f"Erro ao listar avaliações do usuário: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar avaliações do usuário", "details": str(e)}), 500

@bp.route('/<string:test_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def obter_avaliacao(test_id):
    try:
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        return jsonify({
            'id': test.id,
            'title': test.title,
            'description': test.description,
            'type': test.type,
            'subject': test.subject,
            'grade_id': str(test.grade_id) if test.grade_id else None,
            'max_score': test.max_score,
            'time_limit': test.time_limit.isoformat() if test.time_limit else None,
            'created_by': test.created_by,
            'created_at': test.created_at.isoformat() if test.created_at else None,
            'updated_at': test.updated_at.isoformat() if test.updated_at else None,
            'municipalities': test.municipalities,
            'schools': test.schools,
            'course': test.course,
            'model': test.model,
            'subjects_info': test.subjects_info,
            'questions': [
                {
                    'id': q.id,
                    'title': q.title,
                    'question_type': q.question_type,
                    'command': q.command
                }
                for q in test.questions
            ]
        }), 200

    except Exception as e:
        logging.error(f"Error getting test: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting test", "details": str(e)}), 500

@bp.route('/<string:test_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def atualizar_avaliacao(test_id):
    try:
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        campos = [
            'title', 'description', 'type', 'subject', 'grade_id',
            'max_score', 'time_limit', 'intructions', 'municipalities',
            'schools', 'course', 'model', 'subjects_info'
        ]

        for campo in campos:
            if campo in data:
                if campo == 'time_limit' and data[campo]:
                    setattr(test, campo, datetime.fromisoformat(data[campo]))
                else:
                    setattr(test, campo, data[campo])

        if 'questions' in data and isinstance(data['questions'], list):
            test.questions = []
            for question_data in data['questions']:
                question = Question.query.get(question_data['id'])
                if question:
                    test.questions.append(question)
                else:
                    return jsonify({"error": f"Question with ID {question_data['id']} not found"}), 404

        db.session.commit()
        return jsonify({'message': 'Test updated successfully'}), 200

    except ValueError as e:
        return jsonify({"error": "Invalid date format", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating test: {str(e)}", exc_info=True)
        return jsonify({"error": "Error updating test", "details": str(e)}), 500

@bp.route('/<string:test_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def deletar_avaliacao(test_id):
    try:
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        db.session.delete(test)
        db.session.commit()
        return jsonify({'message': 'Test deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting test: {str(e)}", exc_info=True)
        return jsonify({"error": "Error deleting test", "details": str(e)}), 500