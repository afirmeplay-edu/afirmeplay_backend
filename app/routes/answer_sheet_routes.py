# -*- coding: utf-8 -*-
"""
Rotas para geração e correção de cartões resposta
"""

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators.role_required import role_required, get_current_user_from_token
from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.studentClass import Class
from app.models.student import Student
from app.models.user import User
from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
from app.services.cartao_resposta.answer_sheet_correction_service import AnswerSheetCorrectionService
from app.services.cartao_resposta.correction_new_grid import AnswerSheetCorrectionNewGrid
from app.services.progress_store import (
    create_job, update_item_processing, update_item_done,
    update_item_error, complete_job, get_job
)
from app.models.school import School
from app.models.grades import Grade
from app.models.city import City
from typing import Dict, Optional, List, Any
import logging
import base64
import io
import os
import zipfile
import tempfile
import threading
import uuid
from io import BytesIO
from datetime import datetime

bp = Blueprint('answer_sheets', __name__, url_prefix='/answer-sheets')


def _validate_blocks_config(blocks: List, total_questions: int) -> Optional[str]:
    """
    Valida configuração de blocos personalizados
    
    Args:
        blocks: Lista de blocos definidos pelo frontend
        total_questions: Total de questões esperado
    
    Returns:
        String com mensagem de erro ou None se válido
    """
    # 1. Máximo 4 blocos
    if len(blocks) > 4:
        return f"Máximo de 4 blocos permitidos. Você enviou {len(blocks)} blocos."
    
    if len(blocks) == 0:
        return "Nenhum bloco foi definido."
    
    # 2. Validar cada bloco
    total_from_blocks = 0
    expected_start = 1
    
    for i, block in enumerate(sorted(blocks, key=lambda x: x.get('start_question', 0)), start=1):
        block_id = block.get('block_id', i)
        subject_name = block.get('subject_name', '')
        questions_count = block.get('questions_count', 0)
        start_question = block.get('start_question', 0)
        end_question = block.get('end_question', 0)
        
        # Validar campos obrigatórios
        if not subject_name:
            return f"Bloco {block_id}: 'subject_name' é obrigatório."
        
        if questions_count < 1:
            return f"Bloco {block_id} ({subject_name}): deve ter pelo menos 1 questão."
        
        if questions_count > 26:
            return f"Bloco {block_id} ({subject_name}): máximo de 26 questões por bloco. Você definiu {questions_count}."
        
        # Validar sequência
        if start_question != expected_start:
            return f"Bloco {block_id} ({subject_name}): deveria começar na questão {expected_start}, mas começa em {start_question}."
        
        if end_question - start_question + 1 != questions_count:
            return f"Bloco {block_id} ({subject_name}): contagem inconsistente (start={start_question}, end={end_question}, count={questions_count})."
        
        total_from_blocks += questions_count
        expected_start = end_question + 1
    
    # 3. Total de questões
    if total_from_blocks != total_questions:
        return f"Soma das questões dos blocos ({total_from_blocks}) difere do total informado ({total_questions})."
    
    if total_questions > 104:
        return f"Total de {total_questions} questões excede o máximo de 104 (4 blocos × 26 questões)."
    
    return None


def _generate_complete_structure(num_questions: int, use_blocks: bool,
                                 blocks_config: Dict, questions_options: Dict = None) -> Dict:
    """
    Gera estrutura completa de questões e alternativas por bloco
    Formato (será salvo em blocks_config['topology']):
    {
        "blocks": [
            {
                "block_id": 1,
                "questions": [
                    {"q": 1, "alternatives": ["A", "B"]},
                    {"q": 2, "alternatives": ["A", "B", "C", "D"]},
                    ...
                ]
            },
            ...
        ]
    }
    """
    # Processar questions_options: garantir formato correto
    questions_map = {}
    if questions_options:
        for key, value in questions_options.items():
            try:
                q_num = int(key)
                if isinstance(value, list) and len(value) >= 2:
                    questions_map[q_num] = value
                else:
                    questions_map[q_num] = ['A', 'B', 'C', 'D']
            except (ValueError, TypeError):
                continue
    
    # Se questions_map vazio, preencher com padrão
    if not questions_map:
        for q in range(1, num_questions + 1):
            questions_map[q] = ['A', 'B', 'C', 'D']
    else:
        # Garantir que todas questões existam
        for q in range(1, num_questions + 1):
            if q not in questions_map:
                questions_map[q] = ['A', 'B', 'C', 'D']
    
    # Estrutura topology (apenas blocks)
    topology = {}
    
    # ✅ SEMPRE verificar blocos personalizados primeiro (independente de use_blocks)
    custom_blocks = blocks_config.get('blocks', [])
    
    if custom_blocks:
        # ✅ Blocos personalizados (com disciplinas ou não)
        blocks = []
        for block_def in custom_blocks:
            block_id = block_def.get('block_id')
            subject_name = block_def.get('subject_name')
            start_q = block_def.get('start_question')
            end_q = block_def.get('end_question')
            
            questions = []
            for q_num in range(start_q, end_q + 1):
                alternatives = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
                questions.append({
                    "q": q_num,
                    "alternatives": alternatives
                })
            
            blocks.append({
                "block_id": block_id,
                "subject_name": subject_name,
                "questions": questions
            })
        
        topology["blocks"] = blocks
    elif use_blocks:
        # ✅ Distribuição automática por blocos numerados
        num_blocks = blocks_config.get('num_blocks', 1)
        questions_per_block = blocks_config.get('questions_per_block', 12)
        
        blocks = []
        for block_num in range(1, num_blocks + 1):
            start_question = (block_num - 1) * questions_per_block + 1
            end_question = min(block_num * questions_per_block, num_questions)
            
            questions = []
            for q_num in range(start_question, end_question + 1):
                alternatives = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
                questions.append({
                    "q": q_num,
                    "alternatives": alternatives
                })
            
            blocks.append({
                "block_id": block_num,
                "questions": questions
            })
        
        topology["blocks"] = blocks
    else:
        # ✅ Sem blocos: um único bloco com todas questões
        questions = []
        for q_num in range(1, num_questions + 1):
            alternatives = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
            questions.append({
                "q": q_num,
                "alternatives": alternatives
            })
        
        topology["blocks"] = [{
            "block_id": 1,
            "questions": questions
        }]
    
    return topology


