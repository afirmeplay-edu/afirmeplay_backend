from flask import Blueprint, request, jsonify
from app.permissions.decorators import role_required, get_current_user_from_token
from app import db
from app.models import CalendarEvent, CalendarEventUser
from app.services.calendar_event_service import CalendarEventService
from datetime import datetime


bp = Blueprint('calendar', __name__, url_prefix='/calendar')


def to_fullcalendar_event(e: CalendarEvent, user_rec: CalendarEventUser = None) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "start": e.start_at.isoformat() if e.start_at else None,
        "end": e.end_at.isoformat() if e.end_at else None,
        "allDay": bool(e.all_day),
        "extendedProps": {
            "description": e.description,
            "location": e.location,
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


