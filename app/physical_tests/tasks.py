# -*- coding: utf-8 -*-
"""
Tasks Celery para geração de formulários físicos
Processa geração de PDFs de forma assíncrona para evitar timeout
"""

import logging
import tempfile
import zipfile
import os
import gc
from datetime import datetime
from typing import Dict, Any, List, Optional
from celery import Task

from app.report_analysis.celery_app import celery_app
from app import db

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='physical_test_tasks.upload_physical_test_zip_async',
    max_retries=0,  # NÃO fazer retry - upload não é crítico
    time_limit=300,  # 5 minutos máximo
    soft_time_limit=270  # 4.5 minutos soft limit
)
def upload_physical_test_zip_async(
    self: Task,
    test_id: str,
    zip_path: str
) -> Dict[str, Any]:
    """
    Task Celery separada para upload de ZIP de provas físicas no MinIO.
    Desacoplada da geração de PDFs - não bloqueia task principal.
    
    Args:
        test_id: ID da prova
        zip_path: Caminho do arquivo ZIP no disco
    
    Returns:
        Dict com resultado do upload (ou None se falhar)
    """
    try:
        from app.services.storage.minio_service import MinIOService
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        
        if not os.path.exists(zip_path):
            logger.error(f"[CELERY-UPLOAD] ZIP não encontrado: {zip_path}")
            return {'success': False, 'error': 'ZIP não encontrado'}
        
        logger.info(f"[CELERY-UPLOAD] ☁️ Enviando ZIP para MinIO: {zip_path}")
        
        minio = MinIOService()
        upload_result = minio.upload_from_path(
            bucket_name=minio.BUCKETS['PHYSICAL_TESTS'],
            object_name=f"{test_id}/all_forms.zip",
            file_path=zip_path
        )
        
        if upload_result:
            minio_url = upload_result['url']
            minio_object_name = upload_result['object_name']
            minio_bucket = upload_result['bucket']
            download_size = upload_result['size']
            
            logger.info(f"[CELERY-UPLOAD] ✅ Upload concluído: {minio_url}")
            
            # Atualizar gabarito no banco com URL do MinIO
            gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
            if gabarito:
                gabarito.minio_url = minio_url
                gabarito.minio_object_name = minio_object_name
                gabarito.minio_bucket = minio_bucket
                gabarito.zip_generated_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"[CELERY-UPLOAD] ✅ Gabarito atualizado com URL do MinIO")
            
            return {
                'success': True,
                'minio_url': minio_url,
                'download_size_bytes': download_size
            }
        else:
            logger.warning(f"[CELERY-UPLOAD] ⚠️ Upload para MinIO falhou")
            return {'success': False, 'error': 'Upload falhou'}
            
    except Exception as e:
        logger.error(f"[CELERY-UPLOAD] ⚠️ Erro ao fazer upload para MinIO: {str(e)}", exc_info=True)
        # NÃO fazer retry - upload não é crítico
        return {'success': False, 'error': str(e)}