@bp.route('/generate', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def generate_answer_sheets():
    """
    Gera cartões resposta com diferentes escopos (turma, série ou escola)
    
    Body (ESCOPO 1 - Uma turma):
        {
            "title": "Avaliação de Português",
            "num_questions": 48,
            "use_blocks": true,
            "blocks_config": {...},
            "correct_answers": {"1": "A", "2": "B", ...},
            "questions_options": {...} (opcional),
            "test_data": {...},
            "test_id": "uuid" (opcional)
        }
    
    Body (ESCOPO 2 - Todas turmas de uma série):
        {
            "grade_id": "uuid",
            "school_id": "uuid",
            "num_questions": 48,
            ... demais campos
        }
    
    Body (ESCOPO 3 - Todas turmas de uma escola):
        {
            "school_id": "uuid",
            "num_questions": 48,
            ... demais campos
        }
    
    Returns:
        Status 202 com task_id para polling
        - ESCOPO 1: Gera 1 PDF com N páginas (1 por aluno)
        - ESCOPO 2/3: Gera N PDFs (1 por turma), cada um com M páginas
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Validar campos obrigatórios
        num_questions = data.get('num_questions')
        correct_answers = data.get('correct_answers')
        test_data = data.get('test_data', {})
        title = data.get('title', test_data.get('title', 'Cartão Resposta'))
        
        if not num_questions or num_questions <= 0:
            return jsonify({"error": "num_questions deve ser maior que 0"}), 400
        if not correct_answers:
            return jsonify({"error": "correct_answers é obrigatório"}), 400
        
        # ========================================================================
        # ✅ DETERMINAR ESCOPO E BUSCAR TURMAS
        # ========================================================================
        class_id = data.get('class_id')
        grade_id = data.get('grade_id')
        school_id = data.get('school_id')
        
        classes = []
        scope = None
        scope_name = None
        
        if class_id:
            # ESCOPO 1: Uma turma específica
            scope = 'class'
            class_obj = Class.query.get(class_id)
            if not class_obj:
                return jsonify({"error": "Turma não encontrada"}), 404
            classes = [class_obj]
            scope_name = f"Turma {class_obj.name}"
            
        elif grade_id and school_id:
            # ESCOPO 2: Todas turmas de uma série em uma escola
            scope = 'grade'
            from app.models.grades import Grade
            
            grade_obj = Grade.query.get(grade_id)
            if not grade_obj:
                return jsonify({"error": "Série não encontrada"}), 404
            
            classes = Class.query.filter_by(
                grade_id=grade_id,
                school_id=school_id
            ).all()
            
            if not classes:
                return jsonify({"error": "Nenhuma turma encontrada para esta série nesta escola"}), 404
            
            scope_name = f"Série {grade_obj.name}"
            
        elif school_id:
            # ESCOPO 3: Todas turmas de todas séries de uma escola
            scope = 'school'
            from app.models.school import School
            
            school_obj = School.query.get(school_id)
            if not school_obj:
                return jsonify({"error": "Escola não encontrada"}), 404
            
            classes = Class.query.filter_by(school_id=school_id).all()
            
            if not classes:
                return jsonify({"error": "Nenhuma turma encontrada nesta escola"}), 404
            
            scope_name = f"Escola {school_obj.name}"
            
        else:
            return jsonify({"error": "Deve fornecer class_id, grade_id+school_id ou school_id"}), 400
        
        logging.info(f"✅ Escopo determinado: {scope} - {scope_name} ({len(classes)} turma(s))")
        
        # ========================================================================
        # ✅ VALIDAR PERMISSÕES (usuário tem acesso às turmas?)
        # ========================================================================
        if user['role'] == 'professor':
            # Verificar se professor tem acesso às turmas
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                teacher_class_ids = [tc.class_id for tc in TeacherClass.query.filter_by(teacher_id=teacher.id).all()]
                
                # Verificar se todas as turmas estão acessíveis
                for cls in classes:
                    if cls.id not in teacher_class_ids:
                        return jsonify({"error": f"Você não tem acesso à turma {cls.name}"}), 403
        
        elif grade_id:
            # Série inteira
            scope_type = 'grade'
            grade_obj = Grade.query.get(grade_id)
            if not grade_obj:
                return jsonify({"error": "Série não encontrada"}), 404
            
            # Buscar todas as turmas da série
            classes_to_generate = Class.query.filter_by(grade_id=grade_id).all()
            if not classes_to_generate:
                return jsonify({"error": "Nenhuma turma encontrada para esta série"}), 400
        
        elif school_id:
            # Escola inteira
            scope_type = 'school'
            school_obj = School.query.get(school_id)
            if not school_obj:
                return jsonify({"error": "Escola não encontrada"}), 404
            
            # Buscar todas as turmas da escola
            classes_to_generate = Class.query.filter_by(school_id=school_id).all()
            if not classes_to_generate:
                return jsonify({"error": "Nenhuma turma encontrada para esta escola"}), 400
        
        else:
            return jsonify({"error": "Forneça class_id, grade_id ou school_id"}), 400
        
        logging.info(f"[ROTA] ✅ Escopo determinado: {scope_type}, {len(classes_to_generate)} turma(s)")
        
        # ✅ 3. PREPARAR CONFIGURAÇÃO DE BLOCOS
        use_blocks = data.get('use_blocks', False)
        blocks_config = data.get('blocks_config', {})
        
        # ✅ SEMPRE verificar se há blocos personalizados (independente de use_blocks)
        custom_blocks = blocks_config.get('blocks', [])
        
        if custom_blocks:
            # Validar blocos personalizados (disciplinas)
            validation_error = _validate_blocks_config(custom_blocks, num_questions)
            if validation_error:
                return jsonify({"error": validation_error}), 400
            
            # Adicionar campos necessários no nível raiz
            blocks_config['num_blocks'] = len(custom_blocks)
            blocks_config['questions_per_block'] = custom_blocks[0].get('questions_count', 12) if custom_blocks else 12
            blocks_config['use_blocks'] = use_blocks
            blocks_config['separate_by_subject'] = not use_blocks  # true quando usa disciplinas
            
            logging.info(f"[ROTA] ✅ Blocos personalizados: {len(custom_blocks)} blocos, use_blocks={use_blocks}")
        elif use_blocks:
            # Distribuição automática por blocos numerados
            if 'num_blocks' not in blocks_config:
                blocks_config['num_blocks'] = 1
            if 'questions_per_block' not in blocks_config:
                blocks_config['questions_per_block'] = 12
            blocks_config['use_blocks'] = True
            blocks_config['separate_by_subject'] = False
            
            logging.info(f"[ROTA] ✅ Distribuição automática: {blocks_config['num_blocks']} blocos")
        else:
            # Sem blocos - um único bloco com todas as questões
            blocks_config['use_blocks'] = False
            blocks_config['num_blocks'] = 1
            blocks_config['questions_per_block'] = num_questions
            blocks_config['separate_by_subject'] = False
        
        # ✅ 4. GERAR ESTRUTURA COMPLETA (topology)
        questions_options = data.get('questions_options', {})
        complete_structure = _generate_complete_structure(
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            questions_options=questions_options
        )
        blocks_config['topology'] = complete_structure
        
        # ========================================================================
        # ✅ CRIAR 1 GABARITO POR TURMA
        # ========================================================================
        batch_id = str(uuid.uuid4()) if len(classes) > 1 else None
        gabaritos = []
        
        for class_obj in classes:
            # Buscar informações da turma e escola
            cls_school_id = None
            cls_school_name = ''
            cls_grade_name = test_data.get('grade_name', '')
            
            if class_obj.school_id:
                from app.models.school import School
                school = School.query.get(class_obj.school_id)
                if school:
                    cls_school_id = school.id
                    cls_school_name = school.name or ''
            
            # Buscar nome da série se não fornecido
            if not cls_grade_name and class_obj.grade_id:
                from app.models.grades import Grade
                grade_obj = Grade.query.get(class_obj.grade_id)
                if grade_obj:
                    cls_grade_name = grade_obj.name
            
            # Criar gabarito
            gabarito = AnswerSheetGabarito(
                test_id=str(data.get('test_id')) if data.get('test_id') else None,
                class_id=class_obj.id,
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                correct_answers=correct_answers,
                title=test_data.get('title', 'Cartão Resposta'),
                created_by=str(user['id']) if user.get('id') else None,
                school_id=str(cls_school_id) if cls_school_id else None,
                school_name=cls_school_name,
                municipality=test_data.get('municipality', ''),
                state=test_data.get('state', ''),
                grade_name=cls_grade_name,
                institution=test_data.get('institution', ''),
                batch_id=batch_id  # ✅ NOVO: ID do batch (se múltiplas turmas)
            )
            db.session.add(gabarito)
            gabaritos.append(gabarito)
        
        db.session.commit()
        logging.info(f"✅ {len(gabaritos)} gabarito(s) criado(s)")
        
        # Gerar coordenadas para todos os gabaritos
        try:
            from app.services.cartao_resposta.coordinate_generator import CoordinateGenerator
            
            coord_generator = CoordinateGenerator()
            coordinates = coord_generator.generate_coordinates(
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                questions_options=questions_options
            )
            
            # Salvar mesmas coordenadas em todos os gabaritos (mesma estrutura)
            for gabarito in gabaritos:
                gabarito.coordinates = coordinates
            
            db.session.commit()
            logging.info(f"✅ Coordenadas geradas e salvas para {len(gabaritos)} gabarito(s)")
        except Exception as e:
            logging.error(f"[ROTA] ⚠️ Erro ao gerar coordenadas (não crítico): {str(e)}")
        
        # grade_name para test_data: primeiro gabarito ou test_data
        grade_name_for_gabarito = (gabaritos[0].grade_name if gabaritos else '') or test_data.get('grade_name', '')
        
        # ✅ 7. PREPARAR test_data
        test_data_complete = {
            'id': data.get('test_id'),
            'title': title,
            'municipality': test_data.get('municipality', ''),
            'state': test_data.get('state', ''),
            'grade_name': grade_name_for_gabarito,
            'department': test_data.get('department', ''),
            'municipality_logo': test_data.get('municipality_logo'),
            'institution': test_data.get('institution', '')
        }
        
        # ✅ NOVO: Gerar cartões de forma ASSÍNCRONA via Celery (batch)
        from app.services.celery_tasks.answer_sheet_tasks import generate_answer_sheets_batch_async
        
        # Disparar task Celery com lista de gabaritos
        task = generate_answer_sheets_batch_async.delay(
            gabarito_ids=[str(g.id) for g in gabaritos],
            num_questions=num_questions,
            correct_answers=correct_answers,
            test_data=test_data_complete,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            questions_options=questions_options,
            batch_id=batch_id,
            scope=scope
        )
        
        # Preparar informações das turmas
        classes_info = []
        for cls, gab in zip(classes, gabaritos):
            classes_info.append({
                'class_id': str(cls.id),
                'class_name': cls.name,
                'gabarito_id': str(gab.id),
                'grade_name': gab.grade_name
            })
        
        # Retornar resposta imediata com task_id para polling
        return jsonify({
            "status": "processing",
            "message": f"Cartões de resposta sendo gerados em background ({scope}: {scope_name}). Use o task_id para verificar o status.",
            "task_id": task.id,
            "scope": scope,
            "scope_name": scope_name,
            "batch_id": batch_id,
            "gabarito_ids": [str(g.id) for g in gabaritos],
            "classes_count": len(classes),
            "classes": classes_info,
            "num_questions": num_questions,
            "polling_url": f"/answer-sheets/task/{task.id}/status"
        }), 202
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"[ROTA] ❌ Erro ao gerar cartões resposta: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao gerar cartões resposta: {str(e)}"}), 500


@bp.route('/task/<string:task_id>/status', methods=['GET'])
@jwt_required()
def get_answer_sheet_task_status(task_id):
    """
    Consulta o status de uma task Celery de geração de cartões de resposta
    
    Args:
        task_id: ID da task Celery
    
    Returns:
        JSON com status da task:
        - PENDING: Aguardando processamento
        - STARTED: Em execução
        - SUCCESS: Concluída com sucesso
        - FAILURE: Falhou
        - RETRY: Tentando novamente
    """
    try:
        from app.services.celery_tasks.answer_sheet_tasks import generate_answer_sheets_batch_async
        from celery.result import AsyncResult
        
        # Buscar resultado da task
        task_result = AsyncResult(task_id, app=generate_answer_sheets_batch_async.app)
        
        if task_result.state == 'PENDING':
            response = {
                'status': 'pending',
                'message': 'Task aguardando processamento',
                'task_id': task_id
            }
        elif task_result.state == 'STARTED':
            response = {
                'status': 'processing',
                'message': 'Cartões sendo gerados...',
                'task_id': task_id
            }
        elif task_result.state == 'SUCCESS':
            result = task_result.result
            
            # Mostrar avisos se houver
            warnings = []
            if result.get('warning'):
                warnings.append(result['warning'])
            elif result.get('students_count') == 0:
                warnings.append("Nenhum aluno registrado na turma - cartões não foram gerados")
            
            response = {
                'status': 'completed',
                'message': 'Cartões gerados com sucesso',
                'task_id': task_id,
                'warnings': warnings if warnings else None,
                'result': result
            }
        elif task_result.state == 'FAILURE':
            response = {
                'status': 'failed',
                'message': 'Erro ao gerar cartões',
                'task_id': task_id,
                'error': str(task_result.info)
            }
        elif task_result.state == 'RETRY':
            response = {
                'status': 'retrying',
                'message': 'Tentando novamente após erro...',
                'task_id': task_id
            }
        else:
            response = {
                'status': task_result.state.lower(),
                'message': f'Status: {task_result.state}',
                'task_id': task_id
            }
        
        return jsonify(response), 200
        
    except Exception as e:
        logging.error(f"Erro ao consultar status da task {task_id}: {str(e)}")
        return jsonify({"error": f"Erro ao consultar status: {str(e)}"}), 500


# ============================================================================
# FUNÇÃO DE PROCESSAMENTO EM BACKGROUND
# ============================================================================

def process_answer_sheet_batch_in_background(job_id: str, images: list = None):
    """
    Processa correção em lote de cartões resposta em background thread
    
    Args:
        job_id: ID do job para tracking
        images: Lista de imagens em base64
    """
    from app import create_app
    
    # Criar contexto da aplicação para a thread
    app = create_app()
    
    with app.app_context():
        try:
            # Usando novo pipeline OMR robusto
            correction_service = AnswerSheetCorrectionNewGrid(debug=False)
            
            for i, image_base64 in enumerate(images):
                try:
                    # Marcar como processando
                    update_item_processing(job_id, i)
                    
                    # Decodificar imagem
                    if image_base64.startswith('data:image'):
                        image_base64_clean = image_base64.split(',')[1]
                    else:
                        image_base64_clean = image_base64
                    image_data = base64.b64decode(image_base64_clean)
                    
                    # Processar correção com novo pipeline (gabarito_id e student_id vêm do QR code)
                    result = correction_service.corrigir_cartao_resposta(
                        image_data=image_data,
                        auto_detect_qr=True
                    )
                    
                    if result.get('success'):
                        # Buscar nome do aluno se não veio no resultado
                        if not result.get('student_name') and result.get('student_id'):
                            student = Student.query.get(result['student_id'])
                            if student:
                                result['student_name'] = student.name
                        
                        update_item_done(job_id, i, result)
                        logging.info(f"✅ Job {job_id}: Cartão resposta {i+1} processado com sucesso")
                    else:
                        update_item_error(job_id, i, result.get('error', 'Erro desconhecido'))
                        logging.warning(f"❌ Job {job_id}: Cartão resposta {i+1} falhou: {result.get('error')}")
                        
                except Exception as e:
                    update_item_error(job_id, i, str(e))
                    logging.error(f"❌ Job {job_id}: Erro no cartão resposta {i+1}: {str(e)}")
            
            # Marcar job como concluído
            complete_job(job_id)
            logging.info(f"✅ Job {job_id} concluído")
            
        except Exception as e:
            logging.error(f"❌ Erro crítico no job {job_id}: {str(e)}")
            complete_job(job_id)


# ============================================================================
# ROTAS DE CORREÇÃO
# ============================================================================

# ROTA ANTIGA REMOVIDA - Usar /correct-new
# @bp.route('/correct', methods=['POST'])
# def correct_answer_sheet():
#     ... (removida - frontend usa /correct-new)

@bp.route('/correction-progress/<string:job_id>', methods=['GET'])
@jwt_required()
def get_answer_sheet_correction_progress(job_id):
    """
    Consulta progresso de uma correção em lote de cartões resposta
    
    Returns:
    {
        "job_id": "uuid",
        "total": 5,
        "completed": 2,
        "successful": 2,
        "failed": 0,
        "status": "processing",  // "processing" | "completed"
        "percentage": 40.0,
        "items": {
            "0": {"status": "done", "student_id": "xxx", "student_name": "João", ...},
            "1": {"status": "done", "student_id": "yyy", "student_name": "Maria", ...},
            "2": {"status": "processing"},
            "3": {"status": "pending"},
            "4": {"status": "pending"}
        },
        "results": [...]  // Resultados completos quando status = "completed"
    }
    """
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job não encontrado"}), 404
    
    # Calcular porcentagem
    percentage = (job["completed"] / job["total"] * 100) if job["total"] > 0 else 0
    
    response = {
        "job_id": job_id,
        "total": job["total"],
        "completed": job["completed"],
        "successful": job["successful"],
        "failed": job["failed"],
        "status": job["status"],
        "percentage": round(percentage, 1),
        "items": job["items"]
    }
    
    # Incluir resultados completos apenas quando finalizado
    if job["status"] == "completed":
        response["results"] = job["results"]
    
    return jsonify(response), 200


@bp.route('/gabaritos', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def list_gabaritos():
    """
    Lista os gabaritos (cartões resposta gerados) criados pelo usuário atual com paginação
    
    Query Parameters:
        page: Número da página (padrão: 1)
        per_page: Itens por página (padrão: 20)
        class_id: Filtrar por turma (opcional)
        test_id: Filtrar por prova (opcional)
        school_id: Filtrar por escola (opcional)
        title: Filtrar por título (busca parcial, opcional)
    
    Returns:
        Lista de gabaritos criados pelo usuário com informações resumidas
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Obter parâmetros de paginação e filtros
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        class_id = request.args.get('class_id')
        test_id = request.args.get('test_id')
        school_id = request.args.get('school_id')
        title = request.args.get('title')
        
        # Construir query base - filtrar apenas gabaritos criados pelo usuário atual
        query = AnswerSheetGabarito.query.filter(AnswerSheetGabarito.created_by == str(user['id']))
        
        # Aplicar filtros adicionais
        if class_id:
            query = query.filter(AnswerSheetGabarito.class_id == class_id)
        if test_id:
            query = query.filter(AnswerSheetGabarito.test_id == test_id)
        if school_id:
            query = query.filter(AnswerSheetGabarito.school_id == school_id)
        if title:
            query = query.filter(AnswerSheetGabarito.title.ilike(f'%{title}%'))
        
        # Ordenar por data de criação (mais recentes primeiro)
        query = query.order_by(AnswerSheetGabarito.created_at.desc())
        
        # Paginação
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Formatar resultados
        gabaritos = []
        for gabarito in pagination.items:
            # Buscar informações da turma
            class_name = None
            class_students_count = 0
            if gabarito.class_id:
                class_obj = Class.query.get(gabarito.class_id)
                if class_obj:
                    class_name = class_obj.name
                    class_students_count = len(class_obj.students) if class_obj.students else 0
            
            # Buscar informações da série (grade)
            grade_name = None
            total_classes_in_grade = 0
            total_students_in_grade = 0
            if gabarito.grade_id:
                grade_obj = Grade.query.get(gabarito.grade_id)
                if grade_obj:
                    grade_name = grade_obj.name
                    classes_in_grade = Class.query.filter_by(grade_id=gabarito.grade_id).all()
                    total_classes_in_grade = len(classes_in_grade)
                    total_students_in_grade = sum(
                        len(cls.students) if cls.students else 0 
                        for cls in classes_in_grade
                    )
            
            # Buscar informações da escola (school) se necessário
            total_classes_in_school = 0
            total_students_in_school = 0
            if gabarito.scope_type == "school" and gabarito.school_id:
                classes_in_school = Class.query.filter_by(school_id=gabarito.school_id).all()
                total_classes_in_school = len(classes_in_school)
                total_students_in_school = sum(
                    len(cls.students) if cls.students else 0 
                    for cls in classes_in_school
                )
            
            # Determinar contagem baseada no scope_type correto
            final_students_count = 0
            final_classes_count = 0
            
            if gabarito.scope_type == "class":
                final_students_count = class_students_count
                final_classes_count = 1
            elif gabarito.scope_type == "grade":
                final_students_count = total_students_in_grade
                final_classes_count = total_classes_in_grade
            elif gabarito.scope_type == "school":
                final_students_count = total_students_in_school
                final_classes_count = total_classes_in_school
            else:
                # Fallback para scope desconhecido
                final_students_count = total_students_in_grade if total_students_in_grade > 0 else class_students_count
                final_classes_count = total_classes_in_grade if total_classes_in_grade > 0 else 1
            
            # Buscar informações do criador
            creator_name = None
            if gabarito.created_by:
                creator = User.query.get(gabarito.created_by)
                if creator:
                    creator_name = creator.name
            
            # Determinar status (se foi gerado ou não)
            generation_status = "pending"
            if gabarito.minio_url or gabarito.minio_object_name:
                generation_status = "completed"
            
            gabaritos.append({
                "id": str(gabarito.id),
                "test_id": str(gabarito.test_id) if gabarito.test_id else None,
                "class_id": str(gabarito.class_id) if gabarito.class_id else None,
                "class_name": class_name,
                "grade_id": str(gabarito.grade_id) if gabarito.grade_id else None,
                "grade_name": grade_name or gabarito.grade_name,
                "num_questions": gabarito.num_questions,
                "use_blocks": gabarito.use_blocks,
                "title": gabarito.title,
                "school_name": gabarito.school_name,
                "municipality": gabarito.municipality,
                "state": gabarito.state,
                "institution": gabarito.institution,
                # ✅ CONTAGEM CORRIGIDA PARA TODOS OS SCOPE TYPES
                "scope_type": gabarito.scope_type or "class",  # class | grade | school | city
                "generation_status": generation_status,  # pending | completed
                "students_count": final_students_count,
                "classes_count": final_classes_count,
                "minio_url": gabarito.minio_url,
                "can_download": bool(gabarito.minio_url or gabarito.minio_object_name),
                "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None,
                "created_by": str(gabarito.created_by) if gabarito.created_by else None,
                "creator_name": creator_name
            })
        
        return jsonify({
            "gabaritos": gabaritos,
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar gabaritos: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao listar gabaritos: {str(e)}"}), 500


@bp.route('/gabarito/<string:gabarito_id>/download', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def download_gabarito(gabarito_id):
    """
    Retorna URL pré-assinada para download do ZIP de cartões do MinIO
    
    Se o ZIP ainda não foi gerado, retorna erro pedindo para gerar primeiro.
    O ZIP é gerado automaticamente pela task Celery após POST /answer-sheets/generate.
    
    Returns:
        JSON com URL pré-assinada válida por 1 hora
    """
    try:
        from app.services.storage.minio_service import MinIOService
        from datetime import timedelta
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Buscar gabarito
        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404
        
        # Verificar permissão (admin pode baixar qualquer gabarito)
        if user['role'] != 'admin' and gabarito.created_by != str(user['id']):
            return jsonify({"error": "Você não tem permissão para acessar este gabarito"}), 403
        
        # Verificar se ZIP foi gerado no MinIO
        if not gabarito.minio_object_name:
            return jsonify({
                "error": "ZIP de cartões ainda não foi gerado",
                "message": "Use a rota POST /answer-sheets/generate para gerar os cartões primeiro. Após a geração (verifique status via polling), o ZIP estará disponível para download.",
                "gabarito_id": gabarito_id,
                "status": "not_generated"
            }), 400
        
        # Gerar URL pré-assinada (válida por 1 hora)
        minio = MinIOService()
        
        try:
            presigned_url = minio.get_presigned_url(
                bucket_name=gabarito.minio_bucket or minio.BUCKETS['ANSWER_SHEETS'],
                object_name=gabarito.minio_object_name,
                expires=timedelta(hours=1)
            )
            
            # Buscar turma para informações adicionais
            class_obj = Class.query.get(gabarito.class_id) if gabarito.class_id else None
            
            return jsonify({
                "download_url": presigned_url,
                "expires_in": "1 hour",
                "gabarito_id": str(gabarito.id),
                "test_id": str(gabarito.test_id) if gabarito.test_id else None,
                "class_id": str(gabarito.class_id) if gabarito.class_id else None,
                "class_name": class_obj.name if class_obj else None,
                "title": gabarito.title,
                "num_questions": gabarito.num_questions,
                "generated_at": gabarito.zip_generated_at.isoformat() if gabarito.zip_generated_at else None,
                "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None,
                "minio_url": gabarito.minio_url,
                "is_batch": gabarito.batch_id is not None,  # ✅ NOVO
                "batch_id": gabarito.batch_id  # ✅ NOVO
            }), 200
            
        except Exception as minio_error:
            logging.error(f"Erro ao gerar URL pré-assinada: {str(minio_error)}")
            return jsonify({
                "error": "Erro ao gerar URL de download",
                "details": str(minio_error)
            }), 500
        
    except Exception as e:
        logging.error(f"Erro ao baixar gabarito: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao baixar gabarito: {str(e)}"}), 500


@bp.route('/batch/<string:batch_id>/download', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def download_batch(batch_id):
    """
    Retorna URL pré-assinada para download do ZIP de um batch de cartões
    
    Um batch agrupa múltiplas turmas geradas juntas (ex: todas turmas de uma escola).
    O ZIP contém 1 PDF por turma, cada PDF com múltiplas páginas (1 por aluno).
    
    Returns:
        JSON com URL pré-assinada e informações do batch
    """
    try:
        from app.services.storage.minio_service import MinIOService
        from datetime import timedelta
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Buscar qualquer gabarito do batch para obter URL do MinIO
        gabarito = AnswerSheetGabarito.query.filter_by(batch_id=batch_id).first()
        
        if not gabarito:
            return jsonify({"error": "Batch não encontrado"}), 404
        
        # Verificar permissão (admin pode baixar qualquer batch)
        if user['role'] != 'admin' and gabarito.created_by != str(user['id']):
            return jsonify({"error": "Você não tem permissão para acessar este batch"}), 403
        
        # Verificar se ZIP foi gerado
        if not gabarito.minio_object_name:
            return jsonify({
                "error": "ZIP ainda não foi gerado",
                "message": "Aguarde a conclusão da geração dos cartões",
                "batch_id": batch_id,
                "status": "not_generated"
            }), 400
        
        # Buscar todos gabaritos do batch
        gabaritos = AnswerSheetGabarito.query.filter_by(batch_id=batch_id).all()
        
        # Gerar URL pré-assinada (válida por 1 hora)
        minio = MinIOService()
        
        try:
            presigned_url = minio.get_presigned_url(
                bucket_name=gabarito.minio_bucket or minio.BUCKETS['ANSWER_SHEETS'],
                object_name=gabarito.minio_object_name,
                expires=timedelta(hours=1)
            )
            
            # Preparar informações das turmas
            classes_info = []
            for gab in gabaritos:
                class_obj = Class.query.get(gab.class_id) if gab.class_id else None
                classes_info.append({
                    'gabarito_id': str(gab.id),
                    'class_id': str(gab.class_id) if gab.class_id else None,
                    'class_name': class_obj.name if class_obj else None,
                    'grade_name': gab.grade_name,
                    'school_name': gab.school_name
                })
            
            return jsonify({
                "download_url": presigned_url,
                "expires_in": "1 hour",
                "batch_id": batch_id,
                "classes_count": len(gabaritos),
                "classes": classes_info,
                "title": gabarito.title,
                "num_questions": gabarito.num_questions,
                "generated_at": gabarito.zip_generated_at.isoformat() if gabarito.zip_generated_at else None,
                "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None,
                "minio_url": gabarito.minio_url
            }), 200
            
        except Exception as minio_error:
            logging.error(f"Erro ao gerar URL pré-assinada: {str(minio_error)}")
            return jsonify({
                "error": "Erro ao gerar URL de download",
                "details": str(minio_error)
            }), 500
        
    except Exception as e:
        logging.error(f"Erro ao baixar batch: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao baixar batch: {str(e)}"}), 500


@bp.route('/gabarito/<string:gabarito_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_gabarito(gabarito_id):
    """
    Busca informações de um gabarito
    
    Returns:
        Dados do gabarito
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404
        
        return jsonify({
            "id": gabarito.id,
            "test_id": gabarito.test_id,
            "class_id": gabarito.class_id,
            "num_questions": gabarito.num_questions,
            "use_blocks": gabarito.use_blocks,
            "blocks_config": gabarito.blocks_config,
            "correct_answers": gabarito.correct_answers,
            "title": gabarito.title,
            "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar gabarito: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao buscar gabarito: {str(e)}"}), 500


@bp.route('/<string:gabarito_id>', methods=['DELETE'])  # Rota alternativa para compatibilidade
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def delete_gabarito(gabarito_id):
    """
    Exclui um gabarito individual
    
    Returns:
        Confirmação de exclusão
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Buscar gabarito
        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404
        
        # Verificar se o gabarito foi criado pelo usuário atual
        if gabarito.created_by != str(user['id']):
            return jsonify({"error": "Você não tem permissão para excluir este gabarito"}), 403
        
        # Excluir resultados relacionados primeiro
        results_deleted = AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id).delete()
        if results_deleted > 0:
            logging.info(f"Excluídos {results_deleted} resultados relacionados ao gabarito {gabarito_id}")
        
        # Excluir gabarito
        db.session.delete(gabarito)
        db.session.commit()
        
        logging.info(f"Gabarito {gabarito_id} excluído por usuário {user['id']}")
        
        return jsonify({
            "message": "Gabarito excluído com sucesso",
            "gabarito_id": gabarito_id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao excluir gabarito: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao excluir gabarito: {str(e)}"}), 500


@bp.route('/correct-new', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def correct_answer_sheet_new_pipeline():
    """
    🆕 ROTA DE TESTE - Novo Pipeline OMR Robusto
    
    Corrige cartão resposta usando o NOVO pipeline determinístico
    baseado em JSON de topologia.
    
    DIFERENÇAS do pipeline antigo:
    - ✅ Suporta alternativas variáveis (2, 3, 4, 5 opções)
    - ✅ Grid matemático baseado no JSON
    - ✅ Validação rigorosa (rejeita imagens inválidas)
    - ✅ Determinístico (mesma entrada = mesma saída)
    
    Body (JSON):
    {
        "image": "data:image/jpeg;base64,..."
    }
    
    OU upload de arquivo (form-data):
    - Campo: image (arquivo)
    
    Returns:
        Resultado completo da correção com o novo sistema
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        logging.info("🆕 Usando NOVO pipeline OMR robusto (correction_new_grid)")
        
        # Obter imagem
        image_data = None
        
        # Tentar obter de JSON
        try:
            data = request.get_json() or {}
            if 'image' in data:
                single_image = data['image']
                if single_image.startswith('data:image'):
                    single_image_clean = single_image.split(',')[1]
                else:
                    single_image_clean = single_image
                image_data = base64.b64decode(single_image_clean)
        except:
            pass
        
        # Tentar obter de form-data (arquivo)
        if not image_data and 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                image_data = file.read()
        
        # Tentar obter de form-data (base64)
        if not image_data:
            image_base64 = request.form.get('image')
            if image_base64:
                if image_base64.startswith('data:image'):
                    image_base64_clean = image_base64.split(',')[1]
                else:
                    image_base64_clean = image_base64
                image_data = base64.b64decode(image_base64_clean)
        
        if not image_data:
            return jsonify({"error": "Imagem não fornecida"}), 400
        
        # Processar com NOVO pipeline (detecção automática de QR code)
        corrector = AnswerSheetCorrectionNewGrid(debug=False)
        
        result = corrector.corrigir_cartao_resposta(
            image_data=image_data,
            auto_detect_qr=True  # Detecta QR code automaticamente
        )
        
        if result.get('success'):
            # Buscar nome do aluno se tiver student_id
            student_name = None
            if result.get('student_id'):
                student = Student.query.get(result['student_id'])
                if student:
                    student_name = student.name
            
            logging.info(
                f"✅ NOVO PIPELINE: Correção processada com sucesso - "
                f"{result['correct_answers']}/{result['total_questions']} corretas "
                f"({result['score']:.1f}%)"
            )
            
            return jsonify({
                "message": "Correção processada com sucesso (NOVO PIPELINE)",
                "system": "new_grid_pipeline",
                "student_id": result.get('student_id'),
                "student_name": student_name,
                "gabarito_id": result.get('gabarito_id'),
                "test_id": result.get('test_id'),
                "correct": result['correct_answers'],
                "wrong": result['wrong_answers'],
                "blank": result['blank_answers'],
                "invalid": result['invalid_answers'],
                "total": result['total_questions'],
                "score": result['score'],
                "percentage": result['score'],  # Alias para compatibilidade
                # Respostas em múltiplos formatos:
                "detailed_answers": result['detailed_answers'],  # Lista: [{question, marked, correct, is_correct}]
                "student_answers": result['student_answers'],    # Dict: {1: "A", 2: "B"}
                "answer_key": result['answer_key']               # Dict: {1: "C", 2: "D"}
            }), 200
        else:
            return jsonify({
                "error": result.get('error', 'Erro desconhecido na correção'),
                "system": "new_grid_pipeline"
            }), 500
        
    except Exception as e:
        logging.error(f"Erro ao corrigir com novo pipeline: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao corrigir: {str(e)}"}), 500


@bp.route('/gabaritos', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def bulk_delete_gabaritos():
    """
    Exclui múltiplos gabaritos em massa
    
    Body (JSON):
        {
            "ids": ["gabarito_id_1", "gabarito_id_2", ...]
        }
    
    Returns:
        Confirmação de exclusão com estatísticas
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Obter dados da requisição
        data = request.get_json()
        if not data or 'ids' not in data:
            return jsonify({"error": "Lista de 'ids' é obrigatória no corpo da requisição"}), 400
        
        gabarito_ids = data.get('ids', [])
        if not isinstance(gabarito_ids, list):
            return jsonify({"error": "O campo 'ids' deve ser uma lista"}), 400
        
        if not gabarito_ids:
            return jsonify({"message": "Nenhum ID de gabarito fornecido para exclusão"}), 200
        
        # Buscar gabaritos que pertencem ao usuário
        gabaritos_to_delete = AnswerSheetGabarito.query.filter(
            AnswerSheetGabarito.id.in_(gabarito_ids),
            AnswerSheetGabarito.created_by == str(user['id'])
        ).all()
        
        if not gabaritos_to_delete:
            return jsonify({
                "message": "Nenhum gabarito encontrado ou você não tem permissão para excluir os gabaritos fornecidos",
                "deleted_count": 0,
                "requested_count": len(gabarito_ids)
            }), 200
        
        # Contar quantos foram encontrados vs solicitados
        deleted_ids = [str(g.id) for g in gabaritos_to_delete]
        not_found_ids = [gid for gid in gabarito_ids if gid not in deleted_ids]
        
        # Excluir resultados relacionados primeiro
        total_results_deleted = 0
        for gabarito in gabaritos_to_delete:
            results_deleted = AnswerSheetResult.query.filter_by(gabarito_id=str(gabarito.id)).delete()
            total_results_deleted += results_deleted
        
        # Excluir gabaritos
        for gabarito in gabaritos_to_delete:
            db.session.delete(gabarito)
        
        db.session.commit()
        
        if total_results_deleted > 0:
            logging.info(f"Excluídos {total_results_deleted} resultados relacionados aos gabaritos")
        
        logging.info(f"{len(gabaritos_to_delete)} gabaritos excluídos por usuário {user['id']}")
        
        response = {
            "message": f"{len(gabaritos_to_delete)} gabarito(s) excluído(s) com sucesso",
            "deleted_count": len(gabaritos_to_delete),
            "requested_count": len(gabarito_ids),
            "deleted_ids": deleted_ids,
            "results_deleted": total_results_deleted
        }
        
        if not_found_ids:
            response["not_found_or_unauthorized_ids"] = not_found_ids
            response["message"] += f". {len(not_found_ids)} gabarito(s) não encontrado(s) ou sem permissão"
        
        return jsonify(response), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao excluir gabaritos em massa: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao excluir gabaritos: {str(e)}"}), 500


@bp.route('/results', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def list_answer_sheet_results():
    """
    Lista resultados de correção de cartões resposta (AnswerSheetResult)
    
    Query params:
        - gabarito_id (opcional): Filtrar por gabarito específico
        - student_id (opcional): Filtrar por aluno específico
        - page (opcional): Número da página (padrão: 1)
        - per_page (opcional): Resultados por página (padrão: 20, máximo: 100)
    
    Returns:
        Lista de resultados com paginação
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Obter parâmetros de query
        gabarito_id = request.args.get('gabarito_id')
        student_id = request.args.get('student_id')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        
        # Construir query base
        query = AnswerSheetResult.query
        
        # Aplicar filtros
        if gabarito_id:
            query = query.filter_by(gabarito_id=gabarito_id)
        
        if student_id:
            query = query.filter_by(student_id=student_id)
        
        # Filtrar por permissões do usuário
        if user['role'] == 'professor':
            # Professor vê apenas resultados de seus gabaritos
            from app.models.answerSheetGabarito import AnswerSheetGabarito
            gabaritos_ids = [g.id for g in AnswerSheetGabarito.query.filter_by(created_by=user['id']).all()]
            query = query.filter(AnswerSheetResult.gabarito_id.in_(gabaritos_ids))
        
        # Ordenar por data de correção (mais recentes primeiro)
        query = query.order_by(AnswerSheetResult.corrected_at.desc())
        
        # Paginar
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Formatar resultados
        results = []
        for result in pagination.items:
            # Buscar informações do aluno
            student = Student.query.get(result.student_id)
            student_name = student.name if student else "Desconhecido"
            
            # Buscar informações do gabarito
            from app.models.answerSheetGabarito import AnswerSheetGabarito
            gabarito = AnswerSheetGabarito.query.get(result.gabarito_id)
            gabarito_title = gabarito.title if gabarito else "Gabarito não encontrado"
            
            results.append({
                'id': result.id,
                'gabarito_id': result.gabarito_id,
                'gabarito_title': gabarito_title,
                'student_id': result.student_id,
                'student_name': student_name,
                'correct_answers': result.correct_answers,
                'total_questions': result.total_questions,
                'incorrect_answers': result.incorrect_answers,
                'unanswered_questions': result.unanswered_questions,
                'answered_questions': result.answered_questions,
                'score_percentage': result.score_percentage,
                'grade': result.grade,
                'proficiency': result.proficiency,
                'classification': result.classification,
                'corrected_at': result.corrected_at.isoformat() if result.corrected_at else None,
                'detection_method': result.detection_method
            })
        
        return jsonify({
            'results': results,
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }), 200
        
    except Exception as e:
        logging.error(f"❌ Erro ao listar resultados: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro interno do servidor"}), 500


@bp.route('/result/<string:result_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_answer_sheet_result(result_id):
    """
    Busca detalhes de um resultado específico de correção de cartão resposta
    
    Returns:
        Detalhes completos do resultado incluindo respostas detectadas
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Buscar resultado
        result = AnswerSheetResult.query.get(result_id)
        if not result:
            return jsonify({"error": "Resultado não encontrado"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor':
            from app.models.answerSheetGabarito import AnswerSheetGabarito
            gabarito = AnswerSheetGabarito.query.get(result.gabarito_id)
            if not gabarito or gabarito.created_by != user['id']:
                return jsonify({"error": "Você não tem permissão para ver este resultado"}), 403
        
        # Buscar informações do aluno
        student = Student.query.get(result.student_id)
        student_name = student.name if student else "Desconhecido"
        
        # Buscar informações do gabarito
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        gabarito = AnswerSheetGabarito.query.get(result.gabarito_id)
        gabarito_title = gabarito.title if gabarito else "Gabarito não encontrado"
        gabarito_correct_answers = gabarito.correct_answers if gabarito else {}
        
        # Buscar topologia para saber quantas alternativas cada questão tem
        blocks_config = gabarito.blocks_config if gabarito else {}
        topology = blocks_config.get('topology', {}) if isinstance(blocks_config, dict) else {}
        blocks = topology.get('blocks', [])
        
        # Mapear quantas alternativas cada questão tem
        alternatives_map = {}
        for block in blocks:
            for question in block.get('questions', []):
                q_num = question.get('q')
                alternatives = question.get('alternatives', [])
                alternatives_map[q_num] = alternatives
        
        # Construir lista detalhada de questões ordenada
        detailed_questions = []
        detected_answers_dict = result.detected_answers if isinstance(result.detected_answers, dict) else {}
        
        # Obter todas as questões e ordenar numericamente
        all_questions = set(detected_answers_dict.keys()) | set(gabarito_correct_answers.keys())
        sorted_questions = sorted([int(q) for q in all_questions if str(q).isdigit()])
        
        for q_num in sorted_questions:
            q_str = str(q_num)
            student_answer = detected_answers_dict.get(q_str)
            correct_answer = gabarito_correct_answers.get(q_str) or gabarito_correct_answers.get(q_num)
            
            # Determinar número de alternativas
            alternatives = alternatives_map.get(q_num, ['A', 'B', 'C', 'D'])
            num_alternatives = len(alternatives)
            
            # Determinar se acertou
            if student_answer is None:
                status = "blank"
                is_correct = False
            elif student_answer == correct_answer:
                status = "correct"
                is_correct = True
            else:
                status = "incorrect"
                is_correct = False
            
            detailed_questions.append({
                "question": q_num,
                "alternatives": alternatives,
                "num_alternatives": num_alternatives,
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "status": status
            })
        
        return jsonify({
            'id': result.id,
            'gabarito_id': result.gabarito_id,
            'gabarito_title': gabarito_title,
            'student_id': result.student_id,
            'student_name': student_name,
            
            # Estatísticas
            'correct_answers': result.correct_answers,
            'total_questions': result.total_questions,
            'incorrect_answers': result.incorrect_answers,
            'unanswered_questions': result.unanswered_questions,
            'answered_questions': result.answered_questions,
            'score_percentage': result.score_percentage,
            'grade': result.grade,
            'proficiency': result.proficiency,
            'classification': result.classification,
            
            # Metadados
            'corrected_at': result.corrected_at.isoformat() if result.corrected_at else None,
            'detection_method': result.detection_method,
            
            # Questões detalhadas (NOVO - formato simplificado)
            'detailed_questions': detailed_questions
        }), 200
        
    except Exception as e:
        logging.error(f"❌ Erro ao buscar resultado: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro interno do servidor"}), 500


# ============================================================================
# NOVOS ENDPOINTS HIERÁRQUICOS (Escolas → Séries → Turmas)
# ============================================================================

@bp.route('/generate-hierarchical', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def generate_hierarchical_answer_sheets():
    """
    ✅ ENDPOINT DESCONTINUADO
    
    Use POST /answer-sheets/generate com os parâmetros inteligentes:
    - class_id: para gerar para 1 turma
    - grade_id: para gerar para uma série inteira
    - school_id: para gerar para uma escola inteira
    
    A rota /generate agora detecta automaticamente o escopo!
    """
    return jsonify({
        "error": "Endpoint descontinuado",
        "message": "Use POST /answer-sheets/generate com class_id, grade_id ou school_id",
        "example": {
            "school_id": "uuid-escola",
            "num_questions": 48,
            "correct_answers": {"1": "A", "2": "B"},
            "test_data": {"title": "Avaliação"}
        }
    }), 410


@bp.route('/jobs/<job_id>/status', methods=['GET'])
@jwt_required()
def get_job_status(job_id):
    """
    Retorna status REAL da geração com contagem de alunos/turmas REALMENTE gerados
    
    GET /answer-sheets/jobs/uuid/status
    
    ✅ VALIDA NÚMEROS REAIS:
    - Consulta cada AsyncResult para status e resultado
    - Calcula alunos/turmas GERADOS com sucesso (não promessas iniciais)
    - Lista erros específicos de cada turma
    - Marca job "completed" quando todos os tasks finalizarem
    
    Response:
    {
        "job_id": "uuid",
        "gabarito_id": "uuid",
        "status": "processing|completed|failed",
        "progress": {
            "current": 5,
            "total": 10,
            "percentage": 50
        },
        "result": {
            "classes_generated": 4,
            "total_students": 95,
            "successful_classes": 4,
            "failed_classes": 1,
            "scope_type": "grade",
            "minio_url": "https://..."
        },
        "errors": [
            {"class_name": "A", "error": "Turma não tem alunos registrados"}
        ]
    }
    """
    try:
        from celery.result import AsyncResult
        from app.services.celery_tasks.answer_sheet_tasks import generate_answer_sheets_batch_async
        from app.services.progress_store import update_job
        
        current_user_id = get_jwt_identity()
        job = get_job(job_id)
        
        # ✅ Se job não existe na memória, buscar pelo gabarito no banco
        if not job:
            gabarito_from_db = AnswerSheetGabarito.query.filter_by(job_id=job_id).first()
            
            if not gabarito_from_db:
                return jsonify({"error": "Job não encontrado"}), 404
            
            # Validar que o gabarito pertence ao usuário
            if gabarito_from_db.user_id != str(current_user_id):
                return jsonify({"error": "Acesso negado"}), 403
            
            # ✅ Job completado, retornar resultado direto do banco
            return jsonify({
                'job_id': job_id,
                'gabarito_id': str(gabarito_from_db.id),
                'status': 'completed',
                'progress': {
                    'current': 1,
                    'total': 1,
                    'percentage': 100
                },
                'result': {
                    'scope_type': gabarito_from_db.scope_type,
                    'minio_url': gabarito_from_db.minio_url,
                    'download_url': gabarito_from_db.minio_url,
                    'can_download': bool(gabarito_from_db.minio_url),
                    'zip_generated_at': gabarito_from_db.zip_generated_at.isoformat() if gabarito_from_db.zip_generated_at else None
                }
            }), 200

        # Validar que o job pertence ao usuário
        if job.get('user_id') != str(current_user_id):
            return jsonify({"error": "Acesso negado"}), 403

        # ✅ CONSULTAR STATUS REAL DE CADA TASK
        task_ids = job.get('task_ids', [])
        gabarito_id = job.get('gabarito_id')
        completed = 0
        successful = 0
        failed = 0
        classes_generated = 0
        total_students_generated = 0
        errors = []
        
        if task_ids:
            for task_id in task_ids:
                try:
                    task_result = AsyncResult(task_id, app=generate_answer_sheets_batch_async.app)
                    
                    if task_result.state == 'SUCCESS':
                        completed += 1
                        result = task_result.result
                        
                        if result and result.get('success'):
                            successful += 1
                            classes_generated += 1
                            students_count = result.get('students_count', 0)
                            total_students_generated += students_count
                            logging.info(f"✅ Task {task_id}: {result.get('class_name', 'Unknown')} "
                                        f"com {students_count} alunos")
                        else:
                            # Task retornou sucesso na execução, mas sem PDF gerado
                            failed += 1
                            error_msg = result.get('error') if result else 'Erro desconhecido'
                            class_name = result.get('class_name', 'Unknown') if result else 'Unknown'
                            errors.append({
                                'class_name': class_name,
                                'error': error_msg
                            })
                            logging.warning(f"❌ Task {task_id}: {class_name} - {error_msg}")
                                
                    elif task_result.state == 'FAILURE':
                        completed += 1
                        failed += 1
                        error_msg = str(task_result.info) if task_result.info else 'Erro desconhecido'
                        errors.append({
                            'class_name': 'Unknown',
                            'error': error_msg
                        })
                        logging.error(f"❌ Task {task_id} FAILURE: {error_msg}")
                        
                    elif task_result.state in ['PENDING', 'RETRY']:
                        # Task ainda processando
                        pass
                        
                except Exception as e:
                    logging.debug(f"Erro ao consultar task {task_id}: {str(e)}")

        # ✅ DETERMINAR STATUS DO JOB
        job_status = "processing"
        if completed == len(task_ids) and task_ids:
            job_status = "completed"
        
        # ✅ BUSCAR INFORMAÇÕES DO GABARITO
        gabarito = None
        if gabarito_id:
            gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        
        # ✅ PREPARAR RESPOSTA COM NÚMEROS REAIS
        progress = {
            'current': completed,
            'total': len(task_ids),
            'percentage': int((completed / len(task_ids) * 100) if task_ids else 0)
        }
        
        result_data = {
            'classes_generated': classes_generated,
            'total_students': total_students_generated,
            'successful_classes': successful,
            'failed_classes': failed,
            'scope_type': job.get('scope_type', 'unknown'),
            'minio_url': gabarito.minio_url if gabarito else None,
            'download_url': gabarito.minio_url if gabarito else None,
            'can_download': bool(gabarito and gabarito.minio_url),
            'zip_generated_at': gabarito.zip_generated_at.isoformat() if (gabarito and gabarito.zip_generated_at) else None
        }
        
        response = {
            'job_id': job_id,
            'gabarito_id': gabarito_id,
            'status': job_status,
            'progress': progress,
            'result': result_data,
            'errors': errors if errors else None
        }
        
        # ✅ ATUALIZAR JOB NO STORE
        updates = {
            'completed': completed,
            'successful': successful,
            'failed': failed,
            'status': job_status,
            'total_students_generated': total_students_generated,
            'classes_generated': classes_generated
        }
        
        if job_status == "completed" and "completed_at" not in job:
            from datetime import datetime
            updates['completed_at'] = datetime.utcnow().isoformat()
        
        update_job(job_id, updates)
        
        logging.info(f"📊 Job {job_id}: {completed}/{len(task_ids)} tasks, "
                    f"{classes_generated} turmas, {total_students_generated} alunos")
        
        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Erro ao buscar status: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar status"}), 500


@bp.route('/jobs/<job_id>/download', methods=['GET'])
@jwt_required()
def download_job_zip(job_id):
    """
    Faz download de todos os PDFs gerados em um job como ZIP
    
    GET /answer-sheets/jobs/uuid/download
    
    Response:
    - application/zip com todos os PDFs do job
    """
    try:
        current_user_id = get_jwt_identity()
        job = get_job(job_id)
        
        if not job:
            return jsonify({"error": "Job não encontrado"}), 404

        # Validar que o job pertence ao usuário
        if job.get('user_id') != str(current_user_id):
            return jsonify({"error": "Acesso negado"}), 403

        # Status deve ser "completed"
        if job.get('status') != 'completed':
            return jsonify({
                "error": "Job ainda não foi concluído",
                "status": job.get('status')
            }), 400

        from app.services.storage.minio_service import MinIOService
        import shutil
        
        minio = MinIOService()
        
        # Criar diretório temporário para os PDFs
        temp_dir = tempfile.mkdtemp(prefix='job_download_')
        
        try:
            # Buscar todas as tasks do job
            tasks = job.get('tasks', [])
            
            if not tasks:
                return jsonify({"error": "Nenhuma tarefa encontrada para este job"}), 400
            
            # Baixar cada PDF do MinIO
            pdf_count = 0
            for i, task in enumerate(tasks):
                if task.get('status') != 'completed':
                    continue
                
                result = task.get('result', {})
                minio_url = result.get('minio_url')
                
                if not minio_url:
                    logging.warning(f"[DOWNLOAD] Task {i} não tem URL do MinIO")
                    continue
                
                # Extrair object_name da URL
                # Formato: https://files.afirmeplay.com.br/answer-sheets/job_id/filename.pdf
                # object_name esperado: answer-sheets/job_id/filename.pdf
                try:
                    from urllib.parse import urlparse
                    from app.services.storage.minio_service import MinIOService
                    
                    parsed = urlparse(minio_url)
                    
                    # path = /answer-sheets/job_id/filename.pdf
                    # object_name = answer-sheets/job_id/filename.pdf
                    object_name = parsed.path.lstrip('/')
                    
                    # Extrair nome do arquivo para usar como nome local
                    filename = object_name.split('/')[-1]
                    file_path = os.path.join(temp_dir, filename)
                    
                    logging.info(f"[DOWNLOAD] Baixando {filename} do MinIO ({object_name})...")
                    
                    # Baixar arquivo do MinIO
                    pdf_data = minio.download_file(
                        bucket_name=MinIOService.BUCKETS['ANSWER_SHEETS'],
                        object_name=object_name
                    )
                    
                    with open(file_path, 'wb') as f:
                        f.write(pdf_data)
                    
                    pdf_count += 1
                    logging.info(f"[DOWNLOAD] ✅ Baixado: {filename}")
                    
                except Exception as e:
                    logging.error(f"[DOWNLOAD] Erro ao baixar {object_name}: {str(e)}")
                    continue
            
            if pdf_count == 0:
                shutil.rmtree(temp_dir)
                return jsonify({
                    "error": "Nenhum PDF foi encontrado para download"
                }), 400
            
            # Criar ZIP com os PDFs
            zip_filename = f"cartoes-resposta-{job_id}.zip"
            zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
            
            logging.info(f"[DOWNLOAD] Criando ZIP com {pdf_count} PDFs...")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, filename)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, arcname=filename)
            
            logging.info(f"[DOWNLOAD] ✅ ZIP criado: {zip_path}")
            
            # Enviar arquivo para download
            return send_file(
                zip_path,
                as_attachment=True,
                download_name=zip_filename,
                mimetype='application/zip'
            )
            
        finally:
            # Limpar diretório temporário
            try:
                shutil.rmtree(temp_dir)
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except Exception as e:
                logging.warning(f"[DOWNLOAD] Erro ao limpar arquivos temporários: {str(e)}")

    except Exception as e:
        logging.error(f"Erro ao fazer download do job: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao fazer download: {str(e)}"}), 500


# ==================== FUNÇÕES AUXILIARES PARA FILTROS CASCATA ====================

def _obter_estados_disponiveis(user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna estados disponíveis baseado nas permissões do usuário.
    Para CARTÃO RESPOSTA (sem dependência de avaliação).
    """
    if permissao['scope'] == 'all':
        # Admin vê todos os estados
        estados = db.session.query(City.state).distinct().filter(City.state.isnot(None)).all()
    else:
        # Outros usuários veem apenas estados das suas cidades
        estados = db.session.query(City.state).distinct().filter(
            City.state.isnot(None),
            City.id == user.get('city_id')
        ).all()
    
    return [{"id": estado[0], "nome": estado[0]} for estado in estados]


def _obter_municipios_por_estado(estado: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna municípios de um estado específico baseado nas permissões do usuário.
    Para CARTÃO RESPOSTA (sem dependência de avaliação).
    """
    if permissao['scope'] == 'all':
        # Admin vê todos os municípios do estado
        municipios = City.query.filter(City.state.ilike(f"%{estado}%")).all()
    else:
        # Outros usuários veem apenas seu município
        municipios = City.query.filter(
            City.state.ilike(f"%{estado}%"),
            City.id == user.get('city_id')
        ).all()
    
    return [{"id": str(m.id), "nome": m.name} for m in municipios]


def _obter_escolas_por_municipio(municipio_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna escolas de um município específico baseado nas permissões do usuário.
    Para CARTÃO RESPOSTA (sem dependência de avaliação).
    """
    city = City.query.get(municipio_id)
    if not city:
        return []
    
    # Verificar se o usuário tem acesso ao município
    if permissao['scope'] != 'all' and user.get('city_id') != city.id:
        return []
    
    # Aplicar filtros baseados no papel do usuário
    query_escolas = School.query.with_entities(School.id, School.name)\
                           .filter(School.city_id == city.id)
    
    if permissao['scope'] == 'escola':
        if user.get('role') in ['diretor', 'coordenador']:
            # Diretor e Coordenador veem apenas sua escola
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if manager and manager.school_id:
                query_escolas = query_escolas.filter(School.id == manager.school_id)
            else:
                return []
        elif user.get('role') == 'professor':
            # Professor vê apenas escolas onde está vinculado
            from app.models.teacher import Teacher
            from app.models.schoolTeacher import SchoolTeacher
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                teacher_school_ids = [ts.school_id for ts in teacher_schools]
                
                if teacher_school_ids:
                    query_escolas = query_escolas.filter(School.id.in_(teacher_school_ids))
                else:
                    return []
            else:
                return []
    
    escolas = query_escolas.distinct().all()
    return [{"id": str(e[0]), "nome": e[1]} for e in escolas]


def _obter_series_por_escola(escola_id: str, municipio_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna séries (grades) de uma escola específica.
    Para CARTÃO RESPOSTA (sem dependência de avaliação).
    """
    city = City.query.get(municipio_id)
    school = School.query.get(escola_id)
    
    if not city or not school:
        return []
    
    # Verificar se o usuário tem acesso
    if permissao['scope'] != 'all' and user.get('city_id') != city.id:
        return []
    
    if permissao['scope'] == 'escola':
        if user.get('role') in ['diretor', 'coordenador']:
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if not manager or manager.school_id != school.id:
                return []
        elif user.get('role') == 'professor':
            # Verificar se professor está vinculado à escola
            from app.models.teacher import Teacher
            from app.models.schoolTeacher import SchoolTeacher
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return []
            
            teacher_school = SchoolTeacher.query.filter_by(
                teacher_id=teacher.id,
                school_id=school.id
            ).first()
            
            if not teacher_school:
                return []
    
    # Buscar séries da escola
    query_series = db.session.query(Grade.id, Grade.name)\
                             .join(Class, Grade.id == Class.grade_id)\
                             .filter(Class.school_id == school.id)\
                             .distinct()\
                             .order_by(Grade.name)
    
    series = query_series.all()
    return [{"id": str(s[0]), "nome": s[1]} for s in series]


def _obter_turmas_por_serie(escola_id: str, serie_id: str, municipio_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna turmas de uma série específica em uma escola.
    Para CARTÃO RESPOSTA (sem dependência de avaliação).
    """
    city = City.query.get(municipio_id)
    school = School.query.get(escola_id)
    grade = Grade.query.get(serie_id)
    
    if not city or not school or not grade:
        return []
    
    # Verificar permissões
    if permissao['scope'] != 'all' and user.get('city_id') != city.id:
        return []
    
    if permissao['scope'] == 'escola':
        if user.get('role') in ['diretor', 'coordenador']:
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if not manager or manager.school_id != school.id:
                return []
        elif user.get('role') == 'professor':
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return []
    
    # Buscar turmas
    query_turmas = Class.query.with_entities(Class.id, Class.name)\
                              .filter(
                                  Class.school_id == school.id,
                                  Class.grade_id == grade.id
                              )
    
    # Se professor, filtrar apenas turmas onde está vinculado
    if permissao['scope'] == 'escola' and user.get('role') == 'professor':
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        
        teacher = Teacher.query.filter_by(user_id=user['id']).first()
        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        teacher_class_ids = [tc.class_id for tc in teacher_classes]
        
        if teacher_class_ids:
            query_turmas = query_turmas.filter(Class.id.in_(teacher_class_ids))
        else:
            return []
    
    turmas = query_turmas.order_by(Class.name).all()
    return [{"id": str(t[0]), "nome": t[1]} for t in turmas]


# ==================== ENDPOINT: GET /opcoes-filtros ====================

@bp.route('/opcoes-filtros', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_opcoes_filtros():
    """
    Retorna opções hierárquicas de filtros para CARTÃO RESPOSTA.
    Retorna apenas os níveis necessários baseado nos parâmetros fornecidos.
    
    Hierarquia: Estado → Município → Escola → Série → Turma
    
    Query Parameters (todos opcionais, seguindo a hierarquia):
    - estado: Estado selecionado
    - municipio: Município selecionado (requer estado)
    - escola: Escola selecionada (requer municipio)
    - serie: Série selecionada (requer escola)
    
    Exemplos:
    - GET /opcoes-filtros → Retorna apenas estados
    - GET /opcoes-filtros?estado=SP → Retorna estados + municípios de SP
    - GET /opcoes-filtros?estado=SP&municipio=uuid → Retorna estados + municípios + escolas
    - GET /opcoes-filtros?estado=SP&municipio=uuid&escola=uuid → Retorna estados + municípios + escolas + séries
    - GET /opcoes-filtros?estado=SP&municipio=uuid&escola=uuid&serie=uuid → Retorna estados + municípios + escolas + séries + turmas
    """
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        from app.permissions import get_user_permission_scope
        permissao = get_user_permission_scope({
            'id': current_user.id,
            'role': current_user.role,
            'city_id': getattr(current_user, 'city_id', None),
            'tenant_id': getattr(current_user, 'tenant_id', None)
        })
        
        if not permissao['permitted']:
            return jsonify({"error": permissao.get('error', 'Acesso negado')}), 403

        user_dict = {
            'id': current_user.id,
            'role': current_user.role,
            'city_id': getattr(current_user, 'city_id', None)
        }

        # Extrair parâmetros (todos opcionais)
        estado = request.args.get('estado')
        municipio = request.args.get('municipio')
        escola = request.args.get('escola')
        serie = request.args.get('serie')
        
        response = {}
        
        # 1. SEMPRE retornar estados (nível 0)
        response["estados"] = _obter_estados_disponiveis(user_dict, permissao)
        
        # 2. Se estado fornecido, retornar municípios (nível 1)
        if estado:
            response["municipios"] = _obter_municipios_por_estado(estado, user_dict, permissao)
            
            # 3. Se município fornecido, retornar escolas (nível 2)
            if municipio:
                response["escolas"] = _obter_escolas_por_municipio(municipio, user_dict, permissao)
                
                # 4. Se escola fornecido, retornar séries (nível 3)
                if escola:
                    response["series"] = _obter_series_por_escola(escola, municipio, user_dict, permissao)
                    
                    # 5. Se série fornecido, retornar turmas (nível 4)
                    if serie:
                        response["turmas"] = _obter_turmas_por_serie(escola, serie, municipio, user_dict, permissao)
        
        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Erro ao obter opções de filtros: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter opções de filtros", "details": str(e)}), 500


@bp.route('/next-filter-options', methods=['POST'])
@jwt_required()
def get_next_filter_options():
    """
    Retorna próximas opções de filtro (cascata) ✅ Suporta chamadas PARCIAIS
    
    POST /answer-sheets/next-filter-options
    {
        "state": "SP",
        "city": "São Paulo" (obrigatório APENAS para buscar schools/grades/classes),
        "school_id": "uuid-escola" (opcional),
        "grade_id": "uuid-série" (opcional)
    }
    
    Exemplos:
    
    1. Buscar cidades de um estado (PARCIAL):
       {"state": "SP"}
       → Retorna lista de cidades em SP
    
    2. Buscar escolas de uma cidade (PARCIAL):
       {"state": "SP", "city": "São Paulo"}
       → Retorna lista de escolas em São Paulo/SP
    
    3. Buscar séries de uma escola:
       {"state": "SP", "city": "São Paulo", "school_id": "uuid"}
       → Retorna lista de séries da escola
    
    4. Buscar turmas de uma série:
       {"state": "SP", "city": "São Paulo", "school_id": "uuid", "grade_id": "uuid"}
       → Retorna lista de turmas da série
    
    Response (sucesso):
    {
        "current_level": "state|city|school|grade",
        "next_level": "city|school|grade|class|none",
        "options": [
            {
                "id": "uuid",
                "name": "São Paulo",
                "count": 45
            },
            ...
        ]
    }
    
    Response (sem resultados):
    {
        "current_level": "state",
        "next_level": "city",
        "options": [],
        "error": "Nenhuma cidade encontrada para este estado"
    }
    """
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        data = request.get_json()
        state = (data.get('state') or '').strip() if data else ''
        city = (data.get('city') or '').strip() if data else ''
        school_id = (data.get('school_id') or '').strip() or None if data else None
        grade_id = (data.get('grade_id') or '').strip() or None if data else None

        from app.services.cartao_resposta.hierarchical_generator import HierarchicalAnswerSheetGenerator
        
        hier_gen = HierarchicalAnswerSheetGenerator()
        user_dict = {
            'id': current_user.id,
            'email': current_user.email,
            'role': current_user.role,
            'city_id': getattr(current_user, 'city_id', None)
        }

        # Chamar função de validação (agora existe apenas uma)
        result = hier_gen.determine_generation_scope(
            state=state,
            city=city,
            school_id=school_id,
            grade_id=grade_id,
            user=user_dict
        )

        # Se houver validação_errors, retornar erro
        if result.get('validation_errors'):
            return jsonify({
                'error': 'Validação falhou',
                'errors': result['validation_errors']
            }), 400

        return jsonify({
            'scope_type': result['scope_type'],
            'parent_grouping': result['parent_grouping'],
            'city_id': str(result['city_id']),
            'scope': result
        }), 200

    except Exception as e:
        logging.error(f"Erro ao buscar opções de filtro: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar opções"}), 500
