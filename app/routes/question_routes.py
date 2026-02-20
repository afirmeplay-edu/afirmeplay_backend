from flask import Blueprint, request, jsonify
from app.models.question import Question
from app.models.subject import Subject
from app.models.grades import Grade
from app.models.educationStage import EducationStage
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.user import User
from app.models.studentAnswer import StudentAnswer
from app import db
from app.decorators.role_required import get_current_tenant_id
from app.decorators.tenant_required import get_current_tenant_context
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import or_, and_, text
from datetime import datetime
import logging
import base64
import uuid
import os
from PIL import Image
import io
from sqlalchemy.orm import aliased, joinedload, subqueryload
from app.utils.response_formatters import format_question_response, format_test_response

bp = Blueprint('questions', __name__, url_prefix='/questions')

def process_image(image_data, image_type):
    """
    Processa uma imagem em base64 e retorna um dicionário com suas informações
    """
    try:
        # Remove o cabeçalho do base64 se existir
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Decodifica o base64
        image_bytes = base64.b64decode(image_data)
        
        # Abre a imagem com PIL para processamento
        image = Image.open(io.BytesIO(image_bytes))
        
        # Gera um ID único para a imagem
        image_id = str(uuid.uuid4())
        
        # Obtém informações da imagem
        image_info = {
            "id": image_id,
            "type": image_type,
            "size": len(image_bytes),
            "width": image.width,
            "height": image.height,
            "data": image_data  # Mantém o base64 para armazenamento
        }
        
        return image_info
    except Exception as e:
        logging.error(f"Error processing image: {str(e)}")
        raise

def extract_images_from_html(html_content):
    """
    Extrai imagens em base64 do conteúdo HTML
    """
    import re
    images = []
    
    # Procura por tags img com src em base64
    img_pattern = r'<img[^>]+src="(data:image/[^;]+;base64,[^"]+)"[^>]*>'
    matches = re.finditer(img_pattern, html_content)
    
    for match in matches:
        base64_data = match.group(1)
        image_type = base64_data.split(';')[0].split(':')[1]
        image_info = process_image(base64_data, image_type)
        images.append(image_info)
    
    return images

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
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def create_question():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['text', 'type', 'subjectId', 'grade', 'createdBy']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Obter informações do usuário logado
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"error": "User not authenticated"}), 401
        
        user_role = current_user.get('role')
        user_city_id = current_user.get('tenant_id') or current_user.get('city_id')

        # Processa imagens do texto formatado
        images = []
        if data.get('formattedText'):
            images.extend(extract_images_from_html(data['formattedText']))
        
        # Processa imagens da solução formatada
        if data.get('formattedSolution'):
            images.extend(extract_images_from_html(data['formattedSolution']))

        # Validações específicas por tipo de questão
        if data['type'] == 'multipleChoice':
            if not data.get('options') or not isinstance(data.get('options'), list):
                return jsonify({"error": "Multiple choice questions must have alternatives"}), 400
            if not any(alt.get('isCorrect') for alt in data['options']):
                return jsonify({"error": "At least one alternative must be marked as correct"}), 400

        # Normalizar skills: aceitar apenas 1 skill (UUID como string)
        skills_input = data.get('skills')
        skill_value = None
        if skills_input:
            if isinstance(skills_input, list):
                # Se vier array, pegar apenas o primeiro elemento
                skill_value = skills_input[0] if skills_input else None
            else:
                # Se vier string, usar diretamente
                skill_value = skills_input
        
        # Definir scope_type, owner_city_id e owner_user_id baseado na role
        scope_type = None
        owner_city_id = None
        owner_user_id = None
        
        if user_role == 'admin':
            scope_type = 'GLOBAL'
            owner_city_id = None
            owner_user_id = None
        elif user_role == 'tecadm':
            scope_type = 'CITY'
            owner_city_id = user_city_id
            owner_user_id = None
        else:  # professor, coordenador, diretor
            scope_type = 'PRIVATE'
            owner_city_id = None
            owner_user_id = current_user.get('user_id')
        
        question = Question(
            number=data.get('number'),
            text=data.get('text'),
            formatted_text=data.get('formattedText'),
            secondstatement=data.get('secondStatement'),
            images=images,
            subject_id=data.get('subjectId'),
            title=data.get('title'),
            description=data.get('description'),
            command=data.get('command'),
            subtitle=data.get('subtitle'),
            alternatives=data.get('options'),
            skill=skill_value,
            grade_level=data.get('grade'),
            difficulty_level=data.get('difficulty'),
            correct_answer=data.get('solution'),
            formatted_solution=data.get('formattedSolution'),
            question_type=data.get('type'),
            value=data.get('value'),
            topics=data.get('topics'),
            version=data.get('version', 1),
            created_by=data.get('createdBy'),
            last_modified_by=data.get('lastModifiedBy'),
            education_stage_id=data.get('educationStageId'),
            scope_type=scope_type,
            owner_city_id=owner_city_id,
            owner_user_id=owner_user_id
        )

        # MULTITENANT: Todas as questões agora vão para public.question
        # Salvar temporariamente o search_path atual
        current_search_path = db.session.execute(text("SHOW search_path")).fetchone()[0]
        
        # Mudar para public para salvar todas as questões
        db.session.execute(text("SET search_path TO public"))
        
        db.session.add(question)
        db.session.commit()
        
        # Restaurar search_path original
        db.session.execute(text(f"SET search_path TO {current_search_path}"))

        return jsonify({
            "message": "Question created successfully",
            "id": question.id
        }), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating question: {str(e)}", exc_info=True)
        return jsonify({"error": "Error creating question", "details": str(e)}), 500

