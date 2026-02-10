from flask import Blueprint, request, jsonify
from app.permissions.decorators import role_required, get_current_user_from_token
from app.permissions.rules import get_user_permission_scope
from app import db
from app.models import CalendarEvent, CalendarEventUser, City, School, Grade, Class
from app.services.calendar_event_service import CalendarEventService
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from datetime import datetime
from typing import List, Dict, Any


bp = Blueprint('calendar', __name__, url_prefix='/calendar')


def to_fullcalendar_event(e: CalendarEvent, user_rec: CalendarEventUser = None) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "start": e.start_at.isoformat() if e.start_at else None,
        "end": e.end_at.isoformat() if e.end_at else None,
        "allDay": bool(e.all_day),
        "timezone": e.timezone,
        "extendedProps": {
            "description": e.description,
            "location": e.location,
            "recurrence_rule": e.recurrence_rule,
            "read": bool(user_rec.read_at) if user_rec else False,
            "eventId": e.id,
            "metadata": e.metadata_json or {},
        }
    }


@bp.route('/events', methods=['POST'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
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

    event = CalendarEventService.create_event(data, user)
    return jsonify({"event": to_fullcalendar_event(event)}), 201


@bp.route('/events', methods=['GET'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def list_events():
    # Listagem administrativa (filtros opcionais)
    q = CalendarEvent.query
    start = request.args.get('start')
    end = request.args.get('end')
    if start:
        try:
            start_dt = datetime.fromisoformat(start)
            q = q.filter(CalendarEvent.start_at >= start_dt)
        except Exception:
            pass
    if end:
        try:
            end_dt = datetime.fromisoformat(end)
            q = q.filter(CalendarEvent.start_at <= end_dt)
        except Exception:
            pass

    events = q.order_by(CalendarEvent.start_at.desc()).all()
    return jsonify({"events": [to_fullcalendar_event(e) for e in events]}), 200


@bp.route('/events/<string:event_id>', methods=['GET'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_event(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    return jsonify({"event": to_fullcalendar_event(e)}), 200


@bp.route('/events/<string:event_id>', methods=['PUT'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def update_event(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    data = request.get_json() or {}
    e = CalendarEventService.update_event(e, data)
    return jsonify({"event": to_fullcalendar_event(e)}), 200


@bp.route('/events/<string:event_id>', methods=['DELETE'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def delete_event(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    db.session.delete(e)
    db.session.commit()
    return jsonify({"success": True}), 200


@bp.route('/events/<string:event_id>/publish', methods=['POST'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def publish_event(event_id: str):
    e = CalendarEvent.query.get(event_id)
    if not e:
        return jsonify({"error": "Evento não encontrado"}), 404
    e = CalendarEventService.publish_event(e)
    return jsonify({"event": to_fullcalendar_event(e)}), 200


@bp.route('/events/<string:event_id>/recipients', methods=['GET'])
@role_required("admin", "coordenador", "diretor", "tecadm")
def list_recipients(event_id: str):
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
def mark_read(event_id: str):
    user = get_current_user_from_token()
    CalendarEventService.mark_read(event_id, user['id'])
    return jsonify({"success": True}), 200


@bp.route('/events/<string:event_id>/dismiss', methods=['POST'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def mark_dismiss(event_id: str):
    user = get_current_user_from_token()
    CalendarEventService.mark_dismiss(event_id, user['id'])
    return jsonify({"success": True}), 200


@bp.route('/targets/me', methods=['GET'])
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_meus_targets():
    """
    Retorna os targets disponíveis para o usuário logado baseado no seu role.
    
    - Admin: retorna municípios, escolas e turmas (todas)
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

        # Admin: retorna municípios, escolas e turmas
        if user_role == 'admin':
            response['municipios'] = _obter_todos_municipios()
            response['escolas'] = _obter_todas_escolas()
            response['turmas'] = _obter_todas_turmas_formatadas()
        
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


def _obter_todas_escolas() -> List[Dict[str, Any]]:
    """Retorna todas as escolas com relacionamento ao município."""
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


def _obter_todas_turmas_formatadas() -> List[Dict[str, Any]]:
    """Retorna todas as turmas formatadas como 'Série - Turma'."""
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
    turmas = Class.query.join(School, Class.school_id == cast(School.id, PostgresUUID))\
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


