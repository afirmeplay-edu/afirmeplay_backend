# -*- coding: utf-8 -*-
"""
Rotas para geração e correção de cartões resposta
"""

from flask import Blueprint, request, jsonify, send_file, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators.role_required import role_required, get_current_user_from_token
from app.decorators import requires_city_context
from app.utils.tenant_middleware import get_current_tenant_context, set_search_path, city_id_to_schema_name
from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetGenerationJob import AnswerSheetGenerationJob
from app.models.answerSheetResult import AnswerSheetResult
from app.models.studentClass import Class
from app.models.student import Student
from app.models.user import User
from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
from app.services.cartao_resposta.answer_sheet_correction_service import AnswerSheetCorrectionService
from app.services.cartao_resposta.correction_new_grid import AnswerSheetCorrectionNewGrid
from app.config import Config
from app.services.progress_store import (
    create_job, update_item_processing, update_item_done,
    update_item_error, complete_job, get_job, purge_answer_sheet_job_keys,
)
from app.report_analysis.answer_sheet_aggregate_service import (
    any_configured_redis_tcp_unreachable,
)
from app.services.answer_sheet_job_store import (
    create_answer_sheet_job,
    get_answer_sheet_job,
    update_answer_sheet_job,
    seed_answer_sheet_progress_job,
)
from app.models.school import School
from app.models.grades import Grade
from app.models.city import City
from app.models.test import Test
from app.models.skill import Skill
from app.utils.decimal_helpers import round_to_two_decimals
from typing import Dict, Optional, List, Any, Tuple, Set
from collections import defaultdict
from sqlalchemy import cast, String, desc
from sqlalchemy.orm import joinedload
from app.services.cartao_resposta.answer_sheet_gabarito_generation import (
    AnswerSheetGabaritoGeneration,
    enrich_scope_snapshot,
    reapply_gabarito_minio_from_generations,
)
import logging
import re
import base64
import io
import os
import zipfile
import tempfile
import threading
import uuid
from io import BytesIO
from datetime import datetime, timedelta
from urllib.parse import urlencode
from calendar import monthrange
from app.services.ai_analysis_service import AIAnalysisService
from app.services.ai_redis_cache import (
    get_redis_client as _get_ai_redis_client,
    get_status as _ai_cache_get_status,
    make_cache_key as _ai_make_cache_key,
    set_processing as _ai_cache_set_processing,
)
from app.services.celery_tasks.ai_analysis_cache_tasks import generate_ai_analysis_json_to_redis

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
        subject_id = block.get('subject_id') or ''
        subject_name = block.get('subject_name', '')
        questions_count = block.get('questions_count', 0)
        start_question = block.get('start_question', 0)
        end_question = block.get('end_question', 0)
        
        # Identificador do bloco para mensagens (nome ou id)
        block_label = subject_name or str(subject_id) or f"bloco {block_id}"
        
        # Validar campos obrigatórios: subject_id é obrigatório por bloco
        if not subject_id or not str(subject_id).strip():
            return f"Bloco {block_id}: 'subject_id' é obrigatório (disciplina do bloco)."
        
        if questions_count < 1:
            return f"Bloco {block_id} ({block_label}): deve ter pelo menos 1 questão."
        
        if questions_count > 26:
            return f"Bloco {block_id} ({block_label}): máximo de 26 questões por bloco. Você definiu {questions_count}."
        
        # Validar sequência
        if start_question != expected_start:
            return f"Bloco {block_id} ({block_label}): deveria começar na questão {expected_start}, mas começa em {start_question}."
        
        if end_question - start_question + 1 != questions_count:
            return f"Bloco {block_id} ({block_label}): contagem inconsistente (start={start_question}, end={end_question}, count={questions_count})."
        
        total_from_blocks += questions_count
        expected_start = end_question + 1
    
    # 3. Total de questões
    if total_from_blocks != total_questions:
        return f"Soma das questões dos blocos ({total_from_blocks}) difere do total informado ({total_questions})."
    
    if total_questions > 104:
        return f"Total de {total_questions} questões excede o máximo de 104 (4 blocos × 26 questões)."
    
    return None


def _resolve_question_skills_to_ids(question_skills_raw: Dict) -> Dict[int, List[str]]:
    """
    Converte question_skills do payload (códigos ou IDs em string) para um mapa
    número da questão -> lista de IDs (UUID string) de Skill.
    Aceita no payload: {"1": ["EF01LP01", "uuid-aqui"], "2": ["code2"]}.
    """
    if not question_skills_raw or not isinstance(question_skills_raw, dict):
        return {}
    uuid_pattern = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    result = {}
    for q_key, values in question_skills_raw.items():
        try:
            q_num = int(q_key)
        except (ValueError, TypeError):
            continue
        if not isinstance(values, list):
            values = [values] if values is not None else []
        resolved_ids = []
        for v in values:
            if not v or not isinstance(v, str):
                continue
            v = v.strip()
            if not v:
                continue
            if uuid_pattern.match(v):
                skill = Skill.query.filter(Skill.id == v).first()
                if skill:
                    resolved_ids.append(str(skill.id))
            else:
                skill = Skill.query.filter(Skill.code == v).first()
                if skill:
                    resolved_ids.append(str(skill.id))
        if resolved_ids:
            result[q_num] = resolved_ids
    return result


