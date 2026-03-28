from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models.user import User, RoleEnum
from app.models.school import School
from app.routes.mobile.blueprint import mobile_bp
from app.services.mobile.device_service import is_valid_uuid_v4, register_or_touch_device
from app.services.mobile.bundle_service import build_bundle_response
from app.services.mobile.upload_service import process_batch

_ALLOWED = frozenset(
    {
        RoleEnum.ADMIN,
        RoleEnum.COORDENADOR,
        RoleEnum.DIRETOR,
        RoleEnum.TECADM,
    }
)


def _require_device_header():
    device_id = request.headers.get("X-Device-Id")
    if not device_id or not is_valid_uuid_v4(device_id):
        return None, (jsonify({"error": "X-Device-Id obrigatório (UUID v4)"}), 400)
    return device_id, None


def _require_allowed_user():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    if not user or user.role not in _ALLOWED:
        return None, (jsonify({"error": "Operação não autorizada"}), 403)
    return user, None


@mobile_bp.before_request
def _mobile_skip_jwt_device_for_options():
    if request.method == "OPTIONS":
        return None


@mobile_bp.route("/sync/bundle", methods=["GET", "OPTIONS"])
@jwt_required(optional=True)
def mobile_sync_bundle():
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    school_id = request.args.get("school_id")
    if not school_id:
        return jsonify({"error": "school_id obrigatório"}), 400

    raw_since = request.args.get("since_bundle_version")
    since_val = None
    if raw_since is not None and raw_since != "":
        try:
            since_val = int(raw_since)
        except ValueError:
            return jsonify({"error": "since_bundle_version inválido"}), 400

    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 50))
    except ValueError:
        return jsonify({"error": "page ou page_size inválidos"}), 400

    if page < 1 or page_size < 1 or page_size > 200:
        return jsonify({"error": "page >= 1 e 1 <= page_size <= 200"}), 400

    refresh = request.args.get("refresh", "").lower() in ("1", "true", "yes")

    if not School.query.get(school_id):
        return jsonify({"error": "escola não encontrada"}), 404

    try:
        register_or_touch_device(str(user.id), device_id)
        payload = build_bundle_response(
            school_id, since_val, page, page_size, refresh
        )
        db.session.commit()
        return jsonify(payload), 200
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@mobile_bp.route("/sync/upload", methods=["POST", "OPTIONS"])
@jwt_required(optional=True)
def mobile_sync_upload():
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    school_id = body.get("school_id")
    submissions = body.get("submissions")
    if not school_id:
        return jsonify({"error": "school_id obrigatório"}), 400
    if not isinstance(submissions, list):
        return jsonify({"error": "submissions deve ser uma lista"}), 400

    if not School.query.get(school_id):
        return jsonify({"error": "escola não encontrada"}), 404

    hdr_dev = request.headers.get("X-Device-Id")
    for item in submissions:
        item.setdefault("device_id", hdr_dev)
        if item.get("device_id") != hdr_dev:
            return jsonify({"error": "device_id no corpo deve coincidir com X-Device-Id"}), 400

    try:
        results = process_batch(submissions, str(user.id), school_id)
        register_or_touch_device(str(user.id), device_id)
        db.session.commit()
        return jsonify({"results": results}), 200
    except PermissionError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