@bp.route('/debug', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def debug_questions():
    """Endpoint de debug para verificar questões e contexto"""
    try:
        from sqlalchemy import text
        context = get_current_tenant_context()
        
        # Verificar search_path atual
        search_path = db.session.execute(text("SHOW search_path")).scalar()
        
        # Contar questões sem filtro
        total_questions = db.session.execute(text("SELECT COUNT(*) FROM public.question")).scalar()
        
        # Contar por scope_type
        global_count = db.session.execute(text("SELECT COUNT(*) FROM public.question WHERE scope_type = 'GLOBAL'")).scalar()
        city_count = db.session.execute(text("SELECT COUNT(*) FROM public.question WHERE scope_type = 'CITY'")).scalar()
        private_count = db.session.execute(text("SELECT COUNT(*) FROM public.question WHERE scope_type = 'PRIVATE'")).scalar()
        null_scope = db.session.execute(text("SELECT COUNT(*) FROM public.question WHERE scope_type IS NULL")).scalar()
        
        # Contar questões CITY para a cidade atual
        city_questions = 0
        if context and context.city_id:
            city_questions = db.session.execute(
                text("SELECT COUNT(*) FROM public.question WHERE scope_type = 'CITY' AND owner_city_id = :city_id"),
                {"city_id": context.city_id}
            ).scalar()
        
        # Testar query ORM
        orm_count = Question.query.count()
        
        return jsonify({
            "context": {
                "city_id": context.city_id if context else None,
                "city_slug": context.city_slug if context else None,
                "schema": context.schema if context else None,
                "has_tenant_context": context.has_tenant_context if context else False
            },
            "database": {
                "search_path": search_path,
                "total_questions": total_questions,
                "global_questions": global_count,
                "city_questions": city_count,
                "private_questions": private_count,
                "null_scope": null_scope,
                "city_specific_questions": city_questions
            },
            "orm": {
                "questions_found": orm_count
            },
            "info": "Todas as questões agora estão em public.question com scope_type: GLOBAL, CITY ou PRIVATE"
        }), 200
    except Exception as e:
        logging.error(f"Error in debug endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def list_questions():
    try:
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401

        test_id = request.args.get('test_id')
        question_type = request.args.get('type')
        subject_id = request.args.get('subject_id')
        created_by = request.args.get('created_by')
        
        
        
        # Se um test_id foi fornecido, retorna a avaliação completa com suas questões
        if test_id:
            test = Test.query.options(
                joinedload(Test.creator),
                joinedload(Test.subject_rel),
                joinedload(Test.grade),
                subqueryload(Test.test_questions).subqueryload(TestQuestion.question).options(
                    joinedload(Question.subject),
                    joinedload(Question.grade),
                    joinedload(Question.education_stage),
                    joinedload(Question.creator),
                    joinedload(Question.last_modifier)
                )
            ).get(test_id)
            
            if not test:
                return jsonify({"error": "Test not found"}), 404
            
            # Verifica permissões do usuário
            if user['role'] == 'professor' and test.created_by != user['id']:
                return jsonify({"error": "Access denied"}), 403
            
            return jsonify(format_test_response(test)), 200
        
        # Se não foi fornecido test_id, retorna apenas as questões (comportamento original)
        
        
        # FILTRO MULTITENANT: Aplicar escopo de questões
        context = get_current_tenant_context()
        
        
        # Salvar search_path atual
        current_search_path = db.session.execute(text("SHOW search_path")).fetchone()[0]
        
        # Forçar busca em public.question (todas as questões agora estão aqui)
        db.session.execute(text("SET search_path TO public"))
        
        query = Question.query.options(
            joinedload(Question.subject),
            joinedload(Question.grade),
            joinedload(Question.education_stage),
            joinedload(Question.creator),
            joinedload(Question.last_modifier)
        )
        
        # Construir filtros de scope baseado na role e contexto
        scope_filters = []
        
        # 1. GLOBAL: todos podem ver
        scope_filters.append(Question.scope_type == 'GLOBAL')
        
        # 2. CITY: apenas do município atual (se tiver contexto)
        if context and context.city_id:
            scope_filters.append(
                and_(
                    Question.scope_type == 'CITY',
                    Question.owner_city_id == context.city_id
                )
            )
        
        # 3. PRIVATE: apenas do próprio usuário
        if user.get('id'):
            scope_filters.append(
                and_(
                    Question.scope_type == 'PRIVATE',
                    Question.owner_user_id == user.get('id')
                )
            )
        
        # Aplicar filtro de scope (OR entre todos os filtros)
        query = query.filter(or_(*scope_filters))
        
        # Aplicar filtros adicionais
        if question_type:
            query = query.filter(Question.question_type == question_type)
        if subject_id:
            query = query.filter(Question.subject_id == subject_id)
        
        # FILTRO created_by: se fornecido na URL, SEMPRE aplicar
        if created_by:
            query = query.filter(Question.created_by == created_by)
        
        questions = query.all()
        
        
        # Restaurar search_path original
        db.session.execute(text(f"SET search_path TO {current_search_path}"))
        
        return jsonify([format_question_response(q) for q in questions]), 200

    except Exception as e:
        logging.error(f"Error listing questions: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing questions", "details": str(e)}), 500

@bp.route('/<string:question_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def get_question(question_id):
    try:
        question = Question.query.options(
            joinedload(Question.subject),
            joinedload(Question.grade),
            joinedload(Question.education_stage),
            joinedload(Question.creator),
            joinedload(Question.last_modifier)
        ).get(question_id)

        if not question:
            return jsonify({"error": "Question not found"}), 404

        return jsonify(format_question_response(question)), 200

    except Exception as e:
        logging.error(f"Error getting question: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting question", "details": str(e)}), 500


@bp.route('/<string:question_id>/quantidade-respostas', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_question_answer_count(question_id):
    """
    Retorna a quantidade de vezes que uma questão foi respondida (total de
    registros em StudentAnswer para essa question_id).
    """
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({"error": "Questão não encontrada"}), 404
        quantidade = StudentAnswer.query.filter(StudentAnswer.question_id == question_id).count()
        return jsonify({
            "question_id": question_id,
            "quantidade": quantidade,
        }), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao buscar quantidade de respostas", "details": str(e)}), 500
    except Exception as e:
        logging.error(f"Error getting question answer count: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar quantidade de respostas", "details": str(e)}), 500


@bp.route('/<string:question_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def update_question(question_id):
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({"error": "Question not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # 🔥 DETECÇÃO DE MUDANÇA DE GABARITO
        # Armazenar resposta correta antiga antes de atualizar
        old_correct_answer = question.correct_answer
        new_correct_answer = data.get('solution')  # 'solution' mapeia para 'correct_answer'
        
        # Verificar se houve mudança no gabarito
        gabarito_changed = (
            new_correct_answer is not None and 
            old_correct_answer != new_correct_answer and
            old_correct_answer is not None  # Só recalcular se já existia gabarito
        )

        # Mapeia chaves do JSON (camelCase) para atributos do modelo (snake_case)
        field_map = {
            'number': 'number',
            'text': 'text',
            'formattedText': 'formatted_text',
            'subjectId': 'subject_id',
            'title': 'title',
            'description': 'description',
            'command': 'command',
            'secondStatement': 'secondstatement',
            'subtitle': 'subtitle',
            'options': 'alternatives',
            'skills': 'skill',
            'grade': 'grade_level',
            'educationStageId': 'education_stage_id',
            'difficulty': 'difficulty_level',
            'solution': 'correct_answer',
            'formattedSolution': 'formatted_solution',
            # 'test_id': 'test_id',  # REMOVIDO - agora usamos tabela de associação
            'type': 'question_type',
            'value': 'value',
            'topics': 'topics',
            'lastModifiedBy': 'last_modified_by'
        }

        for json_key, model_attr in field_map.items():
            if json_key in data:
                setattr(question, model_attr, data[json_key])
        
        # Tratar skills separadamente para normalizar (apenas 1 skill permitida)
        if 'skills' in data:
            skills_input = data['skills']
            if isinstance(skills_input, list):
                # Se vier array, pegar apenas o primeiro elemento
                question.skill = skills_input[0] if skills_input else None
            else:
                # Se vier string, usar diretamente
                question.skill = skills_input
        
        question.version += 1

        db.session.commit()
        
        # 🔥 RECÁLCULO AUTOMÁTICO DE RESULTADOS SE GABARITO MUDOU
        recalculation_info = None
        if gabarito_changed:
            logging.info(
                f"🔄 Gabarito alterado para questão {question_id}: "
                f"{old_correct_answer} → {new_correct_answer}"
            )
            
            try:
                from app.services.celery_tasks.evaluation_recalculation_tasks import (
                    recalculate_results_after_answer_correction,
                    trigger_recalculation_sync
                )
                
                # Buscar provas que usam essa questão
                test_questions = TestQuestion.query.filter_by(question_id=question_id).all()
                test_ids = [tq.test_id for tq in test_questions]
                
                if test_ids:
                    # Contar quantos alunos únicos responderam essa questão
                    student_answers = StudentAnswer.query.filter(
                        StudentAnswer.question_id == question_id,
                        StudentAnswer.test_id.in_(test_ids)
                    ).all()
                    
                    student_ids = list(set([sa.student_id for sa in student_answers]))
                    total_students = len(student_ids)
                    
                    logging.info(
                        f"📊 Impacto da mudança de gabarito:\n"
                        f"  - Provas afetadas: {len(test_ids)}\n"
                        f"  - Alunos afetados: {total_students}"
                    )
                    
                    # Decidir entre síncrono ou assíncrono baseado no threshold
                    ASYNC_THRESHOLD = 20  # A partir de 20 alunos, usar assíncrono
                    
                    if total_students < ASYNC_THRESHOLD:
                        # RECÁLCULO SÍNCRONO (poucos alunos)
                        logging.info(f"⚡ Recálculo SÍNCRONO ({total_students} alunos)")
                        
                        modified_by = data.get('lastModifiedBy', 'unknown')
                        result = trigger_recalculation_sync(
                            question_id=question_id,
                            old_answer=str(old_correct_answer),
                            new_answer=str(new_correct_answer),
                            modified_by=modified_by,
                            student_ids=student_ids
                        )
                        
                        recalculation_info = {
                            'status': 'completed',
                            'mode': 'sync',
                            'tests_affected': result.get('tests_affected', 0),
                            'students_recalculated': result.get('students_recalculated', 0),
                            'errors': len(result.get('errors', []))
                        }
                        
                    else:
                        # RECÁLCULO ASSÍNCRONO (muitos alunos)
                        logging.info(f"🚀 Recálculo ASSÍNCRONO ({total_students} alunos)")
                        
                        modified_by = data.get('lastModifiedBy', 'unknown')
                        task = recalculate_results_after_answer_correction.delay(
                            question_id=question_id,
                            old_answer=str(old_correct_answer),
                            new_answer=str(new_correct_answer),
                            modified_by=modified_by
                        )
                        
                        recalculation_info = {
                            'status': 'processing',
                            'mode': 'async',
                            'task_id': task.id,
                            'tests_affected': len(test_ids),
                            'students_to_recalculate': total_students,
                            'message': 'Recálculo em andamento em background'
                        }
                        
                else:
                    recalculation_info = {
                        'status': 'skipped',
                        'reason': 'Questão não está em nenhuma prova'
                    }
                    
            except Exception as e:
                logging.error(
                    f"❌ Erro ao disparar recálculo para questão {question_id}: {str(e)}",
                    exc_info=True
                )
                recalculation_info = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Preparar resposta
        response = {
            'message': 'Question updated successfully',
            'question_id': question_id,
            'version': question.version
        }
        
        # Incluir informações de recálculo se houve mudança de gabarito
        if recalculation_info:
            response['gabarito_changed'] = True
            response['old_answer'] = old_correct_answer
            response['new_answer'] = new_correct_answer
            response['recalculation'] = recalculation_info
        
        return jsonify(response), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating question: {str(e)}", exc_info=True)
        return jsonify({"error": "Error updating question", "details": str(e)}), 500

@bp.route('', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def bulk_delete_questions():
    """ Rota para deletar múltiplas questões em massa. """
    try:
        data = request.get_json()
        if not data or 'ids' not in data or not isinstance(data['ids'], list):
            return jsonify({"error": "A list of 'ids' is required in the request body"}), 400

        question_ids = data['ids']
        if not question_ids:
            return jsonify({"message": "No question IDs provided to delete"}), 200

        # Filtra as questões a serem deletadas
        questions_to_delete = Question.query.filter(Question.id.in_(question_ids)).all()

        if not questions_to_delete:
            return jsonify({"error": "None of the provided question IDs were found"}), 404

        for question in questions_to_delete:
            db.session.delete(question)
        
        db.session.commit()

        return jsonify({'message': f'{len(questions_to_delete)} questions deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error bulk deleting questions: {str(e)}", exc_info=True)
        return jsonify({"error": "Error bulk deleting questions", "details": str(e)}), 500

@bp.route('/<string:question_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def delete_question(question_id):
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({"error": "Question not found"}), 404

        db.session.delete(question)
        db.session.commit()
        return jsonify({'message': 'Question deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting question: {str(e)}", exc_info=True)
        return jsonify({"error": "Error deleting question", "details": str(e)}), 500