def _generate_complete_structure(num_questions: int, use_blocks: bool,
                                 blocks_config: Dict, questions_options: Dict = None,
                                 question_skills: Optional[Dict[int, List[str]]] = None) -> Dict:
    """
    Gera estrutura completa de questões e alternativas por bloco.
    question_skills: opcional, mapa número da questão -> lista de IDs (UUID) de Skill;
    cada questão na topology recebe a chave "skills" com essa lista.
    Formato (será salvo em blocks_config['topology']):
    {
        "blocks": [
            {
                "block_id": 1,
                "questions": [
                    {"q": 1, "alternatives": ["A", "B"], "skills": ["uuid1", "uuid2"]},
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
        # ✅ Blocos personalizados: subject_id obrigatório, subject_name opcional (resolvido do Subject se faltar)
        from app.models.subject import Subject
        blocks = []
        for block_def in custom_blocks:
            block_id = block_def.get('block_id')
            subject_id = block_def.get('subject_id')
            subject_name = block_def.get('subject_name')
            if not subject_name and subject_id:
                subject_obj = Subject.query.get(str(subject_id))
                if subject_obj and getattr(subject_obj, 'name', None):
                    subject_name = subject_obj.name
            start_q = block_def.get('start_question')
            end_q = block_def.get('end_question')
            
            questions = []
            for q_num in range(start_q, end_q + 1):
                alternatives = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
                q_dict = {"q": q_num, "alternatives": alternatives}
                if question_skills is not None:
                    q_dict["skills"] = list(question_skills.get(q_num, []))
                questions.append(q_dict)
            
            blocks.append({
                "block_id": block_id,
                "subject_id": str(subject_id) if subject_id else None,
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
                q_dict = {"q": q_num, "alternatives": alternatives}
                if question_skills is not None:
                    q_dict["skills"] = list(question_skills.get(q_num, []))
                questions.append(q_dict)
            
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
            q_dict = {"q": q_num, "alternatives": alternatives}
            if question_skills is not None:
                q_dict["skills"] = list(question_skills.get(q_num, []))
            questions.append(q_dict)
        
        topology["blocks"] = [{
            "block_id": 1,
            "questions": questions
        }]
    
    return topology


@bp.route('/create-gabaritos', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def create_gabarito_only():
    """
    Cria e salva apenas a definição do cartão resposta (template) na tabela answer_sheet_gabaritos.
    Não gera PDFs; o escopo (estado, município, escolas, séries, turmas) é definido na hora de gerar (POST /generate).

    Body:
        title, num_questions, correct_answers, use_blocks, blocks_config,
        questions_options (opcional), question_skills (opcional), test_id (opcional), test_data (opcional, ex: institution).

    O registro é salvo no schema da cidade do tenant (city_xxx.answer_sheet_gabaritos).
    Campos MinIO (minio_url, etc.) permanecem NULL até uma geração via POST /generate.

    Returns:
        201: { "gabarito_id": "uuid", "title": "...", "num_questions": N }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400

        num_questions = data.get('num_questions')
        correct_answers = data.get('correct_answers')
        test_data = data.get('test_data', {})
        title = data.get('title', test_data.get('title', 'Cartão Resposta'))

        if not num_questions or num_questions <= 0:
            return jsonify({"error": "num_questions deve ser maior que 0"}), 400
        if not correct_answers:
            return jsonify({"error": "correct_answers é obrigatório"}), 400

        use_blocks = data.get('use_blocks', False)
        blocks_config = data.get('blocks_config', {}).copy() if data.get('blocks_config') else {}

        custom_blocks = blocks_config.get('blocks', [])
        if custom_blocks:
            validation_error = _validate_blocks_config(custom_blocks, num_questions)
            if validation_error:
                return jsonify({"error": validation_error}), 400
            blocks_config['num_blocks'] = len(custom_blocks)
            blocks_config['questions_per_block'] = custom_blocks[0].get('questions_count', 12) if custom_blocks else 12
            blocks_config['use_blocks'] = use_blocks
            blocks_config['separate_by_subject'] = not use_blocks
        elif use_blocks:
            blocks_config.setdefault('num_blocks', 1)
            blocks_config.setdefault('questions_per_block', 12)
            blocks_config['use_blocks'] = True
            blocks_config['separate_by_subject'] = False
        else:
            blocks_config['use_blocks'] = False
            blocks_config['num_blocks'] = 1
            blocks_config['questions_per_block'] = num_questions
            blocks_config['separate_by_subject'] = False

        questions_options = data.get('questions_options', {})
        question_skills_raw = data.get('question_skills', {})
        question_skills_ids = _resolve_question_skills_to_ids(question_skills_raw)
        complete_structure = _generate_complete_structure(
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            questions_options=questions_options,
            question_skills=question_skills_ids if question_skills_ids else None
        )
        blocks_config['topology'] = complete_structure

        gabarito = AnswerSheetGabarito(
            test_id=str(data.get('test_id')) if data.get('test_id') else None,
            class_id=None,
            grade_id=None,
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            title=title,
            created_by=str(user['id']) if user.get('id') else None,
            scope_type=None,
            school_id=None,
            school_name=None,
            municipality=None,
            state=None,
            grade_name=None,
            institution=test_data.get('institution', '') or ''
        )
        db.session.add(gabarito)
        db.session.commit()
        gabarito_id = str(gabarito.id)

        try:
            from app.services.cartao_resposta.coordinate_generator import CoordinateGenerator
            coord_generator = CoordinateGenerator()
            coordinates = coord_generator.generate_coordinates(
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                questions_options=questions_options
            )
            gabarito.coordinates = coordinates
            db.session.commit()
        except Exception as e:
            logging.warning(f"[create-gabaritos] Erro ao gerar coordenadas: {str(e)}")

        return jsonify({
            'gabarito_id': gabarito_id,
            'title': title,
            'num_questions': num_questions,
        }), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"[create-gabaritos] Erro: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@bp.route('/generate', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def generate_answer_sheets():
    """
    Gera cartões resposta de forma INTELIGENTE e HIERÁRQUICA.

    Dois modos:
    - Com gabarito_id: gera PDFs a partir de um cartão já criado (POST /create-gabaritos).
      Body deve ter gabarito_id + filtros de escopo (school_ids, grade_ids, class_ids). Permite regerar (sobrescreve MinIO).
    - Sem gabarito_id: cria um novo gabarito e gera PDFs (fluxo legado). Body completo como abaixo.

    Escopo em cascata (município vem do tenant). Filtros opcionais restringem o conjunto:
    - Nenhum filtro → todas as escolas, séries e turmas do município.
    - school_ids → todas as séries e turmas dessas escolas.
    - school_ids + grade_ids → turmas dessas séries nessas escolas.
    - school_ids + grade_ids + class_ids → apenas essas turmas (ou só class_ids = essas turmas no município).
    Aceita também no singular (retrocompat): class_id, grade_id, school_id.
    
    Body (sem gabarito_id):
        {
            "title": "Avaliação de Português",
            "num_questions": 48,
            "use_blocks": true,
            "blocks_config": {...},
            "correct_answers": {...},
            "questions_options": {...},
            "question_skills": {"1": ["EF01LP01", "uuid-opcional"], "2": ["code2"]},  // opcional; códigos ou IDs de Skill por questão
            "test_data": {...},
            "test_id": "uuid" (opcional),
            
            "school_ids": ["uuid-escola1", "uuid-escola2"],  // opcional; vazio = todas do município
            "grade_ids": ["uuid-serie1", "uuid-serie2"],     // opcional; vazio = todas as séries
            "class_ids": ["uuid-turma1", "uuid-turma2"]     // opcional; vazio = todas as turmas
            // Retrocompat: class_id, grade_id, school_id (singular) também aceitos
        }
    
    Returns (202 Accepted):
        {
            "status": "processing",
            "job_id": "uuid",
            "gabarito_id": "uuid",
            "scope_type": "class|grade|school",
            "total_classes": N,
            "total_students": M,
            "tasks": [
                {"class_id": "...", "class_name": "A", "task_id": "..."},
                ...
            ],
            "polling_url": "/answer-sheets/jobs/{job_id}/status"
        }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400

        from app.decorators.tenant_required import get_current_tenant_context
        context_scope = get_current_tenant_context()
        city_id_scope = context_scope.city_id if context_scope else None
        if not city_id_scope:
            return jsonify({"error": "Contexto de município não encontrado"}), 400

        def _norm_list(key_plural, key_singular):
            raw = data.get(key_plural)
            if raw is not None and isinstance(raw, list):
                return [str(x).strip() for x in raw if x]
            single = (data.get(key_singular) or '').strip() or None
            return [single] if single else []

        school_ids = _norm_list('school_ids', 'school_id')
        grade_ids = _norm_list('grade_ids', 'grade_id')
        class_ids_param = _norm_list('class_ids', 'class_id')

        # ========== MODO: Gerar a partir de gabarito já criado (POST /create-gabaritos) ==========
        existing_gabarito_id = (data.get('gabarito_id') or '').strip() or None
        if existing_gabarito_id:
            gabarito = AnswerSheetGabarito.query.get(existing_gabarito_id)
            if not gabarito:
                return jsonify({"error": "Gabarito não encontrado"}), 404
            if gabarito.created_by and str(gabarito.created_by) != str(user.get('id')):
                return jsonify({"error": "Você não tem permissão para usar este gabarito"}), 403

            school_ids_scope = school_ids
            grade_ids_scope = grade_ids
            class_ids_scope = class_ids_param

            school_ids_city_subq = db.session.query(School.id).filter(
                School.city_id == city_id_scope
            ).subquery()
            q = Class.query.filter(Class.school_id.in_(school_ids_city_subq))
            if school_ids_scope:
                schools_in_city = db.session.query(School.id).filter(
                    School.id.in_(school_ids_scope),
                    School.city_id == city_id_scope
                ).all()
                valid_school_ids = [s[0] for s in schools_in_city]
                if len(valid_school_ids) != len(school_ids_scope):
                    return jsonify({"error": "Uma ou mais escolas não pertencem ao município ou não existem"}), 400
                q = q.filter(Class.school_id.in_(valid_school_ids))
            if grade_ids_scope:
                q = q.filter(Class.grade_id.in_(grade_ids_scope))
            if class_ids_scope:
                q = q.filter(Class.id.in_(class_ids_scope))
            classes_to_generate = q.all()
            if not classes_to_generate:
                return jsonify({"error": "Nenhuma turma encontrada com os filtros informados"}), 400

            if len(classes_to_generate) == 1 and class_ids_scope:
                scope_type = 'class'
            elif grade_ids_scope and not class_ids_scope and len(school_ids_scope) <= 1:
                scope_type = 'grade'
            elif school_ids_scope and len(school_ids_scope) == 1 and not grade_ids_scope and not class_ids_scope:
                scope_type = 'school'
            else:
                scope_type = 'city'

            if user['role'] == 'professor':
                from app.models.teacher import Teacher
                from app.models.teacherClass import TeacherClass
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    allowed = set(
                        tc.class_id for tc in
                        TeacherClass.query.filter_by(teacher_id=teacher.id).filter(
                            TeacherClass.class_id.in_([c.id for c in classes_to_generate])
                        ).all()
                    )
                    if len(allowed) != len(classes_to_generate):
                        return jsonify({"error": "Você não tem acesso a uma ou mais turmas selecionadas"}), 403

            municipality_for_pdf = gabarito.municipality or ''
            state_for_pdf = gabarito.state or ''
            grade_name_for_pdf = gabarito.grade_name or gabarito.title or ''
            if not municipality_for_pdf or not state_for_pdf:
                city_obj = City.query.get(city_id_scope)
                if city_obj:
                    if not municipality_for_pdf:
                        municipality_for_pdf = city_obj.name or ''
                    if not state_for_pdf:
                        state_for_pdf = city_obj.state or ''
            if not grade_name_for_pdf and classes_to_generate and classes_to_generate[0].grade_id:
                grade_obj = Grade.query.get(classes_to_generate[0].grade_id)
                if grade_obj:
                    grade_name_for_pdf = grade_obj.name or ''

            test_data_complete = {
                'id': gabarito.test_id,
                'title': gabarito.title or 'Cartão Resposta',
                'municipality': municipality_for_pdf,
                'state': state_for_pdf,
                'grade_name': grade_name_for_pdf,
                'department': data.get('test_data', {}).get('department', ''),
                'institution': gabarito.institution or '',
            }
            # Extrair questions_options do blocks_config do gabarito (topology.blocks[].questions[].q + alternatives)
            questions_options_from_gabarito = {}
            for b in (gabarito.blocks_config or {}).get('topology', {}).get('blocks', []):
                for qq in b.get('questions', []):
                    q = qq.get('q')
                    a = qq.get('alternatives', ['A', 'B', 'C', 'D'])
                    if q is not None:
                        questions_options_from_gabarito[q] = a
            class_ids = [str(c.id) for c in classes_to_generate]
            job_id = str(uuid.uuid4())
            # Diretório compartilhado entre workers: /app/tmp/answer_sheets/{job_id}
            answer_sheets_base = os.environ.get("ANSWER_SHEETS_TMP_BASE", "/app/tmp/answer_sheets")
            os.makedirs(answer_sheets_base, exist_ok=True)
            base_output_dir = os.path.join(answer_sheets_base, job_id)
            os.makedirs(base_output_dir, exist_ok=True)

            # ========================================================================
            # OTIMIZADO: 1 Task Batch Única (sem chord)
            # Gera 1 template base para TODAS as turmas + overlay por aluno
            # Igual às provas físicas (simples, confiável, rápido com arch4)
            # ========================================================================
            from app.services.celery_tasks.answer_sheet_tasks import generate_answer_sheets_batch_async

            task = generate_answer_sheets_batch_async.delay(
                gabarito_ids=[existing_gabarito_id],
                city_id=city_id_scope,
                num_questions=gabarito.num_questions,
                correct_answers=gabarito.correct_answers,
                test_data=test_data_complete,
                use_blocks=gabarito.use_blocks,
                blocks_config=gabarito.blocks_config or {},
                questions_options=questions_options_from_gabarito,
                batch_id=job_id,
                scope=scope_type,
                class_ids=class_ids  # Lista de turmas para processar
            )
            task_id = task.id
            create_answer_sheet_job(
                job_id=job_id,
                total=len(classes_to_generate),
                gabarito_id=existing_gabarito_id,
                user_id=str(user['id']),
                task_ids=[task_id],
                city_id=city_id_scope,
                scope_type=scope_type,
            )
            for cls in classes_to_generate:
                db.session.refresh(cls)
            seed_answer_sheet_progress_job(
                job_id=job_id,
                classes_to_generate=classes_to_generate,
                gabarito_id=existing_gabarito_id,
                user_id=str(user['id']),
                task_ids=[task_id],
            )
            gabarito.last_generation_job_id = job_id
            db.session.commit()

            total_students = 0
            for cls in classes_to_generate:
                db.session.refresh(cls)
                total_students += len(cls.students) if cls.students else 0

            return jsonify({
                'status': 'processing',
                'job_id': job_id,
                'gabarito_id': existing_gabarito_id,
                'scope_type': scope_type,
                'total_classes': len(classes_to_generate),
                'total_students': total_students,
                'note': 'Números de alunos e turmas são estimativas. Valores reais estão no status do job.',
                'tasks': [{'class_id': str(c.id), 'class_name': c.name, 'status': 'pending'} for c in classes_to_generate],
                'polling_url': f"/answer-sheets/jobs/{job_id}/status"
            }), 202
        # ========== FIM MODO gabarito_id ==========

        # ✅ 1. VALIDAR CAMPOS OBRIGATÓRIOS (fluxo: criar novo gabarito + gerar)
        num_questions = data.get('num_questions')
        correct_answers = data.get('correct_answers')
        test_data = data.get('test_data', {})
        title = data.get('title', test_data.get('title', 'Cartão Resposta'))

        if not num_questions or num_questions <= 0:
            return jsonify({"error": "num_questions deve ser maior que 0"}), 400
        if not correct_answers:
            return jsonify({"error": "correct_answers é obrigatório"}), 400

        # ✅ 2. DETERMINAR ESCOPO (cascata: município → escolas → séries → turmas)
        class_ids = class_ids_param

        # Base: turmas do município (escolas da cidade)
        school_ids_city_subq = db.session.query(School.id).filter(
            School.city_id == city_id_scope
        ).subquery()
        q = Class.query.filter(Class.school_id.in_(school_ids_city_subq))

        # Filtro por escolas: só turmas dessas escolas (e validar que escolas são do município)
        if school_ids:
            schools_in_city = db.session.query(School.id).filter(
                School.id.in_(school_ids),
                School.city_id == city_id_scope
            ).all()
            valid_school_ids = [s[0] for s in schools_in_city]
            if len(valid_school_ids) != len(school_ids):
                return jsonify({"error": "Uma ou mais escolas não pertencem ao município ou não existem"}), 400
            q = q.filter(Class.school_id.in_(valid_school_ids))

        # Filtro por séries
        if grade_ids:
            q = q.filter(Class.grade_id.in_(grade_ids))

        # Filtro por turmas (restringe às turmas enviadas)
        if class_ids:
            q = q.filter(Class.id.in_(class_ids))

        classes_to_generate = q.all()

        if not classes_to_generate:
            return jsonify({"error": "Nenhuma turma encontrada com os filtros informados"}), 400

        # Derivar scope_type para resposta/listagem
        if len(classes_to_generate) == 1 and class_ids:
            scope_type = 'class'
        elif grade_ids and not class_ids and len(school_ids) <= 1:
            scope_type = 'grade'
        elif school_ids and len(school_ids) == 1 and not grade_ids and not class_ids:
            scope_type = 'school'
        else:
            scope_type = 'city'

        # Permissão professor: deve ter acesso a todas as turmas selecionadas
        if user['role'] == 'professor':
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                allowed = set(
                    tc.class_id for tc in
                    TeacherClass.query.filter_by(teacher_id=teacher.id).filter(
                        TeacherClass.class_id.in_([c.id for c in classes_to_generate])
                    ).all()
                )
                if len(allowed) != len(classes_to_generate):
                    return jsonify({"error": "Você não tem acesso a uma ou mais turmas selecionadas"}), 403

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
        
        # ✅ 4. GERAR ESTRUTURA COMPLETA (topology) + skills por questão
        questions_options = data.get('questions_options', {})
        question_skills_raw = data.get('question_skills', {})
        question_skills_ids = _resolve_question_skills_to_ids(question_skills_raw)
        complete_structure = _generate_complete_structure(
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            questions_options=questions_options,
            question_skills=question_skills_ids if question_skills_ids else None
        )
        blocks_config['topology'] = complete_structure
        
        logging.info(f"[ROTA] ✅ Estrutura de blocos preparada")
        
        # ✅ 5. CRIAR 1 ÚNICO GABARITO PARA TODAS AS TURMAS
        school_id_for_gabarito = None
        school_name = ''
        grade_id_for_gabarito = None
        grade_name_for_gabarito = test_data.get('grade_name', '')  # ✅ Pegar do payload primeiro

        municipality_for_gabarito = test_data.get('municipality', '') or ''
        state_for_gabarito = test_data.get('state', '') or ''

        if scope_type == 'city':
            # Município inteiro: sem escola/série específica no gabarito
            # Preencher municipality/state a partir do tenant se não vierem no payload
            if not municipality_for_gabarito or not state_for_gabarito:
                from app.decorators.tenant_required import get_current_tenant_context
                ctx = get_current_tenant_context()
                if ctx and ctx.city_id:
                    city_obj = City.query.get(ctx.city_id)
                    if city_obj:
                        if not municipality_for_gabarito:
                            municipality_for_gabarito = city_obj.name or ''
                        if not state_for_gabarito:
                            state_for_gabarito = city_obj.state or ''
        elif classes_to_generate:
            first_class = classes_to_generate[0]
            if first_class.school_id:
                school_id_for_gabarito = first_class.school_id
                if first_class.school:
                    school_name = first_class.school.name or ''
                    # Preencher município/estado a partir da escola se não vierem no payload
                    if (not municipality_for_gabarito or not state_for_gabarito) and first_class.school.city:
                        if not municipality_for_gabarito:
                            municipality_for_gabarito = first_class.school.city.name or ''
                        if not state_for_gabarito:
                            state_for_gabarito = first_class.school.city.state or ''
            if first_class.grade_id:
                grade_id_for_gabarito = first_class.grade_id
                # ✅ Se não veio no payload, buscar do banco
                if not grade_name_for_gabarito and first_class.grade:
                    grade_name_for_gabarito = first_class.grade.name
        
        gabarito = AnswerSheetGabarito(
            test_id=str(data.get('test_id')) if data.get('test_id') else None,
            class_id=str(classes_to_generate[0].id) if scope_type == 'class' and len(classes_to_generate) == 1 else None,
            grade_id=grade_id_for_gabarito,
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            title=title,
            created_by=str(user['id']) if user.get('id') else None,
            scope_type=scope_type,  # ✅ NOVO CAMPO
            school_id=str(school_id_for_gabarito) if school_id_for_gabarito else None,
            school_name=school_name,
            municipality=municipality_for_gabarito,
            state=state_for_gabarito,
            grade_name=grade_name_for_gabarito,  # ✅ Usar variável que busca do banco se necessário
            institution=test_data.get('institution', '')
        )
        db.session.add(gabarito)
        db.session.commit()
        gabarito_id = str(gabarito.id)
        
        logging.info(f"[ROTA] ✅ Gabarito criado: {gabarito_id} (scope: {scope_type})")
        
        # ✅ 6. GERAR COORDENADAS
        try:
            from app.services.cartao_resposta.coordinate_generator import CoordinateGenerator
            
            coord_generator = CoordinateGenerator()
            coordinates = coord_generator.generate_coordinates(
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                questions_options=questions_options
            )
            
            gabarito.coordinates = coordinates
            db.session.commit()
            logging.info(f"[ROTA] ✅ Coordenadas geradas para gabarito {gabarito_id}")
        except Exception as e:
            logging.error(f"[ROTA] ⚠️ Erro ao gerar coordenadas (não crítico): {str(e)}")
        
        # ✅ 7. PREPARAR test_data (usar município/estado já preenchidos do contexto para o PDF)
        test_data_complete = {
            'id': data.get('test_id'),
            'title': title,
            'municipality': municipality_for_gabarito,
            'state': state_for_gabarito,
            'grade_name': grade_name_for_gabarito,  # ✅ Adicionar grade_name
            'department': test_data.get('department', ''),
            'institution': test_data.get('institution', ''),
            'grade_name': test_data.get('grade_name', '')
        }
        
        # ✅ 8. DISPARAR CELERY: 1 task batch (1× template WeasyPrint + overlay por aluno) — SEM chord / task por turma
        from app.services.celery_tasks.answer_sheet_tasks import generate_answer_sheets_batch_async

        if not city_id_scope:
            logging.error("[ROTA] ❌ Contexto de cidade não encontrado")
            return jsonify({"error": "City context not found"}), 500

        class_ids_for_batch = [str(cls.id) for cls in classes_to_generate]
        job_id = str(uuid.uuid4())

        answer_sheets_base = os.environ.get("ANSWER_SHEETS_TMP_BASE", "/app/tmp/answer_sheets")
        os.makedirs(answer_sheets_base, exist_ok=True)
        _base_output_dir = os.path.join(answer_sheets_base, job_id)
        os.makedirs(_base_output_dir, exist_ok=True)

        task = generate_answer_sheets_batch_async.delay(
            gabarito_ids=[gabarito_id],
            city_id=city_id_scope,
            num_questions=num_questions,
            correct_answers=correct_answers,
            test_data=test_data_complete,
            use_blocks=use_blocks,
            blocks_config=blocks_config or {},
            questions_options=questions_options,
            batch_id=job_id,
            scope=scope_type,
            class_ids=class_ids_for_batch,
        )
        task_id = task.id

        create_answer_sheet_job(
            job_id=job_id,
            total=len(classes_to_generate),
            gabarito_id=gabarito_id,
            user_id=str(user['id']),
            task_ids=[task_id],
            city_id=city_id_scope,
            scope_type=scope_type,
        )
        for cls in classes_to_generate:
            db.session.refresh(cls)
        seed_answer_sheet_progress_job(
            job_id=job_id,
            classes_to_generate=classes_to_generate,
            gabarito_id=gabarito_id,
            user_id=str(user['id']),
            task_ids=[task_id],
        )
        gabarito.last_generation_job_id = job_id
        db.session.commit()

        logging.info(
            "[ROTA] ✅ Batch async disparado (1 template base / todas as turmas): task=%s job=%s gabarito=%s turmas=%s",
            task_id,
            job_id,
            gabarito_id,
            len(class_ids_for_batch),
        )

        total_students = 0
        for cls in classes_to_generate:
            db.session.refresh(cls)
            total_students += len(cls.students) if cls.students else 0

        response_tasks = [
            {
                'class_id': str(class_obj.id),
                'class_name': class_obj.name,
                'status': 'pending',
            }
            for class_obj in classes_to_generate
        ]

        return jsonify({
            'status': 'processing',
            'job_id': job_id,
            'gabarito_id': gabarito_id,
            'scope_type': scope_type,
            'total_classes': len(classes_to_generate),
            'total_students': total_students,
            'note': 'Números de alunos e turmas são estimativas. Valores reais estão no status do job.',
            'tasks': response_tasks,
            'polling_url': f"/answer-sheets/jobs/{job_id}/status",
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
        from app.services.celery_tasks.answer_sheet_tasks import generate_answer_sheets_async
        from celery.result import AsyncResult
        
        # Buscar resultado da task
        task_result = AsyncResult(task_id, app=generate_answer_sheets_async.app)
        
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

def process_answer_sheet_batch_in_background(job_id: str, images: list = None, tenant_schema: str = None):
    """
    Processa correção em lote de cartões resposta em background thread.
    Multitenant: usa tenant_schema (ex: city_xxx) via bind ORM (schema_translate_map).
    Multitenant: usa tenant_schema (ex: city_xxx) via bind ORM (schema_translate_map).

    Args:
        job_id: ID do job para tracking
        images: Lista de imagens em base64
        tenant_schema: Nome do schema PostgreSQL do tenant (ex: city_9a2f95ed_9f70_4863_a5f1_1b6c6c262b0d)
    """
    from app import create_app

    app = create_app()

    with app.app_context():
        try:
            # Multitenant: definir schema da cidade para que AnswerSheetGabarito e demais tabelas sejam encontradas
            if tenant_schema:
                set_search_path(tenant_schema)

            correction_service = AnswerSheetCorrectionNewGrid(debug=Config.OMR_DEBUG)
            
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
                        student_name = result.get('student_name')
                        if not student_name and result.get('student_id'):
                            student = Student.query.get(result['student_id'])
                            if student:
                                student_name = student.name
                        # Adaptar resultado para o progress_store (correct/total/percentage)
                        adapted = {
                            "student_id": result.get("student_id"),
                            "student_name": student_name,
                            "correct": result.get("correct_answers"),
                            "total": result.get("total_questions"),
                            "percentage": result.get("score"),
                        }
                        update_item_done(job_id, i, adapted)
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


@bp.route('/process-correction', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def process_answer_sheet_correction_batch():
    """
    Processa correção em lote de vários cartões resposta (assíncrono).
    Cartão e aluno são identificados pelo QR code em cada imagem.

    Body (JSON):
    {
        "images": [
            "data:image/jpeg;base64,...",
            "data:image/jpeg;base64,...",
            ...
        ]
    }

    Returns (202 Accepted):
        {"job_id": "uuid", "message": "Processamento em lote iniciado", "total": N, "status": "processing"}
        Use GET /answer-sheets/correction-progress/<job_id> para acompanhar o progresso.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        data = request.get_json() or {}
        images = data.get("images")
        if not isinstance(images, list):
            return jsonify({"error": "Campo 'images' (array de imagens em base64) é obrigatório"}), 400
        if len(images) == 0:
            return jsonify({"error": "Nenhuma imagem fornecida"}), 400
        if len(images) > 50:
            return jsonify({"error": "Máximo de 50 imagens por lote"}), 400

        # Multitenant: correção em lote deve rodar no mesmo schema de quem chamou (cidade do usuário ou admin com contexto)
        tenant_ctx = get_current_tenant_context()
        if not tenant_ctx or not getattr(tenant_ctx, "has_tenant_context", False):
            return jsonify({
                "error": "Correção em lote requer contexto de município. Use o subdomínio da cidade (ex: jaru.afirmeplay.com.br) ou envie o header X-City-ID ou X-City-Slug."
            }), 400
        tenant_schema = tenant_ctx.schema

        job_id = str(uuid.uuid4())
        create_job(job_id, len(images), test_id=None, user_id=str(user.get("id")))

        thread = threading.Thread(
            target=process_answer_sheet_batch_in_background,
            args=(job_id, images, tenant_schema),
            daemon=True,
        )
        thread.start()

        return jsonify({
            "job_id": job_id,
            "message": "Processamento em lote iniciado",
            "total": len(images),
            "status": "processing",
            "polling_url": f"/answer-sheets/correction-progress/{job_id}",
        }), 202
    except Exception as e:
        logging.error(f"Erro ao iniciar correção em lote: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro interno do servidor"}), 500


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
@requires_city_context
def list_gabaritos():
    """
    Lista **todos** os cartões (gabaritos) do usuário no **tenant atual** (schema city_xxx via contexto).

    Em **uma única resposta**, cada item inclui:
    - Dados resumidos do cartão (último download em minio_url / can_download, etc.)
    - **generations**: histórico **completo** de todas as gerações (cada job tem ZIP próprio: `minio_url`,
      `download_url` com `job_id`). O `minio_url` / `download_url` no **nível do cartão** espelham só a
      **última** geração gravada no registro do gabarito — para baixar uma geração antiga use o item em
      `generations[]`.

    Query Parameters:
        page: Número da página (padrão: 1)
        per_page: Itens por página (padrão: 20)
        class_id: Filtrar por turma (opcional)
        test_id: Filtrar por prova (opcional)
        school_id: Filtrar por escola (opcional)
        title: Filtrar por título (busca parcial, opcional)
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

        # Histórico de gerações por gabarito (todos os escopos / jobs)
        page_ids = [str(g.id) for g in pagination.items]
        generations_by_gabarito: Dict[str, List[dict]] = defaultdict(list)
        if page_ids:
            try:
                gen_rows = (
                    AnswerSheetGabaritoGeneration.query.filter(
                        AnswerSheetGabaritoGeneration.gabarito_id.in_(page_ids)
                    )
                    .order_by(
                        AnswerSheetGabaritoGeneration.gabarito_id,
                        desc(AnswerSheetGabaritoGeneration.created_at),
                    )
                    .all()
                )
                for gr in gen_rows:
                    row_dict = gr.to_dict()
                    row_dict["scope_snapshot"] = enrich_scope_snapshot(
                        row_dict.get("scope_snapshot")
                    )
                    _dl = url_for(
                        "answer_sheets.download_gabarito",
                        gabarito_id=str(gr.gabarito_id),
                        _external=True,
                    )
                    row_dict["download_url"] = (
                        f"{_dl}?{urlencode({'redirect': '1', 'job_id': row_dict['job_id']})}"
                    )
                    generations_by_gabarito[str(gr.gabarito_id)].append(row_dict)
            except Exception as gen_err:
                logging.warning(
                    'Listagem generations (tabela ausente ou erro): %s',
                    gen_err,
                    exc_info=True,
                )
        
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

            # Buscar informações do município se necessário (e resumo por escola)
            total_classes_in_city = 0
            total_students_in_city = 0
            schools_summary = []  # [{ school_id, school_name, classes_count, students_count }]
            response_municipality = gabarito.municipality or ''
            response_state = gabarito.state or ''

            if gabarito.scope_type == "city":
                city_obj_resolved = None
                if gabarito.municipality:
                    city_obj_resolved = City.query.filter(
                        City.name.ilike(f"%{gabarito.municipality}%")
                    ).first()
                if not city_obj_resolved:
                    from app.decorators.tenant_required import get_current_tenant_context
                    ctx = get_current_tenant_context()
                    if ctx and ctx.city_id:
                        city_obj_resolved = City.query.get(ctx.city_id)
                        if city_obj_resolved:
                            response_municipality = city_obj_resolved.name or ''
                            response_state = city_obj_resolved.state or ''

                if city_obj_resolved:
                    school_ids_city = db.session.query(School.id).filter(
                        School.city_id == city_obj_resolved.id
                    ).subquery()
                    classes_in_city = Class.query.filter(
                        Class.school_id.in_(school_ids_city)
                    ).all()
                    total_classes_in_city = len(classes_in_city)
                    total_students_in_city = sum(
                        len(cls.students) if cls.students else 0
                        for cls in classes_in_city
                    )
                    # Resumo por escola: escolas x quantidades
                    schools_in_city = School.query.filter(
                        School.city_id == city_obj_resolved.id
                    ).all()
                    for school in schools_in_city:
                        classes_school = [c for c in classes_in_city if c.school_id == school.id]
                        students_school = sum(
                            len(c.students) if c.students else 0 for c in classes_school
                        )
                        schools_summary.append({
                            "school_id": str(school.id),
                            "school_name": school.name or "",
                            "classes_count": len(classes_school),
                            "students_count": students_school,
                        })

            # Determinar contagem baseada no scope_type correto (ou totais da última geração se persistidos)
            final_students_count = 0
            final_classes_count = 0
            if getattr(gabarito, 'last_generation_classes_count', None) is not None or getattr(gabarito, 'last_generation_students_count', None) is not None:
                final_classes_count = getattr(gabarito, 'last_generation_classes_count', None) or 0
                final_students_count = getattr(gabarito, 'last_generation_students_count', None) or 0
            elif gabarito.scope_type == "class":
                final_students_count = class_students_count
                final_classes_count = 1
            elif gabarito.scope_type == "grade":
                final_students_count = total_students_in_grade
                final_classes_count = total_classes_in_grade
            elif gabarito.scope_type == "school":
                final_students_count = total_students_in_school
                final_classes_count = total_classes_in_school
            elif gabarito.scope_type == "city":
                final_students_count = total_students_in_city
                final_classes_count = total_classes_in_city
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
            
            item = {
                "id": str(gabarito.id),
                "test_id": str(gabarito.test_id) if gabarito.test_id else None,
                "class_id": str(gabarito.class_id) if gabarito.class_id else None,
                "class_name": class_name,
                "grade_id": str(gabarito.grade_id) if gabarito.grade_id else None,
                "grade_name": grade_name or gabarito.grade_name or gabarito.title or "",
                "num_questions": gabarito.num_questions,
                "use_blocks": gabarito.use_blocks,
                "title": gabarito.title,
                "school_id": str(gabarito.school_id) if gabarito.school_id else None,
                "school_name": gabarito.school_name or "",
                "municipality": response_municipality if gabarito.scope_type == "city" else (gabarito.municipality or ""),
                "state": response_state if gabarito.scope_type == "city" else (gabarito.state or ""),
                "institution": gabarito.institution or "",
                "scope_type": gabarito.scope_type or "class",
                "generation_status": generation_status,
                "students_count": final_students_count,
                "classes_count": final_classes_count,
                "minio_url": gabarito.minio_url,
                "can_download": bool(gabarito.minio_url or gabarito.minio_object_name),
                "download_url": (
                    request.url_root.rstrip("/")
                    + url_for("answer_sheets.download_gabarito", gabarito_id=gabarito.id)
                    + "?redirect=1"
                    if gabarito.minio_object_name else None
                ),
                "latest_generation_job_id": gabarito.last_generation_job_id,
                "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None,
                "created_by": str(gabarito.created_by) if gabarito.created_by else None,
                "creator_name": creator_name,
            }
            if gabarito.scope_type == "city":
                item["schools_summary"] = schools_summary
            gens = generations_by_gabarito.get(str(gabarito.id), [])
            item["generations"] = gens
            item["generations_count"] = len(gens)
            gabaritos.append(item)

        tenant_city_id = None
        try:
            from app.decorators.tenant_required import get_current_tenant_context as _ctx
            _c = _ctx()
            if _c and getattr(_c, 'city_id', None):
                tenant_city_id = str(_c.city_id)
        except Exception:
            pass
        
        return jsonify({
            "gabaritos": gabaritos,
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages,
            "city_id": tenant_city_id,
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar gabaritos: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao listar gabaritos: {str(e)}"}), 500


@bp.route('/gabarito/<string:gabarito_id>/download', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def download_gabarito(gabarito_id):
    """
    URL pré-assinada para o ZIP no MinIO.

    - Sem **job_id**: objeto no gabarito (em geral a última geração).
    - Com **?job_id=&lt;uuid&gt;**: ZIP daquela linha em ``answer_sheet_generations`` (qualquer geração).
    """
    try:
        from app.services.storage.minio_service import MinIOService
        from datetime import timedelta
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404
        
        if user['role'] != 'admin' and gabarito.created_by != str(user['id']):
            return jsonify({"error": "Você não tem permissão para acessar este gabarito"}), 403
        
        minio = MinIOService()
        job_id_param = (request.args.get("job_id") or "").strip() or None
        bucket_name = gabarito.minio_bucket or minio.BUCKETS['ANSWER_SHEETS']
        object_name = None
        zip_generated_at = gabarito.zip_generated_at
        resolved_job_id = gabarito.last_generation_job_id
        minio_url_out = gabarito.minio_url
        gen_row = None

        if job_id_param:
            gen_row = AnswerSheetGabaritoGeneration.query.filter_by(
                gabarito_id=gabarito_id,
                job_id=job_id_param,
            ).first()
            if not gen_row:
                return jsonify({
                    "error": "Geração não encontrada para este cartão",
                    "gabarito_id": gabarito_id,
                    "job_id": job_id_param,
                }), 404
            if not gen_row.minio_object_name:
                return jsonify({
                    "error": "ZIP desta geração não está disponível",
                    "job_id": job_id_param,
                }), 400
            object_name = gen_row.minio_object_name
            bucket_name = gen_row.minio_bucket or minio.BUCKETS['ANSWER_SHEETS']
            zip_generated_at = gen_row.zip_generated_at
            resolved_job_id = gen_row.job_id
            minio_url_out = gen_row.minio_url
        else:
            if not gabarito.minio_object_name:
                return jsonify({
                    "error": "ZIP de cartões ainda não foi gerado",
                    "message": "Use a rota POST /answer-sheets/generate para gerar os cartões primeiro. Após a geração (verifique status via polling), o ZIP estará disponível para download.",
                    "gabarito_id": gabarito_id,
                    "status": "not_generated"
                }), 400
            object_name = gabarito.minio_object_name
        
        try:
            presigned_url = minio.get_presigned_url(
                bucket_name=bucket_name,
                object_name=object_name,
                expires=timedelta(hours=1)
            )
            
            if request.args.get("redirect") == "1":
                return redirect(presigned_url, code=302)
            
            class_obj = Class.query.get(gabarito.class_id) if gabarito.class_id else None
            
            return jsonify({
                "download_url": presigned_url,
                "expires_in": "1 hour",
                "gabarito_id": str(gabarito.id),
                "job_id": resolved_job_id,
                "test_id": str(gabarito.test_id) if gabarito.test_id else None,
                "class_id": str(gabarito.class_id) if gabarito.class_id else None,
                "class_name": class_obj.name if class_obj else None,
                "title": gabarito.title,
                "num_questions": gabarito.num_questions,
                "generated_at": zip_generated_at.isoformat() if zip_generated_at else None,
                "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None,
                "minio_url": minio_url_out,
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


@bp.route('/gabarito/<string:gabarito_id>/generations/<string:job_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def delete_answer_sheet_generation(gabarito_id, job_id):
    """
    Remove **uma** geração (histórico + ZIP no MinIO + job em public + cache Redis).
    O cartão (gabarito) permanece; campos minio/last_generation no gabarito são realinhados
    com a geração mais recente que sobrar.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404
        if user["role"] != "admin" and str(gabarito.created_by) != str(user.get("id")):
            return jsonify({"error": "Você não tem permissão"}), 403

        gen = AnswerSheetGabaritoGeneration.query.filter_by(
            gabarito_id=gabarito_id, job_id=job_id
        ).first()
        if not gen:
            return jsonify({"error": "Geração não encontrada", "job_id": job_id}), 404

        from app.services.storage.minio_service import MinIOService

        minio = MinIOService()
        if gen.minio_object_name:
            bucket = gen.minio_bucket or minio.BUCKETS["ANSWER_SHEETS"]
            try:
                minio.delete_file(bucket, gen.minio_object_name)
            except Exception as ex:
                logging.warning(
                    "MinIO ao excluir geração %s: %s", job_id, ex, exc_info=True
                )

        db.session.delete(gen)
        pub = AnswerSheetGenerationJob.query.filter_by(job_id=job_id).first()
        if pub:
            db.session.delete(pub)

        reapply_gabarito_minio_from_generations(gabarito_id)
        db.session.commit()
        purge_answer_sheet_job_keys(job_id)

        return (
            jsonify(
                {
                    "message": "Geração removida",
                    "gabarito_id": gabarito_id,
                    "job_id": job_id,
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        logging.error("Erro ao excluir geração: %s", e, exc_info=True)
        return jsonify({"error": "Erro ao excluir geração"}), 500


@bp.route('/gabarito/<string:gabarito_id>/generations', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def delete_all_answer_sheet_generations(gabarito_id):
    """
    Remove **todas** as gerações do cartão (cada ZIP + registros + jobs + Redis), sem apagar o gabarito.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404
        if user["role"] != "admin" and str(gabarito.created_by) != str(user.get("id")):
            return jsonify({"error": "Você não tem permissão"}), 403

        rows = AnswerSheetGabaritoGeneration.query.filter_by(
            gabarito_id=gabarito_id
        ).all()
        if not rows:
            return jsonify(
                {"message": "Nenhuma geração para remover", "gabarito_id": gabarito_id, "removed": 0}
            ), 200

        from app.services.storage.minio_service import MinIOService

        minio = MinIOService()
        job_ids_removed = []
        for gen in rows:
            jid = gen.job_id
            job_ids_removed.append(jid)
            if gen.minio_object_name:
                bucket = gen.minio_bucket or minio.BUCKETS["ANSWER_SHEETS"]
                try:
                    minio.delete_file(bucket, gen.minio_object_name)
                except Exception as ex:
                    logging.warning(
                        "MinIO ao excluir geração %s: %s", jid, ex, exc_info=True
                    )
            db.session.delete(gen)
            pub = AnswerSheetGenerationJob.query.filter_by(job_id=jid).first()
            if pub:
                db.session.delete(pub)

        reapply_gabarito_minio_from_generations(gabarito_id)
        db.session.commit()
        for jid in job_ids_removed:
            purge_answer_sheet_job_keys(jid)

        return (
            jsonify(
                {
                    "message": "Gerações removidas",
                    "gabarito_id": gabarito_id,
                    "removed": len(job_ids_removed),
                    "job_ids": job_ids_removed,
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        logging.error("Erro ao excluir gerações: %s", e, exc_info=True)
        return jsonify({"error": "Erro ao excluir gerações"}), 500


@bp.route('/gabarito/<string:gabarito_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def get_gabarito(gabarito_id):
    """
    Busca um gabarito com o mesmo histórico **generations** da listagem (todas as gerações / ZIPs).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404

        if gabarito.created_by and str(gabarito.created_by) != str(user.get('id')):
            return jsonify({"error": "Você não tem permissão para acessar este gabarito"}), 403

        generations_list = []
        try:
            gen_rows = (
                AnswerSheetGabaritoGeneration.query.filter_by(gabarito_id=gabarito_id)
                .order_by(desc(AnswerSheetGabaritoGeneration.created_at))
                .all()
            )
            for gr in gen_rows:
                row_dict = gr.to_dict()
                row_dict["scope_snapshot"] = enrich_scope_snapshot(row_dict.get("scope_snapshot"))
                _dl = url_for(
                    "answer_sheets.download_gabarito",
                    gabarito_id=str(gr.gabarito_id),
                    _external=True,
                )
                row_dict["download_url"] = (
                    f"{_dl}?{urlencode({'redirect': '1', 'job_id': row_dict['job_id']})}"
                )
                generations_list.append(row_dict)
        except Exception as gen_err:
            logging.warning("get_gabarito generations: %s", gen_err, exc_info=True)
        
        return jsonify({
            "id": gabarito.id,
            "test_id": gabarito.test_id,
            "class_id": gabarito.class_id,
            "num_questions": gabarito.num_questions,
            "use_blocks": gabarito.use_blocks,
            "blocks_config": gabarito.blocks_config,
            "correct_answers": gabarito.correct_answers,
            "title": gabarito.title,
            "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None,
            "latest_generation_job_id": gabarito.last_generation_job_id,
            "generations": generations_list,
            "generations_count": len(generations_list),
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar gabarito: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao buscar gabarito: {str(e)}"}), 500


@bp.route('/gabaritos/<string:gabarito_id>', methods=['PATCH', 'POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def patch_gabarito_correct_answers(gabarito_id: str):
    """
    Edita APENAS o gabarito (correct_answers) e dispara recálculo dos resultados.

    Body:
        { "correct_answers": { "1": "A", "2": "B", ... } }

    Métodos:
        - PATCH: semântica REST de edição parcial.
        - POST: mesmo corpo e comportamento; use no browser se o preflight CORS
          do ambiente não listar PATCH em Access-Control-Allow-Methods.

    Returns (202 em sucesso):
        { status, job_id, gabarito_id, polling_url, task_id?, recalculated_sync }

        Sempre **202 Accepted** quando o recálculo foi aceito/concluído com sucesso
        (incluindo execução síncrona). O cliente usa `status` e `recalculated_sync`
        para saber se precisa do polling; não use só o código HTTP para isso.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404

        # Permissão: apenas criador (padrão já adotado em outras rotas do módulo)
        if gabarito.created_by and str(gabarito.created_by) != str(user.get("id")):
            return jsonify({"error": "Você não tem permissão para editar este gabarito"}), 403
        if not gabarito.created_by:
            return jsonify({"error": "Gabarito sem criador definido não pode ser editado"}), 403

        data = request.get_json() or {}
        if "correct_answers" not in data:
            return jsonify({"error": "Campo 'correct_answers' é obrigatório"}), 400

        from app.services.cartao_resposta.answer_sheet_recalculation_service import (
            validate_correct_answers_payload,
        )

        ok, err, normalized = validate_correct_answers_payload(
            data.get("correct_answers"),
            int(gabarito.num_questions or 0),
        )
        if not ok:
            return jsonify({"error": err}), 400

        gabarito.correct_answers = {str(k): v for k, v in normalized.items()}
        db.session.commit()

        # Criar job de recálculo (um item por AnswerSheetResult)
        results = (
            AnswerSheetResult.query.options(joinedload(AnswerSheetResult.student))
            .filter_by(gabarito_id=gabarito_id)
            .all()
        )

        job_id = str(uuid.uuid4())
        items_meta = []
        for r in results:
            st = getattr(r, "student", None)
            items_meta.append(
                {
                    "student_id": str(r.student_id) if r.student_id else None,
                    "student_name": getattr(st, "name", "") if st else "",
                }
            )

        create_job(
            job_id,
            len(items_meta),
            gabarito_id=str(gabarito_id),
            user_id=str(user.get("id")),
            task_ids=[],
            items_meta=items_meta if items_meta else None,
            stage_message="Recalculando resultados...",
        )

        context = get_current_tenant_context()
        city_id = str(context.city_id) if context else None
        if not city_id:
            return jsonify({"error": "Contexto de município não encontrado"}), 400

        # Espelho em public.answer_sheet_generation_jobs: GET /recalculate-jobs/.../status
        # em outro worker ou sem Redis ainda encontra o job (contadores/status).
        try:
            from app.services.answer_sheet_job_store import create_answer_sheet_job
            from sqlalchemy.exc import IntegrityError

            create_answer_sheet_job(
                job_id,
                len(items_meta),
                str(gabarito_id),
                str(user.get("id")),
                [],
                city_id,
                scope_type="recalculate_gabarito",
            )
        except IntegrityError:
            db.session.rollback()
            logging.debug("Job de recálculo %s já existia na tabela (reuso)", job_id)
        except Exception as db_job_err:
            db.session.rollback()
            logging.warning(
                "Espelho DB do job de recálculo não criado (GET status pode falhar entre workers): %s",
                db_job_err,
            )

        # Disparar task Celery (ou recálculo síncrono se broker/Redis indisponível)
        from app.services.celery_tasks.answer_sheet_tasks import (
            recalculate_answer_sheet_results_for_gabarito,
            run_recalculate_answer_sheet_results_for_gabarito,
        )
        from app.services.progress_store import update_job
        from app.services.answer_sheet_job_store import update_answer_sheet_job

        task_id = None
        recalculated_sync = False

        def _run_sync_recalc() -> None:
            run_recalculate_answer_sheet_results_for_gabarito(
                str(gabarito_id), job_id, city_id
            )

        # Evita chamar apply_async quando algum Redis configurado não aceita TCP:
        # o cliente tenta reconectar dezenas de vezes e segura a requisição ~20s+.
        if any_configured_redis_tcp_unreachable():
            logging.warning(
                "Redis inacessível (pré-check TCP); recálculo síncrono para gabarito %s",
                gabarito_id,
            )
            try:
                _run_sync_recalc()
                recalculated_sync = True
            except Exception as sync_err:
                logging.error(
                    "Recálculo síncrono falhou para gabarito %s: %s",
                    gabarito_id,
                    sync_err,
                    exc_info=True,
                )
                return jsonify(
                    {
                        "error": "Recálculo falhou (Redis inacessível e execução síncrona falhou).",
                        "details": str(sync_err),
                        "job_id": job_id,
                    }
                ), 500
        else:
            try:
                # ignore_result reduz uso do result backend (Redis) ao publicar a task
                task = recalculate_answer_sheet_results_for_gabarito.apply_async(
                    args=[str(gabarito_id), job_id, city_id],
                    ignore_result=True,
                )
                task_id = task.id
                update_job(job_id, {"task_ids": [task.id]})
                try:
                    update_answer_sheet_job(job_id, {"task_ids": [task.id]})
                except Exception as upd_db_err:
                    logging.debug(
                        "Não foi possível gravar task_ids no job DB %s: %s", job_id, upd_db_err
                    )
            except Exception as enqueue_err:
                logging.warning(
                    "Fila Celery indisponível (%s); executando recálculo síncrono",
                    enqueue_err,
                )
                try:
                    _run_sync_recalc()
                    recalculated_sync = True
                except Exception as sync_err:
                    logging.error(
                        "Recálculo síncrono falhou para gabarito %s: %s",
                        gabarito_id,
                        sync_err,
                        exc_info=True,
                    )
                    return jsonify(
                        {
                            "error": "Recálculo falhou (Celery indisponível e execução síncrona falhou).",
                            "details": str(sync_err),
                            "job_id": job_id,
                        }
                    ), 500

        payload_status = "completed" if recalculated_sync else "processing"

        # Sempre 202: clientes que só aceitam 202 como “iniciou” quebravam com 200
        # quando o recálculo rodava síncrono (Redis/Celery indisponível).
        return (
            jsonify(
                {
                    "status": payload_status,
                    "job_id": job_id,
                    "task_id": task_id,
                    "gabarito_id": str(gabarito_id),
                    "polling_url": f"/answer-sheets/recalculate-jobs/{job_id}/status",
                    "recalculated_sync": recalculated_sync,
                }
            ),
            202,
        )
    except Exception as e:
        db.session.rollback()
        logging.error("Erro ao editar gabarito %s: %s", gabarito_id, e, exc_info=True)
        return jsonify({"error": "Erro ao editar gabarito"}), 500


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
        corrector = AnswerSheetCorrectionNewGrid(debug=Config.OMR_DEBUG)
        
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
        
        # Mapear alternativas e skills por questão (topology em blocks_config)
        alternatives_map = {}
        skills_map = {}
        for block in blocks:
            for question in block.get('questions', []):
                q_num = question.get('q')
                alternatives = question.get('alternatives', [])
                alternatives_map[q_num] = alternatives
                skills_map[q_num] = question.get('skills', [])
        
        # Carregar Skills para enriquecer detailed_questions
        all_skill_ids = set()
        for ids in skills_map.values():
            all_skill_ids.update(str(sid) for sid in ids if sid)
        skills_by_id = {}
        if all_skill_ids:
            skills_list = Skill.query.filter(Skill.id.in_(all_skill_ids)).all()
            skills_by_id = {str(s.id): s for s in skills_list}
        
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
            
            # Skills da questão (da topology)
            skill_ids = skills_map.get(q_num, [])
            skills_payload = [
                {"id": str(skills_by_id[sid].id), "code": skills_by_id[sid].code, "description": skills_by_id[sid].description}
                for sid in skill_ids
                if sid and str(sid) in skills_by_id
            ]
            
            detailed_questions.append({
                "question": q_num,
                "alternatives": alternatives,
                "num_alternatives": num_alternatives,
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "status": status,
                "skills": skills_payload
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
# RESULTADOS AGREGADOS (cartões resposta) — semelhante a evaluation_results
# ============================================================================

def _is_valid_filter(value):
    return value and str(value).strip().lower() != 'all'


def _parse_cartao_periodo_bounds(periodo: str) -> Tuple[datetime, datetime]:
    """periodo no formato YYYY-MM → primeiro e último dia do mês (datetime 00:00)."""
    s = str(periodo).strip()
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if not m:
        raise ValueError("Use o formato YYYY-MM (ex.: 2026-04).")
    year, month = int(m.group(1)), int(m.group(2))
    if month < 1 or month > 12:
        raise ValueError("Mês deve estar entre 01 e 12.")
    last = monthrange(year, month)[1]
    return datetime(year, month, 1), datetime(year, month, last)


def _apply_answer_sheet_result_period_filter(query, periodo_bounds: Optional[Tuple[datetime, datetime]]):
    """Restringe a correções com corrected_at no mês (exclusivo no fim do mês)."""
    if periodo_bounds is None:
        return query
    dt_inicio, dt_fim = periodo_bounds
    end_exclusive = dt_fim + timedelta(days=1)
    return query.filter(
        AnswerSheetResult.corrected_at.isnot(None),
        AnswerSheetResult.corrected_at >= dt_inicio,
        AnswerSheetResult.corrected_at < end_exclusive,
    )


def _dedupe_answer_sheet_results_latest_per_student(
    results: List[AnswerSheetResult],
) -> List[AnswerSheetResult]:
    """
    Um aluno conta uma vez por gabarito nas agregações. Se houver vários AnswerSheetResult
    para o mesmo student_id, mantém o mais recente (corrected_at maior; desempate por id).
    Registros sem corrected_at perdem para qualquer um com data.
    """
    if not results:
        return []

    def _prefer_newer(a: AnswerSheetResult, b: AnswerSheetResult) -> AnswerSheetResult:
        ta, tb = a.corrected_at, b.corrected_at
        if ta is not None and tb is None:
            return a
        if ta is None and tb is not None:
            return b
        if ta is not None and tb is not None and ta != tb:
            return a if ta > tb else b
        return a if str(a.id) >= str(b.id) else b

    by_student: Dict[str, AnswerSheetResult] = {}
    for r in results:
        sid = str(r.student_id)
        if sid not in by_student:
            by_student[sid] = r
        else:
            by_student[sid] = _prefer_newer(r, by_student[sid])
    return list(by_student.values())


def _school_ids_com_correcao_cartao_no_periodo(
    gabarito_id: str, school_ids: List[str], periodo_bounds: Tuple[datetime, datetime]
) -> set:
    """IDs de escolas (como string) com pelo menos uma correção do gabarito no período."""
    if not school_ids:
        return set()
    class_ids = [c.id for c in Class.query.filter(Class.school_id.in_(school_ids)).all()]
    if not class_ids:
        return set()
    stu = [s.id for s in Student.query.filter(Student.class_id.in_(class_ids)).all()]
    if not stu:
        return set()
    _rq = AnswerSheetResult.query.filter(
        AnswerSheetResult.gabarito_id == gabarito_id,
        AnswerSheetResult.student_id.in_(stu),
    )
    _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
    hit_students = {row[0] for row in _rq.with_entities(AnswerSheetResult.student_id).distinct().all()}
    if not hit_students:
        return set()
    classes_hit = Student.query.filter(Student.id.in_(hit_students)).with_entities(Student.class_id).distinct().all()
    cids = [c[0] for c in classes_hit if c[0]]
    if not cids:
        return set()
    return {str(c.school_id) for c in Class.query.filter(Class.id.in_(cids)).all() if c.school_id}


def _determinar_escopo_busca_cartao(
    estado, municipio, escola, serie, turma, gabarito, user=None, periodo_bounds=None
):
    """
    Determina o escopo de busca para resultados agregados de cartões resposta.
    Escolas = escolas do município que têm pelo menos um resultado do gabarito (quando gabarito selecionado).
    """
    try:
        from app.permissions import get_user_permission_scope
        permissao = get_user_permission_scope(user) if user else {'permitted': True, 'scope': 'all'}
        if not permissao.get('permitted'):
            return None

        municipio_id = None
        city_data = None
        if _is_valid_filter(municipio):
            city = City.query.get(municipio) or City.query.filter(City.name.ilike(f"%{municipio}%")).first()
            if city:
                municipio_id = city.id
                city_data = city
        elif _is_valid_filter(estado):
            city = City.query.filter(City.state.ilike(f"%{estado}%")).first()
            if city:
                municipio_id = city.id
                city_data = city
        if not municipio_id:
            return None

        if user and permissao.get('scope') == 'municipio' and str(user.get('city_id')) != str(municipio_id):
            return None

        escolas = []
        gabarito_id = str(gabarito).strip() if _is_valid_filter(gabarito) else None

        if gabarito_id:
            # Validar acesso ao gabarito:
            # - Admin/tecadm/diretor/coordenador: basta existir
            # - Professor: pode acessar se (a) criou OU (b) o gabarito está vinculado a turma/escola em que ele está vinculado
            g = AnswerSheetGabarito.query.get(gabarito_id)
            if not g:
                return None
            if user and str(user.get('role') or '').lower() == 'professor':
                created_by_ok = str(getattr(g, "created_by", None) or "") == str(user.get("id"))
                vinculado_ok = False
                try:
                    from app.models.teacher import Teacher
                    from app.models.teacherClass import TeacherClass

                    teacher = Teacher.query.filter_by(user_id=user["id"]).first()
                    if teacher:
                        tc = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                        teacher_class_ids = [t.class_id for t in tc if t.class_id]
                        if teacher_class_ids:
                            teacher_school_ids = list(
                                {
                                    c.school_id
                                    for c in Class.query.filter(Class.id.in_(teacher_class_ids)).all()
                                    if c.school_id
                                }
                            )
                            vinculado_ok = (
                                (getattr(g, "class_id", None) in teacher_class_ids)
                                or (getattr(g, "school_id", None) in teacher_school_ids)
                            )
                except Exception:
                    vinculado_ok = False
                # Caso city/escopos múltiplos: school_id/class_id podem ser nulos; validar pelo escopo real
                # (union de gerações/batch/resultados) intersectando com as turmas do professor.
                if not vinculado_ok:
                    try:
                        from app.report_analysis.answer_sheet_report_builder import (
                            union_target_class_ids_for_gabarito,
                        )

                        allowed = set()
                        try:
                            from app.permissions.utils import get_teacher_classes

                            allowed = {str(x) for x in (get_teacher_classes(user["id"]) or []) if x}
                        except Exception:
                            allowed = set()
                        if allowed:
                            tgt = {str(x) for x in (union_target_class_ids_for_gabarito(g) or set()) if x}
                            vinculado_ok = bool(tgt & allowed)
                    except Exception:
                        pass
                if not (created_by_ok or vinculado_ok):
                    return None
            # Turmas que têm pelo menos um resultado deste gabarito (opcionalmente no mês de corrected_at)
            _rq = AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
            _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
            results = _rq.all()
            student_ids = list({r.student_id for r in results})
            if not student_ids:
                return {'municipio_id': municipio_id, 'city_data': city_data, 'escolas': [], 'estado': estado, 'municipio': municipio, 'escola': escola, 'serie': serie, 'turma': turma, 'gabarito': gabarito}
            students = Student.query.filter(Student.id.in_(student_ids)).filter(Student.class_id.isnot(None)).all()
            class_ids = list({s.class_id for s in students})
            if not class_ids:
                return {'municipio_id': municipio_id, 'city_data': city_data, 'escolas': [], 'estado': estado, 'municipio': municipio, 'escola': escola, 'serie': serie, 'turma': turma, 'gabarito': gabarito}
            classes = Class.query.filter(Class.id.in_(class_ids)).all()
            school_ids = list({c.school_id for c in classes if c.school_id})
            if not school_ids:
                return {'municipio_id': municipio_id, 'city_data': city_data, 'escolas': [], 'estado': estado, 'municipio': municipio, 'escola': escola, 'serie': serie, 'turma': turma, 'gabarito': gabarito}
            escolas = School.query.filter(School.id.in_(school_ids), School.city_id == municipio_id).all()
            if _is_valid_filter(escola):
                escolas = [e for e in escolas if str(e.id) == str(escola)]
        else:
            if _is_valid_filter(escola):
                school = School.query.filter(School.id == escola).first() or School.query.filter(School.name.ilike(f"%{escola}%")).first()
                if school and (not municipio_id or school.city_id == municipio_id):
                    escolas = [school]
            else:
                escolas = School.query.filter_by(city_id=municipio_id).all()

        if user and permissao.get('scope') == 'escola':
            if user.get('role') in ['diretor', 'coordenador']:
                from app.models.manager import Manager
                manager = Manager.query.filter_by(user_id=user['id']).first()
                escolas = [e for e in escolas if manager and str(e.id) == str(manager.school_id)] if manager else []
            elif user.get('role') == 'professor':
                from app.models.teacher import Teacher
                from app.models.teacherClass import TeacherClass
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    tc = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                    teacher_class_ids = [t.class_id for t in tc]
                    if teacher_class_ids:
                        teacher_school_ids = list({c.school_id for c in Class.query.filter(Class.id.in_(teacher_class_ids)).all() if c.school_id})
                        escolas = [e for e in escolas if e.id in teacher_school_ids]
                    else:
                        escolas = []

        return {
            'municipio_id': municipio_id,
            'city_data': city_data,
            'escolas': escolas,
            'estado': estado,
            'municipio': municipio,
            'escola': escola,
            'serie': serie,
            'turma': turma,
            'gabarito': gabarito,
        }
    except Exception as e:
        logging.error(f"Erro ao determinar escopo cartão: {str(e)}", exc_info=True)
        return None


def _determinar_nivel_granularidade_cartao(estado, municipio, escola, serie, turma, gabarito):
    if not _is_valid_filter(gabarito):
        return "municipio" if _is_valid_filter(municipio) else "estado"
    if _is_valid_filter(turma):
        return "turma"
    if _is_valid_filter(serie):
        return "serie"
    if _is_valid_filter(escola):
        return "escola"
    return "municipio"


def _get_nome_granularidade_cartao(nivel, scope_info, escola_nome, serie_nome):
    if nivel == "turma":
        return f"Turma - {serie_nome}" if serie_nome else "Turma"
    if nivel == "serie":
        return serie_nome or "Série"
    if nivel == "escola":
        return escola_nome or "Escola"
    if nivel == "municipio":
        city = scope_info.get('city_data')
        return city.name if city else "Município"
    return "Geral"


def _get_empty_statistics_gerais_cartao(scope_info, nivel_granularidade):
    city_data = scope_info.get('city_data')
    escola_nome = None
    serie_nome = None

    # Mesmo sem alunos/turmas no recorte, devolver o "contexto" selecionado (UX)
    try:
        if scope_info.get('escola') and _is_valid_filter(scope_info.get('escola')):
            s = School.query.get(scope_info['escola'])
            escola_nome = s.name if s else None
    except Exception:
        escola_nome = None

    try:
        if scope_info.get('serie') and _is_valid_filter(scope_info.get('serie')):
            g = Grade.query.get(scope_info['serie'])
            serie_nome = g.name if g else None
    except Exception:
        serie_nome = None

    # Se houver gabarito, tentar inferir a série a partir dele (ex.: gabarito por série)
    try:
        if serie_nome is None and scope_info.get('gabarito') and _is_valid_filter(scope_info.get('gabarito')):
            gab = AnswerSheetGabarito.query.get(str(scope_info.get('gabarito')).strip())
            if gab:
                if gab.grade_name and str(gab.grade_name).strip():
                    serie_nome = gab.grade_name.strip()
                elif gab.grade_id:
                    g = Grade.query.get(gab.grade_id)
                    serie_nome = g.name if g else None
    except Exception:
        pass

    return {
        "tipo": nivel_granularidade,
        "nome": _get_nome_granularidade_cartao(nivel_granularidade, scope_info, escola_nome, serie_nome),
        "estado": scope_info.get('estado', 'Todos os estados'),
        "municipio": city_data.name if city_data else "Todos os municípios",
        "escola": escola_nome,
        "serie": serie_nome,
        "total_escolas": 0,
        "total_series": 0,
        "total_turmas": 0,
        "total_gabaritos": 0,
        "total_alunos": 0,
        "alunos_participantes": 0,
        "alunos_pendentes": 0,
        "alunos_ausentes": 0,
        "percentual_comparecimento": 0.0,
        "nivel_classificacao": None,
        "media_nota_geral": 0.0,
        "media_proficiencia_geral": 0.0,
        "distribuicao_classificacao_geral": {
            "abaixo_do_basico": 0,
            "basico": 0,
            "adequado": 0,
            "avancado": 0
        }
    }


def _determinar_escopo_calculo_cartao(scope_info, nivel_granularidade):
    escopo = {}
    if nivel_granularidade == "municipio":
        escopo['tipo'] = "municipio"
        escopo['municipio_id'] = scope_info.get('municipio_id')
        escopo['gabarito_id'] = scope_info.get('gabarito')
    elif nivel_granularidade == "escola":
        escopo['tipo'] = "escola"
        escopo['escola_id'] = scope_info.get('escola')
        escopo['gabarito_id'] = scope_info.get('gabarito')
        escopo['municipio_id'] = scope_info.get('municipio_id')
    elif nivel_granularidade == "serie":
        escopo['tipo'] = "serie"
        escopo['serie_id'] = scope_info.get('serie')
        escopo['escola_id'] = scope_info.get('escola')
        escopo['gabarito_id'] = scope_info.get('gabarito')
        escopo['municipio_id'] = scope_info.get('municipio_id')
    elif nivel_granularidade == "turma":
        escopo['tipo'] = "turma"
        escopo['turma_id'] = scope_info.get('turma')
        escopo['serie_id'] = scope_info.get('serie')
        escopo['escola_id'] = scope_info.get('escola')
        escopo['gabarito_id'] = scope_info.get('gabarito')
        escopo['municipio_id'] = scope_info.get('municipio_id')
    return escopo


def _obter_class_ids_com_resultado_cartao(gabarito_id, escopo, periodo_bounds=None):
    """Retorna class_ids no escopo que têm pelo menos um resultado do gabarito."""
    if not gabarito_id:
        return []
    _rq = AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
    _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
    results = _rq.all()
    student_ids = list({r.student_id for r in results})
    if not student_ids:
        return []
    students = Student.query.filter(Student.id.in_(student_ids)).filter(Student.class_id.isnot(None)).all()
    class_ids = list({s.class_id for s in students})
    if not class_ids:
        return []
    q = Class.query.filter(Class.id.in_(class_ids))
    if escopo.get('tipo') == 'municipio' and escopo.get('municipio_id'):
        q = q.join(School, School.id == cast(Class.school_id, String)).filter(School.city_id == escopo['municipio_id'])
    elif escopo.get('tipo') == 'escola' and escopo.get('escola_id'):
        q = q.filter(Class.school_id == escopo['escola_id'])
    elif escopo.get('tipo') == 'serie':
        q = q.filter(Class.grade_id == escopo.get('serie_id'))
        if escopo.get('escola_id'):
            q = q.filter(Class.school_id == escopo['escola_id'])
    elif escopo.get('tipo') == 'turma' and escopo.get('turma_id'):
        q = q.filter(Class.id == escopo['turma_id'])
    return [c.id for c in q.all()]


def _class_ids_alunos_previstos_cartao(
    gabarito_id: Optional[str],
    scope_info: dict,
    nivel_granularidade: str,
    user: Optional[dict] = None,
) -> List[Any]:
    """
    Turmas-alvo do cartão conforme criação do gabarito (scope_snapshot, batch, escopo legado),
    recortadas pelo filtro da URL (município / escola / série / turma) e pela permissão.
    Usado para total de alunos previstos em resultados agregados.
    """
    if not gabarito_id or not scope_info:
        return []
    gid = str(gabarito_id).strip()
    gab = AnswerSheetGabarito.query.get(gid)
    if not gab:
        return []

    from uuid import UUID

    from app.report_analysis.answer_sheet_report_builder import _resolve_target_class_ids

    municipio_id = scope_info.get('municipio_id')
    escola_param = scope_info.get('escola')
    serie_param = scope_info.get('serie')
    turma_param = scope_info.get('turma')

    if _is_valid_filter(escola_param):
        rtype = 'school'
        ref = str(escola_param).strip()
    else:
        rtype = 'city'
        ref = str(municipio_id) if municipio_id else None

    if not ref:
        return []

    raw_ids = _resolve_target_class_ids(gab, rtype, ref)
    if not raw_ids:
        return []

    restrict_school_id = None
    if user:
        from app.permissions import get_user_permission_scope

        perm = get_user_permission_scope(user)
        if perm.get('scope') == 'escola' and user.get('role') in ('diretor', 'coordenador'):
            from app.models.manager import Manager

            mgr = Manager.query.filter_by(user_id=user['id']).first()
            if mgr and mgr.school_id:
                restrict_school_id = str(mgr.school_id)

    out: List[Any] = []
    for cid_str in raw_ids:
        try:
            uid = UUID(str(cid_str))
        except ValueError:
            continue
        c = Class.query.get(uid)
        if not c:
            continue
        if restrict_school_id and str(c.school_id) != restrict_school_id:
            continue
        if _is_valid_filter(turma_param):
            if str(c.id) != str(turma_param).strip():
                continue
        elif _is_valid_filter(serie_param):
            if not c.grade_id or str(c.grade_id) != str(serie_param).strip():
                continue
        out.append(c.id)

    if user and user.get('role') == 'professor':
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass

        teacher = Teacher.query.filter_by(user_id=user['id']).first()
        if not teacher:
            return []
        allowed = {tc.class_id for tc in TeacherClass.query.filter_by(teacher_id=teacher.id).all()}
        out = [x for x in out if x in allowed]

    return out


def _calcular_estatisticas_consolidadas_cartao(scope_info, nivel_granularidade, gabarito_id, user, periodo_bounds=None):
    try:
        class_ids = _class_ids_alunos_previstos_cartao(gabarito_id, scope_info, nivel_granularidade, user)
        if not class_ids:
            return _get_empty_statistics_gerais_cartao(scope_info, nivel_granularidade)

        todos_alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
        total_alunos = len(todos_alunos)
        student_ids = [a.id for a in todos_alunos]
        if not gabarito_id:
            resultados = []
        else:
            _rq = AnswerSheetResult.query.filter(
                AnswerSheetResult.gabarito_id == gabarito_id,
                AnswerSheetResult.student_id.in_(student_ids),
            )
            _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
            resultados = _rq.all()
        resultados = _dedupe_answer_sheet_results_latest_per_student(resultados)
        alunos_participantes = len(resultados)
        # Agregação hierárquica (município = média das escolas; escola = média das séries; …)
        from app.utils.school_equal_weight_means import (
            granularidade_to_hierarchical_target,
            hierarchical_mean_grade_and_proficiency,
        )

        if resultados:
            media_nota, media_prof = hierarchical_mean_grade_and_proficiency(
                resultados, granularidade_to_hierarchical_target(nivel_granularidade)
            )
        else:
            media_nota = 0.0
            media_prof = 0.0
        dist = {'abaixo_do_basico': 0, 'basico': 0, 'adequado': 0, 'avancado': 0}
        for r in resultados:
            c = r.classification
            if not c:
                continue
            cl = c.lower()
            # "Básico" contém "básico": testar "abaixo" antes para não confundir com "Abaixo do Básico"
            if 'abaixo' in cl:
                dist['abaixo_do_basico'] += 1
            elif 'básico' in cl or 'basico' in cl:
                dist['basico'] += 1
            elif 'adequado' in cl:
                dist['adequado'] += 1
            elif 'avançado' in cl or 'avancado' in cl:
                dist['avancado'] += 1

        escolas_unicas = set()
        series_unicas = set()
        turmas_unicas = set(class_ids)
        for c in Class.query.filter(Class.id.in_(class_ids)).all():
            if c.school_id:
                escolas_unicas.add(c.school_id)
            if c.grade_id:
                series_unicas.add(c.grade_id)

        escola_nome = None
        serie_nome = None
        if scope_info.get('escola') and _is_valid_filter(scope_info.get('escola')):
            s = School.query.get(scope_info['escola'])
            escola_nome = s.name if s else None
        if scope_info.get('serie') and _is_valid_filter(scope_info.get('serie')):
            g = Grade.query.get(scope_info['serie'])
            serie_nome = g.name if g else None

        # Com gabarito na consulta, a série do cartão resposta deve aparecer mesmo sem filtro ?serie=
        if serie_nome is None and gabarito_id:
            gab = AnswerSheetGabarito.query.get(str(gabarito_id).strip())
            if gab:
                if gab.grade_name and str(gab.grade_name).strip():
                    serie_nome = gab.grade_name.strip()
                elif gab.grade_id:
                    g = Grade.query.get(gab.grade_id)
                    serie_nome = g.name if g else None
        if serie_nome is None and len(series_unicas) == 1:
            only_gid = next(iter(series_unicas))
            g = Grade.query.get(only_gid)
            serie_nome = g.name if g else None

        pct = round(100.0 * alunos_participantes / total_alunos, 2) if total_alunos else 0.0
        nivel_classificacao_geral = None
        if gabarito_id and alunos_participantes:
            gab_stat = AnswerSheetGabarito.query.get(str(gabarito_id).strip())
            if gab_stat:
                nivel_classificacao_geral = _nivel_escola_por_media_proficiencia_cartao(media_prof, gab_stat)

        return {
            "tipo": nivel_granularidade,
            "nome": _get_nome_granularidade_cartao(nivel_granularidade, scope_info, escola_nome, serie_nome),
            "estado": scope_info.get('estado', 'Todos os estados'),
            "municipio": scope_info.get('city_data').name if scope_info.get('city_data') else "Todos os municípios",
            "escola": escola_nome,
            "serie": serie_nome,
            "total_escolas": len(escolas_unicas),
            "total_series": len(series_unicas),
            "total_turmas": len(turmas_unicas),
            "total_gabaritos": 1 if gabarito_id else 0,
            "total_alunos": total_alunos,
            "alunos_participantes": alunos_participantes,
            "alunos_pendentes": total_alunos - alunos_participantes,
            "alunos_ausentes": max(0, total_alunos - alunos_participantes),
            "percentual_comparecimento": pct,
            "nivel_classificacao": nivel_classificacao_geral,
            "media_nota_geral": round(media_nota, 2),
            "media_proficiencia_geral": round(media_prof, 2),
            "distribuicao_classificacao_geral": dist
        }
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas consolidadas cartão: {str(e)}", exc_info=True)
        return _get_empty_statistics_gerais_cartao(scope_info, nivel_granularidade)


def _calcular_estatisticas_grupo_cartao(
    class_ids, gabarito_id, periodo_bounds=None, aggregation_level: str = "escola"
):
    """Estatísticas para um grupo de turmas (usado em resultados_detalhados).

    ``aggregation_level``: ``escola`` (média séries→turmas→alunos), ``serie``, ``turma`` —
    conforme o que o grupo representa (ex.: uma escola inteira vs uma série vs uma turma).
    """
    if not class_ids or not gabarito_id:
        return {'total_alunos': 0, 'alunos_participantes': 0, 'alunos_pendentes': 0, 'media_nota': 0.0, 'media_proficiencia': 0.0, 'distribuicao_classificacao': {'abaixo_do_basico': 0, 'basico': 0, 'adequado': 0, 'avancado': 0}}
    alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
    total_alunos = len(alunos)
    sid_list = [a.id for a in alunos]
    _rq = AnswerSheetResult.query.filter(AnswerSheetResult.gabarito_id == gabarito_id, AnswerSheetResult.student_id.in_(sid_list))
    _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
    resultados = _dedupe_answer_sheet_results_latest_per_student(_rq.all())
    participantes = len(resultados)
    from app.utils.school_equal_weight_means import hierarchical_mean_grade_and_proficiency

    if resultados:
        media_nota, media_prof = hierarchical_mean_grade_and_proficiency(
            resultados, aggregation_level
        )
    else:
        media_nota = 0.0
        media_prof = 0.0
    dist = {'abaixo_do_basico': 0, 'basico': 0, 'adequado': 0, 'avancado': 0}
    for r in resultados:
        c = r.classification
        cl = (c or '').lower()
        if 'abaixo' in cl:
            dist['abaixo_do_basico'] += 1
        elif 'básico' in cl or 'basico' in cl:
            dist['basico'] += 1
        elif 'adequado' in cl:
            dist['adequado'] += 1
        elif 'avançado' in cl or 'avancado' in cl:
            dist['avancado'] += 1
    return {'total_alunos': total_alunos, 'alunos_participantes': participantes, 'alunos_pendentes': total_alunos - participantes, 'media_nota': round(media_nota, 2), 'media_proficiencia': round(media_prof, 2), 'distribuicao_classificacao': dist}


def _subject_name_is_lingua_portuguesa(name: str) -> bool:
    n = (name or "").lower()
    return "portug" in n or "lingua" in n or "língua" in n or "lp " in n


def _subject_name_is_matematica(name: str) -> bool:
    return "matem" in (name or "").lower()


def _medias_por_disciplina_de_resultados_cartao(
    results: List[AnswerSheetResult],
    gabarito: Optional[AnswerSheetGabarito],
    aggregation_level: str = "municipio",
) -> Dict[str, Any]:
    """
    Agrega nota/proficiência por disciplina a partir de proficiency_by_subject (mesma lógica
    de _calcular_resultados_por_disciplina_cartao, recorte = lista de resultados já filtrada).
    """
    import json

    if not results or not gabarito:
        return {"lista": [], "media_nota_lp": None, "media_nota_mat": None}
    grade_name = (gabarito.grade_name or gabarito.title or "") or ""
    from app.services.cartao_resposta.proficiency_by_subject import _get_course_name_from_grade
    from app.services.evaluation_calculator import EvaluationCalculator

    course_name = _get_course_name_from_grade(grade_name)
    from app.utils.school_equal_weight_means import hierarchical_mean_from_subject_rows

    by_subject: Dict[str, Dict[str, Any]] = {}
    subject_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in results:
        pbs = r.proficiency_by_subject or {}
        if isinstance(pbs, str):
            try:
                pbs = json.loads(pbs)
            except Exception:
                pbs = {}
        for sid, data in (pbs or {}).items():
            sidk = str(sid)
            if sidk not in by_subject:
                by_subject[sidk] = {
                    "disciplina": (data.get("subject_name") if isinstance(data, dict) else None) or sidk,
                    "n": 0,
                }
            if not isinstance(data, dict):
                continue
            by_subject[sidk]["n"] += 1
            nota_disc = data.get("grade")
            if nota_disc is None and data.get("proficiency") is not None:
                subject_name = data.get("subject_name") or "Outras"
                nota_disc = EvaluationCalculator.calculate_grade(
                    data.get("proficiency"), course_name, subject_name
                )
            nf = float(nota_disc) if nota_disc is not None else 0.0
            pf = float(data.get("proficiency") or 0)
            subject_rows[sidk].append(
                {"student_id": r.student_id, "grade": nf, "proficiency": pf}
            )
            if data.get("subject_name"):
                by_subject[sidk]["disciplina"] = data.get("subject_name")

    lista = []
    notas_lp: List[float] = []
    notas_mat: List[float] = []
    for _sidk, agg in by_subject.items():
        n = agg["n"]
        if not n:
            continue
        nom = agg["disciplina"]
        rows = subject_rows.get(_sidk) or []
        mn, mp, _ = hierarchical_mean_from_subject_rows(rows, aggregation_level)
        mn = round(mn, 2)
        mp = round(mp, 2)
        lista.append({"disciplina": nom, "media_nota": mn, "media_proficiencia": mp})
        if _subject_name_is_lingua_portuguesa(nom):
            notas_lp.append(mn)
        if _subject_name_is_matematica(nom):
            notas_mat.append(mn)

    media_lp = round(sum(notas_lp) / len(notas_lp), 2) if notas_lp else None
    media_mat = round(sum(notas_mat) / len(notas_mat), 2) if notas_mat else None
    return {"lista": lista, "media_nota_lp": media_lp, "media_nota_mat": media_mat}


def _complementar_metricas_escola_municipio_cartao(
    stats: Dict[str, Any],
    class_ids: List[Any],
    gabarito_id: str,
    periodo_bounds: Optional[Tuple[datetime, datetime]],
    gabarito: AnswerSheetGabarito,
    aggregation_level: str = "municipio",
) -> Dict[str, Any]:
    """Campos extras para escopo município (comparecimento, nível, médias LP/MAT, ausentes)."""
    total = int(stats.get("total_alunos") or 0)
    part = int(stats.get("alunos_participantes") or 0)
    pct = round(100.0 * part / total, 2) if total else 0.0
    nivel = None
    if part:
        nivel = _nivel_escola_por_media_proficiencia_cartao(float(stats.get("media_proficiencia") or 0), gabarito)
    alunos = Student.query.filter(Student.class_id.in_(class_ids)).all() if class_ids else []
    sid_list = [a.id for a in alunos]
    results: List[AnswerSheetResult] = []
    if sid_list and gabarito_id:
        _rq = AnswerSheetResult.query.filter(
            AnswerSheetResult.gabarito_id == gabarito_id,
            AnswerSheetResult.student_id.in_(sid_list),
        )
        _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
        results = _dedupe_answer_sheet_results_latest_per_student(_rq.all())
    md = _medias_por_disciplina_de_resultados_cartao(results, gabarito, aggregation_level)
    ausentes = max(0, total - part)
    return {
        "percentual_comparecimento": pct,
        "nivel_classificacao": nivel,
        "media_nota_lingua_portuguesa": md["media_nota_lp"],
        "media_nota_matematica": md["media_nota_mat"],
        "medias_por_disciplina": md["lista"],
        "alunos_ausentes": ausentes,
    }


def _complementar_linha_resultado_detalhado_cartao(
    stats: Dict[str, Any],
    class_ids: List[Any],
    gabarito_id: str,
    periodo_bounds: Optional[Tuple[datetime, datetime]],
    gab: Optional[AnswerSheetGabarito],
    aggregation_level: str = "escola",
) -> Dict[str, Any]:
    """Campos extras (comparecimento, LP/MAT, disciplinas, ausentes) para cada linha de resultados_detalhados."""
    if gab:
        return _complementar_metricas_escola_municipio_cartao(
            stats, class_ids, gabarito_id, periodo_bounds, gab, aggregation_level
        )
    total = int(stats.get("total_alunos") or 0)
    part = int(stats.get("alunos_participantes") or 0)
    return {
        "percentual_comparecimento": round(100.0 * part / total, 2) if total else 0.0,
        "nivel_classificacao": None,
        "media_nota_lingua_portuguesa": None,
        "media_nota_matematica": None,
        "medias_por_disciplina": [],
        "alunos_ausentes": max(0, total - part),
    }


def _gerar_resultados_detalhados_por_granularidade_cartao(
    scope_info, nivel_granularidade, gabarito_id, periodo_bounds=None, user=None
):
    """Gera lista agregada por escola / série / turma."""
    gabarito_id = str(gabarito_id).strip() if gabarito_id else None
    if not gabarito_id:
        return []
    class_ids = _class_ids_alunos_previstos_cartao(gabarito_id, scope_info, nivel_granularidade, user)
    if not class_ids:
        return []
    classes = Class.query.filter(Class.id.in_(class_ids)).all()
    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
    titulo_gabarito = gabarito.title if gabarito else "Gabarito"
    city_data = scope_info.get('city_data')
    municipio_nome = city_data.name if city_data else "N/A"
    estado_nome = scope_info.get('estado', 'N/A')
    resultados_detalhados = []

    if nivel_granularidade == "municipio":
        by_school = {}
        for c in classes:
            sid = c.school_id
            if sid not in by_school:
                by_school[sid] = []
            by_school[sid].append(c.id)
        for sid, cids in by_school.items():
            school = School.query.get(sid)
            stats = _calcular_estatisticas_grupo_cartao(
                cids, gabarito_id, periodo_bounds, aggregation_level="escola"
            )
            comp = _complementar_linha_resultado_detalhado_cartao(
                stats, cids, gabarito_id, periodo_bounds, gabarito, aggregation_level="escola"
            )
            row = {
                "id": f"escola_{sid}",
                "escola_id": str(sid),
                "titulo": f"{titulo_gabarito} - {school.name if school else sid}",
                "serie": "Todas as séries",
                "turma": "Todas as turmas",
                "escola": school.name if school else "N/A",
                "municipio": municipio_nome,
                "estado": estado_nome,
                "total_alunos": stats['total_alunos'],
                "alunos_participantes": stats['alunos_participantes'],
                "alunos_pendentes": stats['alunos_pendentes'],
                "media_nota": stats['media_nota'],
                "media_proficiencia": stats['media_proficiencia'],
                "distribuicao_classificacao": stats['distribuicao_classificacao'],
            }
            row.update(comp)
            resultados_detalhados.append(row)

    elif nivel_granularidade == "escola":
        by_grade = {}
        for c in classes:
            gid = c.grade_id
            if gid not in by_grade:
                by_grade[gid] = []
            by_grade[gid].append(c.id)
        school = School.query.get(scope_info.get('escola')) if scope_info.get('escola') else None
        escola_nome = school.name if school else "N/A"
        escola_id_scope = (
            str(scope_info.get("escola")).strip() if scope_info and _is_valid_filter(scope_info.get("escola")) else None
        )
        for gid, cids in by_grade.items():
            grade = Grade.query.get(gid)
            stats = _calcular_estatisticas_grupo_cartao(
                cids, gabarito_id, periodo_bounds, aggregation_level="serie"
            )
            comp = _complementar_linha_resultado_detalhado_cartao(
                stats, cids, gabarito_id, periodo_bounds, gabarito, aggregation_level="serie"
            )
            row = {
                "id": f"serie_{gid}",
                "escola_id": escola_id_scope,
                "serie_id": str(gid) if gid else None,
                "titulo": f"{titulo_gabarito} - {grade.name if grade else gid}",
                "serie": grade.name if grade else "N/A",
                "turma": "Todas as turmas",
                "escola": escola_nome,
                "municipio": municipio_nome,
                "estado": estado_nome,
                "total_alunos": stats['total_alunos'],
                "alunos_participantes": stats['alunos_participantes'],
                "alunos_pendentes": stats['alunos_pendentes'],
                "media_nota": stats['media_nota'],
                "media_proficiencia": stats['media_proficiencia'],
                "distribuicao_classificacao": stats['distribuicao_classificacao'],
            }
            row.update(comp)
            resultados_detalhados.append(row)

    else:
        for c in classes:
            grade = Grade.query.get(c.grade_id) if c.grade_id else None
            school = School.query.get(c.school_id) if c.school_id else None
            cids_one = [c.id]
            stats = _calcular_estatisticas_grupo_cartao(
                cids_one, gabarito_id, periodo_bounds, aggregation_level="turma"
            )
            comp = _complementar_linha_resultado_detalhado_cartao(
                stats, cids_one, gabarito_id, periodo_bounds, gabarito, aggregation_level="turma"
            )
            row = {
                "id": f"turma_{c.id}",
                "escola_id": str(c.school_id) if c.school_id else None,
                "serie_id": str(c.grade_id) if c.grade_id else None,
                "turma_id": str(c.id),
                "titulo": f"{titulo_gabarito} - {c.name or f'Turma {c.id}'}",
                "serie": grade.name if grade else "N/A",
                "turma": c.name or f"Turma {c.id}",
                "escola": school.name if school else "N/A",
                "municipio": municipio_nome,
                "estado": estado_nome,
                "total_alunos": stats['total_alunos'],
                "alunos_participantes": stats['alunos_participantes'],
                "alunos_pendentes": stats['alunos_pendentes'],
                "media_nota": stats['media_nota'],
                "media_proficiencia": stats['media_proficiencia'],
                "distribuicao_classificacao": stats['distribuicao_classificacao'],
            }
            row.update(comp)
            resultados_detalhados.append(row)

    return resultados_detalhados


def _extrair_blocos_por_disciplina_cartao(blocks_config):
    """Agrupa blocos por subject_id (uma disciplina pode ter vários blocos). Retorna list de { id, nome, question_numbers }."""
    from app.services.cartao_resposta.proficiency_by_subject import _extract_blocks_with_questions
    blocks = _extract_blocks_with_questions(blocks_config)
    by_subject = {}
    for b in blocks:
        sid = b.get('subject_id') or f"block_{b.get('block_id', 0)}"
        sid = str(sid)
        name = b.get('subject_name') or 'Outras'
        if sid not in by_subject:
            by_subject[sid] = {'id': sid, 'nome': name, 'question_numbers': []}
        by_subject[sid]['question_numbers'].extend(b.get('question_numbers', []))
    return list(by_subject.values())


def _calcular_resultados_por_disciplina_cartao(
    scope_info, nivel_granularidade, gabarito_id, periodo_bounds=None, user=None
):
    """Retorna lista no mesmo formato de evaluation_results: resultados_por_disciplina."""
    if not gabarito_id:
        return []
    class_ids = _class_ids_alunos_previstos_cartao(gabarito_id, scope_info, nivel_granularidade, user)
    if not class_ids:
        return []
    student_ids = [s.id for s in Student.query.filter(Student.class_id.in_(class_ids)).all()]
    _rq = AnswerSheetResult.query.filter(
        AnswerSheetResult.gabarito_id == gabarito_id,
        AnswerSheetResult.student_id.in_(student_ids),
    )
    _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
    results = _dedupe_answer_sheet_results_latest_per_student(_rq.all())
    if not results:
        return []
    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
    grade_name = (gabarito.grade_name or gabarito.title or '') if gabarito else ''
    from app.services.cartao_resposta.proficiency_by_subject import _get_course_name_from_grade
    course_name = _get_course_name_from_grade(grade_name)
    from app.utils.school_equal_weight_means import (
        granularidade_to_hierarchical_target,
        hierarchical_mean_from_subject_rows,
    )

    tgt = granularidade_to_hierarchical_target(nivel_granularidade)
    subject_rows: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    # Agregar por disciplina a partir de proficiency_by_subject
    by_subject = {}
    for r in results:
        pbs = r.proficiency_by_subject or {}
        if isinstance(pbs, str):
            try:
                import json
                pbs = json.loads(pbs)
            except Exception:
                pbs = {}
        for sid, data in (pbs or {}).items():
            if sid not in by_subject:
                by_subject[sid] = {
                    'disciplina': data.get('subject_name', sid),
                    'total_alunos': 0,
                    'alunos_participantes': 0,
                    'dist': {'abaixo_do_basico': 0, 'basico': 0, 'adequado': 0, 'avancado': 0}
                }
            by_subject[sid]['alunos_participantes'] += 1
            nota_disc = data.get('grade')
            if nota_disc is None and data.get('proficiency') is not None:
                from app.services.evaluation_calculator import EvaluationCalculator
                subject_name = data.get('subject_name') or 'Outras'
                nota_disc = EvaluationCalculator.calculate_grade(
                    data.get('proficiency'), course_name, subject_name
                )
            nf = float(nota_disc) if nota_disc is not None else 0.0
            pf = float(data.get('proficiency') or 0)
            subject_rows[sid].append(
                {"student_id": r.student_id, "grade": nf, "proficiency": pf}
            )
            cl = (data.get('classification') or '').lower()
            if 'abaixo' in cl:
                by_subject[sid]['dist']['abaixo_do_basico'] += 1
            elif 'básico' in cl or 'basico' in cl:
                by_subject[sid]['dist']['basico'] += 1
            elif 'adequado' in cl:
                by_subject[sid]['dist']['adequado'] += 1
            elif 'avançado' in cl or 'avancado' in cl:
                by_subject[sid]['dist']['avancado'] += 1
    total_alunos = len(student_ids)
    out = []
    for sid, agg in by_subject.items():
        n = agg['alunos_participantes']
        rows = subject_rows.get(sid) or []
        media_nota, media_prof, _ = hierarchical_mean_from_subject_rows(rows, tgt)
        media_nota = round(media_nota, 2)
        media_prof = round(media_prof, 2)
        out.append({
            "disciplina": agg['disciplina'],
            "total_avaliacoes": 1,
            "total_alunos": total_alunos,
            "alunos_participantes": n,
            "alunos_pendentes": total_alunos - n,
            "alunos_ausentes": max(0, total_alunos - n),
            "media_nota": media_nota,
            "media_proficiencia": media_prof,
            "distribuicao_classificacao": agg['dist']
        })
    return out


def _build_question_skill_lookup_for_detailed_table(
    gabarito: AnswerSheetGabarito,
) -> Tuple[Dict[int, List[str]], Dict[str, Dict[str, str]]]:
    """
    Mapa questão -> lista de UUIDs (topology + fallback test_id) e
    UUID normalizado -> {id, code} para a tabela detalhada de resultados agregados.
    """
    from app.report_analysis.answer_sheet_report_builder import question_skills_map_for_answer_sheet

    q_map = question_skills_map_for_answer_sheet(gabarito)
    uuids_ordered = []
    seen = set()
    for lst in q_map.values():
        for sid in lst or []:
            t = str(sid).strip()
            if not t:
                continue
            try:
                u = uuid.UUID(t)
            except ValueError:
                continue
            us = str(u)
            if us not in seen:
                seen.add(us)
                uuids_ordered.append(u)
    skill_by_uuid: Dict[str, Dict[str, str]] = {}
    if uuids_ordered:
        rows = Skill.query.filter(Skill.id.in_(uuids_ordered)).all()
        for sk in rows:
            skill_by_uuid[str(sk.id)] = {
                "id": str(sk.id),
                "code": (sk.code or "").strip() or "N/A",
            }
    return q_map, skill_by_uuid


def _skills_payload_for_question_number(
    q_num: int,
    q_map: Dict[int, List[str]],
    skill_by_uuid: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    """Lista de {id, code} por questão; preserva token não-UUID como código de habilidade."""
    na = {"id": "N/A", "code": "N/A"}
    out: List[Dict[str, str]] = []
    for raw in q_map.get(q_num) or []:
        t = str(raw).strip()
        if not t:
            continue
        try:
            uid = str(uuid.UUID(t))
        except ValueError:
            # Token já pode ser código (ex.: EF15_D2). Não colapsar para N/A.
            out.append({"id": t, "code": t})
            continue
        row = skill_by_uuid.get(uid)
        out.append(dict(row) if row else na.copy())
    return out


def _gerar_tabela_detalhada_cartao(scope_info, nivel_granularidade, gabarito_id, user, periodo_bounds=None):
    """Tabela detalhada no mesmo formato de evaluation_results: disciplinas (com questões e alunos com respostas_por_questao) e geral (alunos com totais e proficiência geral)."""
    import json
    class_ids = _class_ids_alunos_previstos_cartao(gabarito_id, scope_info, nivel_granularidade, user)
    if not class_ids or not gabarito_id:
        return {"disciplinas": [], "geral": {"alunos": []}}
    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
    if not gabarito:
        return {"disciplinas": [], "geral": {"alunos": []}}
    correct_answers = gabarito.correct_answers
    if isinstance(correct_answers, str):
        correct_answers = json.loads(correct_answers)
    gabarito_dict = {}
    for k, v in (correct_answers or {}).items():
        try:
            gabarito_dict[int(k)] = str(v).upper() if v else ''
        except (ValueError, TypeError):
            pass
    blocks_config = getattr(gabarito, 'blocks_config', None) or {}
    disciplinas_config = _extrair_blocos_por_disciplina_cartao(blocks_config)
    if not disciplinas_config:
        disciplinas_config = [{'id': 'geral', 'nome': 'Geral', 'question_numbers': list(gabarito_dict.keys())}]
    student_ids = [s.id for s in Student.query.filter(Student.class_id.in_(class_ids)).all()]
    _rq = AnswerSheetResult.query.filter(
        AnswerSheetResult.gabarito_id == gabarito_id,
        AnswerSheetResult.student_id.in_(student_ids),
    )
    _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
    results = _dedupe_answer_sheet_results_latest_per_student(_rq.all())
    result_by_student = {r.student_id: r for r in results}
    classes_by_id = {c.id: c for c in Class.query.filter(Class.id.in_(class_ids)).all()}
    schools_by_id = {}
    for c in classes_by_id.values():
        if c.school_id and c.school_id not in schools_by_id:
            schools_by_id[c.school_id] = School.query.get(c.school_id)
    students = Student.query.filter(Student.id.in_(student_ids)).all()
    grade_name = gabarito.grade_name or gabarito.title or ''
    from app.services.cartao_resposta.proficiency_by_subject import _get_course_name_from_grade
    from app.services.evaluation_calculator import EvaluationCalculator
    course_name = _get_course_name_from_grade(grade_name)
    q_skills_map, skill_by_uuid = _build_question_skill_lookup_for_detailed_table(gabarito)

    def build_respostas_por_questao(question_numbers, detected_answers):
        respostas = []
        for q_num in sorted(question_numbers):
            resp = detected_answers.get(q_num) if detected_answers else None
            correct = gabarito_dict.get(q_num)
            acertou = (resp is not None and correct is not None and str(resp).upper().strip() == str(correct).upper().strip())
            respostas.append({
                "questao": q_num,
                "acertou": acertou,
                "respondeu": resp is not None,
                "resposta": str(resp) if resp is not None else None,
                "skills": _skills_payload_for_question_number(q_num, q_skills_map, skill_by_uuid),
            })
        return respostas

    disciplinas_out = []
    for disc_cfg in disciplinas_config:
        subject_id = disc_cfg.get('id', '')
        subject_name = disc_cfg.get('nome', 'Outras')
        q_numbers = disc_cfg.get('question_numbers', [])
        questoes = [
            {
                "numero": q,
                "skills": _skills_payload_for_question_number(q, q_skills_map, skill_by_uuid),
            }
            for q in sorted(q_numbers)
        ]
        alunos_disciplina = []
        for s in students:
            r = result_by_student.get(s.id)
            class_obj = classes_by_id.get(s.class_id) if s.class_id else None
            school_obj = schools_by_id.get(class_obj.school_id) if class_obj else None
            escola_nome = school_obj.name if school_obj else "N/A"
            serie_nome = (Grade.query.get(class_obj.grade_id).name if (class_obj and class_obj.grade_id) else None) or "N/A"
            turma_nome = class_obj.name if class_obj else "N/A"
            detected = (r.detected_answers if r else None) or {}
            if isinstance(detected, str):
                try:
                    detected = json.loads(detected)
                except Exception:
                    detected = {}
            detected = {int(k): v for k, v in detected.items() if k is not None}
            respostas_por_questao = build_respostas_por_questao(q_numbers, detected)
            total_acertos = sum(1 for x in respostas_por_questao if x.get('acertou'))
            total_respondidas = sum(1 for x in respostas_por_questao if x.get('respondeu'))
            total_questoes_disciplina = len(q_numbers)
            # Erros incluem: marcadas erradas, inválidas e em branco (não respondidas)
            total_erros = max(0, total_questoes_disciplina - total_acertos)
            pbs = (r.proficiency_by_subject or {}) if r else {}
            if isinstance(pbs, str):
                try:
                    pbs = json.loads(pbs)
                except Exception:
                    pbs = {}
            disc_data = (pbs or {}).get(str(subject_id), pbs.get(subject_id, {}))
            disciplina_proficiencia = disc_data.get('proficiency') if isinstance(disc_data, dict) else (r.proficiency if r else 0)
            disciplina_classificacao = disc_data.get('classification') if isinstance(disc_data, dict) else (r.classification if r else None)
            if isinstance(disc_data, dict) and disc_data.get('proficiency') is not None:
                disciplina_nota = EvaluationCalculator.calculate_grade(
                    proficiency=float(disc_data['proficiency']),
                    course_name=course_name,
                    subject_name=subject_name,
                    use_simple_calculation=False,
                )
            elif isinstance(disc_data, dict) and disc_data.get('grade') is not None:
                disciplina_nota = float(disc_data['grade'])
            else:
                disciplina_nota = 0.0
            alunos_disciplina.append({
                "id": str(s.id),
                "nome": s.name or "N/A",
                "escola": escola_nome,
                "serie": serie_nome,
                "turma": turma_nome,
                "respostas_por_questao": respostas_por_questao,
                "total_acertos": total_acertos,
                "total_erros": total_erros,
                "total_respondidas": total_respondidas,
                "total_questoes_disciplina": total_questoes_disciplina,
                "total_em_branco": total_questoes_disciplina - total_respondidas,
                "nivel_proficiencia": disciplina_classificacao,
                "nota": round(disciplina_nota, 2),
                "proficiencia": round(disciplina_proficiencia, 2) if disciplina_proficiencia else 0.0,
                "status": "concluida" if r else "pendente",
                # Percentual deve considerar o total de questões da disciplina (inclui em branco como erro)
                "percentual_acertos": round((total_acertos / total_questoes_disciplina * 100), 2) if total_questoes_disciplina > 0 else 0.0
            })
        disciplinas_out.append({
            "id": subject_id,
            "nome": subject_name,
            "questoes": questoes,
            "alunos": alunos_disciplina
        })

    student_ids_com_resultado = {str(sid) for sid in result_by_student.keys()}
    dados_gerais = _calcular_dados_gerais_alunos_cartao(disciplinas_out, grade_name, student_ids_com_resultado)
    return {"disciplinas": disciplinas_out, "geral": dados_gerais}


def _calcular_dados_gerais_alunos_cartao(disciplinas_out, grade_name, student_ids_com_resultado: Set[str]):
    """Consolida por aluno: nota_geral, proficiencia_geral, total_acertos_geral, respostas_por_questao (todas as questões).

    status_geral: concluida se existe AnswerSheetResult para o aluno (mesmo sem respostas detectadas); caso contrário pendente.
    """
    dados_alunos = {}
    for disc in disciplinas_out:
        for aluno_data in disc.get("alunos", []):
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
                    "respostas_por_questao_geral": []
                }
                dados_alunos[aluno_id]["respostas_por_questao_geral"] = list(aluno_data.get("respostas_por_questao", []))
            else:
                dados_alunos[aluno_id]["notas_disciplinas"].append(aluno_data["nota"])
                dados_alunos[aluno_id]["proficiencias_disciplinas"].append(aluno_data["proficiencia"])
                dados_alunos[aluno_id]["total_acertos_geral"] += aluno_data["total_acertos"]
                dados_alunos[aluno_id]["total_questoes_geral"] += aluno_data["total_questoes_disciplina"]
                dados_alunos[aluno_id]["total_respondidas_geral"] += aluno_data["total_respondidas"]
                existing = {x["questao"]: x for x in dados_alunos[aluno_id]["respostas_por_questao_geral"]}
                for x in aluno_data.get("respostas_por_questao", []):
                    existing[x["questao"]] = x
                dados_alunos[aluno_id]["respostas_por_questao_geral"] = sorted(existing.values(), key=lambda t: t["questao"])
                continue
            dados_alunos[aluno_id]["notas_disciplinas"].append(aluno_data["nota"])
            dados_alunos[aluno_id]["proficiencias_disciplinas"].append(aluno_data["proficiencia"])
            dados_alunos[aluno_id]["total_acertos_geral"] += aluno_data["total_acertos"]
            dados_alunos[aluno_id]["total_questoes_geral"] += aluno_data["total_questoes_disciplina"]
            dados_alunos[aluno_id]["total_respondidas_geral"] += aluno_data["total_respondidas"]
    from app.services.cartao_resposta.proficiency_by_subject import _get_course_name_from_grade
    from app.services.evaluation_calculator import EvaluationCalculator
    course_name_geral = _get_course_name_from_grade(grade_name)
    has_matematica = any(
        "matem" in (disc.get("nome") or "").lower()
        for disc in disciplinas_out
    )
    alunos_gerais = []
    for aluno_id, dados in dados_alunos.items():
        nota_geral = sum(dados["notas_disciplinas"]) / len(dados["notas_disciplinas"]) if dados["notas_disciplinas"] else 0.0
        proficiencia_geral = sum(dados["proficiencias_disciplinas"]) / len(dados["proficiencias_disciplinas"]) if dados["proficiencias_disciplinas"] else 0.0
        percentual = (dados["total_acertos_geral"] / dados["total_questoes_geral"] * 100) if dados["total_questoes_geral"] > 0 else 0.0
        cl = None
        if dados["proficiencias_disciplinas"]:
            cl = EvaluationCalculator.determine_classification(
                proficiencia_geral,
                course_name_geral,
                "GERAL",
                has_matematica=has_matematica,
            )
        alunos_gerais.append({
            "id": dados["id"],
            "nome": dados["nome"],
            "escola": dados["escola"],
            "serie": dados["serie"],
            "turma": dados["turma"],
            "nota_geral": round(nota_geral, 2),
            "proficiencia_geral": round(proficiencia_geral, 2),
            "nivel_proficiencia_geral": cl,
            "total_acertos_geral": dados["total_acertos_geral"],
            "total_questoes_geral": dados["total_questoes_geral"],
            "total_respondidas_geral": dados["total_respondidas_geral"],
            "total_em_branco_geral": dados["total_questoes_geral"] - dados["total_respondidas_geral"],
            "percentual_acertos_geral": round(percentual, 2),
            "status_geral": "concluida" if dados["id"] in student_ids_com_resultado else "pendente",
            "respostas_por_questao": dados["respostas_por_questao_geral"]
        })
    alunos_gerais.sort(key=lambda x: x["nome"])
    return {"alunos": alunos_gerais}


def _calcular_ranking_cartao(scope_info, nivel_granularidade, gabarito_id, user, periodo_bounds=None):
    """Ranking de alunos por nota no gabarito."""
    class_ids = _class_ids_alunos_previstos_cartao(gabarito_id, scope_info, nivel_granularidade, user)
    if not class_ids or not gabarito_id:
        return []
    student_ids = [s.id for s in Student.query.filter(Student.class_id.in_(class_ids)).all()]
    _rq = AnswerSheetResult.query.filter(
        AnswerSheetResult.gabarito_id == gabarito_id,
        AnswerSheetResult.student_id.in_(student_ids),
    )
    _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
    results = _dedupe_answer_sheet_results_latest_per_student(_rq.all())
    enriched = []
    for r in results:
        enriched.append((r, float(r.grade or 0), r.classification or ""))
    sorted_results = sorted(
        enriched,
        key=lambda t: (t[1], t[0].proficiency or 0),
        reverse=True,
    )
    ranking = []
    for pos, (r, eff_grade, _) in enumerate(sorted_results, 1):
        student = Student.query.get(r.student_id)
        ranking.append({
            "posicao": pos,
            "student_id": str(r.student_id),
            "nome": student.name if student else "N/A",
            "grade": eff_grade,
            "proficiency": r.proficiency,
            "classification": r.classification,
            "score_percentage": r.score_percentage
        })
    return ranking


def _gerar_opcoes_proximos_filtros_cartao(scope_info, nivel_granularidade, user, periodo_bounds=None):
    """Opções para próximos filtros (gabaritos, escolas, séries, turmas)."""
    from app.permissions import get_user_permission_scope
    opcoes = {"gabaritos": [], "escolas": [], "series": [], "turmas": []}
    municipio_id = scope_info.get('municipio_id')
    gabarito_id = scope_info.get('gabarito') if _is_valid_filter(scope_info.get('gabarito')) else None
    permissao = get_user_permission_scope(user) if user else {'scope': 'all'}

    if nivel_granularidade in ["estado", "municipio", "escola"] and municipio_id:
        q = AnswerSheetGabarito.query.with_entities(AnswerSheetGabarito.id, AnswerSheetGabarito.title).filter(AnswerSheetGabarito.created_by == str(user['id'])) if user and user.get('role') == 'professor' else AnswerSheetGabarito.query.with_entities(AnswerSheetGabarito.id, AnswerSheetGabarito.title)
        gabaritos = q.distinct().all()
        _rq = AnswerSheetResult.query.join(Student).join(Class).join(School, School.id == cast(Class.school_id, String)).filter(School.city_id == municipio_id)
        _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
        results_for_city = _rq.with_entities(AnswerSheetResult.gabarito_id).distinct().all()
        gabarito_ids_city = list({r[0] for r in results_for_city})
        if periodo_bounds is not None:
            opcoes["gabaritos"] = [{"id": str(g[0]), "titulo": g[1]} for g in gabaritos if g[0] in gabarito_ids_city]
        else:
            opcoes["gabaritos"] = [{"id": str(g[0]), "titulo": g[1]} for g in gabaritos if g[0] in gabarito_ids_city or not gabarito_ids_city]

    if gabarito_id and municipio_id and nivel_granularidade in ["estado", "municipio", "escola"]:
        _rq = AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
        _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
        results = _rq.all()
        student_ids = list({r.student_id for r in results})
        students = Student.query.filter(Student.id.in_(student_ids)).filter(Student.class_id.isnot(None)).all()
        class_ids = list({s.class_id for s in students})
        classes = Class.query.filter(Class.id.in_(class_ids)).all()
        school_ids = list({c.school_id for c in classes if c.school_id})
        schools = School.query.filter(School.id.in_(school_ids), School.city_id == municipio_id)
        if permissao.get('scope') == 'escola' and user:
            if user.get('role') in ['diretor', 'coordenador']:
                from app.models.manager import Manager
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if manager and manager.school_id:
                    schools = schools.filter(School.id == manager.school_id)
            elif user.get('role') == 'professor':
                from app.models.teacher import Teacher
                from app.models.teacherClass import TeacherClass
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    tc = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                    teacher_cids = [t.class_id for t in tc]
                    if teacher_cids:
                        teacher_sids = list({c.school_id for c in Class.query.filter(Class.id.in_(teacher_cids)).all() if c.school_id})
                        schools = schools.filter(School.id.in_(teacher_sids))
                    else:
                        schools = schools.filter(False)
        for s in schools.distinct().all():
            opcoes["escolas"].append({"id": str(s.id), "name": s.name})
    if gabarito_id and scope_info.get('escola') and _is_valid_filter(scope_info.get('escola')):
        _rq = AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
        _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
        results = _rq.all()
        student_ids = list({r.student_id for r in results})
        students = Student.query.filter(Student.id.in_(student_ids)).filter(Student.class_id.isnot(None)).all()
        class_ids = list({s.class_id for s in students})
        grades = Grade.query.join(Class, Class.grade_id == Grade.id).filter(Class.id.in_(class_ids), Class.school_id == scope_info['escola']).with_entities(Grade.id, Grade.name).distinct().all()
        opcoes["series"] = [{"id": str(g[0]), "name": g[1]} for g in grades]
    if gabarito_id and scope_info.get('serie') and _is_valid_filter(scope_info.get('serie')):
        _rq = AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
        _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
        results = _rq.all()
        student_ids = list({r.student_id for r in results})
        students = Student.query.filter(Student.id.in_(student_ids)).filter(Student.class_id.isnot(None)).all()
        class_ids = list({s.class_id for s in students})
        turmas = Class.query.filter(Class.id.in_(class_ids), Class.grade_id == scope_info['serie']).with_entities(Class.id, Class.name).all()
        opcoes["turmas"] = [{"id": str(t[0]), "name": t[1] or f"Turma {t[0]}"} for t in turmas]
    return opcoes


# ==================== OPÇÕES DE FILTROS HIERÁRQUICOS (para GET /opcoes-filtros-results) ====================

def _obter_estados_disponiveis_cartao(user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """Estados disponíveis conforme permissão (admin = todos; tecadm = só seu município)."""
    if permissao.get('scope') == 'all':
        estados = db.session.query(City.state).distinct().filter(City.state.isnot(None)).all()
    else:
        estados = db.session.query(City.state).distinct().filter(
            City.state.isnot(None),
            City.id == user.get('city_id')
        ).all()
    return [{"id": e[0], "nome": e[0]} for e in estados]


def _obter_municipios_por_estado_cartao(estado: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """Municípios do estado conforme permissão."""
    if permissao.get('scope') == 'all':
        municipios = City.query.filter(City.state.ilike(f"%{estado}%")).all()
    else:
        municipios = City.query.filter(
            City.state.ilike(f"%{estado}%"),
            City.id == user.get('city_id')
        ).all()
    return [{"id": str(m.id), "nome": m.name} for m in municipios]


def _obter_gabaritos_por_municipio_cartao(
    municipio_id: str, user: dict, permissao: dict, periodo_bounds: Optional[Tuple[datetime, datetime]] = None
) -> List[Dict[str, Any]]:
    """Gabaritos criados para o município (por school_id, class_id ou municipality/state), mesmo sem correções."""
    from sqlalchemy import or_, and_
    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao.get('scope') != 'all' and str(user.get('city_id')) != str(city.id):
        return []
    school_ids_city = [s.id for s in School.query.filter(School.city_id == municipio_id).all()]
    class_ids_city = [c.id for c in Class.query.filter(Class.school_id.in_(school_ids_city)).all()] if school_ids_city else []
    city_name = (city.name or "").strip()
    city_state = (city.state or "").strip()
    # Usamos o modelo completo porque o pós-filtro (professor) precisa ler created_by/class_id/school_id
    # e resolver escopo real via gerações/batch/resultados.
    q = AnswerSheetGabarito.query
    conditions = []
    if school_ids_city:
        conditions.append(AnswerSheetGabarito.school_id.in_(school_ids_city))
    if class_ids_city:
        conditions.append(AnswerSheetGabarito.class_id.in_(class_ids_city))
    if city_name or city_state:
        if city_name and city_state:
            conditions.append(
                and_(
                    AnswerSheetGabarito.municipality.ilike(f"%{city_name}%"),
                    AnswerSheetGabarito.state.ilike(f"%{city_state}%")
                )
            )
        elif city_name:
            conditions.append(AnswerSheetGabarito.municipality.ilike(f"%{city_name}%"))
        elif city_state:
            conditions.append(AnswerSheetGabarito.state.ilike(f"%{city_state}%"))
    if not conditions:
        return []
    q = q.filter(or_(*conditions))
    # Só cartão-resposta: não listar gabaritos vinculados a prova online (avaliação virtual)
    q = q.outerjoin(Test, AnswerSheetGabarito.test_id == Test.id).filter(
        or_(
            AnswerSheetGabarito.test_id.is_(None),
            Test.evaluation_mode == 'physical',
        )
    )
    # Admin (scope 'all') vê todos os gabaritos do município.
    # Tecadm vê todos do seu município (sem restringir por created_by).
    # Diretor/Coordenador com scope escola: filtro por escola abaixo; aqui não restringir por created_by.
    # Professor: regra específica abaixo (o que criou OU escopo turmas/escolas).
    # Demais perfis: apenas o que criaram.
    user_role = str(user.get("role") or "").lower()
    if permissao.get('scope') != 'all' and user_role not in (
        'tecadm',
        'diretor',
        'coordenador',
        'professor',
    ):
        q = q.filter(AnswerSheetGabarito.created_by == str(user['id']))
    if permissao.get('scope') == 'escola' and user.get('role') in ['diretor', 'coordenador']:
        from app.models.manager import Manager
        manager = Manager.query.filter_by(user_id=user['id']).first()
        if manager and manager.school_id:
            # Não filtrar somente por school_id aqui: gabaritos scope_type="city" podem ter school_id/class_id nulos.
            # O filtro correto para diretor/coordenador será aplicado via pós-filtro abaixo, usando o escopo real.
            pass
        else:
            return []
    elif permissao.get('scope') == 'escola' and user.get('role') == 'professor':
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        from sqlalchemy import or_
        teacher = Teacher.query.filter_by(user_id=user['id']).first()
        if not teacher:
            return []
        tc = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        teacher_class_ids = [t.class_id for t in tc]
        if not teacher_class_ids:
            return []
        teacher_school_ids = list({c.school_id for c in Class.query.filter(Class.id.in_(teacher_class_ids)).all() if c.school_id})
        # Observação importante:
        # Para professor, não restringimos o SQL apenas por created_by/class_id/school_id, porque gabaritos
        # com scope_type="city" (ou múltiplas gerações) podem ter school_id/class_id nulos. O filtro correto
        # precisa considerar answer_sheet_generations (+ batch + resultados). Isso é aplicado logo abaixo
        # como pós-filtro em Python, usando union_target_class_ids_for_gabarito ∩ turmas do professor.
        pass
    gabaritos = q.order_by(AnswerSheetGabarito.created_at.desc()).all()

    # ✅ Importante: gabaritos com scope_type="city" (ou gerados por escopos múltiplos) podem ter
    # school_id/class_id nulos. Nesses casos, o escopo real vem de answer_sheet_generations (+ batch + resultados).
    # Para manter consistente com as rotas de detalhe/relatório, aplicamos um pós-filtro para professor
    # baseado na interseção entre as turmas-alvo do gabarito e as turmas do professor.
    user_role = str(user.get("role") or "").lower()
    if user_role == "professor" and user:
        # Pós-filtro robusto: nunca "zera tudo" por falha em um gabarito.
        from app.permissions.utils import get_teacher_classes, get_teacher_schools
        from app.report_analysis.answer_sheet_report_builder import (
            union_target_class_ids_for_gabarito,
        )

        allowed_class_ids = {str(x) for x in (get_teacher_classes(user["id"]) or []) if x}
        allowed_school_ids = {str(x) for x in (get_teacher_schools(user["id"]) or []) if x}

        if not allowed_class_ids and not allowed_school_ids:
            gabaritos = [
                g for g in gabaritos if str(getattr(g, "created_by", "") or "") == str(user["id"])
            ]
        else:
            filtered_gabs = []
            for g in gabaritos:
                # (a) Criado pelo professor
                if str(getattr(g, "created_by", "") or "") == str(user["id"]):
                    filtered_gabs.append(g)
                    continue
                # (b) Vínculo direto por turma/escola no registro do gabarito
                if getattr(g, "class_id", None) and str(getattr(g, "class_id")) in allowed_class_ids:
                    filtered_gabs.append(g)
                    continue
                if getattr(g, "school_id", None) and str(getattr(g, "school_id")) in allowed_school_ids:
                    filtered_gabs.append(g)
                    continue
                # (c) Vínculo por escopo real (geraçōes/batch/resultados)
                try:
                    tgt = {str(x) for x in (union_target_class_ids_for_gabarito(g) or set()) if x}
                except Exception:
                    tgt = set()
                if tgt and (tgt & allowed_class_ids):
                    filtered_gabs.append(g)
            gabaritos = filtered_gabs

    # Pós-filtro para diretor/coordenador (escopo escola):
    # - Gabaritos explícitos da escola (school_id) continuam
    # - Gabaritos city/escopos múltiplos entram se o escopo real (geraçōes/batch/resultados) tiver
    #   ao menos uma turma na escola do manager.
    if user_role in ("diretor", "coordenador") and user and permissao.get("scope") == "escola":
        try:
            from app.models.manager import Manager
            from app.report_analysis.answer_sheet_report_builder import (
                get_answer_sheet_target_classes_for_report,
            )

            manager = Manager.query.filter_by(user_id=user["id"]).first()
            mid = str(getattr(manager, "school_id", None) or "")
            if not mid:
                gabaritos = []
            else:
                keep = []
                for g in gabaritos:
                    if getattr(g, "school_id", None) and str(getattr(g, "school_id")) == mid:
                        keep.append(g)
                        continue
                    try:
                        classes = get_answer_sheet_target_classes_for_report(
                            g, "city", str(municipio_id)
                        )
                    except Exception:
                        classes = []
                    if any(str(getattr(c, "school_id", "")) == mid for c in (classes or [])):
                        keep.append(g)
                gabaritos = keep
        except Exception:
            # Em erro, manter comportamento mais restritivo: apenas school_id explícito.
            try:
                from app.models.manager import Manager

                manager = Manager.query.filter_by(user_id=user["id"]).first()
                mid = str(getattr(manager, "school_id", None) or "")
            except Exception:
                mid = ""
            if mid:
                gabaritos = [g for g in gabaritos if str(getattr(g, "school_id", "") or "") == mid]
            else:
                gabaritos = []
    seen = set()
    out = []
    for g in gabaritos:
        gid = str(getattr(g, "id", "") or "")
        if not gid or gid in seen:
            continue
        seen.add(gid)
        out.append({"id": gid, "titulo": (getattr(g, "title", None) or "Gabarito")})
    if not periodo_bounds or not out:
        return out
    school_ids_city = [s.id for s in School.query.filter(School.city_id == municipio_id).all()]
    if not school_ids_city:
        return []
    class_ids_city = [c.id for c in Class.query.filter(Class.school_id.in_(school_ids_city)).all()]
    if not class_ids_city:
        return []
    student_ids_city = [s.id for s in Student.query.filter(Student.class_id.in_(class_ids_city)).all()]
    if not student_ids_city:
        return []
    kept_ids = set()
    for item in out:
        gid = item["id"]
        _rq = AnswerSheetResult.query.filter(
            AnswerSheetResult.gabarito_id == gid,
            AnswerSheetResult.student_id.in_(student_ids_city),
        )
        _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
        if _rq.first():
            kept_ids.add(gid)
    return [g for g in out if g["id"] in kept_ids]


def _gabarito_eh_somente_cartao_resposta(gabarito_id: str) -> bool:
    """Gabarito elegível para fluxo cartão-resposta (não ligado a teste online/virtual)."""
    g = AnswerSheetGabarito.query.get(gabarito_id)
    if not g:
        return False
    if not g.test_id:
        return True
    t = Test.query.get(g.test_id)
    if not t:
        return True
    mode = (getattr(t, 'evaluation_mode', None) or 'virtual')
    return mode == 'physical'


def _nivel_escola_por_media_proficiencia_cartao(media_prof: float, gabarito: AnswerSheetGabarito) -> Optional[str]:
    """Um rótulo único: classificação pela média de proficiência (EvaluationCalculator, GERAL)."""
    from app.services.cartao_resposta.proficiency_by_subject import _get_course_name_from_grade
    from app.services.evaluation_calculator import EvaluationCalculator

    grade_name = (gabarito.grade_name or gabarito.title or "") if gabarito else ""
    course_name = _get_course_name_from_grade(grade_name)
    has_matematica = False
    try:
        blocos = _extrair_blocos_por_disciplina_cartao(getattr(gabarito, "blocks_config", None) or {})
        has_matematica = any("matem" in (b.get("nome") or "").lower() for b in blocos)
    except Exception:
        has_matematica = False
    return EvaluationCalculator.determine_classification(
        float(media_prof or 0),
        course_name,
        "GERAL",
        has_matematica=has_matematica,
    )


def _enriquecer_escolas_estatisticas_municipio_cartao(
    escolas: List[Dict[str, Any]],
    gabarito_id: str,
    gabarito: AnswerSheetGabarito,
    municipio_id: str,
    city: City,
    estado_param: Optional[str],
    user: dict,
    periodo_bounds: Optional[Tuple[datetime, datetime]],
) -> None:
    """Preenche métricas por escola (mesma base que resultados-agregados com escola selecionada)."""
    gid = str(gabarito_id).strip()
    estado_ef = (estado_param or "").strip() or (getattr(city, "state", None) or "")
    scope_municipio = {
        "municipio_id": str(municipio_id),
        "city_data": city,
        "estado": estado_ef,
        "municipio": str(municipio_id),
        "escola": None,
        "serie": None,
        "turma": None,
        "gabarito": gid,
        "escolas": [],
    }
    mcids = _class_ids_alunos_previstos_cartao(gid, scope_municipio, "municipio", user)
    by_school: Dict[str, List[Any]] = defaultdict(list)
    if mcids:
        for row in Class.query.filter(Class.id.in_(mcids)).all():
            if row.school_id:
                by_school[str(row.school_id)].append(row.id)
    for item in escolas:
        cids = by_school.get(item["id"], [])
        st = _calcular_estatisticas_grupo_cartao(
            cids, gid, periodo_bounds, aggregation_level="escola"
        )
        dist = st.get("distribuicao_classificacao") or {}
        item["total_alunos"] = st.get("total_alunos", 0)
        item["alunos_participantes"] = st.get("alunos_participantes", 0)
        item["alunos_pendentes"] = st.get("alunos_pendentes", 0)
        item["media_nota"] = st.get("media_nota", 0.0)
        item["media_proficiencia"] = st.get("media_proficiencia", 0.0)
        item["distribuicao_classificacao"] = {
            "abaixo_do_basico": dist.get("abaixo_do_basico", 0),
            "basico": dist.get("basico", 0),
            "adequado": dist.get("adequado", 0),
            "avancado": dist.get("avancado", 0),
        }
        if st.get("alunos_participantes", 0):
            item["nivel_classificacao"] = _nivel_escola_por_media_proficiencia_cartao(
                float(st.get("media_proficiencia") or 0), gabarito
            )
        else:
            item["nivel_classificacao"] = None


def _obter_escolas_por_gabarito_cartao(
    gabarito_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
    estado: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Escolas do município ligadas ao gabarito: união das escolas das turmas em **todas** as
    gerações (answer_sheet_generations) + batch + correções, não só o school_id denormalizado
    no gabarito (que reflete a última geração).
    Se não houver turma/resultado identificável, cai no fallback de todas as escolas do município.
    """
    from uuid import UUID

    from app.report_analysis.answer_sheet_report_builder import union_target_class_ids_for_gabarito

    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao.get('scope') != 'all' and str(user.get('city_id')) != str(city.id):
        return []
    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
    if not gabarito:
        return []
    school_ids_set: Set[str] = set()
    for cid in union_target_class_ids_for_gabarito(gabarito):
        try:
            uid = UUID(str(cid))
        except ValueError:
            continue
        co = Class.query.get(uid)
        if not co or not co.school_id:
            continue
        school = School.query.filter(School.id == co.school_id, School.city_id == municipio_id).first()
        if school:
            school_ids_set.add(str(school.id))
    school_ids = list(school_ids_set)
    if not school_ids:
        schools_in_city = School.query.filter(School.city_id == municipio_id).with_entities(School.id, School.name).all()
        school_ids = [s[0] for s in schools_in_city]
    if not school_ids:
        return []
    query = School.query.with_entities(School.id, School.name).filter(School.id.in_(school_ids))
    if permissao.get('scope') == 'escola':
        if user.get('role') in ['diretor', 'coordenador']:
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if manager and manager.school_id:
                query = query.filter(School.id == manager.school_id)
            else:
                return []
        elif user.get('role') == 'professor':
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                tc = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                teacher_class_ids = [t.class_id for t in tc]
                if teacher_class_ids:
                    teacher_school_ids = list({c.school_id for c in Class.query.filter(Class.id.in_(teacher_class_ids)).all() if c.school_id})
                    query = query.filter(School.id.in_(teacher_school_ids))
                else:
                    return []
            else:
                return []
    escolas = query.order_by(School.name).all()
    out = [{"id": str(e[0]), "nome": e[1]} for e in escolas]
    if periodo_bounds:
        sids = [e["id"] for e in out]
        hit = _school_ids_com_correcao_cartao_no_periodo(str(gabarito_id), sids, periodo_bounds)
        out = [e for e in out if e["id"] in hit]
    _enriquecer_escolas_estatisticas_municipio_cartao(
        out, gabarito_id, gabarito, municipio_id, city, estado, user, periodo_bounds
    )
    return out


def _obter_series_por_escola_cartao(
    gabarito_id: str,
    escola_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    """Séries (grades) que existem na escola selecionada (onde o gabarito pode ter sido gerado)."""
    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao.get('scope') != 'all' and str(user.get('city_id')) != str(city.id):
        return []
    query = Grade.query.with_entities(Grade.id, Grade.name).join(
        Class, Grade.id == Class.grade_id
    ).filter(Class.school_id == escola_id)
    if permissao.get('scope') == 'escola' and user.get('role') == 'professor':
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        teacher = Teacher.query.filter_by(user_id=user['id']).first()
        if teacher:
            tc = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids = [t.class_id for t in tc]
            if teacher_class_ids:
                query = query.filter(Class.id.in_(teacher_class_ids))
            else:
                return []
        else:
            return []
    series = query.distinct().order_by(Grade.name).all()
    out = [{"id": str(s[0]), "nome": s[1]} for s in series]
    if not periodo_bounds:
        return out
    filtered = []
    for item in out:
        cids = [c.id for c in Class.query.filter(Class.school_id == escola_id, Class.grade_id == item["id"]).all()]
        if not cids:
            continue
        stu = [s.id for s in Student.query.filter(Student.class_id.in_(cids)).all()]
        if not stu:
            continue
        _rq = AnswerSheetResult.query.filter(
            AnswerSheetResult.gabarito_id == gabarito_id,
            AnswerSheetResult.student_id.in_(stu),
        )
        _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
        if _rq.first():
            filtered.append(item)
    return filtered


def _obter_turmas_por_serie_cartao(
    gabarito_id: str,
    escola_id: str,
    serie_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    """Turmas (classes) da escola e série selecionadas (onde o gabarito pode ter sido gerado)."""
    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao.get('scope') != 'all' and str(user.get('city_id')) != str(city.id):
        return []
    query = Class.query.with_entities(Class.id, Class.name).filter(
        Class.school_id == escola_id, Class.grade_id == serie_id
    )
    if permissao.get('scope') == 'escola' and user.get('role') == 'professor':
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        teacher = Teacher.query.filter_by(user_id=user['id']).first()
        if teacher:
            tc = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids = [t.class_id for t in tc]
            if teacher_class_ids:
                query = query.filter(Class.id.in_(teacher_class_ids))
            else:
                return []
        else:
            return []
    turmas = query.order_by(Class.name).all()
    out = [{"id": str(t[0]), "nome": t[1] or f"Turma {t[0]}"} for t in turmas]
    if not periodo_bounds:
        return out
    filtered = []
    for item in out:
        cid = item["id"]
        stu = [s.id for s in Student.query.filter(Student.class_id == cid).all()]
        if not stu:
            continue
        _rq = AnswerSheetResult.query.filter(
            AnswerSheetResult.gabarito_id == gabarito_id,
            AnswerSheetResult.student_id.in_(stu),
        )
        _rq = _apply_answer_sheet_result_period_filter(_rq, periodo_bounds)
        if _rq.first():
            filtered.append(item)
    return filtered


@bp.route('/opcoes-filtros-results', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_opcoes_filtros_cartao():
    """
    Retorna opções hierárquicas de filtros para resultados de cartões resposta.
    Mesmo padrão de GET /evaluation-results/opcoes-filtros.
    Hierarquia: Estado → Município → Cartão resposta (gabarito) → Escola → Série → Turma.
    Query params (todos opcionais): estado, municipio, gabarito, escola, serie, turma, periodo (YYYY-MM).
    Ex.: GET /opcoes-filtros-results → estados; ?estado=SP → estados + municipios; ?estado=SP&municipio=id → + gabaritos; etc.
    """
    try:
        from app.permissions import get_user_permission_scope
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        permissao = get_user_permission_scope(user)
        if not permissao.get('permitted'):
            return jsonify({"error": permissao.get('error', 'Acesso negado')}), 403

        estado = request.args.get('estado')
        municipio = request.args.get('municipio')
        gabarito = request.args.get('gabarito')
        escola = request.args.get('escola')
        serie = request.args.get('serie')
        turma = request.args.get('turma')
        periodo_raw = request.args.get('periodo')
        periodo_bounds = None
        if periodo_raw and str(periodo_raw).strip():
            try:
                periodo_bounds = _parse_cartao_periodo_bounds(str(periodo_raw).strip())
            except ValueError:
                return jsonify({"error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04)."}), 400

        response = {}
        response["estados"] = _obter_estados_disponiveis_cartao(user, permissao)

        if estado:
            response["municipios"] = _obter_municipios_por_estado_cartao(estado, user, permissao)
            if municipio:
                municipio_str = str(municipio).strip()
                # Gabaritos, escolas, turmas e classes ficam no schema do tenant do município
                set_search_path(city_id_to_schema_name(municipio_str))
                response["gabaritos"] = _obter_gabaritos_por_municipio_cartao(
                    municipio_str, user, permissao, periodo_bounds
                )
                if gabarito:
                    response["escolas"] = _obter_escolas_por_gabarito_cartao(
                        gabarito, municipio, user, permissao, periodo_bounds, estado
                    )
                    if escola:
                        response["series"] = _obter_series_por_escola_cartao(
                            gabarito, escola, municipio, user, permissao, periodo_bounds
                        )
                        if serie:
                            response["turmas"] = _obter_turmas_por_serie_cartao(
                                gabarito, escola, serie, municipio, user, permissao, periodo_bounds
                            )

        return jsonify(response), 200
    except Exception as e:
        logging.error(f"Erro ao obter opções de filtros (cartão resposta): {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter opções de filtros", "details": str(e)}), 500


@bp.route('/resultados-agregados', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_resultados_agregados():
    """
    Resultados agregados de cartões resposta (semelhante a GET /evaluation-results/avaliacoes).
    Filtros hierárquicos: estado, municipio, escola, serie, turma, gabarito.
    Query opcional: periodo=YYYY-MM (filtra por mês de corrected_at do AnswerSheetResult).
    Retorna estatísticas gerais, resultados por escola/série/turma, tabela de alunos e ranking.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        estado = request.args.get('estado')
        municipio = request.args.get('municipio')
        escola = request.args.get('escola')
        serie = request.args.get('serie')
        turma = request.args.get('turma')
        gabarito = request.args.get('gabarito')
        ai_analises = (request.args.get("ai_analises") or "").strip().lower() in {"1", "true", "yes"}
        periodo_raw = request.args.get('periodo')
        periodo_bounds = None
        if periodo_raw and str(periodo_raw).strip():
            try:
                periodo_bounds = _parse_cartao_periodo_bounds(str(periodo_raw).strip())
            except ValueError:
                return jsonify({"error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04)."}), 400

        if not _is_valid_filter(estado):
            return jsonify({"error": "Estado é obrigatório e não pode ser 'all'"}), 400
        if not _is_valid_filter(municipio):
            return jsonify({"error": "Município é obrigatório"}), 400

        scope_info = _determinar_escopo_busca_cartao(
            estado, municipio, escola, serie, turma, gabarito, user, periodo_bounds
        )
        if not scope_info:
            return jsonify({"error": "Não foi possível determinar o escopo de busca"}), 400

        nivel_granularidade = _determinar_nivel_granularidade_cartao(estado, municipio, escola, serie, turma, gabarito)
        gabarito_id = str(gabarito).strip() if _is_valid_filter(gabarito) else None

        estatisticas_gerais = _calcular_estatisticas_consolidadas_cartao(
            scope_info, nivel_granularidade, gabarito_id, user, periodo_bounds
        )
        resultados_por_disciplina = (
            _calcular_resultados_por_disciplina_cartao(
                scope_info, nivel_granularidade, gabarito_id, periodo_bounds, user
            )
            if gabarito_id
            else []
        )
        resultados_detalhados = (
            _gerar_resultados_detalhados_por_granularidade_cartao(
                scope_info, nivel_granularidade, gabarito_id, periodo_bounds, user
            )
            if gabarito_id
            else []
        )
        tabela_detalhada = (
            _gerar_tabela_detalhada_cartao(scope_info, nivel_granularidade, gabarito_id, user, periodo_bounds)
            if gabarito_id
            else {"disciplinas": [], "geral": {"alunos": []}}
        )
        ranking = (
            _calcular_ranking_cartao(scope_info, nivel_granularidade, gabarito_id, user, periodo_bounds)
            if gabarito_id
            else []
        )
        opcoes_proximos_filtros = _gerar_opcoes_proximos_filtros_cartao(
            scope_info, nivel_granularidade, user, periodo_bounds
        )

        response_payload = {
            "nivel_granularidade": nivel_granularidade,
            "filtros_aplicados": {
                "estado": estado,
                "municipio": municipio,
                "escola": escola,
                "serie": serie,
                "turma": turma,
                "gabarito": gabarito,
                "periodo": (str(periodo_raw).strip() if periodo_raw and str(periodo_raw).strip() else None),
            },
            "estatisticas_gerais": estatisticas_gerais,
            "resultados_por_disciplina": resultados_por_disciplina,
            "resultados_detalhados": {
                "gabaritos": resultados_detalhados,
                "paginacao": {"page": 1, "per_page": len(resultados_detalhados), "total": len(resultados_detalhados), "total_pages": 1}
            },
            "tabela_detalhada": tabela_detalhada,
            "ranking": ranking,
            "opcoes_proximos_filtros": opcoes_proximos_filtros
        }

        if ai_analises:
            try:
                ttl_sec = int(os.getenv("AI_ANALYSIS_CACHE_TTL_SEC", "3600"))
                prompt_version = str(os.getenv("AI_ANALYSIS_PROMPT_VERSION", "v1"))
                user_id = str(user.get("id") or "")

                # Série/Ano (prioriza filtro)
                serie_ano = (str(serie).strip() if serie and str(serie).strip() and str(serie).strip().lower() != "all" else "")
                if not serie_ano:
                    # fallback: tenta do primeiro aluno
                    alunos_geral = (((tabela_detalhada or {}).get("geral") or {}).get("alunos") or [])
                    if alunos_geral:
                        serie_ano = str(alunos_geral[0].get("serie") or "").strip()

                # Componente curricular: lista de disciplinas presentes
                componentes = []
                for row in (resultados_por_disciplina or []):
                    dn = (row.get("disciplina") if isinstance(row, dict) else None) or ""
                    dn = str(dn).strip()
                    if dn:
                        componentes.append(dn)
                componentes = list(dict.fromkeys(componentes))
                componente_curricular = componentes[0] if len(componentes) == 1 else "all"

                # Níveis de proficiência alcançados (distribuição + médias)
                distrib = (estatisticas_gerais or {}).get("distribuicao_classificacao_geral") or {}
                media_prof = (estatisticas_gerais or {}).get("media_proficiencia_geral")
                media_nota = (estatisticas_gerais or {}).get("media_nota_geral") or (estatisticas_gerais or {}).get("media_nota")
                niveis_proficiencia_alcancados = {
                    "media_proficiencia_geral": media_prof,
                    "media_nota_geral": media_nota,
                    "distribuicao_classificacao_geral": distrib,
                }

                # Habilidades foco: coletar códigos (skills.code) da tabela detalhada
                habilidades_codes = []
                for disc in ((tabela_detalhada or {}).get("disciplinas") or []):
                    for q in (disc.get("questoes") or []):
                        for sk in (q.get("skills") or []):
                            code = (sk.get("code") if isinstance(sk, dict) else "") or ""
                            code = str(code).strip()
                            if code and code.upper() != "N/A":
                                habilidades_codes.append(code)
                habilidades_codes = list(dict.fromkeys(habilidades_codes))

                # Referência da avaliação (gabarito)
                gabarito_title = ""
                try:
                    gab = AnswerSheetGabarito.query.get(str(gabarito_id)) if gabarito_id else None
                    gabarito_title = (getattr(gab, "title", None) or "").strip() if gab else ""
                except Exception:
                    gabarito_title = ""

                prompt = (
                    "Aja como um Especialista em Avaliação Educacional e Gestor Pedagógico Orientado a Dados.\n"
                    "Sua tarefa é gerar um Relatório Escolar Analítico e Reflexivo com base nos resultados de uma avaliação aplicada.\n\n"
                    "[DADOS DE ENTRADA NECESSÁRIOS]\n"
                    f"• Série/Ano Avaliado: {serie_ano}\n"
                    f"• Componente Curricular: {componente_curricular}\n"
                    f"• Níveis de Proficiência Alcançados: {niveis_proficiencia_alcancados}\n"
                    f"• Habilidades Foco da Avaliação: {habilidades_codes}\n\n"
                    "[REGRAS E DIRETRIZES ESTRITAS DE GERAÇÃO]\n"
                    "1. Adaptação de Nomenclatura de Etapa: se Anos Iniciais (1º ao 4º), use matriz de final de ciclo dos Anos Iniciais; "
                    "NUNCA mencione \"5º ano\". Se Anos Finais (6º ao 8º), use matriz de final de ciclo dos Anos Finais; NUNCA mencione \"9º ano\".\n"
                    "2. Restrição de Vocabulário: sob nenhuma circunstância utilize a sigla \"SAEB\" ou faça referência ao \"Sistema de Avaliação da Educação Básica\". "
                    "Use termos como \"avaliação aplicada\", \"instrumento avaliativo\", \"diagnóstico da rede\" ou \"a presente prova\".\n"
                    "3. Princípio da Cumulatividade: deixe claro que a escala está organizada em níveis da menor para a maior proficiência e que cada nível acumula saberes dos níveis anteriores.\n"
                    "4. Alerta para Níveis Críticos: para estudantes no Nível 0 (desempenho menor que 125), emitir alerta de \"atenção especial\".\n\n"
                    "[ESTRUTURA OBRIGATÓRIA DO RELATÓRIO]\n"
                    "I. Panorama Geral da Avaliação Aplicada\n"
                    "II. Reflexão sobre os Níveis Alcançados e Habilidades (para cada nível identificado)\n"
                    "III. Encaminhamentos e Cultura Digital (Opcional, se aplicável)\n\n"
                    "IMPORTANTE: Responda APENAS com um JSON válido (objeto) e nada além do JSON. "
                    "O JSON deve conter as chaves: panorama_geral, reflexao_niveis (lista), encaminhamentos_cultura_digital (opcional), metadados_entrada.\n"
                    f"Metadados adicionais: titulo_avaliacao={gabarito_title or 'Cartão-resposta'}.\n"
                )

                cache_key = _ai_make_cache_key(
                    "answer_sheets_resultados_agregados",
                    user_id=user_id,
                    prompt_version=prompt_version,
                    key_parts={
                        "estado": estado,
                        "municipio": municipio,
                        "escola": escola,
                        "serie": serie,
                        "turma": turma,
                        "gabarito": gabarito,
                        "periodo": (str(periodo_raw).strip() if periodo_raw and str(periodo_raw).strip() else None),
                    },
                )

                cached = _ai_cache_get_status(cache_key)
                if cached and cached.get("status") == "ready":
                    response_payload["analise_ia"] = cached.get("result") or {}
                    response_payload["analise_ia_status"] = "ready"
                    response_payload["analise_ia_cache_key"] = cache_key
                else:
                    # Se Redis indisponível, faz fallback síncrono para não quebrar fluxo
                    r = _get_ai_redis_client()
                    if not r:
                        ai_service = AIAnalysisService()
                        response_payload["analise_ia"] = ai_service.analyze_intervention_plan_json(prompt)
                        response_payload["analise_ia_status"] = "ready"
                    else:
                        # Marcar processing com NX (evita duplicar em paralelo)
                        should_enqueue = _ai_cache_set_processing(cache_key, ttl_sec=ttl_sec)
                        if should_enqueue:
                            generate_ai_analysis_json_to_redis.delay(
                                cache_key=cache_key,
                                prompt=prompt,
                                ttl_sec=ttl_sec,
                            )
                        response_payload["analise_ia_status"] = (cached or {}).get("status") or "processing"
                        response_payload["analise_ia_cache_key"] = cache_key
            except Exception as _exc:
                response_payload["analise_ia"] = {"error": "Falha ao gerar análise de IA", "details": str(_exc)}
                response_payload["analise_ia_status"] = "error"

        return jsonify(response_payload), 200
    except Exception as e:
        logging.error(f"Erro ao obter resultados agregados: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter resultados agregados", "details": str(e)}), 500


@bp.route("/resultados-agregados/analise-ia", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_resultados_agregados_analise_ia():
    """
    Retorna apenas o status/resultado da análise de IA (JSON) para resultados agregados de cartão-resposta.
    - Consulta Redis primeiro (sem recalcular agregados).
    - Se não houver cache, calcula 1x, dispara Celery e devolve processing.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        estado = request.args.get("estado")
        municipio = request.args.get("municipio")
        escola = request.args.get("escola")
        serie = request.args.get("serie")
        turma = request.args.get("turma")
        gabarito = request.args.get("gabarito")
        periodo_raw = request.args.get("periodo")

        if not _is_valid_filter(estado):
            return jsonify({"error": "Estado é obrigatório e não pode ser 'all'"}), 400
        if not _is_valid_filter(municipio):
            return jsonify({"error": "Município é obrigatório"}), 400

        ttl_sec = int(os.getenv("AI_ANALYSIS_CACHE_TTL_SEC", "3600"))
        prompt_version = str(os.getenv("AI_ANALYSIS_PROMPT_VERSION", "v1"))
        user_id = str(user.get("id") or "")
        cache_key = _ai_make_cache_key(
            "answer_sheets_resultados_agregados",
            user_id=user_id,
            prompt_version=prompt_version,
            key_parts={
                "estado": estado,
                "municipio": municipio,
                "escola": escola,
                "serie": serie,
                "turma": turma,
                "gabarito": gabarito,
                "periodo": (str(periodo_raw).strip() if periodo_raw and str(periodo_raw).strip() else None),
            },
        )

        cached = _ai_cache_get_status(cache_key)
        if cached:
            st = cached.get("status")
            if st == "ready":
                return jsonify(
                    {
                        "analise_ia_status": "ready",
                        "analise_ia_cache_key": cache_key,
                        "analise_ia": cached.get("result") or {},
                    }
                ), 200
            if st == "error":
                return jsonify(
                    {
                        "analise_ia_status": "error",
                        "analise_ia_cache_key": cache_key,
                        "error": cached.get("error") or "Falha ao gerar análise de IA",
                        "details": cached.get("details") or "",
                    }
                ), 200
            return jsonify(
                {
                    "analise_ia_status": "processing",
                    "analise_ia_cache_key": cache_key,
                }
            ), 200

        # Cache não existe: calcular dados 1x e disparar task
        periodo_bounds = None
        if periodo_raw and str(periodo_raw).strip():
            try:
                periodo_bounds = _parse_cartao_periodo_bounds(str(periodo_raw).strip())
            except ValueError:
                return jsonify({"error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04)."}), 400

        scope_info = _determinar_escopo_busca_cartao(
            estado, municipio, escola, serie, turma, gabarito, user, periodo_bounds
        )
        if not scope_info:
            return jsonify({"error": "Não foi possível determinar o escopo de busca"}), 400

        nivel_granularidade = _determinar_nivel_granularidade_cartao(
            estado, municipio, escola, serie, turma, gabarito
        )
        gabarito_id = str(gabarito).strip() if _is_valid_filter(gabarito) else None

        estatisticas_gerais = _calcular_estatisticas_consolidadas_cartao(
            scope_info, nivel_granularidade, gabarito_id, user, periodo_bounds
        )
        resultados_por_disciplina = (
            _calcular_resultados_por_disciplina_cartao(
                scope_info, nivel_granularidade, gabarito_id, periodo_bounds, user
            )
            if gabarito_id
            else []
        )
        tabela_detalhada = (
            _gerar_tabela_detalhada_cartao(
                scope_info, nivel_granularidade, gabarito_id, user, periodo_bounds
            )
            if gabarito_id
            else {"disciplinas": [], "geral": {"alunos": []}}
        )

        # Série/Ano (prioriza filtro)
        serie_ano = (
            str(serie).strip()
            if serie and str(serie).strip() and str(serie).strip().lower() != "all"
            else ""
        )
        if not serie_ano:
            alunos_geral = (((tabela_detalhada or {}).get("geral") or {}).get("alunos") or [])
            if alunos_geral:
                serie_ano = str(alunos_geral[0].get("serie") or "").strip()

        # Disciplinas presentes no payload (para análise por disciplina quando aplicável)
        componentes = []
        by_disc_row = {}
        for row in (resultados_por_disciplina or []):
            if not isinstance(row, dict):
                continue
            dn = str((row.get("disciplina") or "")).strip()
            if not dn:
                continue
            componentes.append(dn)
            by_disc_row[dn] = row
        componentes = list(dict.fromkeys(componentes))
        componente_curricular = componentes[0] if len(componentes) == 1 else "all"

        distrib = (estatisticas_gerais or {}).get("distribuicao_classificacao_geral") or {}
        media_prof = (estatisticas_gerais or {}).get("media_proficiencia_geral")
        media_nota = (estatisticas_gerais or {}).get("media_nota_geral") or (estatisticas_gerais or {}).get("media_nota")
        niveis_proficiencia_alcancados = {
            "media_proficiencia_geral": media_prof,
            "media_nota_geral": media_nota,
            "distribuicao_classificacao_geral": distrib,
        }

        # Habilidades foco: coletar {codigo, descricao} (não apenas código)
        def _safe_uuid(s: str) -> Optional[str]:
            try:
                return str(uuid.UUID(str(s).strip()))
            except Exception:
                return None

        habilidades_foco_geral: List[Dict[str, str]] = []
        # também gerar por disciplina para análise por disciplina
        habilidades_por_disciplina: Dict[str, List[Dict[str, str]]] = {}

        skills_to_fetch_by_id: Set[str] = set()
        skills_to_fetch_by_code: Set[str] = set()
        for disc in ((tabela_detalhada or {}).get("disciplinas") or []):
            dn = str(disc.get("nome") or disc.get("id") or "").strip() or "Outras"
            for q in (disc.get("questoes") or []):
                for sk in (q.get("skills") or []):
                    if not isinstance(sk, dict):
                        continue
                    sid = str(sk.get("id") or "").strip()
                    scode = str(sk.get("code") or "").strip()
                    if sid and _safe_uuid(sid):
                        skills_to_fetch_by_id.add(_safe_uuid(sid))
                    elif sid:
                        skills_to_fetch_by_code.add(sid)
                    if scode and scode.upper() != "N/A":
                        skills_to_fetch_by_code.add(scode)
            if dn not in habilidades_por_disciplina:
                habilidades_por_disciplina[dn] = []

        skills_db_by_id: Dict[str, Skill] = {}
        if skills_to_fetch_by_id:
            try:
                skills_db_by_id = {str(s.id): s for s in Skill.query.filter(Skill.id.in_(list(skills_to_fetch_by_id))).all()}
            except Exception:
                skills_db_by_id = {}
        skills_db_by_code: Dict[str, Skill] = {}
        if skills_to_fetch_by_code:
            try:
                skills_db_by_code = {str(s.code): s for s in Skill.query.filter(Skill.code.in_(list(skills_to_fetch_by_code))).all()}
            except Exception:
                skills_db_by_code = {}

        def _resolve_skill(sid: str, code: str) -> Tuple[str, str]:
            # retorna (codigo, descricao)
            uid = _safe_uuid(sid) if sid else None
            if uid and uid in skills_db_by_id:
                s = skills_db_by_id[uid]
                return (str(s.code or "").strip() or uid, str(s.description or "").strip() or "")
            if code and code in skills_db_by_code:
                s = skills_db_by_code[code]
                return (str(s.code or "").strip() or code, str(s.description or "").strip() or "")
            if sid and sid in skills_db_by_code:
                s = skills_db_by_code[sid]
                return (str(s.code or "").strip() or sid, str(s.description or "").strip() or "")
            # fallback
            c = (code or sid or "").strip()
            return (c, "")

        # popular listas
        for disc in ((tabela_detalhada or {}).get("disciplinas") or []):
            dn = str(disc.get("nome") or disc.get("id") or "").strip() or "Outras"
            for q in (disc.get("questoes") or []):
                for sk in (q.get("skills") or []):
                    if not isinstance(sk, dict):
                        continue
                    codigo, descricao = _resolve_skill(str(sk.get("id") or "").strip(), str(sk.get("code") or "").strip())
                    if not codigo or codigo.upper() == "N/A":
                        continue
                    item = {"codigo": codigo, "descricao": descricao}
                    habilidades_foco_geral.append(item)
                    habilidades_por_disciplina.setdefault(dn, []).append(item)

        # dedupe preservando ordem
        def _dedupe(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
            seen = set()
            out = []
            for it in items:
                k = (it.get("codigo") or "") + "||" + (it.get("descricao") or "")
                if k in seen:
                    continue
                seen.add(k)
                out.append(it)
            return out

        habilidades_foco_geral = _dedupe(habilidades_foco_geral)
        for dn in list(habilidades_por_disciplina.keys()):
            habilidades_por_disciplina[dn] = _dedupe(habilidades_por_disciplina.get(dn) or [])

        gabarito_title = ""
        try:
            gab = AnswerSheetGabarito.query.get(str(gabarito_id)) if gabarito_id else None
            gabarito_title = (getattr(gab, "title", None) or "").strip() if gab else ""
        except Exception:
            gabarito_title = ""

        def _component_from_disciplina_name(name: str) -> str:
            n = (name or "").lower()
            return "MATEMÁTICA" if "matem" in n else "LÍNGUA PORTUGUESA"

        # Sempre pedir análise por disciplina (mesmo quando só houver 1 disciplina),
        # para o frontend ter explícito "qual análise é de qual disciplina".
        if not componentes:
            componentes = ["Outras"]
        entrada_por_disciplina = {}
        for dn in componentes:
            comp = _component_from_disciplina_name(dn)
            row = by_disc_row.get(dn) or {}
            entrada_por_disciplina[dn] = {
                "serie_ano_avaliado": serie_ano,
                "componente_curricular": comp,
                "niveis_proficiencia_alcancados": {
                    "media_proficiencia": row.get("media_proficiencia"),
                    "media_nota": row.get("media_nota"),
                    "distribuicao_classificacao": row.get("distribuicao_classificacao") or {},
                },
                "habilidades_foco": habilidades_por_disciplina.get(dn) or habilidades_foco_geral,
            }
        dados_entrada = entrada_por_disciplina
        formato_saida = (
            "IMPORTANTE: Responda APENAS com um JSON válido (objeto) e nada além do JSON. "
            "Retorne um JSON no formato: "
            "{ \"analises_por_disciplina\": { \"<disciplina>\": <relatorio_json> }, \"metadados_gerais\": {...} }."
        )

        prompt = (
            "Aja como um Especialista em Avaliação Educacional e Gestor Pedagógico Orientado a Dados.\n"
            "Sua tarefa é gerar um Relatório Escolar Analítico e Reflexivo com base nos resultados de uma avaliação aplicada a uma turma ou aluno específico.\n"
            "O objetivo é traduzir escalas de proficiência em intervenções pedagógicas claras, analisando as habilidades cobradas, o que cada nível significa e os efeitos práticos.\n\n"
            "[DADOS DE ENTRADA NECESSÁRIOS]\n"
            f"{dados_entrada}\n\n"
            "[REGRAS E DIRETRIZES ESTRITAS DE GERAÇÃO]\n"
            "1. Adaptação de Nomenclatura de Etapa: se Anos Iniciais (1º ao 4º), use matriz de final de ciclo dos Anos Iniciais; "
            "NUNCA mencione \"5º ano\". Se Anos Finais (6º ao 8º), use matriz de final de ciclo dos Anos Finais; NUNCA mencione \"9º ano\".\n"
            "2. Restrição de Vocabulário: sob nenhuma circunstância utilize a sigla \"SAEB\" ou faça referência ao \"Sistema de Avaliação da Educação Básica\". "
            "Use termos como \"avaliação aplicada\", \"instrumento avaliativo\", \"diagnóstico da rede\" ou \"a presente prova\".\n"
            "3. Princípio da Cumulatividade: deixe claro que a escala está organizada em níveis da menor para a maior proficiência e que cada nível acumula saberes dos níveis anteriores.\n"
            "4. Alerta para Níveis Críticos: para estudantes no Nível 0 (desempenho menor que 125), emitir alerta de \"atenção especial\".\n\n"
            "[ESTRUTURA OBRIGATÓRIA DO RELATÓRIO]\n"
            "I. Panorama Geral da Avaliação Aplicada\n"
            "II. Reflexão sobre os Níveis Alcançados e Habilidades (para cada nível identificado)\n"
            "III. Encaminhamentos e Cultura Digital (Opcional, se aplicável)\n\n"
            f"{formato_saida}\n"
            f"Metadados adicionais: titulo_avaliacao={gabarito_title or 'Cartão-resposta'}.\n"
        )

        r = _get_ai_redis_client()
        if not r:
            ai_service = AIAnalysisService()
            return jsonify(
                {
                    "analise_ia_status": "ready",
                    "analise_ia_cache_key": cache_key,
                    "analise_ia": ai_service.analyze_intervention_plan_json(prompt),
                }
            ), 200

        should_enqueue = _ai_cache_set_processing(cache_key, ttl_sec=ttl_sec)
        if should_enqueue:
            generate_ai_analysis_json_to_redis.delay(
                cache_key=cache_key,
                prompt=prompt,
                ttl_sec=ttl_sec,
            )

        return jsonify(
            {
                "analise_ia_status": "processing",
                "analise_ia_cache_key": cache_key,
            }
        ), 200

    except Exception as e:
        logging.error("Erro analise IA resultados-agregados: %s", e, exc_info=True)
        return jsonify({"error": "Erro ao gerar análise de IA", "details": str(e)}), 500


@bp.route("/mapa-habilidades/analise-ia", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def mapa_habilidades_cartao_analise_ia():
    """
    Retorna apenas o status/resultado da análise de IA (JSON) para o mapa de habilidades (cartão-resposta).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        estado = request.args.get("estado")
        municipio = request.args.get("municipio")
        escola = request.args.get("escola")
        serie = request.args.get("serie")
        turma = request.args.get("turma")
        gabarito = request.args.get("gabarito")
        disciplina = request.args.get("disciplina") or "all"
        periodo_raw = request.args.get("periodo")

        if not _is_valid_filter(estado):
            return jsonify({"error": "Estado é obrigatório e não pode ser 'all'"}), 400
        if not _is_valid_filter(municipio):
            return jsonify({"error": "Município é obrigatório"}), 400
        if not _is_valid_filter(gabarito):
            return jsonify({"error": "Gabarito é obrigatório"}), 400

        ttl_sec = int(os.getenv("AI_ANALYSIS_CACHE_TTL_SEC", "3600"))
        prompt_version = str(os.getenv("AI_ANALYSIS_PROMPT_VERSION", "v1"))
        user_id = str(user.get("id") or "")
        cache_key = _ai_make_cache_key(
            "answer_sheets_mapa_habilidades",
            user_id=user_id,
            prompt_version=prompt_version,
            key_parts={
                "estado": estado,
                "municipio": municipio,
                "escola": escola,
                "serie": serie,
                "turma": turma,
                "gabarito": gabarito,
                "disciplina": disciplina,
                "periodo": (str(periodo_raw).strip() if periodo_raw and str(periodo_raw).strip() else None),
            },
        )

        cached = _ai_cache_get_status(cache_key)
        if cached:
            st = cached.get("status")
            if st == "ready":
                return jsonify(
                    {
                        "analise_ia_status": "ready",
                        "analise_ia_cache_key": cache_key,
                        "analise_ia": cached.get("result") or {},
                    }
                ), 200
            if st == "error":
                return jsonify(
                    {
                        "analise_ia_status": "error",
                        "analise_ia_cache_key": cache_key,
                        "error": cached.get("error") or "Falha ao gerar análise de IA",
                        "details": cached.get("details") or "",
                    }
                ), 200
            return jsonify(
                {"analise_ia_status": "processing", "analise_ia_cache_key": cache_key}
            ), 200

        # Cache não existe: calcular mapa 1x, montar prompt e disparar task
        periodo_bounds = None
        if periodo_raw and str(periodo_raw).strip():
            try:
                periodo_bounds = _parse_cartao_periodo_bounds(str(periodo_raw).strip())
            except ValueError:
                return jsonify({"error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04)."}), 400

        municipio_str = str(municipio).strip()
        set_search_path(city_id_to_schema_name(municipio_str))

        gabarito_id = str(gabarito).strip()
        if not _gabarito_eh_somente_cartao_resposta(gabarito_id):
            return jsonify(
                {
                    "error": "Gabarito inválido",
                    "details": "Use apenas gabaritos de cartão-resposta. Avaliações online aparecem na outra aba.",
                }
            ), 400

        scope_info = _determinar_escopo_busca_cartao(
            estado, municipio, escola, serie, turma, gabarito, user
        )
        if not scope_info:
            return jsonify({"error": "Não foi possível determinar o escopo de busca"}), 400

        nivel_granularidade = _determinar_nivel_granularidade_cartao(
            estado, municipio, escola, serie, turma, gabarito
        )
        class_ids = _class_ids_alunos_previstos_cartao(
            gabarito_id, scope_info, nivel_granularidade, user
        )
        if not class_ids:
            # Sem dados: devolve pronto com warning
            return jsonify(
                {
                    "analise_ia_status": "ready",
                    "analise_ia_cache_key": cache_key,
                    "analise_ia": {
                        "document_title": "ESTRATÉGIAS DE INTERVENÇÃO",
                        "warning": "Nenhum aluno/resultado encontrado para o escopo informado.",
                    },
                }
            ), 200

        disc_filt = None if str(disciplina).strip().lower() == "all" else str(disciplina).strip()
        from app.services.skills_map_service import build_skills_map_answer_sheet

        raw = build_skills_map_answer_sheet(gabarito_id, [str(c) for c in class_ids], disc_filt)
        por_faixa = raw.get("por_faixa", {}) or {}
        habilidades_abaixo = por_faixa.get("abaixo_do_basico", []) or []
        habilidades_basico = por_faixa.get("basico", []) or []
        habilidades_criticas = list(habilidades_abaixo) + list(habilidades_basico)

        # Sempre pedir/retornar análise por disciplina (mesmo quando disciplina=all)
        # Agrupa habilidades críticas por disciplina_nome do próprio mapa.
        habilidades_por_disciplina: Dict[str, List[Dict[str, str]]] = {}
        for h in habilidades_criticas:
            dn = str(h.get("disciplina_nome") or "Outras").strip() or "Outras"
            codigo = str(h.get("codigo") or "").strip()
            desc = str(h.get("descricao") or "").strip()
            if not codigo and not desc:
                continue
            habilidades_por_disciplina.setdefault(dn, []).append(
                {"codigo": codigo or (h.get("skill_id") or ""), "descricao": desc}
            )

        # De-duplicar mantendo ordem por disciplina
        for dn in list(habilidades_por_disciplina.keys()):
            seen = set()
            out = []
            for it in habilidades_por_disciplina[dn]:
                k = (it.get("codigo") or "") + "||" + (it.get("descricao") or "")
                if k in seen:
                    continue
                seen.add(k)
                out.append(it)
            habilidades_por_disciplina[dn] = out

        gab = AnswerSheetGabarito.query.get(gabarito_id)
        avaliacao_referencia = (getattr(gab, "title", None) or "Cartão-resposta").strip() if gab else "Cartão-resposta"

        if serie and str(serie).strip():
            ano_serie = str(serie).strip()
        elif gab and getattr(gab, "grade_name", None):
            ano_serie = str(gab.grade_name).strip()
        else:
            ano_serie = ""

        dados_entrada = {}
        for dn, habs in habilidades_por_disciplina.items():
            dados_entrada[dn] = {
                "ano_serie": ano_serie,
                "disciplina": dn,
                "avaliacao_referencia": avaliacao_referencia,
                "habilidades_criticas": habs,
            }

        prompt = (
            "Atue como um Especialista em Avaliação Educacional e Recomposição de Aprendizagem, com profundo conhecimento nas matrizes de referência do SAEB, SPAECE e SAVEAL.\n\n"
            "Abaixo, fornecerei os dados de uma avaliação (Mensal ou Larga Escala) referentes a uma turma.\n\n"
            "Sua tarefa é gerar um plano de ação estritamente focado em alunos que se encontram nos níveis de proficiência \"ABAIXO DO BÁSICO\" e \"BÁSICO\". "
            "O plano deve ser realista, aplicável na rede pública ou privada, utilizando recursos acessíveis de sala de aula.\n\n"
            "Nomeie o documento final obrigatoriamente como: **ESTRATÉGIAS DE INTERVENÇÃO**.\n\n"
            "IMPORTANTE: Responda APENAS com JSON válido.\n"
            "Como há possivelmente mais de uma disciplina, devolva SEMPRE no formato:\n"
            "{ \"analises_por_disciplina\": { \"<disciplina>\": <estrategias_de_intervencao_json> } }\n\n"
            "DADOS PARA A ANÁLISE (por disciplina):\n"
            f"{dados_entrada}\n\n"
            "O JSON <estrategias_de_intervencao_json> deve conter obrigatoriamente os campos equivalentes a:\n"
            "1) foco_analitico\n"
            "2) matriz_acao_por_habilidade (lista)\n"
            "3) dinamica_sala_recomposicao\n"
        )

        r = _get_ai_redis_client()
        if not r:
            ai_service = AIAnalysisService()
            return jsonify(
                {
                    "analise_ia_status": "ready",
                    "analise_ia_cache_key": cache_key,
                    "analise_ia": ai_service.analyze_intervention_plan_json(prompt),
                }
            ), 200

        should_enqueue = _ai_cache_set_processing(cache_key, ttl_sec=ttl_sec)
        if should_enqueue:
            generate_ai_analysis_json_to_redis.delay(
                cache_key=cache_key,
                prompt=prompt,
                ttl_sec=ttl_sec,
            )

        return jsonify(
            {"analise_ia_status": "processing", "analise_ia_cache_key": cache_key}
        ), 200

    except Exception as e:
        logging.error("Erro analise IA mapa-habilidades (cartão): %s", e, exc_info=True)
        return jsonify({"error": "Erro ao gerar análise de IA", "details": str(e)}), 500


@bp.route("/mapa-habilidades", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def mapa_habilidades_cartao():
    """
    Mapa de habilidades para cartão-resposta (gabarito).
    Query: estado, municipio, gabarito (obrigatório), escola, serie, turma, disciplina (id do bloco ou all).
    Query opcional: periodo=YYYY-MM (filtra correções por corrected_at).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        estado = request.args.get("estado")
        municipio = request.args.get("municipio")
        escola = request.args.get("escola")
        serie = request.args.get("serie")
        turma = request.args.get("turma")
        gabarito = request.args.get("gabarito")
        disciplina = request.args.get("disciplina") or "all"
        periodo_raw = request.args.get("periodo")
        periodo_bounds = None
        if periodo_raw and str(periodo_raw).strip():
            try:
                periodo_bounds = _parse_cartao_periodo_bounds(str(periodo_raw).strip())
            except ValueError:
                return jsonify({"error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04)."}), 400

        if not _is_valid_filter(estado):
            return jsonify({"error": "Estado é obrigatório e não pode ser 'all'"}), 400
        if not _is_valid_filter(municipio):
            return jsonify({"error": "Município é obrigatório"}), 400
        if not _is_valid_filter(gabarito):
            return jsonify({"error": "Gabarito é obrigatório para o mapa de habilidades"}), 400

        municipio_str = str(municipio).strip()
        set_search_path(city_id_to_schema_name(municipio_str))

        gabarito_id = str(gabarito).strip()
        if not _gabarito_eh_somente_cartao_resposta(gabarito_id):
            return jsonify(
                {
                    "error": "Gabarito inválido",
                    "details": "Use apenas gabaritos de cartão-resposta. Avaliações online aparecem na outra aba.",
                }
            ), 400

        scope_info = _determinar_escopo_busca_cartao(
            estado, municipio, escola, serie, turma, gabarito, user
        )
        if not scope_info:
            return jsonify({"error": "Não foi possível determinar o escopo de busca"}), 400

        nivel_granularidade = _determinar_nivel_granularidade_cartao(
            estado, municipio, escola, serie, turma, gabarito
        )

        class_ids = _class_ids_alunos_previstos_cartao(gabarito_id, scope_info, nivel_granularidade, user)
        if not class_ids:
            return jsonify(
                {
                    "nivel_granularidade": nivel_granularidade,
                    "disciplinas_disponiveis": [],
                    "habilidades": [],
                    "por_faixa": {
                        "abaixo_do_basico": [],
                        "basico": [],
                        "adequado": [],
                        "avancado": [],
                    },
                    "filtros_aplicados": {
                        "estado": estado,
                        "municipio": municipio,
                        "escola": escola,
                        "serie": serie,
                        "turma": turma,
                        "gabarito": gabarito,
                        "disciplina": disciplina,
                        "periodo": str(periodo_raw).strip() if periodo_raw and str(periodo_raw).strip() else None,
                    },
                    "total_alunos_escopo_turma": 0,
                    "total_alunos_participantes": 0,
                    "total_alunos_escopo": 0,
                    "analise_ia": {
                        "document_title": "ESTRATÉGIAS DE INTERVENÇÃO",
                        "warning": "Nenhum aluno/resultado encontrado para o escopo informado.",
                    },
                }
            ), 200

        disc_filt = None if str(disciplina).strip().lower() == "all" else str(disciplina).strip()

        from app.services.skills_map_service import build_skills_map_answer_sheet

        raw = build_skills_map_answer_sheet(gabarito_id, [str(c) for c in class_ids], disc_filt)
        students = raw.pop("_students_snapshot", []) or []
        raw.pop("_failed_by_skill", None)
        n_turma = int(raw.pop("_students_all_count", len(students)) or 0)
        n_part = len(students)

        por_faixa = raw.get("por_faixa", {}) or {}
        habilidades_abaixo = por_faixa.get("abaixo_do_basico", []) or []
        habilidades_basico = por_faixa.get("basico", []) or []
        habilidades_criticas = list(habilidades_abaixo) + list(habilidades_basico)

        # Resolver nome da disciplina (quando disciplina != all)
        disciplina_nome = None
        if disc_filt:
            for d in raw.get("disciplinas_disponiveis", []) or []:
                if str(d.get("id")) == str(disc_filt):
                    disciplina_nome = d.get("nome")
                    break
        disciplina_label = (disciplina_nome or str(disc_filt)) if disc_filt else "all"

        # Resolver referência da avaliação
        gab = AnswerSheetGabarito.query.get(gabarito_id)
        avaliacao_referencia = (getattr(gab, "title", None) or "Cartão-resposta").strip() if gab else "Cartão-resposta"

        # Resolver série/ano
        if serie and str(serie).strip():
            ano_serie = str(serie).strip()
        elif gab and getattr(gab, "grade_name", None):
            ano_serie = str(gab.grade_name).strip()
        else:
            ano_serie = ""

        # Montar lista de habilidades no formato do prompt
        skills_lines: List[str] = []
        for idx, h in enumerate(habilidades_criticas, start=1):
            codigo = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if codigo and desc:
                item = f"{codigo} - {desc}"
            else:
                item = codigo or desc or (h.get("skill_id") or "")
            skills_lines.append(f"  {idx}. {item}")

        prompt = (
            "Atue como um Especialista em Avaliação Educacional e Recomposição de Aprendizagem, com profundo conhecimento "
            "nas matrizes de referência do SAEB, SPAECE e SAVEAL.\n\n"
            "Abaixo, fornecerei os dados de uma avaliação (Mensal ou Larga Escala) referentes a uma turma.\n\n"
            "Sua tarefa é gerar um plano de ação estritamente focado em alunos que se encontram nos níveis de proficiência "
            "\"ABAIXO DO BÁSICO\" e \"BÁSICO\". O plano deve ser realista, aplicável na rede pública ou privada, utilizando "
            "recursos acessíveis de sala de aula.\n\n"
            "Nomeie o documento final obrigatoriamente como: **ESTRATÉGIAS DE INTERVENÇÃO**.\n\n"
            "O documento deve seguir rigorosamente a estrutura abaixo:\n\n"
            "# ESTRATÉGIAS DE INTERVENÇÃO\n\n"
            "## 1. Foco Analítico: Níveis Abaixo do Básico e Básico\n"
            "[Escreva um breve parágrafo (máx 3 linhas) resumindo qual é a principal barreira cognitiva esperada para esses "
            "alunos nas habilidades fornecidas.]\n\n"
            "## 2. Matriz de Ação por Habilidade\n"
            "Crie uma tabela para cada habilidade listada, contendo:\n"
            "* **Habilidade (Código e Descrição):**\n"
            "* **Conteúdo Estruturante:** (Qual é o conceito matemático ou linguístico fundamental que o aluno precisa dominar "
            "para atingir essa habilidade?)\n"
            "* **Dificuldade Mapeada (Abaixo do Básico/Básico):** (Exatamente onde o aluno trava? Ex: \"Não compreende a "
            "conservação de quantidade\" ou \"Não localiza informação se não estiver no início do texto\").\n"
            "* **Como Trabalhar (Passo a Passo Prático):** (3 etapas progressivas. Comece sempre do concreto/visual, vá para o "
            "pictórico e depois para o abstrato/simbólico. Sem sugestões genéricas; dê exemplos do que o professor deve dizer "
            "ou desenhar no quadro).\n"
            "* **Sugestão de Atividade Curta:** (Uma atividade de no máximo 10 minutos para fixação imediata).\n\n"
            "## 3. Dinâmica de Sala e Recomposição\n"
            "Melhore as estratégias gerais adaptando-as EXCLUSIVAMENTE para alunos com defasagem:\n"
            "* **Agrupamentos Produtivos Focados:** (Como juntar um aluno \"Básico\" com um \"Adequado\" sem que o Adequado faça "
            "o trabalho todo? Dê instruções de papéis na dupla).\n"
            "* **Avaliação Formativa de Baixo Risco (Tickets de Saída):** (Sugira 2 perguntas curtas e diretas para o professor "
            "usar no final da aula e checar se a intervenção daquela habilidade funcionou).\n\n"
            "---\n"
            "DADOS PARA A ANÁLISE:\n"
            f"- Ano/Série: {ano_serie}\n"
            f"- Disciplina: {disciplina_label}\n"
            f"- Avaliação Referência: {avaliacao_referencia}\n"
            "- Habilidades Críticas a serem trabalhadas:\n"
            f"{chr(10).join(skills_lines) if skills_lines else '  1. '}\n\n"
            "IMPORTANTE: Sua resposta deve ser APENAS um JSON válido (objeto) e NADA além do JSON.\n"
            "O JSON deve conter a estrutura equivalente ao documento \"ESTRATÉGIAS DE INTERVENÇÃO\", com chaves para os itens "
            "1, 2 (lista por habilidade) e 3 (dinâmica e tickets).\n"
        )

        ai_service = AIAnalysisService()
        analise_ia = ai_service.analyze_intervention_plan_json(prompt)

        return jsonify(
            {
                "nivel_granularidade": nivel_granularidade,
                "disciplinas_disponiveis": raw.get("disciplinas_disponiveis", []),
                "habilidades": raw.get("habilidades", []),
                "por_faixa": raw.get("por_faixa", {}),
                "analise_ia": analise_ia,
                "filtros_aplicados": {
                    "estado": estado,
                    "municipio": municipio,
                    "escola": escola,
                    "serie": serie,
                    "turma": turma,
                    "gabarito": gabarito,
                    "disciplina": disciplina,
                    "periodo": str(periodo_raw).strip() if periodo_raw and str(periodo_raw).strip() else None,
                },
                "total_alunos_escopo_turma": n_turma,
                "total_alunos_participantes": n_part,
                "total_alunos_escopo": n_part,
            }
        ), 200
    except Exception as e:
        logging.error("Erro mapa habilidades (cartão): %s", e, exc_info=True)
        return jsonify({"error": "Erro ao obter mapa de habilidades", "details": str(e)}), 500


@bp.route("/mapa-habilidades/erros", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def mapa_habilidades_cartao_erros():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        skill_id = request.args.get("skill_id")
        if not skill_id or not str(skill_id).strip():
            return jsonify({"error": "skill_id é obrigatório"}), 400

        estado = request.args.get("estado")
        municipio = request.args.get("municipio")
        escola = request.args.get("escola")
        serie = request.args.get("serie")
        turma = request.args.get("turma")
        gabarito = request.args.get("gabarito")
        disciplina = request.args.get("disciplina") or "all"
        periodo_raw_erros = request.args.get("periodo")
        periodo_bounds_erros = None
        if periodo_raw_erros and str(periodo_raw_erros).strip():
            try:
                periodo_bounds_erros = _parse_cartao_periodo_bounds(str(periodo_raw_erros).strip())
            except ValueError:
                return jsonify({"error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04)."}), 400

        if not _is_valid_filter(estado):
            return jsonify({"error": "Estado é obrigatório e não pode ser 'all'"}), 400
        if not _is_valid_filter(municipio):
            return jsonify({"error": "Município é obrigatório"}), 400
        if not _is_valid_filter(gabarito):
            return jsonify({"error": "Gabarito é obrigatório"}), 400

        municipio_str = str(municipio).strip()
        set_search_path(city_id_to_schema_name(municipio_str))

        gabarito_id = str(gabarito).strip()
        if not _gabarito_eh_somente_cartao_resposta(gabarito_id):
            return jsonify(
                {
                    "error": "Gabarito inválido",
                    "details": "Use apenas gabaritos de cartão-resposta. Avaliações online aparecem na outra aba.",
                }
            ), 400

        scope_info = _determinar_escopo_busca_cartao(
            estado, municipio, escola, serie, turma, gabarito, user
        )
        if not scope_info:
            return jsonify({"error": "Não foi possível determinar o escopo de busca"}), 400

        nivel_granularidade = _determinar_nivel_granularidade_cartao(
            estado, municipio, escola, serie, turma, gabarito
        )

        class_ids = _class_ids_alunos_previstos_cartao(gabarito_id, scope_info, nivel_granularidade, user)

        disc_filt = None if str(disciplina).strip().lower() == "all" else str(disciplina).strip()

        from app.services.skills_map_service import (
            answer_sheet_students_passed_vs_failed,
            build_skills_map_answer_sheet,
        )

        if not class_ids:
            return jsonify(
                {
                    "percentual_erros": 0.0,
                    "percentual_acertos": 0.0,
                    "total_alunos_escopo": 0,
                    "total_alunos_que_erraram": 0,
                    "total_alunos_que_acertaram": 0,
                    "alunos_que_erraram": [],
                    "alunos_que_acertaram": [],
                    "alunos": [],
                    "filtros_aplicados": {
                        "estado": estado,
                        "municipio": municipio,
                        "escola": escola,
                        "serie": serie,
                        "turma": turma,
                        "gabarito": gabarito,
                        "disciplina": disciplina,
                        "skill_id": str(skill_id).strip(),
                        "bloco_disciplina": str(
                            request.args.get("bloco_disciplina") or request.args.get("subject_id") or ""
                        ).strip()
                        or None,
                        "question_ref": str(request.args.get("question_ref") or "").strip() or None,
                        "periodo": (
                            str(periodo_raw_erros).strip()
                            if periodo_raw_erros and str(periodo_raw_erros).strip()
                            else None
                        ),
                    },
                }
            ), 200

        raw = build_skills_map_answer_sheet(gabarito_id, [str(c) for c in class_ids], disc_filt)
        students = raw.get("_students_snapshot") or []
        failed_by_skill = raw.get("_failed_by_skill") or {}

        school_ids = list(
            {s.class_.school_id for s in students if s.class_ and getattr(s.class_, "school_id", None)}
        )
        school_by_id = (
            {s.id: s for s in School.query.filter(School.id.in_(school_ids)).all()}
            if school_ids
            else {}
        )

        bloco_disciplina = request.args.get("bloco_disciplina") or request.args.get("subject_id")
        question_ref = request.args.get("question_ref")

        alunos_err, alunos_ok, n_err, n_ok, n_tot = answer_sheet_students_passed_vs_failed(
            students,
            str(skill_id).strip(),
            failed_by_skill,
            school_by_id,
            bloco_disciplina=str(bloco_disciplina).strip() if bloco_disciplina else None,
            question_ref=str(question_ref).strip() if question_ref else None,
        )
        pct_err = round_to_two_decimals((n_err / n_tot * 100.0) if n_tot else 0.0)
        pct_ok = round_to_two_decimals((n_ok / n_tot * 100.0) if n_tot else 0.0)

        return jsonify(
            {
                "percentual_erros": pct_err,
                "percentual_acertos": pct_ok,
                "total_alunos_escopo": n_tot,
                "total_alunos_que_erraram": n_err,
                "total_alunos_que_acertaram": n_ok,
                "alunos_que_erraram": alunos_err,
                "alunos_que_acertaram": alunos_ok,
                "alunos": alunos_err,
                "filtros_aplicados": {
                    "estado": estado,
                    "municipio": municipio,
                    "escola": escola,
                    "serie": serie,
                    "turma": turma,
                    "gabarito": gabarito,
                    "disciplina": disciplina,
                    "skill_id": str(skill_id).strip(),
                    "bloco_disciplina": str(bloco_disciplina).strip() if bloco_disciplina else None,
                    "question_ref": str(question_ref).strip() if question_ref else None,
                    "periodo": (
                        str(periodo_raw_erros).strip()
                        if periodo_raw_erros and str(periodo_raw_erros).strip()
                        else None
                    ),
                },
            }
        ), 200
    except Exception as e:
        logging.error("Erro mapa habilidades erros (cartão): %s", e, exc_info=True)
        return jsonify({"error": "Erro ao obter alunos que erraram", "details": str(e)}), 500


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


@bp.route('/gabaritos/<string:gabarito_id>/generation-jobs', methods=['GET'])
@jwt_required()
@requires_city_context
def list_generation_jobs_for_gabarito(gabarito_id):
    """
    Lista todos os jobs de geração associados a um cartão resposta (gabarito), em qualquer status
    (processing, completed, failed, etc.), para o front retomar o polling ou saber que pode gerar de novo.

    GET /answer-sheets/gabaritos/<gabarito_id>/generation-jobs
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404

        if gabarito.created_by and str(gabarito.created_by) != str(user.get('id')):
            return jsonify({"error": "Você não tem permissão para acessar este gabarito"}), 403

        current_user_id = str(user.get('id'))
        rows = (
            AnswerSheetGenerationJob.query.filter_by(
                gabarito_id=gabarito_id,
                user_id=current_user_id,
            )
            .order_by(AnswerSheetGenerationJob.created_at.desc())
            .all()
        )

        jobs = []
        for row in rows:
            jid = row.job_id
            jobs.append(
                {
                    "job_id": jid,
                    "gabarito_id": row.gabarito_id,
                    "status": row.status,
                    "scope_type": row.scope_type,
                    "total": row.total,
                    "completed": row.completed,
                    "successful": row.successful,
                    "failed": row.failed,
                    "progress_current": row.progress_current,
                    "progress_percentage": row.progress_percentage,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                    "total_students_generated": row.total_students_generated,
                    "classes_generated": row.classes_generated,
                    "polling_url": f"/answer-sheets/jobs/{jid}/status",
                }
            )

        return (
            jsonify(
                {
                    "gabarito_id": gabarito_id,
                    "last_generation_job_id": gabarito.last_generation_job_id,
                    "jobs": jobs,
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(
            "Erro ao listar jobs de geração do gabarito %s: %s",
            gabarito_id,
            str(e),
            exc_info=True,
        )
        return jsonify({"error": "Erro ao listar jobs de geração"}), 500


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
        from app.services.celery_tasks.answer_sheet_tasks import generate_answer_sheets_async

        current_user_id = get_jwt_identity()
        job_from_db = get_answer_sheet_job(job_id)
        job_redis = get_job(job_id)
        # DB não guarda items (to_dict devolve items={}); Celery grava progresso detalhado no Redis — mesclar.
        if job_from_db:
            job = dict(job_from_db)
            if job_redis:
                if 'items' in job_redis and job_redis['items'] is not None:
                    job['items'] = job_redis['items']
                for k in ('phase', 'stage_message', 'completed', 'successful', 'failed', 'results', 'warnings'):
                    if k in job_redis and job_redis[k] is not None:
                        job[k] = job_redis[k]
        else:
            job = job_redis
        
        if not job:
            return jsonify({"error": "Job não encontrado"}), 404

        # Validar que o job pertence ao usuário
        if job.get('user_id') != str(current_user_id):
            return jsonify({"error": "Acesso negado"}), 403

        # ✅ CONSULTAR STATUS DA TASK BATCH (UMA ÚNICA TASK)
        task_ids = job.get('task_ids', [])
        gabarito_id = job.get('gabarito_id')
        completed = 0
        successful = 0
        failed = 0
        classes_generated = 0
        total_students_generated = 0
        errors = []
        message = 'Processando...'
        
        if task_ids:
            # Agora temos apenas 1 task batch
            task_id = task_ids[0]
            try:
                from app.services.celery_tasks.answer_sheet_tasks import generate_answer_sheets_batch_async
                task_result = AsyncResult(task_id, app=generate_answer_sheets_batch_async.app)
                
                # Determinar mensagem baseada no estado da task
                if task_result.state == 'PENDING':
                    message = 'Aguardando processamento...'
                elif task_result.state == 'STARTED':
                    message = 'Gerando cartões resposta PDF (isso pode levar alguns minutos)...'
                elif task_result.state == 'SUCCESS':
                    result_data_task = task_result.result
                    message = result_data_task.get('message', 'Cartões gerados com sucesso') if result_data_task else 'Cartões gerados com sucesso'
                elif task_result.state == 'FAILURE':
                    message = 'Erro ao gerar cartões'
                elif task_result.state == 'RETRY':
                    message = 'Tentando novamente após erro temporário...'
                else:
                    message = f'Estado: {task_result.state}'
                
                if task_result.state == 'SUCCESS':
                    completed = 1
                    result = task_result.result
                    
                    if result and result.get('success'):
                        # Task batch retorna informações consolidadas
                        successful = 1
                        classes_generated = result.get('total_classes', 0)
                        total_students_generated = result.get('total_students', 0)
                        
                        # Extrair turmas puladas para erros
                        skipped = result.get('skipped_classes', [])
                        for skipped_class in skipped:
                            errors.append({
                                'class_name': skipped_class.get('class_name', 'Unknown'),
                                'error': 'Turma sem alunos registrados'
                            })
                        
                        logging.info(f"✅ Task batch {task_id}: {classes_generated} turma(s), "
                                    f"{total_students_generated} aluno(s) gerados")
                    else:
                        # Task retornou sucesso na execução, mas falhou na geração
                        failed = 1
                        error_msg = result.get('error') if result else 'Erro desconhecido'
                        errors.append({
                            'class_name': 'Batch',
                            'error': error_msg
                        })
                        logging.warning(f"❌ Task batch {task_id}: {error_msg}")
                            
                elif task_result.state == 'FAILURE':
                    completed = 1
                    failed = 1
                    error_msg = str(task_result.info) if task_result.info else 'Erro desconhecido'
                    errors.append({
                        'class_name': 'Batch',
                        'error': error_msg
                    })
                    logging.error(f"❌ Task batch {task_id} FAILURE: {error_msg}")
                    
                elif task_result.state in ['PENDING', 'STARTED', 'RETRY']:
                    # Task ainda processando — progresso progressivo vem do job
                    pass
                    
            except Exception as e:
                logging.debug(f"Erro ao consultar task batch {task_id}: {str(e)}")

        # ✅ DETERMINAR STATUS DO JOB
        job_status = "processing"
        if completed == len(task_ids) and task_ids:
            job_status = "completed"
        
        # ✅ BUSCAR INFORMAÇÕES DO GABARITO
        gabarito = None
        if gabarito_id:
            gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        
        # ✅ PREPARAR PROGRESSO: progressivo durante execução, 100% ao concluir
        # job.get('total') = número de TURMAS (não alunos!)
        total_classes = job.get('total', 1)
        if job_status == "processing" and total_classes > 0:
            progress_current = job.get('progress_current', 0)
            progress_pct = job.get('progress_percentage', 0)
            progress = {
                'current': progress_current,
                'total': total_classes,
                'percentage': min(100, progress_pct),
                'message': f'Processando turma {progress_current}/{total_classes}'
            }
        else:
            progress = {
                'current': total_classes if job_status == "completed" else 0,
                'total': total_classes,
                'percentage': 100 if job_status == "completed" else 0,
                'message': 'Concluído' if job_status == "completed" else 'Aguardando...'
            }
        
        # ✅ INFORMAÇÕES DETALHADAS POR TURMA (igual provas físicas)
        items = job.get('items') or {}
        classes_map = {}
        errors_list = []

        for idx_str, item in items.items():
            st = item.get('status', 'pending')
            class_id = item.get('class_id') or ''
            class_name = item.get('class_name') or 'Turma não informada'
            school_name = item.get('school_name') or ''
            student_id = item.get('student_id')
            student_name = item.get('student_name') or ''

            key = (class_id, class_name, school_name)
            if key not in classes_map:
                classes_map[key] = {
                    'class_id': class_id,
                    'class_name': class_name,
                    'school_name': school_name,
                    'status': 'pending',
                    'total_students': 0,
                    'completed': 0,
                    'successful': 0,
                    'failed': 0,
                    'errors': [],
                }
            classes_map[key]['total_students'] += 1
            if st == 'done':
                classes_map[key]['completed'] += 1
                classes_map[key]['successful'] += 1
            elif st == 'error':
                classes_map[key]['completed'] += 1
                classes_map[key]['failed'] += 1
                err_msg = item.get('error', 'Erro desconhecido')
                classes_map[key]['errors'].append({
                    'student_id': student_id,
                    'student_name': student_name,
                    'error': err_msg,
                })
                errors_list.append({
                    'class_id': class_id,
                    'class_name': class_name,
                    'school_name': school_name,
                    'student_id': student_id,
                    'student_name': student_name,
                    'error': err_msg,
                })
            elif st == 'processing':
                classes_map[key]['status'] = 'processing'

            if classes_map[key]['status'] == 'pending' and st in ('processing', 'done', 'error'):
                classes_map[key]['status'] = 'processing' if st == 'processing' else 'completed'

        classes_list = list(classes_map.values())
        for c in classes_list:
            if c['failed'] > 0:
                c['status'] = 'completed_with_errors'
            elif c['completed'] == c['total_students'] and c['total_students'] > 0:
                c['status'] = 'completed'

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
            'task_id': task_ids[0] if task_ids else None,
            'status': job_status,
            'message': message,
            'progress': progress,
            'result': result_data,
            'summary': {
                'total_classes': len(classes_list) if classes_list else total_classes,
                'completed_classes': sum(1 for c in classes_list if c['status'] in ('completed', 'completed_with_errors')),
                'successful_classes': sum(1 for c in classes_list if c['failed'] == 0 and c['completed'] == c['total_students']),
                'failed_classes': sum(1 for c in classes_list if c['failed'] > 0),
                'total_students': total_students_generated if job_status == 'completed' else sum(c['total_students'] for c in classes_list),
                'completed_students': sum(c['completed'] for c in classes_list),
                'successful_students': sum(c['successful'] for c in classes_list),
                'failed_students': sum(c['failed'] for c in classes_list),
                'zip_minio_url': gabarito.minio_url if gabarito else None,
                'can_download': bool(gabarito and gabarito.minio_url),
            },
            'classes': classes_list,
            'errors': errors_list if errors_list else errors
        }
        
        # Mensagem e fase atuais
        if job.get('stage_message'):
            response['message'] = job['stage_message']
        response['phase'] = job.get('phase')
        
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
        
        if job_from_db is not None:
            update_answer_sheet_job(job_id, updates)
        else:
            from app.services.progress_store import update_job
            update_job(job_id, updates)
        
        logging.info(f"📊 Job {job_id}: {completed}/{len(task_ids)} tasks, "
                    f"{classes_generated} turmas, {total_students_generated} alunos")
        
        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Erro ao buscar status: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar status"}), 500


@bp.route('/recalculate-jobs/<job_id>/status', methods=['GET'])
@jwt_required()
def get_recalculate_job_status(job_id: str):
    """
    Status de recálculo após edição do gabarito.
    Usa progress_store (memória/Redis) e, se necessário, espelho em
    public.answer_sheet_generation_jobs (scope_type=recalculate_gabarito)
    para outro worker ou quando Redis não guarda o job.
    """
    try:
        from app.services.answer_sheet_job_store import get_answer_sheet_job

        current_user_id = get_jwt_identity()
        job = get_job(job_id)
        if not job:
            job_db = get_answer_sheet_job(job_id)
            if job_db and job_db.get("scope_type") == "recalculate_gabarito":
                job = dict(job_db)
        if not job:
            return jsonify({"error": "Job não encontrado"}), 404

        uid_job = str(job.get("user_id") or "")
        uid_req = str(current_user_id) if current_user_id is not None else ""
        if uid_job != uid_req:
            return jsonify({"error": "Acesso negado"}), 403

        total = int(job.get("total") or 0)
        completed = int(job.get("completed") or 0)
        pct = int(round((completed / total * 100))) if total > 0 else 0
        st = job.get("status") or "processing"
        msg = job.get("stage_message") or (
            "Concluído" if st == "completed" else "Processando..."
        )
        phase = job.get("phase")
        if phase is None and st == "completed":
            phase = "done"

        return (
            jsonify(
                {
                    "job_id": job_id,
                    "gabarito_id": job.get("gabarito_id"),
                    "task_id": (job.get("task_ids") or [None])[0],
                    "status": st,
                    "message": msg,
                    "phase": phase,
                    "progress": {
                        "current": completed,
                        "total": total,
                        "percentage": min(100, pct),
                    },
                    "items": job.get("items") or {},
                    "summary": {
                        "total_items": total,
                        "completed_items": completed,
                        "successful_items": int(job.get("successful") or 0),
                        "failed_items": int(job.get("failed") or 0),
                    },
                    "error": job.get("error"),
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(
            "Erro ao buscar status do recálculo %s: %s", job_id, e, exc_info=True
        )
        return jsonify({"error": "Erro ao buscar status do recálculo"}), 500


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
        job = get_answer_sheet_job(job_id) or get_job(job_id)
        
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
            # Professor: ver apenas escolas onde possui TURMA vinculada (TeacherClass → Class → School)
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass

            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return []

            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids = [tc.class_id for tc in teacher_classes]
            if not teacher_class_ids:
                return []

            # Buscar escolas distintas das turmas do professor neste município
            school_ids = [
                s[0] for s in Class.query.with_entities(Class.school_id).distinct().filter(
                    Class.id.in_(teacher_class_ids),
                    Class.school_id.isnot(None),
                ).all()
            ]
            if not school_ids:
                return []

            query_escolas = query_escolas.filter(School.id.in_(school_ids))
    
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
            # Professor: retornar apenas séries onde possui TURMA vinculada nesta escola
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass

            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return []

            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids = [tc.class_id for tc in teacher_classes]
            if not teacher_class_ids:
                return []

    # Buscar séries da escola
    query_series = db.session.query(Grade.id, Grade.name)\
                             .join(Class, Grade.id == Class.grade_id)\
                             .filter(Class.school_id == school.id)\
                             .distinct()\
                             .order_by(Grade.name)

    # Se professor, filtrar apenas séries derivadas das turmas vinculadas
    if permissao['scope'] == 'escola' and user.get('role') == 'professor':
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass

        teacher = Teacher.query.filter_by(user_id=user['id']).first()
        if not teacher:
            return []

        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        teacher_class_ids = [tc.class_id for tc in teacher_classes]
        if teacher_class_ids:
            query_series = query_series.filter(Class.id.in_(teacher_class_ids))
        else:
            return []

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
        role_value = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        )
        role_value = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        )
        permissao = get_user_permission_scope({
            'id': current_user.id,
            'role': role_value,
            'role': role_value,
            'city_id': getattr(current_user, 'city_id', None),
            'tenant_id': getattr(current_user, 'tenant_id', None)
        })
        
        if not permissao['permitted']:
            return jsonify({"error": permissao.get('error', 'Acesso negado')}), 403

        user_dict = {
            'id': current_user.id,
            'role': role_value,
            'role': role_value,
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
