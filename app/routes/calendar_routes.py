from flask import Blueprint, request, jsonify
from app.permissions.decorators import role_required, get_current_user_from_token
from app.permissions.rules import get_user_permission_scope
from app.decorators import requires_city_context
from app import db
from app.models import CalendarEvent, CalendarEventUser, CalendarEventResource, City, School, Grade, Class, User
from app.services.calendar_event_service import CalendarEventService
from sqlalchemy import cast, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import urlparse
from datetime import timedelta
from app.services.storage.minio_service import MinIOService
from app.utils.tenant_middleware import get_current_tenant_context
import os
import uuid
from werkzeug.utils import secure_filename


bp = Blueprint('calendar', __name__, url_prefix='/calendar')
_MAX_RESOURCE_UPLOAD_BYTES = int(os.getenv('CALENDAR_MAX_UPLOAD_MB', '50')) * 1024 * 1024


def _created_by_payload(e: CalendarEvent) -> dict:
    u = User.query.get(e.created_by_user_id) if e.created_by_user_id else None
    return {
        "id": e.created_by_user_id,
        "role": e.created_by_role,
        "name": u.name if u else None,
    }


def _is_event_creator(e: CalendarEvent, user_id: str) -> bool:
    return bool(e and e.created_by_user_id and str(e.created_by_user_id) == str(user_id))


def _can_access_event_content(e: CalendarEvent, user_id: str) -> bool:
    """Criador ou destinatário materializado pode ver o evento (detalhe / download)."""
    if _is_event_creator(e, user_id):
        return True
    return CalendarEventUser.query.filter_by(event_id=e.id, user_id=user_id).first() is not None


def to_fullcalendar_event(e: CalendarEvent, user_rec: CalendarEventUser = None) -> dict:
    resources = []
    for r in sorted(getattr(e, 'resources', []), key=lambda x: (x.sort_order or 0, x.id or "")):
        item = {
            "id": r.id,
            "type": r.resource_type,
            "title": r.title,
            "sort_order": r.sort_order or 0,
        }
        if r.resource_type == "link":
            item["url"] = r.url
        elif r.resource_type == "file":
            item["file_name"] = r.original_filename
            item["mime_type"] = r.content_type
            item["size_bytes"] = r.size_bytes
        resources.append(item)

    return {
        "id": e.id,
        "title": e.title,
        "start": e.start_at.isoformat() if e.start_at else None,
        "end": e.end_at.isoformat() if e.end_at else None,
        "allDay": bool(e.all_day),
        "timezone": e.timezone,
        "created_by": _created_by_payload(e),
        "extendedProps": {
            "description": e.description,
            "location": e.location,
            "recurrence_rule": e.recurrence_rule,
            "read": bool(user_rec.read_at) if user_rec else False,
            "eventId": e.id,
            "metadata": e.metadata_json or {},
            "resources": resources,
        }
    }


def _parse_link_resources(raw):
    if raw is None:
        return None, None
    if not isinstance(raw, list):
        return None, (jsonify({"error": "resources deve ser uma lista"}), 400)
    out = []
    for idx, res in enumerate(raw):
        if not isinstance(res, dict):
            return None, (jsonify({"error": f"Item {idx} de resources inválido"}), 400)
        if res.get("type") != "link":
            return None, (jsonify({"error": f"resources[{idx}] deve ser type='link'"}), 400)
        title = (res.get("title") or "").strip()
        if not title:
            return None, (jsonify({"error": f"title obrigatório em resources[{idx}]"}), 400)
        url = (res.get("url") or "").strip()
        if not url:
            return None, (jsonify({"error": f"url obrigatório em resources[{idx}]"}), 400)
        parsed = urlparse(url)
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            return None, (jsonify({"error": f"URL inválida em resources[{idx}]"}), 400)
        sort_order = res.get("sort_order", idx)
        try:
            sort_order = int(sort_order)
        except (TypeError, ValueError):
            sort_order = idx
        rid = res.get("id")
        if rid is not None:
            rid = str(rid).strip() or None
        out.append({"id": rid, "title": title, "url": url, "sort_order": sort_order})
    return out, None


