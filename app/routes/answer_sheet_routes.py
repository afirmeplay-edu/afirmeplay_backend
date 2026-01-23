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
from typing import Dict, Optional, List
import logging
import base64
import io
import zipfile
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
    
    # Estrutura topology (sem use_blocks, apenas blocks)
    topology = {}
    
    if use_blocks:
        custom_blocks = blocks_config.get('blocks', [])
        
        if custom_blocks:
            # ✅ NOVO: Blocos personalizados com disciplinas
            blocks = []
            for block_def in custom_blocks:
                block_id = block_def.get('block_id')
                subject_name = block_def.get('subject_name')  # ✅ NOVO
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
                    "subject_name": subject_name,  # ✅ NOVO
                    "questions": questions
                })
        else:
            # ✅ Fallback: distribuir automaticamente (comportamento original)
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
        # Sem blocos: um único bloco com todas questões
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
    Gera cartões resposta para uma turma e retorna como arquivo ZIP
    
    Body:
        {
            "class_id": "uuid",
            "num_questions": 48,
            "use_blocks": true,
            "blocks_config": {
                "num_blocks": 4,
                "questions_per_block": 12,
                "separate_by_subject": false
            },
            "correct_answers": {
                "1": "A",
                "2": "B",
                ...
            },
            "questions_options": {
                "1": ["A", "B", "C"],
                "2": ["A", "B", "C", "D"],
                ...
            } (opcional - se omitido, usa A, B, C, D para todas),
            "test_data": {
                "title": "Nome da Prova",
                "municipality": "...",
                "state": "...",
                ...
            },
            "test_id": "uuid" (opcional)
        }
    
    Returns:
        Arquivo ZIP contendo todos os PDFs dos cartões resposta
        O ZIP também contém um arquivo metadata.json com informações do gabarito
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Validar campos obrigatórios
        class_id = data.get('class_id')
        num_questions = data.get('num_questions')
        correct_answers = data.get('correct_answers')
        questions_options = data.get('questions_options')  # Opcional
        test_data = data.get('test_data', {})
        
        if not class_id:
            return jsonify({"error": "class_id é obrigatório"}), 400
        if not num_questions or num_questions <= 0:
            return jsonify({"error": "num_questions deve ser maior que 0"}), 400
        if not correct_answers:
            return jsonify({"error": "correct_answers é obrigatório"}), 400
        
        # Validar turma
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({"error": "Turma não encontrada"}), 404
        
        # Validar permissões
        if user['role'] == 'professor':
            # Verificar se professor tem acesso à turma
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                teacher_class = TeacherClass.query.filter_by(
                    teacher_id=teacher.id,
                    class_id=class_id
                ).first()
                if not teacher_class:
                    return jsonify({"error": "Você não tem acesso a esta turma"}), 403
        
        # Configuração de blocos
        use_blocks = data.get('use_blocks', False)
        blocks_config = data.get('blocks_config', {})
        if use_blocks:
            blocks_config['use_blocks'] = True
            
            # ✅ NOVO: Validar blocos personalizados se fornecidos
            custom_blocks = blocks_config.get('blocks', [])
            
            if custom_blocks:
                # Validar blocos personalizados (com disciplinas)
                validation_error = _validate_blocks_config(custom_blocks, num_questions)
                if validation_error:
                    return jsonify({"error": validation_error}), 400
                
                logging.info(f"✅ Blocos personalizados validados: {len(custom_blocks)} blocos")
            else:
                # Fallback: distribuir automaticamente (comportamento original)
                if 'num_blocks' not in blocks_config:
                    blocks_config['num_blocks'] = 1
                if 'questions_per_block' not in blocks_config:
                    blocks_config['questions_per_block'] = 12
                
                logging.info(f"✅ Usando distribuição automática de blocos")
        
        # Gerar estrutura completa de questões e alternativas por bloco
        # Isso será usado na correção como "contrato" da estrutura
        questions_options = data.get('questions_options', {})
        complete_structure = _generate_complete_structure(
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            questions_options=questions_options
        )
        
        # Adicionar estrutura completa ao blocks_config como 'topology'
        blocks_config['topology'] = complete_structure
        
        # Buscar informações da turma e escola para salvar no gabarito
        school_id = None
        school_name = ''
        if class_obj.school_id:
            from app.models.school import School
            school = School.query.get(class_obj.school_id)
            if school:
                school_id = school.id
                school_name = school.name or ''
        
        # Salvar gabarito no banco (garantir que UUIDs sejam strings)
        gabarito = AnswerSheetGabarito(
            test_id=str(data.get('test_id')) if data.get('test_id') else None,
            class_id=class_id,  # Já é UUID pelo modelo
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            title=test_data.get('title', 'Cartão Resposta'),
            created_by=str(user['id']) if user.get('id') else None,
            # Campos adicionais
            school_id=str(school_id) if school_id else None,
            school_name=school_name,
            municipality=test_data.get('municipality', ''),
            state=test_data.get('state', ''),
            grade_name=test_data.get('grade_name', ''),
            institution=test_data.get('institution', '')
        )
        db.session.add(gabarito)
        db.session.commit()
        
        # Gerar coordenadas automaticamente
        try:
            from app.services.cartao_resposta.coordinate_generator import CoordinateGenerator
            
            coord_generator = CoordinateGenerator()
            coordinates = coord_generator.generate_coordinates(
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                questions_options=questions_options
            )
            
            # Salvar coordenadas no gabarito
            gabarito.coordinates = coordinates
            db.session.commit()
            
            logging.info(f"✅ Coordenadas geradas e salvas para gabarito {str(gabarito.id)}")
        except Exception as e:
            logging.error(f"Erro ao gerar coordenadas: {str(e)}", exc_info=True)
            # Continuar mesmo se falhar
        
        # Preparar test_data completo
        test_data_complete = {
            'id': data.get('test_id'),
            'title': test_data.get('title', 'Cartão Resposta'),
            'municipality': test_data.get('municipality', ''),
            'state': test_data.get('state', ''),
            'department': test_data.get('department', ''),
            'municipality_logo': test_data.get('municipality_logo'),
            'institution': test_data.get('institution', ''),
            'grade_name': test_data.get('grade_name', '')
        }
        
        # Gerar cartões resposta
        generator = AnswerSheetGenerator()
        generated_files = generator.generate_answer_sheets(
            class_id=class_id,
            test_data=test_data_complete,
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            gabarito_id=str(gabarito.id),
            questions_options=questions_options
        )
        
        if not generated_files:
            return jsonify({"error": "Nenhum cartão resposta foi gerado"}), 400
        
        # Criar ZIP em memória
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Adicionar cada PDF ao ZIP
            for file_info in generated_files:
                pdf_data = file_info.get('pdf_data')
                if pdf_data:
                    # Nome do arquivo: cartao_NomeAluno_studentId.pdf
                    student_name = file_info.get('student_name', 'Aluno')
                    student_id = file_info.get('student_id', '')
                    
                    # Limpar caracteres inválidos do nome do arquivo
                    safe_name = "".join(c for c in student_name if c.isalnum() or c in (' ', '-', '_')).strip()
                    safe_name = safe_name.replace(' ', '_')
                    
                    filename = f"cartao_{safe_name}_{student_id[:8]}.pdf"
                    zip_file.writestr(filename, pdf_data)
            
            # Adicionar arquivo de metadados com informações do gabarito
            metadata = {
                "gabarito_id": str(gabarito.id),
                "test_id": str(gabarito.test_id) if gabarito.test_id else None,
                "class_id": str(gabarito.class_id) if gabarito.class_id else None,
                "title": gabarito.title,
                "num_questions": gabarito.num_questions,
                "use_blocks": gabarito.use_blocks,
                "blocks_config": gabarito.blocks_config,
                "generated_count": len([f for f in generated_files if f.get('pdf_data')]),
                "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None
            }
            import json as json_module
            zip_file.writestr("metadata.json", json_module.dumps(metadata, indent=2, ensure_ascii=False))
        
        zip_buffer.seek(0)
        
        # Nome do arquivo ZIP
        zip_filename = f"cartoes_resposta_{test_data_complete.get('title', 'CartaoResposta')}_{str(gabarito.id)[:8]}.zip"
        # Limpar caracteres inválidos
        zip_filename = "".join(c for c in zip_filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        zip_filename = zip_filename.replace(' ', '_')
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao gerar cartões resposta: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao gerar cartões resposta: {str(e)}"}), 500


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
            if gabarito.class_id:
                class_obj = Class.query.get(gabarito.class_id)
                if class_obj:
                    class_name = class_obj.name
            
            # Buscar informações do criador
            creator_name = None
            if gabarito.created_by:
                creator = User.query.get(gabarito.created_by)
                if creator:
                    creator_name = creator.name
            
            gabaritos.append({
                "id": str(gabarito.id),
                "test_id": str(gabarito.test_id) if gabarito.test_id else None,
                "class_id": str(gabarito.class_id) if gabarito.class_id else None,
                "class_name": class_name,
                "num_questions": gabarito.num_questions,
                "use_blocks": gabarito.use_blocks,
                "title": gabarito.title,
                "school_name": gabarito.school_name,
                "municipality": gabarito.municipality,
                "state": gabarito.state,
                "grade_name": gabarito.grade_name,
                "institution": gabarito.institution,
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
    Regenera e baixa os cartões resposta de um gabarito existente
    
    Returns:
        Arquivo ZIP contendo todos os PDFs dos cartões resposta
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
            return jsonify({"error": "Você não tem permissão para acessar este gabarito"}), 403
        
        # Validar que temos class_id
        if not gabarito.class_id:
            return jsonify({"error": "Gabarito não possui turma associada"}), 400
        
        # Buscar turma
        class_obj = Class.query.get(gabarito.class_id)
        if not class_obj:
            return jsonify({"error": "Turma não encontrada"}), 404
        
        # Preparar test_data a partir do gabarito
        test_data_complete = {
            'id': gabarito.test_id,
            'title': gabarito.title or 'Cartão Resposta',
            'municipality': gabarito.municipality or '',
            'state': gabarito.state or '',
            'department': '',  # Não armazenado no gabarito
            'municipality_logo': None,  # Não armazenado no gabarito
            'institution': gabarito.institution or '',
            'grade_name': gabarito.grade_name or ''
        }
        
        # Extrair questions_options do blocks_config se existir
        questions_options = None
        if gabarito.blocks_config and 'topology' in gabarito.blocks_config:
            topology = gabarito.blocks_config.get('topology', {})
            blocks = topology.get('blocks', [])
            questions_options = {}
            for block in blocks:
                for question in block.get('questions', []):
                    q_num = question.get('q')
                    alternatives = question.get('alternatives', ['A', 'B', 'C', 'D'])
                    if q_num:
                        questions_options[str(q_num)] = alternatives
        
        # Gerar cartões resposta usando os dados do gabarito
        generator = AnswerSheetGenerator()
        generated_files = generator.generate_answer_sheets(
            class_id=str(gabarito.class_id),
            test_data=test_data_complete,
            num_questions=gabarito.num_questions,
            use_blocks=gabarito.use_blocks,
            blocks_config=gabarito.blocks_config or {},
            correct_answers=gabarito.correct_answers,
            gabarito_id=str(gabarito.id),
            questions_options=questions_options
        )
        
        if not generated_files:
            return jsonify({"error": "Nenhum cartão resposta foi gerado"}), 400
        
        # Criar ZIP em memória
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Adicionar cada PDF ao ZIP
            for file_info in generated_files:
                pdf_data = file_info.get('pdf_data')
                if pdf_data:
                    # Nome do arquivo: cartao_NomeAluno_studentId.pdf
                    student_name = file_info.get('student_name', 'Aluno')
                    student_id = file_info.get('student_id', '')
                    
                    # Limpar caracteres inválidos do nome do arquivo
                    safe_name = "".join(c for c in student_name if c.isalnum() or c in (' ', '-', '_')).strip()
                    safe_name = safe_name.replace(' ', '_')
                    
                    filename = f"cartao_{safe_name}_{student_id[:8]}.pdf"
                    zip_file.writestr(filename, pdf_data)
            
            # Adicionar arquivo de metadados com informações do gabarito
            metadata = {
                "gabarito_id": str(gabarito.id),
                "test_id": str(gabarito.test_id) if gabarito.test_id else None,
                "class_id": str(gabarito.class_id) if gabarito.class_id else None,
                "title": gabarito.title,
                "num_questions": gabarito.num_questions,
                "use_blocks": gabarito.use_blocks,
                "blocks_config": gabarito.blocks_config,
                "generated_count": len([f for f in generated_files if f.get('pdf_data')]),
                "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None,
                "regenerated_at": datetime.now().isoformat()
            }
            import json as json_module
            zip_file.writestr("metadata.json", json_module.dumps(metadata, indent=2, ensure_ascii=False))
        
        zip_buffer.seek(0)
        
        # Nome do arquivo ZIP
        zip_filename = f"cartoes_resposta_{gabarito.title or 'CartaoResposta'}_{str(gabarito.id)[:8]}.zip"
        # Limpar caracteres inválidos
        zip_filename = "".join(c for c in zip_filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        zip_filename = zip_filename.replace(' ', '_')
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        logging.error(f"Erro ao baixar gabarito: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao baixar gabarito: {str(e)}"}), 500


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


@bp.route('/gabarito/<string:gabarito_id>', methods=['DELETE'])
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