@celery_app.task(
    bind=True,
    name='physical_test_tasks.generate_physical_forms_async',
    max_retries=2,  # Retry 2x se falhar
    default_retry_delay=60,  # 1 minuto entre retries
    time_limit=900,  # 15 minutos máximo (para turmas muito grandes)
    soft_time_limit=840  # 14 minutos soft limit
)
def generate_physical_forms_async(
    self: Task,
    test_id: str,
    city_id: str,
    force_regenerate: bool = False,
    blocks_config: Dict = None,
    school_ids: List = None,
    grade_ids: List = None,
    class_ids: List = None
) -> Dict[str, Any]:
    """
    Task Celery para geração ASSÍNCRONA de formulários físicos.
    
    Gera PDFs institucionais para todos os alunos de uma prova de forma assíncrona,
    evitando timeout do Gunicorn e permitindo processar turmas grandes.
    
    Args:
        test_id: ID da prova (UUID)
        city_id: ID da cidade (UUID) - necessário para configurar search_path
        force_regenerate: Se True, regenera mesmo se já existirem formulários
        blocks_config: Configuração de blocos do payload (opcional)
            {
                'use_blocks': bool,
                'num_blocks': int,
                'questions_per_block': int,
                'separate_by_subject': bool
            }
        school_ids: (opcional) Lista de IDs de escolas para gerar apenas para essas escolas
        grade_ids: (opcional) Lista de IDs de séries para gerar apenas para essas séries
        class_ids: (opcional) Lista de IDs de turmas para gerar apenas para essas turmas
        Filtros em cascata: só turmas que pertencem às escolas/séries/turmas informadas.
    
    Returns:
        Dict com resultado da geração:
        {
            'success': bool,
            'test_id': str,
            'test_title': str,
            'generated_forms': int,
            'total_students': int,
            'total_questions': int,
            'gabarito_id': str,
            'forms': List[Dict]  # Lista de formulários gerados
        }
    
    Raises:
        Exception: Se ocorrer erro na geração (com retry automático)
    
    Example:
        # Disparar task
        task = generate_physical_forms_async.delay(
            test_id='abc-123',
            city_id='city-uuid',
            blocks_config={'use_blocks': True, 'num_blocks': 2, 'questions_per_block': 5}
        )
        
        # Verificar status
        from celery.result import AsyncResult
        result = AsyncResult(task.id)
        if result.ready():
            data = result.get()
    """
    job_id = None
    try:
        job_id = self.request.id
        print(f"[CELERY] ========== TASK CELERY INICIADA ==========")
        print(f"[CELERY] test_id: {test_id}")
        print(f"[CELERY] city_id: {city_id}")
        print(f"[CELERY] force_regenerate: {force_regenerate}")
        print(f"[CELERY] blocks_config recebido: {blocks_config}")
        logger.info(f"[CELERY] 🚀 Iniciando geração de formulários físicos para test_id={test_id}, city_id={city_id}")
        
        # Imports locais para evitar problemas de circular import
        from app.models.test import Test
        from app.models.student import Student
        from app.models.classTest import ClassTest
        from app.models.question import Question
        from app.models.testQuestion import TestQuestion
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        from app.models.studentClass import Class
        from app.models.school import School
        from app.physical_tests.form_service import PhysicalTestFormService
        from app.models.city import City
        from sqlalchemy import text
        
        # MULTITENANT FIX: Configurar search_path para o schema da cidade
        city = City.query.get(city_id)
        if not city:
            error_msg = f"Cidade {city_id} não encontrada"
            logger.error(f"[CELERY] ❌ {error_msg}")
            raise ValueError(error_msg)
        
        city_schema = f"city_{city.id.replace('-', '_')}"
        logger.info(f"[CELERY] 🌐 Configurando search_path para: {city_schema}, public")
        
        from app import db
        db.session.execute(text(f'SET search_path TO "{city_schema}", public'))
        
        # Verificar se a prova existe
        test = Test.query.get(test_id)
        if not test:
            error_msg = f"Prova {test_id} não encontrada"
            logger.error(f"[CELERY] ❌ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"[CELERY] ✅ Prova encontrada: {test.title}")
        
        # Buscar ClassTest (aplicações da prova)
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
        if not class_tests:
            error_msg = f"A prova {test.title} não foi aplicada em nenhuma turma"
            logger.warning(f"[CELERY] ⚠️ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'test_id': test_id,
                'test_title': test.title,
                'generated_forms': 0
            }
        
        logger.info(f"[CELERY] 📊 Prova aplicada em {len(class_tests)} turma(s)")

        # Aplicar filtros de escopo (escola / série / turma) em cascata
        if school_ids or grade_ids or class_ids:
            class_ids_raw = [ct.class_id for ct in class_tests]
            classes = Class.query.filter(Class.id.in_(class_ids_raw)).all()
            allowed_class_ids = set()
            for c in classes:
                if school_ids and (c.school_id is None or str(c.school_id) not in [str(x) for x in school_ids]):
                    continue
                if grade_ids and (c.grade_id is None or str(c.grade_id) not in [str(x) for x in grade_ids]):
                    continue
                if class_ids and str(c.id) not in [str(x) for x in class_ids]:
                    continue
                allowed_class_ids.add(c.id)
            class_tests = [ct for ct in class_tests if ct.class_id in allowed_class_ids]
            if not class_tests:
                error_msg = "Nenhuma turma encontrada para os filtros de escola/série/turma informados"
                logger.warning(f"[CELERY] ⚠️ {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'test_id': test_id,
                    'test_title': test.title,
                    'generated_forms': 0
                }
            logger.info(f"[CELERY] 📊 Após filtros: {len(class_tests)} turma(s)")

        # Coletar todos os alunos das turmas (já filtradas se escopo foi informado)
        all_students = []
        class_ids = [ct.class_id for ct in class_tests]
        
        students = Student.query.filter(
            Student.class_id.in_(class_ids)
        ).order_by(Student.name).all()
        
        students_data = [
            {
                'id': str(s.id),
                'nome': s.name
            }
            for s in students
        ]
        
        logger.info(f"[CELERY] 📊 Total de alunos ativos: {len(students_data)}")
        
        if not students_data:
            error_msg = "Nenhum aluno ativo encontrado nas turmas"
            logger.warning(f"[CELERY] ⚠️ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'test_id': test_id,
                'test_title': test.title,
                'generated_forms': 0
            }
        
        # Buscar questões da prova
        test_questions = TestQuestion.query.filter_by(
            test_id=test_id
        ).order_by(TestQuestion.order).all()
        
        from app.models.skill import Skill
        
        def _resolve_question_subject_id(question) -> Optional[str]:
            """Resolve disciplina da questão: via primeira habilidade (skill), fallback subject_id."""
            if question.skill:
                skill_id_raw = (question.skill or '').strip().strip('{}')
                if skill_id_raw:
                    try:
                        skill_obj = Skill.query.get(skill_id_raw)
                        if skill_obj and getattr(skill_obj, 'subject_id', None):
                            return str(skill_obj.subject_id)
                    except Exception:
                        pass
            if getattr(question, 'subject_id', None):
                return str(question.subject_id)
            return None
        
        questions_data = []
        for tq in test_questions:
            question = Question.query.get(tq.question_id)
            if question:
                questions_data.append({
                    'id': str(question.id),
                    'text': question.text,
                    'formatted_text': question.formatted_text,
                    'title': question.title,
                    'alternatives': question.alternatives or [],
                    'correct_answer': question.correct_answer,
                    'order': tq.order,
                    'subject_id': _resolve_question_subject_id(question),
                })
        
        num_questions = len(questions_data)
        logger.info(f"[CELERY] 📝 Total de questões: {num_questions}")
        
        # Preparar respostas corretas
        correct_answers = {}
        for i, q in enumerate(questions_data, start=1):
            correct_answers[str(i)] = q.get('correct_answer', 'A')
        
        # Extrair questions_options (alternativas por questão)
        questions_options = {}
        for i, q in enumerate(questions_data, start=1):
            alternatives = q.get('alternatives', [])
            if isinstance(alternatives, list) and len(alternatives) >= 2:
                # Converter para formato ['A', 'B', 'C', 'D']
                letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
                options_list = []
                for idx, alt in enumerate(alternatives):
                    if idx < len(letters):
                        options_list.append(letters[idx])
                if options_list:
                    questions_options[str(i)] = options_list
                else:
                    questions_options[str(i)] = ['A', 'B', 'C', 'D']
            else:
                questions_options[str(i)] = ['A', 'B', 'C', 'D']
        
        # ✅ USAR blocks_config recebido do payload (se fornecido)
        if blocks_config is None:
            blocks_config = {}
        
        # Validar e normalizar blocks_config
        use_blocks = blocks_config.get('use_blocks', False)
        if use_blocks:
            if 'num_blocks' not in blocks_config:
                blocks_config['num_blocks'] = 1
            if 'questions_per_block' not in blocks_config:
                blocks_config['questions_per_block'] = 12
            if 'separate_by_subject' not in blocks_config:
                blocks_config['separate_by_subject'] = False
        
        # ✅ CRÍTICO: Gerar estrutura completa (topology) SEMPRE que use_blocks=True
        # Isso garante que a topologia completa seja salva no banco
        if use_blocks:
            if 'topology' in blocks_config and blocks_config.get('topology'):
                logger.info(f"[CELERY] ✅ Topology já existe no blocks_config")
            elif blocks_config.get('separate_by_subject'):
                # ✅ Separar por disciplina: 2–4 blocos, um por disciplina; disciplina da questão via primeira habilidade
                from app.utils.response_formatters import _get_all_subjects_from_test
                subjects_info = _get_all_subjects_from_test(test)
                if not subjects_info:
                    logger.info(f"[CELERY] separate_by_subject ativo mas sem disciplinas na prova; usando estrutura padrão")
                    from app.physical_tests.routes import _generate_complete_structure
                    complete_structure = _generate_complete_structure(
                        num_questions=num_questions,
                        use_blocks=use_blocks,
                        blocks_config=blocks_config,
                        questions_options=questions_options
                    )
                    blocks_config['topology'] = complete_structure
                else:
                    num_blocks = min(4, max(2, len(subjects_info)))
                    # Mapa número da questão (1-based) -> alternativas
                    questions_map = {}
                    for key, value in questions_options.items():
                        try:
                            q_num = int(key)
                            questions_map[q_num] = value if isinstance(value, list) and len(value) >= 2 else ['A', 'B', 'C', 'D']
                        except (ValueError, TypeError):
                            continue
                    for q in range(1, num_questions + 1):
                        if q not in questions_map:
                            questions_map[q] = ['A', 'B', 'C', 'D']
                    subject_ids_ordered = [str(s['id']) for s in subjects_info]
                    blocks_question_numbers = []
                    if len(subjects_info) == 1 and num_blocks == 2:
                        # Uma disciplina com 2 blocos: repartir em até 22 no primeiro, resto no segundo
                        sid = subject_ids_ordered[0]
                        q_nums = [i + 1 for i in range(num_questions) if (questions_data[i].get('subject_id') or '').strip() == sid]
                        if not q_nums:
                            q_nums = list(range(1, num_questions + 1))
                        n = len(q_nums)
                        blocks_question_numbers = [q_nums[: min(22, n)], q_nums[min(22, n):]]
                    else:
                        # Um bloco por disciplina (máx. 4 disciplinas)
                        for subj in subjects_info[:num_blocks]:
                            sid = str(subj['id'])
                            q_nums = [i + 1 for i in range(num_questions) if (questions_data[i].get('subject_id') or '').strip() == sid]
                            blocks_question_numbers.append(q_nums)
                    topology_blocks = []
                    for block_idx, q_nums in enumerate(blocks_question_numbers, start=1):
                        questions_in_block = [
                            {"q": q_num, "alternatives": questions_map.get(q_num, ['A', 'B', 'C', 'D'])}
                            for q_num in q_nums
                        ]
                        topology_blocks.append({"block_id": block_idx, "questions": questions_in_block})
                    if not topology_blocks and num_questions > 0:
                        topology_blocks = [{
                            "block_id": 1,
                            "questions": [{"q": i, "alternatives": questions_map.get(i, ['A', 'B', 'C', 'D'])} for i in range(1, num_questions + 1)]
                        }]
                    blocks_config['topology'] = {'blocks': topology_blocks}
                    blocks_config['num_blocks'] = len(topology_blocks)
                    logger.info(f"[CELERY] ✅ Estrutura por disciplina: {len(topology_blocks)} blocos")
            else:
                if 'topology' not in blocks_config or not blocks_config.get('topology'):
                    logger.info(f"[CELERY] 🔨 Gerando estrutura completa de blocos...")
                    from app.physical_tests.routes import _generate_complete_structure
                    complete_structure = _generate_complete_structure(
                        num_questions=num_questions,
                        use_blocks=use_blocks,
                        blocks_config=blocks_config,
                        questions_options=questions_options
                    )
                    blocks_config['topology'] = complete_structure
                    logger.info(f"[CELERY] ✅ Estrutura gerada: {blocks_config.get('num_blocks', 1)} blocos, {len(complete_structure.get('blocks', []))} blocos na topology")
                else:
                    logger.info(f"[CELERY] ✅ Topology já existe no blocks_config")
        
        # ✅ MODIFICADO: SEMPRE criar/atualizar AnswerSheetGabarito central para provas físicas
        # Isso centraliza os dados pesados (topology + gabarito) em um único lugar
        logger.info(f"[CELERY] 📋 Criando/atualizando AnswerSheetGabarito central para prova física")
        logger.info(f"[CELERY]    num_questions={num_questions}, use_blocks={use_blocks}, num_blocks={blocks_config.get('num_blocks', 1)}")
        logger.info(f"[CELERY]    blocks_config tem topology: {'topology' in blocks_config}")
        if 'topology' in blocks_config:
            logger.info(f"[CELERY]    topology tem {len(blocks_config['topology'].get('blocks', []))} blocos")
        
        # Buscar ou criar AnswerSheetGabarito
        gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
        
        # Buscar metadados da primeira turma para o gabarito
        first_class_id = class_ids[0] if class_ids else None
        school_id = None
        school_name = ''
        municipality = ''
        state = ''
        
        if first_class_id:
            first_class = Class.query.get(first_class_id)
            if first_class and first_class.school_id:
                school = School.query.get(first_class.school_id)
                if school:
                    school_id = school.id
                    school_name = school.name or ''
                    if school.city_id:
                        city_obj = City.query.get(school.city_id)
                        if city_obj:
                            municipality = city_obj.name or ''
                            state = city_obj.state or ''
        
        if gabarito:
            # Atualizar gabarito existente com novos dados
            gabarito.num_questions = num_questions
            gabarito.use_blocks = use_blocks
            gabarito.blocks_config = blocks_config.copy()
            gabarito.correct_answers = correct_answers.copy()
            gabarito.class_id = first_class_id
            gabarito.school_id = str(school_id) if school_id else None
            gabarito.school_name = school_name
            gabarito.municipality = municipality
            gabarito.state = state
            gabarito.grade_name = test.grade.name if test.grade else None
            gabarito.title = test.title
            logger.info(f"[CELERY] ✅ AnswerSheetGabarito atualizado: {gabarito.id}")
        else:
            # Criar novo gabarito central
            gabarito = AnswerSheetGabarito(
                test_id=test_id,
                class_id=first_class_id,
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config.copy(),
                correct_answers=correct_answers.copy(),
                title=test.title,
                school_id=str(school_id) if school_id else None,
                school_name=school_name,
                municipality=municipality,
                state=state,
                grade_name=test.grade.name if test.grade else None
            )
            db.session.add(gabarito)
            logger.info(f"[CELERY] ✅ AnswerSheetGabarito criado para prova física")
        
        db.session.commit()
        gabarito_id = gabarito.id
        logger.info(f"[CELERY] ✅ Gabarito central salvo: gabarito_id={gabarito_id}")
        
        # Preparar test_data com blocks_config atualizado
        print(f"[CELERY] ========== PREPARANDO CORRECTION_DATA ==========")
        print(f"[CELERY] num_questions: {num_questions}")
        print(f"[CELERY] use_blocks: {use_blocks}")
        print(f"[CELERY] blocks_config ANTES de copiar: {blocks_config}")
        print(f"[CELERY] blocks_config tem topology: {'topology' in blocks_config if blocks_config else False}")
        if blocks_config and 'topology' in blocks_config:
            print(f"[CELERY] topology tem {len(blocks_config['topology'].get('blocks', []))} blocos")
        print(f"[CELERY] correct_answers: {correct_answers}")
        
        correction_data_to_pass = {
            'num_questions': num_questions,
            'use_blocks': use_blocks,
            'blocks_config': blocks_config.copy() if blocks_config else {},  # ✅ Copiar para garantir que não seja modificado
            'correct_answers': correct_answers.copy() if correct_answers else {}  # ✅ Copiar para garantir que não seja modificado
        }
        
        print(f"[CELERY] correction_data preparado: {correction_data_to_pass}")
        print(f"[CELERY] correction_data['blocks_config'] tem topology: {'topology' in correction_data_to_pass.get('blocks_config', {})}")
        
        test_data = {
            'id': str(test.id),
            'title': test.title,
            'description': test.description or '',
            'blocks_config': blocks_config or {},
            'num_questions': num_questions,
            # ✅ NOVO: Passar gabarito_id para incluir no QR Code
            'gabarito_id': gabarito_id,
            # ✅ NOVO: Passar dados de correção para salvar no PhysicalTestForm
            # IMPORTANTE: blocks_config aqui já deve ter a topology completa
            'correction_data': correction_data_to_pass,
            # Filtros de escopo para o serviço aplicar (cascata escola -> série -> turma)
            'scope_filter': {
                'school_ids': school_ids or None,
                'grade_ids': grade_ids or None,
                'class_ids': class_ids or None
            }
        }
        
        # ✅ Job de progresso: items com turma desde o início (status mostra turmas corretas logo no primeiro GET)
        from app.services.progress_store import create_job, complete_job, update_job
        class_ids_unique = list({s.class_id for s in students if s.class_id})
        classes_objs = Class.query.filter(Class.id.in_(class_ids_unique)).all() if class_ids_unique else []
        class_map = {c.id: c for c in classes_objs}
        school_ids_unique = list({c.school_id for c in classes_objs if c.school_id})
        schools_objs = School.query.filter(School.id.in_(school_ids_unique)).all() if school_ids_unique else []
        school_map = {s.id: (s.name or '') for s in schools_objs}
        items_meta = []
        for s in students:
            c = class_map.get(s.class_id)
            class_name = (c.name or '') if c else ''
            school_name = school_map.get(c.school_id, '') if c and c.school_id else ''
            items_meta.append({
                'student_id': str(s.id),
                'student_name': s.name or '',
                'class_id': str(s.class_id) if s.class_id else '',
                'class_name': class_name,
                'school_name': school_name,
            })
        create_job(job_id=job_id, total=len(students_data), test_id=test_id, items_meta=items_meta)
        test_data['job_id'] = job_id
        
        print(f"[CELERY] test_data['correction_data'] existe: {'correction_data' in test_data}")
        print(f"[CELERY] ========== CHAMANDO FORM_SERVICE ==========")
        
        # Criar diretório temporário para ZIP (PDFs serão salvos no output_dir padrão)
        temp_dir = tempfile.mkdtemp()
        
        # Gerar formulários usando o serviço existente (processamento incremental)
        logger.info(f"[CELERY] 🔨 Iniciando geração de PDFs para {len(students_data)} alunos...")
        
        form_service = PhysicalTestFormService()
        
        # output_dir padrão será usado (/tmp/celery_pdfs/physical_tests)
        result = form_service.generate_physical_forms(
            test_id=test_id,
            test_data=test_data
            # output_dir padrão será usado automaticamente
        )
        
        if result.get('success'):
            generated_count = result.get('generated_forms', 0)
            logger.info(f"[CELERY] ✅ Formulários gerados com sucesso: {generated_count}/{len(students_data)}")
            
            # Obter arquivos gerados diretamente do resultado (não do banco)
            generated_files = result.get('generated_files', [])
            
            # Buscar formulários salvos para resposta
            forms = form_service.get_physical_forms_by_test(test_id)
            formularios_gerados = []
            
            for form in forms:
                formularios_gerados.append({
                    'student_id': form['student_id'],
                    'student_name': form['student_name'],
                    'form_id': form['id'],
                    'form_type': form['form_type'],
                    'created_at': form['generated_at']
                })
            
            # ========================================================================
            # CRIAR ZIP A PARTIR DE ARQUIVOS EM DISCO (NÃO EM MEMÓRIA)
            # ========================================================================
            zip_path = os.path.join(temp_dir, f'provas_fisicas_{test_id}.zip')
            try:
                update_job(job_id, {"phase": "zipping", "stage_message": "Criando pacote para download..."})
            except Exception:
                pass
            logger.info(f"[CELERY] 📦 Criando ZIP a partir de arquivos em disco...")
            
            minio_url = None
            minio_object_name = None
            minio_bucket = None
            download_size = 0
            
            if generated_files:
                try:
                    # Estrutura de pastas no ZIP = mesma do cartão-resposta: municipio_/escola_/serie_/turma_/arquivo.pdf
                    from app.services.cartao_resposta.answer_sheet_generator import sanitize_filename
                    from app.models.grades import Grade

                    student_id_to_class_id = {str(s.id): s.class_id for s in students}
                    city_ids = list({s.city_id for s in schools_objs if getattr(s, 'city_id', None)})
                    cities = {c.id: c for c in (City.query.filter(City.id.in_(city_ids)).all() if city_ids else [])}
                    grade_ids = list({c.grade_id for c in classes_objs if c.grade_id})
                    grades = {g.id: g for g in (Grade.query.filter(Grade.id.in_(grade_ids)).all() if grade_ids else [])}

                    class_id_to_path_parts = {}
                    for c in classes_objs:
                        school = next((s for s in schools_objs if s.id == c.school_id), None)
                        city_name = 'municipio'
                        if school and getattr(school, 'city_id', None):
                            city_obj = cities.get(school.city_id)
                            if city_obj and getattr(city_obj, 'name', None):
                                city_name = city_obj.name
                        school_name = (school.name if school else None) or 'escola'
                        grade_name = (grades.get(c.grade_id).name if c.grade_id and grades.get(c.grade_id) else None) or 'serie'
                        class_name = (c.name or 'turma').strip() or 'turma'
                        class_id_to_path_parts[c.id] = (city_name, school_name, grade_name, class_name)

                    fallback_parts = ('municipio', 'escola', 'serie', 'turma')

                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for file_info in generated_files:
                            pdf_path = file_info.get('pdf_path')
                            if pdf_path and os.path.exists(pdf_path):
                                student_id = file_info.get('student_id')
                                student_name = file_info.get('student_name') or 'aluno'
                                class_id = student_id_to_class_id.get(str(student_id)) if student_id else None
                                if class_id and class_id in class_id_to_path_parts:
                                    city_name, school_name, grade_name, class_name = class_id_to_path_parts[class_id]
                                else:
                                    city_name, school_name, grade_name, class_name = fallback_parts
                                folder_path = os.path.join(
                                    f"municipio_{sanitize_filename(city_name, max_length=60)}",
                                    f"escola_{sanitize_filename(school_name, max_length=60)}",
                                    f"serie_{sanitize_filename(grade_name, max_length=40)}",
                                    f"turma_{sanitize_filename(class_name, max_length=40)}",
                                )
                                grade_safe = sanitize_filename(grade_name, max_length=40)
                                class_safe = sanitize_filename(class_name, max_length=40)
                                name_safe = sanitize_filename(student_name, max_length=60)
                                filename = f"{name_safe}_{grade_safe}_{class_safe}.pdf"
                                arcname = os.path.join(folder_path, filename)
                                zf.write(pdf_path, arcname)
                    
                    zip_size = os.path.getsize(zip_path)
                    logger.info(f"[CELERY] ✅ ZIP criado: {zip_size} bytes")
                    
                    # ========================================================================
                    # UPLOAD PARA MINIO (NÃO CRÍTICO - não deve derrubar a task)
                    # ========================================================================
                    try:
                        update_job(job_id, {"phase": "uploading", "stage_message": "Enviando arquivos para o servidor..."})
                    except Exception:
                        pass
                    logger.info(f"[CELERY] ☁️ Enviando ZIP para MinIO...")
                    try:
                        from app.services.storage.minio_service import MinIOService
                        
                        minio = MinIOService()
                        # Usar upload_from_path para não carregar ZIP inteiro em memória
                        upload_result = minio.upload_from_path(
                            bucket_name=minio.BUCKETS['PHYSICAL_TESTS'],
                            object_name=f"{test_id}/all_forms.zip",
                            file_path=zip_path
                        )
                        
                        if upload_result:
                            minio_url = upload_result['url']
                            minio_object_name = upload_result['object_name']
                            minio_bucket = upload_result['bucket']
                            download_size = upload_result['size']
                            
                            logger.info(f"[CELERY] ✅ Upload concluído: {minio_url}")
                            
                            # Criar ou atualizar AnswerSheetGabarito para o download-all funcionar
                            gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
                            if gabarito:
                                gabarito.minio_url = minio_url
                                gabarito.minio_object_name = minio_object_name
                                gabarito.minio_bucket = minio_bucket
                                gabarito.zip_generated_at = datetime.utcnow()
                                logger.info(f"[CELERY] ✅ Gabarito atualizado com URL do MinIO (prova física)")
                            else:
                                gabarito = AnswerSheetGabarito(
                                    test_id=test_id,
                                    class_id=class_ids[0] if class_ids else None,
                                    num_questions=num_questions,
                                    use_blocks=use_blocks,
                                    blocks_config=blocks_config,
                                    correct_answers=correct_answers,
                                    title=test.title,
                                    grade_name=test.grade.name if test.grade else None,
                                    minio_url=minio_url,
                                    minio_object_name=minio_object_name,
                                    minio_bucket=minio_bucket,
                                    zip_generated_at=datetime.utcnow()
                                )
                                db.session.add(gabarito)
                                logger.info(f"[CELERY] ✅ Gabarito criado com URL do MinIO (prova física)")
                            db.session.commit()
                        else:
                            logger.warning(f"[CELERY] ⚠️ Upload para MinIO falhou, mas PDFs foram gerados com sucesso")
                            
                    except Exception as minio_error:
                        # 🔒 Erro de MinIO NÃO deve derrubar a task - PDFs já foram gerados
                        logger.error(f"[CELERY] ⚠️ Erro ao fazer upload para MinIO (não crítico): {str(minio_error)}", exc_info=True)
                    
                    # Liberar memória explicitamente
                    gc.collect()
                    
                finally:
                    # Limpar arquivos temporários
                    try:
                        import shutil
                        shutil.rmtree(temp_dir)
                        logger.info(f"[CELERY] 🧹 Arquivos temporários limpos")
                    except Exception as e:
                        logger.warning(f"[CELERY] ⚠️ Erro ao limpar arquivos temporários: {str(e)}")
            
            complete_job(job_id)
            return {
                'success': True,
                'test_id': test_id,
                'test_title': test.title,
                'total_questions': num_questions,
                'total_students': len(students_data),
                'generated_forms': len(formularios_gerados),
                # ✅ MODIFICADO: Provas físicas não têm gabarito_id (dados estão em PhysicalTestForm)
                'minio_url': minio_url,
                'download_size_bytes': download_size,
                'forms': formularios_gerados,
                'message': f'Formulários gerados com sucesso para {len(formularios_gerados)} alunos'
            }
        else:
            error_msg = result.get('error', 'Erro desconhecido ao gerar formulários')
            logger.error(f"[CELERY] ❌ Erro na geração: {error_msg}")
            if job_id:
                complete_job(job_id)
            raise Exception(error_msg)
    
    except Exception as e:
        from app.services.progress_store import complete_job as _complete_job
        error_msg = str(e)
        logger.error(f"[CELERY] ❌ Erro ao gerar formulários físicos: {error_msg}", exc_info=True)

        # 🔒 NÃO fazer retry por erro de MinIO - apenas por erros críticos de geração
        # Se PDFs foram gerados mas upload falhou, não retryar
        is_minio_error = 'minio' in error_msg.lower() or 's3' in error_msg.lower() or 'ssl' in error_msg.lower()

        if is_minio_error:
            logger.warning(f"[CELERY] ⚠️ Erro de MinIO detectado - não retryando task (PDFs podem ter sido gerados)")
            if job_id:
                _complete_job(job_id)
            return {
                'success': False,
                'error': error_msg,
                'test_id': test_id,
                'generated_forms': 0,
                'is_minio_error': True
            }

        # Retry apenas para erros críticos (não relacionados a MinIO)
        if self.request.retries < self.max_retries:
            logger.info(f"[CELERY] 🔄 Tentando novamente (retry {self.request.retries + 1}/{self.max_retries})...")
            raise self.retry(exc=e)
        else:
            if job_id:
                _complete_job(job_id)
            return {
                'success': False,
                'error': error_msg,
                'test_id': test_id,
                'generated_forms': 0
            }