def _sync_link_resources_for_event(event_id: str, items: List[Dict[str, Any]]) -> None:
    existing_links = CalendarEventResource.query.filter_by(event_id=event_id, resource_type="link").all()
    by_id = {r.id: r for r in existing_links}
    incoming_ids = set()

    for idx, item in enumerate(items):
        rid = item.get("id")
        if rid:
            row = by_id.get(rid)
            if not row:
                raise ValueError(f"Recurso link id={rid} não encontrado neste evento")
            incoming_ids.add(rid)
            row.title = item["title"]
            row.url = item["url"]
            row.sort_order = item.get("sort_order", idx)
        else:
            db.session.add(CalendarEventResource(
                id=str(uuid.uuid4()),
                event_id=event_id,
                resource_type="link",
                title=item["title"],
                url=item["url"],
                sort_order=item.get("sort_order", idx),
            ))

    for row in existing_links:
        if row.id not in incoming_ids:
            db.session.delete(row)


@bp.route('/events', methods=['POST'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
@requires_city_context
def create_event():
    user = get_current_user_from_token()
    data = request.get_json() or {}

    # Validações simples
    if not data.get('title') or not data.get('start_at'):
        return jsonify({"error": "Campos obrigatórios: title, start_at"}), 400

    if data.get('end_at') and data['end_at'] < data['start_at']:
        return jsonify({"error": "end_at não pode ser anterior a start_at"}), 400

    # Validar permissões de targets
    targets = data.get('targets', [])
    if targets:
        is_valid, error_message = CalendarEventService.validate_targets_by_role(user, targets)
        if not is_valid:
            return jsonify({"error": error_message}), 403

    resources_plan, res_err = _parse_link_resources(data.get("resources"))
    if res_err:
        return res_err

    event = CalendarEventService.create_event(data, user)
    if resources_plan is not None:
        _sync_link_resources_for_event(event.id, resources_plan)
        db.session.commit()
    return jsonify({"event": to_fullcalendar_event(event)}), 201


# GET /calendar/events — desativado: expunha todos os eventos do tenant a vários perfis.
# Usar GET /calendar/my-events. Reative apenas com escopo/papel explícitos no produto.
# @bp.route('/events', methods=['GET'])
# @role_required("admin", "professor", "coordenador", "diretor", "tecadm")
# @requires_city_context
# def list_events():
#     q = CalendarEvent.query
#     start = request.args.get('start')
#     end = request.args.get('end')
#     if start:
#         try:
#             start_dt = datetime.fromisoformat(start)
#             q = q.filter(CalendarEvent.start_at >= start_dt)
#         except Exception:
#             pass
#     if end:
#         try:
#             end_dt = datetime.fromisoformat(end)
#             q = q.filter(CalendarEvent.start_at <= end_dt)
#         except Exception:
#             pass
#     events = q.order_by(CalendarEvent.start_at.desc()).all()
#     return jsonify({"events": [to_fullcalendar_event(e) for e in events]}), 200


@bp.route('/events/<string:event_id>', methods=['GET'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
@requires_city_context
def get_event(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    user = get_current_user_from_token()
    if not _can_access_event_content(e, user['id']):
        return jsonify({"error": "Acesso negado a este evento"}), 403
    rec = CalendarEventUser.query.filter_by(event_id=e.id, user_id=user['id']).first()
    return jsonify({"event": to_fullcalendar_event(e, rec)}), 200


@bp.route('/events/<string:event_id>', methods=['PUT'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def update_event(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    user = get_current_user_from_token()
    if not _is_event_creator(e, user['id']):
        return jsonify({"error": "Somente quem criou o evento pode alterá-lo"}), 403
    data = request.get_json() or {}
    if 'targets' in data:
        is_valid, error_message = CalendarEventService.validate_targets_by_role(user, data.get('targets') or [])
        if not is_valid:
            return jsonify({"error": error_message}), 403

    if 'resources' in data:
        resources_plan, res_err = _parse_link_resources(data.get("resources"))
        if res_err:
            return res_err
    else:
        resources_plan = None

    e = CalendarEventService.update_event(e, data)
    if resources_plan is not None:
        try:
            _sync_link_resources_for_event(e.id, resources_plan)
            db.session.commit()
        except ValueError as ve:
            db.session.rollback()
            return jsonify({"error": str(ve)}), 400
    return jsonify({"event": to_fullcalendar_event(e)}), 200


@bp.route('/events/<string:event_id>', methods=['DELETE'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def delete_event(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    user = get_current_user_from_token()
    if not _is_event_creator(e, user['id']):
        return jsonify({"error": "Somente quem criou o evento pode excluí-lo"}), 403
    db.session.delete(e)
    db.session.commit()
    return jsonify({"success": True}), 200


@bp.route('/events/<string:event_id>/resources/file', methods=['POST'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
@requires_city_context
def upload_event_resource_file(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    user = get_current_user_from_token()
    if not _is_event_creator(e, user['id']):
        return jsonify({"error": "Somente quem criou o evento pode anexar arquivos"}), 403

    title = (request.form.get('title') or "").strip()
    if not title or len(title) > 200:
        return jsonify({"error": "title obrigatório (máx. 200 caracteres)"}), 400

    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({"error": "Arquivo file é obrigatório"}), 400

    upload.seek(0, os.SEEK_END)
    size = upload.tell()
    upload.seek(0)
    if size > _MAX_RESOURCE_UPLOAD_BYTES:
        return jsonify({"error": "Arquivo excede o tamanho máximo permitido"}), 400

    ctx = get_current_tenant_context()
    city_part = str(ctx.city_id).replace("-", "_") if ctx and ctx.city_id else "city"
    resource_id = str(uuid.uuid4())
    raw_name = secure_filename(upload.filename) or "upload"
    bucket = MinIOService.BUCKETS["USER_UPLOADS"]
    object_name = f"calendar/{city_part}/{event_id}/{resource_id}_{raw_name}"

    data = upload.read()
    minio = MinIOService()
    result = minio.upload_file(
        bucket_name=bucket,
        object_name=object_name,
        data=data,
        content_type=upload.content_type,
    )
    if not result:
        return jsonify({"error": "Falha ao enviar arquivo para o armazenamento"}), 500

    sort_order_raw = request.form.get("sort_order")
    try:
        sort_order = int(sort_order_raw) if sort_order_raw is not None else 0
    except (TypeError, ValueError):
        sort_order = 0

    res = CalendarEventResource(
        id=resource_id,
        event_id=event_id,
        resource_type="file",
        title=title,
        minio_bucket=result.get("bucket") or bucket,
        minio_object_name=result.get("object_name"),
        original_filename=upload.filename[:500],
        content_type=(upload.content_type or "application/octet-stream")[:200],
        size_bytes=size,
        sort_order=sort_order,
    )
    db.session.add(res)
    db.session.commit()

    return jsonify({
        "resource": {
            "id": res.id,
            "type": "file",
            "title": res.title,
            "file_name": res.original_filename,
            "mime_type": res.content_type,
            "size_bytes": res.size_bytes,
            "sort_order": res.sort_order,
        }
    }), 201


@bp.route('/events/<string:event_id>/resources/<string:resource_id>/download', methods=['GET'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
@requires_city_context
def download_event_resource(event_id: str, resource_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    user = get_current_user_from_token()
    if not _can_access_event_content(e, user['id']):
        return jsonify({"error": "Acesso negado a este recurso"}), 403

    res = CalendarEventResource.query.filter_by(id=resource_id, event_id=event_id).first()
    if not res or res.resource_type != "file":
        return jsonify({"error": "Recurso não encontrado"}), 404
    if not res.minio_object_name:
        return jsonify({"error": "Arquivo indisponível"}), 404

    minio = MinIOService()
    bucket = res.minio_bucket or minio.BUCKETS["USER_UPLOADS"]
    url = minio.get_presigned_url(bucket, res.minio_object_name, expires=timedelta(hours=1))
    return jsonify({
        "download_url": url,
        "expires_in_seconds": 3600,
        "file_name": res.original_filename,
    }), 200


@bp.route('/events/<string:event_id>/resources/<string:resource_id>', methods=['DELETE'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
@requires_city_context
def delete_event_resource(event_id: str, resource_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    user = get_current_user_from_token()
    if not _is_event_creator(e, user['id']):
        return jsonify({"error": "Somente quem criou o evento pode remover anexos"}), 403

    res = CalendarEventResource.query.filter_by(id=resource_id, event_id=event_id).first()
    if not res:
        return jsonify({"error": "Recurso não encontrado"}), 404

    if res.resource_type == "file" and res.minio_object_name:
        m = MinIOService()
        m.delete_file(res.minio_bucket or m.BUCKETS["USER_UPLOADS"], res.minio_object_name)

    db.session.delete(res)
    db.session.commit()
    return jsonify({"success": True}), 200


@bp.route('/events/<string:event_id>/publish', methods=['POST'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def publish_event(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    user = get_current_user_from_token()
    if not _is_event_creator(e, user['id']):
        return jsonify({"error": "Somente quem criou o evento pode publicá-lo"}), 403
    e = CalendarEventService.publish_event(e)
    return jsonify({"event": to_fullcalendar_event(e)}), 200


@bp.route('/events/<string:event_id>/recipients', methods=['GET'])
@role_required("admin", "coordenador", "diretor", "tecadm")
@requires_city_context
def list_recipients(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    user = get_current_user_from_token()
    if not _is_event_creator(e, user['id']):
        return jsonify({"error": "Somente quem criou o evento pode listar destinatários"}), 403

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    q = CalendarEventUser.query.filter_by(event_id=event_id)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    items = [{
        "user_id": r.user_id,
        "read_at": r.read_at.isoformat() if r.read_at else None,
        "dismissed_at": r.dismissed_at.isoformat() if r.dismissed_at else None,
        "school_id": r.school_id,
        "class_id": r.class_id,
        "role_snapshot": r.role_snapshot,
    } for r in pagination.items]
    return jsonify({
        "items": items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total
    }), 200


@bp.route('/my-events', methods=['GET'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
@requires_city_context
def my_events():
    user = get_current_user_from_token()
    start = request.args.get('start')
    end = request.args.get('end')
    if not start or not end:
        return jsonify({"error": "Parâmetros start e end são obrigatórios (ISO 8601)"}), 400
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except Exception:
        return jsonify({"error": "Datas inválidas. Use ISO 8601."}), 400

    events = CalendarEventService.list_my_events(user['id'], start_dt, end_dt)
    # Recuperar registros de recipient para flag read
    recs = {r.event_id: r for r in CalendarEventUser.query.filter(
        CalendarEventUser.user_id == user['id'],
        CalendarEventUser.event_id.in_([e.id for e in events])
    ).all()}
    result = [to_fullcalendar_event(e, recs.get(e.id)) for e in events]
    return jsonify(result), 200


@bp.route('/events/<string:event_id>/read', methods=['POST'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
@requires_city_context
def mark_read(event_id: str):
    user = get_current_user_from_token()
    CalendarEventService.mark_read(event_id, user['id'])
    return jsonify({"success": True}), 200


@bp.route('/events/<string:event_id>/dismiss', methods=['POST'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
@requires_city_context
def mark_dismiss(event_id: str):
    user = get_current_user_from_token()
    CalendarEventService.mark_dismiss(event_id, user['id'])
    return jsonify({"success": True}), 200


@bp.route('/targets/me', methods=['GET'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def obter_meus_targets():
    """
    Retorna os targets disponíveis para o usuário logado baseado no seu role.
    
    - Admin: retorna municípios (global), escolas e turmas do município atual (contexto)
    - Tecadm: retorna escolas e turmas do município
    - Diretor/Coordenador: retorna turmas da escola
    - Professor: retorna escolas vinculadas e turmas vinculadas
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        permissao = get_user_permission_scope(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao.get('error', 'Acesso negado')}), 403

        response = {}
        user_role = user.get('role', '').lower()

        # Admin: retorna municípios (global) e escolas/turmas do município atual (contexto)
        if user_role == 'admin':
            response['municipios'] = _obter_todos_municipios()
            response['escolas'] = _obter_todas_escolas_do_contexto()
            response['turmas'] = _obter_todas_turmas_do_contexto()
        
        # Tecadm: retorna escolas e turmas do município
        elif user_role == 'tecadm':
            city_id = user.get('city_id') or user.get('tenant_id')
            if city_id:
                response['escolas'] = _obter_escolas_por_municipio(city_id)
                response['turmas'] = _obter_turmas_por_municipio_formatadas(city_id)
        
        # Diretor/Coordenador: retorna turmas da escola
        elif user_role in ['diretor', 'coordenador']:
            from app.permissions.utils import get_manager_school
            school_id = get_manager_school(user['id'])
            if school_id:
                response['turmas'] = _obter_turmas_por_escola_formatadas(school_id)
        
        # Professor: retorna escolas vinculadas e turmas vinculadas
        elif user_role == 'professor':
            from app.permissions.utils import get_teacher_schools, get_teacher_classes
            school_ids = get_teacher_schools(user['id'])
            class_ids = get_teacher_classes(user['id'])
            
            if school_ids:
                response['escolas'] = _obter_escolas_por_ids(school_ids)
            if class_ids:
                response['turmas'] = _obter_turmas_por_ids_formatadas(class_ids)

        return jsonify(response), 200

    except Exception as e:
        import logging
        logging.error(f"Erro ao obter targets: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter targets", "details": str(e)}), 500


def _obter_todos_municipios() -> List[Dict[str, Any]]:
    """Retorna todos os municípios."""
    municipios = City.query.all()
    return [{"id": str(m.id), "nome": m.name, "target_type": "MUNICIPALITY"} for m in municipios]


def _obter_todas_escolas_do_contexto() -> List[Dict[str, Any]]:
    """Retorna todas as escolas do município atual (contexto) com relacionamento ao município."""
    escolas = School.query.all()
    result = []
    for escola in escolas:
        municipio = escola.city if escola.city else None
        result.append({
            "id": str(escola.id),
            "nome": escola.name,
            "target_type": "SCHOOL",
            "city_id": str(escola.city_id) if escola.city_id else None,
            "municipio_nome": municipio.name if municipio else None
        })
    return result


def _obter_todas_turmas_do_contexto() -> List[Dict[str, Any]]:
    """Retorna todas as turmas do município atual (contexto) formatadas como 'Série - Turma'."""
    turmas = Class.query.join(Grade, Class.grade_id == Grade.id).all()
    result = []
    for turma in turmas:
        serie_nome = turma.grade.name if turma.grade else "Sem série"
        turma_nome = turma.name or "Sem nome"
        nome_formatado = f"{serie_nome} - {turma_nome}"
        
        result.append({
            "id": str(turma.id),
            "nome": nome_formatado,
            "target_type": "CLASS",
            "serie_id": str(turma.grade_id) if turma.grade_id else None,
            "serie_nome": serie_nome,
            "escola_id": turma.school_id,
            "escola_nome": turma.school.name if turma.school else None
        })
    return result


def _obter_escolas_por_municipio(city_id: str) -> List[Dict[str, Any]]:
    """Retorna escolas de um município com relacionamento ao município."""
    escolas = School.query.filter_by(city_id=city_id).all()
    # Buscar o município uma vez para evitar queries repetidas
    municipio = City.query.get(city_id)
    municipio_nome = municipio.name if municipio else None
    
    result = []
    for escola in escolas:
        result.append({
            "id": str(escola.id),
            "nome": escola.name,
            "target_type": "SCHOOL",
            "city_id": str(city_id),
            "municipio_nome": municipio_nome
        })
    return result


def _obter_turmas_por_municipio_formatadas(city_id: str) -> List[Dict[str, Any]]:
    """Retorna turmas do município formatadas como 'Série - Turma'."""
    turmas = Class.query.join(School, School.id == cast(Class.school_id, String))\
                        .join(Grade, Class.grade_id == Grade.id)\
                        .filter(School.city_id == city_id).all()
    result = []
    for turma in turmas:
        serie_nome = turma.grade.name if turma.grade else "Sem série"
        turma_nome = turma.name or "Sem nome"
        nome_formatado = f"{serie_nome} - {turma_nome}"
        
        result.append({
            "id": str(turma.id),
            "nome": nome_formatado,
            "target_type": "CLASS",
            "serie_id": str(turma.grade_id) if turma.grade_id else None,
            "serie_nome": serie_nome,
            "escola_id": turma.school_id,
            "escola_nome": turma.school.name if turma.school else None
        })
    return result


def _obter_turmas_por_escola_formatadas(school_id: str) -> List[Dict[str, Any]]:
    """Retorna turmas da escola formatadas como 'Série - Turma'."""
    turmas = Class.query.join(Grade, Class.grade_id == Grade.id)\
                        .filter(Class.school_id == school_id).all()
    # Buscar a escola uma vez para evitar queries repetidas
    escola = School.query.get(school_id)
    escola_nome = escola.name if escola else None
    
    result = []
    for turma in turmas:
        serie_nome = turma.grade.name if turma.grade else "Sem série"
        turma_nome = turma.name or "Sem nome"
        nome_formatado = f"{serie_nome} - {turma_nome}"
        
        result.append({
            "id": str(turma.id),
            "nome": nome_formatado,
            "target_type": "CLASS",
            "serie_id": str(turma.grade_id) if turma.grade_id else None,
            "serie_nome": serie_nome,
            "escola_id": str(school_id),
            "escola_nome": escola_nome
        })
    return result


def _obter_escolas_por_ids(school_ids: List[str]) -> List[Dict[str, Any]]:
    """Retorna escolas por IDs com relacionamento ao município."""
    escolas = School.query.filter(School.id.in_(school_ids)).all()
    result = []
    for escola in escolas:
        municipio = escola.city if escola.city else None
        result.append({
            "id": str(escola.id),
            "nome": escola.name,
            "target_type": "SCHOOL",
            "city_id": str(escola.city_id) if escola.city_id else None,
            "municipio_nome": municipio.name if municipio else None
        })
    return result


def _obter_turmas_por_ids_formatadas(class_ids: List[str]) -> List[Dict[str, Any]]:
    """Retorna turmas por IDs formatadas como 'Série - Turma'."""
    turmas = Class.query.join(Grade, Class.grade_id == Grade.id)\
                        .filter(Class.id.in_(class_ids)).all()
    result = []
    for turma in turmas:
        serie_nome = turma.grade.name if turma.grade else "Sem série"
        turma_nome = turma.name or "Sem nome"
        nome_formatado = f"{serie_nome} - {turma_nome}"
        
        result.append({
            "id": str(turma.id),
            "nome": nome_formatado,
            "target_type": "CLASS",
            "serie_id": str(turma.grade_id) if turma.grade_id else None,
            "serie_nome": serie_nome,
            "escola_id": turma.school_id,
            "escola_nome": turma.school.name if turma.school else None
        })
    return result


