from flask import Blueprint, request, jsonify, send_file
from app.exams.models.question import Question
from app.models.subject import Subject
from app.models.grades import Grade
from app.models.educationStage import EducationStage
from app.exams.models.test import Test
from app.exams.models.testQuestion import TestQuestion
from app.models.user import User
from app.exams.models.studentAnswer import StudentAnswer
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
import re
from io import BytesIO
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
    Extrai imagens em base64 do conteúdo HTML (legado; usado por migração).
    Retorna lista de dicts com id, type, width, height, data (base64).
    """
    images = []
    img_pattern = r'<img[^>]+src="(data:image/[^;]+;base64,[^"]+)"[^>]*>'
    for match in re.finditer(img_pattern, html_content or ''):
        base64_data = match.group(1)
        image_type = base64_data.split(';')[0].split(':')[1]
        image_info = process_image(base64_data, image_type)
        images.append(image_info)
    return images


def _mime_to_ext(mime):
    """Mapeia MIME type para extensão de arquivo."""
    m = (mime or '').lower()
    if 'png' in m:
        return 'png'
    if 'jpeg' in m or 'jpg' in m:
        return 'jpg'
    if 'gif' in m:
        return 'gif'
    if 'webp' in m:
        return 'webp'
    return 'png'


def _upload_html_base64_images_to_minio(question_id, html_content):
    """
    Extrai imagens base64 do HTML, envia para MinIO e substitui src por URL da API.
    Retorna (novo_html, lista de metadados de imagens sem campo 'data').
    """
    if not html_content or 'data:image/' not in html_content:
        return html_content, []
    img_pattern = r'<img[^>]+src="(data:image/[^;]+;base64,[^"]+)"[^>]*>'
    from app.services.storage.minio_service import MinIOService
    minio = MinIOService()
    bucket_name = MinIOService.BUCKETS['QUESTION_IMAGES']
    new_html = html_content
    images_meta = []
    for match in re.finditer(img_pattern, html_content):
        src = match.group(1)
        b64 = src.split(',', 1)[1] if ',' in src else src
        try:
            image_bytes = base64.b64decode(b64)
        except Exception as e:
            logging.warning(f"Decode base64 image failed: {e}")
            continue
        mime = src.split(';')[0].split(':')[-1].strip()
        image_id = str(uuid.uuid4())
        ext = _mime_to_ext(mime)
        image_name = f"{image_id}.{ext}"
        result = minio.upload_question_image(question_id, image_bytes, image_name)
        if not result:
            logging.error(f"Upload question image failed for question {question_id}")
            continue
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            width, height = pil_img.width, pil_img.height
        except Exception:
            width, height = None, None
        images_meta.append({
            "id": image_id,
            "type": mime,
            "width": width,
            "height": height,
            "minio_bucket": bucket_name,
            "minio_object_name": result["object_name"],
        })
        api_url = f"/questions/{question_id}/images/{image_id}"
        new_html = new_html.replace(src, api_url, 1)
    return new_html, images_meta


def _sanitize_stored_image_meta(image_obj):
    """Retorna metadados persistíveis (sem base64/data)."""
    if not isinstance(image_obj, dict):
        return None
    clean = {}
    for key in ('id', 'type', 'width', 'height', 'minio_bucket', 'minio_object_name', 'size'):
        val = image_obj.get(key)
        if val is not None:
            clean[key] = val
    return clean if clean.get('id') else None


def _decode_image_bytes_and_mime(image_input):
    """Decodifica bytes e MIME a partir de string data-URL, base64 ou dict com 'data'."""
    raw = image_input
    if isinstance(image_input, dict):
        raw = image_input.get('data') or image_input.get('base64')
    if not raw or not isinstance(raw, str):
        return None, None
    mime = 'image/png'
    b64 = raw
    if raw.startswith('data:image'):
        header, _, payload = raw.partition(',')
        b64 = payload
        mime = header.split(';')[0].split(':')[-1].strip() or mime
    try:
        image_bytes = base64.b64decode(b64)
    except Exception as e:
        logging.warning(f"Decode alternative image base64 failed: {e}")
        return None, None
    return image_bytes, mime


def _upload_alternative_image(question_id, image_input, existing_by_id=None):
    """
    Processa imagem de alternativa: upload MinIO se base64, ou reutiliza metadados existentes.
    Retorna dict de metadados (sem data) ou None.
    """
    if image_input is None:
        return None
    if isinstance(image_input, dict) and not image_input:
        return None

    existing_by_id = existing_by_id or {}
    from app.services.storage.minio_service import MinIOService
    bucket_name = MinIOService.BUCKETS['QUESTION_IMAGES']

    if isinstance(image_input, dict):
        if image_input.get('minio_bucket') and image_input.get('minio_object_name'):
            image_id = image_input.get('id') or str(uuid.uuid4())
            meta = _sanitize_stored_image_meta({**image_input, 'id': image_id})
            if meta and not meta.get('minio_bucket'):
                meta['minio_bucket'] = bucket_name
            return meta
        image_id = image_input.get('id')
        if image_id and str(image_id) in existing_by_id:
            return _sanitize_stored_image_meta(existing_by_id[str(image_id)])

    image_bytes, mime = _decode_image_bytes_and_mime(image_input)
    if not image_bytes:
        return None

    minio = MinIOService()
    image_id = str(uuid.uuid4())
    if isinstance(image_input, dict) and image_input.get('id'):
        image_id = str(image_input['id'])
    ext = _mime_to_ext(mime)
    image_name = f"{image_id}.{ext}"
    result = minio.upload_question_image(question_id, image_bytes, image_name)
    if not result:
        logging.error(f"Upload alternative image failed for question {question_id}")
        return None
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        width, height = pil_img.width, pil_img.height
    except Exception:
        width, height = None, None
    return {
        'id': image_id,
        'type': mime,
        'width': width,
        'height': height,
        'minio_bucket': bucket_name,
        'minio_object_name': result['object_name'],
        'size': len(image_bytes),
    }


def _alternative_has_content(alt):
    """Alternativa válida se tiver texto ou imagem."""
    if not isinstance(alt, dict):
        return bool(alt)
    text = (alt.get('text') or alt.get('answer') or '').strip()
    if text:
        return True
    image = alt.get('image')
    if isinstance(image, str) and image.strip():
        return True
    if isinstance(image, dict):
        return bool(
            image.get('data') or image.get('base64') or image.get('id')
            or image.get('minio_object_name')
        )
    return False


def _validate_multiple_choice_options(options):
    if not options or not isinstance(options, list):
        return False, 'Multiple choice questions must have alternatives'
    for i, alt in enumerate(options):
        if not _alternative_has_content(alt):
            return False, f'Alternative at index {i} must have text or image'
    return True, None


def _process_alternatives_images(question_id, alternatives, existing_images=None):
    """Upload/processa imagens das alternativas. Retorna (alternatives, metadados)."""
    if not alternatives or not isinstance(alternatives, list):
        return alternatives, []

    existing_by_id = {}
    for img in (existing_images or []):
        if isinstance(img, dict) and img.get('id'):
            existing_by_id[str(img['id'])] = img

    processed = []
    images_meta = []
    for alt in alternatives:
        if not isinstance(alt, dict):
            processed.append(alt)
            continue
        new_alt = {k: v for k, v in alt.items() if k != 'image'}
        image_input = alt.get('image')
        if image_input is not None:
            meta = _upload_alternative_image(question_id, image_input, existing_by_id)
            if meta:
                new_alt['image'] = meta
                images_meta.append(meta)
                existing_by_id[str(meta['id'])] = meta
        processed.append(new_alt)
    return processed, images_meta


def _rebuild_question_images_catalog(
    question_id,
    formatted_text,
    formatted_solution,
    alternatives,
    existing_images=None,
    new_html_metas=None,
):
    """Monta question.images a partir de enunciado, solução e alternativas."""
    existing_by_id = {}
    for img in (existing_images or []):
        if isinstance(img, dict) and img.get('id'):
            existing_by_id[str(img['id'])] = _sanitize_stored_image_meta(img) or img

    for m in (new_html_metas or []):
        if isinstance(m, dict) and m.get('id'):
            existing_by_id[str(m['id'])] = m

    all_ids = []
    for content in (formatted_text or '', formatted_solution or ''):
        for iid in re.findall(r'/questions/[^/]+/images/([a-f0-9-]{36})', content):
            if iid not in all_ids:
                all_ids.append(iid)

    if isinstance(alternatives, list):
        for alt in alternatives:
            if isinstance(alt, dict):
                img = alt.get('image')
                if isinstance(img, dict) and img.get('id'):
                    iid = str(img['id'])
                    if iid not in all_ids:
                        all_ids.append(iid)

    return [
        existing_by_id[iid]
        for iid in all_ids
        if iid in existing_by_id
    ]


def _apply_question_images_pipeline(question, alternatives_override=None):
    """
    Processa imagens do enunciado, solução e alternativas; atualiza question in-place.
    alternatives_override: lista já atribuída a question.alternatives (após setattr).
    """
    question_id = question.id
    alts = alternatives_override if alternatives_override is not None else question.alternatives

    new_ft = question.formatted_text
    new_fs = question.formatted_solution
    html_metas = []
    if question.formatted_text:
        new_ft, meta_text = _upload_html_base64_images_to_minio(question_id, question.formatted_text)
        html_metas.extend(meta_text)
    if question.formatted_solution:
        new_fs, meta_solution = _upload_html_base64_images_to_minio(question_id, question.formatted_solution)
        html_metas.extend(meta_solution)

    processed_alts, alt_metas = _process_alternatives_images(
        question_id, alts, existing_images=question.images
    )

    for m in alt_metas:
        if m.get('id') and str(m['id']) not in {str(x.get('id')) for x in html_metas if isinstance(x, dict)}:
            html_metas.append(m)

    existing_images = question.images or []
    for m in alt_metas + html_metas:
        if isinstance(m, dict) and m.get('id'):
            existing_images = [
                img for img in existing_images
                if not (isinstance(img, dict) and str(img.get('id')) == str(m['id']))
            ]
            existing_images.append(m)

    images_list = _rebuild_question_images_catalog(
        question_id,
        new_ft,
        new_fs,
        processed_alts,
        existing_images=existing_images,
        new_html_metas=html_metas,
    )

    question.formatted_text = new_ft
    question.formatted_solution = new_fs
    question.alternatives = processed_alts
    question.images = images_list
    return question


def _collect_question_image_objects(question):
    """Coleta pares únicos (bucket, object_name) de question.images e alternatives[].image."""
    seen = set()
    objects = []

    def _add(bucket, object_name):
        if bucket and object_name:
            key = (bucket, object_name)
            if key not in seen:
                seen.add(key)
                objects.append(key)

    for img in (question.images or []):
        if isinstance(img, dict):
            _add(img.get('minio_bucket'), img.get('minio_object_name'))

    alts = question.alternatives or []
    if isinstance(alts, str):
        try:
            import json
            alts = json.loads(alts)
        except Exception:
            alts = []

    if isinstance(alts, list):
        for alt in alts:
            if isinstance(alt, dict):
                img = alt.get('image')
                if isinstance(img, dict):
                    _add(img.get('minio_bucket'), img.get('minio_object_name'))

    return objects


def _delete_question_images_from_minio(question):
    """
    Remove do MinIO todas as imagens da questão (enunciado, solução e alternativas).
    Usa metadados do banco e, como fallback, apaga tudo sob o prefixo {question_id}/.
    Falhas no MinIO são logadas mas não impedem a exclusão da questão.
    """
    question_id = str(question.id) if question.id else None
    if not question_id:
        return

    from app.services.storage.minio_service import MinIOService
    minio = MinIOService()
    bucket_name = MinIOService.BUCKETS['QUESTION_IMAGES']

    to_delete = set(_collect_question_image_objects(question))
    try:
        for object_name in minio.list_files(bucket_name, prefix=f"{question_id}/"):
            to_delete.add((bucket_name, object_name))
    except Exception as e:
        logging.warning(f"List MinIO files for question {question_id} failed: {e}")

    for bucket, object_name in to_delete:
        if not minio.delete_file(bucket, object_name):
            logging.warning(
                f"Could not delete MinIO object {bucket}/{object_name} for question {question_id}"
            )


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

        # Validações específicas por tipo de questão
        if data['type'] == 'multipleChoice':
            ok, err = _validate_multiple_choice_options(data.get('options'))
            if not ok:
                return jsonify({"error": err}), 400
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
            images=[],
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

        # MULTITENANT: questões em public.question (metadata ORM)
        db.session.add(question)
        db.session.commit()

        # Imagens: enunciado, solução e alternativas → MinIO + catálogo question.images
        _apply_question_images_pipeline(question)
        db.session.commit()

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
        from app.multitenant.physical_schema_binding import get_effective_tenant_physical_schema

        context = get_current_tenant_context()
        tenant_physical_schema = get_effective_tenant_physical_schema()
        
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
                "tenant_physical_schema": tenant_physical_schema,
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

        return jsonify([format_question_response(q) for q in questions]), 200

    except Exception as e:
        logging.error(f"Error listing questions: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing questions", "details": str(e)}), 500


@bp.route('/batch', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_questions_batch():
    """
    Retorna várias questões em uma única requisição.
    Query: ids=uuid1,uuid2,uuid3 (máx. 100 IDs).
    Evita ERR_EMPTY_RESPONSE ao carregar muitas questões em paralelo (ex.: detalhes de competição).
    """
    try:
        ids_param = request.args.get('ids', '')
        if not ids_param or not ids_param.strip():
            return jsonify({"error": "Parâmetro ids é obrigatório (ex.: ?ids=uuid1,uuid2)"}), 400
        raw_ids = [x.strip() for x in ids_param.split(',') if x.strip()]
        if len(raw_ids) > 100:
            return jsonify({"error": "Máximo de 100 questões por requisição"}), 400
        if not raw_ids:
            return jsonify([]), 200

        questions = (
            Question.query.options(
                joinedload(Question.subject),
                joinedload(Question.grade),
                joinedload(Question.education_stage),
                joinedload(Question.creator),
                joinedload(Question.last_modifier),
            )
            .filter(Question.id.in_(raw_ids))
            .all()
        )
        # Manter ordem dos IDs solicitados
        by_id = {str(q.id): q for q in questions}
        ordered = [format_question_response(by_id[qid]) for qid in raw_ids if qid in by_id]
        return jsonify(ordered), 200
    except Exception as e:
        logging.error(f"Error in get_questions_batch: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar questões em lote", "details": str(e)}), 500


@bp.route('/<string:question_id>/images/<string:image_id>', methods=['GET'])
def get_question_image(question_id, image_id):
    """
    Serve imagem de questão a partir do MinIO.
    Não expõe URLs do MinIO; retorna o binário com Content-Type correto.
    """
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({"error": "Question not found"}), 404
        images = question.images or []
        image_meta = next((img for img in images if isinstance(img, dict) and img.get("id") == image_id), None)
        if not image_meta:
            return jsonify({"error": "Image not found"}), 404
        bucket = image_meta.get("minio_bucket")
        object_name = image_meta.get("minio_object_name")
        if not bucket or not object_name:
            return jsonify({"error": "Image not stored in MinIO"}), 404
        from app.services.storage.minio_service import MinIOService
        minio = MinIOService()
        data = minio.download_file(bucket_name=bucket, object_name=object_name)
        content_type = image_meta.get("type") or "application/octet-stream"
        return send_file(BytesIO(data), mimetype=content_type, as_attachment=False)
    except Exception as e:
        logging.error(f"Error serving question image: {str(e)}", exc_info=True)
        return jsonify({"error": "Error loading image", "details": str(e)}), 500


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
        logging.error(f"Error getting question {question_id}: {str(e)}", exc_info=True)
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

        if question.question_type == 'multipleChoice' and 'options' in data:
            ok, err = _validate_multiple_choice_options(data.get('options'))
            if not ok:
                return jsonify({"error": err}), 400

        # Imagens: enunciado, solução e/ou alternativas
        if any(k in data for k in ('formattedText', 'formattedSolution', 'options')):
            _apply_question_images_pipeline(question)

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
                from app.evaluations.tasks import (
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
            _delete_question_images_from_minio(question)
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

        _delete_question_images_from_minio(question)
        db.session.delete(question)
        db.session.commit()
        return jsonify({'message': 'Question deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting question: {str(e)}", exc_info=True)
        return jsonify({"error": "Error deleting question", "details": str(e)}), 500