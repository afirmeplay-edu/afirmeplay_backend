from flask import jsonify, request, g

from app import db
from app.decorators.tenant_required import get_current_tenant_context, requires_city_context
from app.models.mobile_models import MobileOfflinePackCode
from app.permissions import get_current_user_from_token, role_required
from app.routes.mobile.blueprint import mobile_bp
from app.services.mobile.device_service import is_valid_uuid_v4
from app.services.mobile import offline_pack_service as pack_svc


def _sanitize_scope(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("scope deve ser um objeto")
    return {k: v for k, v in raw.items() if not str(k).startswith("_")}


def _web_pack_auth():
    """Decoradores comuns para rotas do painel web (register, list, get, patch)."""
    user = get_current_user_from_token()
    if not user:
        return None, (jsonify({"error": "não autenticado"}), 401)

    ctx = get_current_tenant_context()
    if not ctx or not getattr(ctx, "city_id", None):
        return None, (jsonify({"error": "contexto de município obrigatório"}), 403)

    return (user, ctx), None


@mobile_bp.route("/offline-pack/register", methods=["POST", "OPTIONS"])
def offline_pack_register():
    if request.method == "OPTIONS":
        return "", 200
    return _offline_pack_register_post()


@requires_city_context
@role_required("admin", "tecadm", "diretor", "coordenador", "aplicador")
def _offline_pack_register_post():
    auth, err = _web_pack_auth()
    if err:
        return err
    user, ctx = auth

    body = request.get_json(silent=True) or {}
    try:
        scope = _sanitize_scope(body.get("scope") or {})
        ttl_hours = int(body.get("ttl_hours", 48))
        max_redemptions = int(body.get("max_redemptions", 50))
    except (TypeError, ValueError) as e:
        return jsonify({"error": f"corpo inválido: {e}"}), 400

    try:
        code_str, row = pack_svc.register_offline_pack(
            city_id=str(ctx.city_id),
            created_by_user_id=user["id"],
            scope=scope,
            ttl_hours=ttl_hours,
            max_redemptions=max_redemptions,
        )
        response_pack_id = str(row.id)
        response_expires_at = row.expires_at.isoformat() + "Z"
        response_max_redemptions = int(row.max_redemptions)
        response_scope = pack_svc.user_scope_persisted(row)
        qr_payload = pack_svc.offline_pack_qrcode_api_dict(row)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify(
            {
                "code": code_str,
                "offline_pack_id": response_pack_id,
                "expires_at": response_expires_at,
                "max_redemptions": response_max_redemptions,
                "scope": response_scope,
                "qr_code_png_base64": qr_payload["qr_code_png_base64"],
                "qr_code_data_url": qr_payload["qr_code_data_url"],
            }
        ),
        200,
    )


@mobile_bp.route("/offline-pack", methods=["GET", "OPTIONS"])
def offline_pack_list():
    if request.method == "OPTIONS":
        return "", 200
    return _offline_pack_list_get()


@requires_city_context
@role_required("admin", "tecadm", "diretor", "coordenador", "aplicador")
def _offline_pack_list_get():
    auth, err = _web_pack_auth()
    if err:
        return err
    user, _ = auth

    include_expired = request.args.get("include_expired", "").lower() in (
        "1",
        "true",
        "yes",
    )
    try:
        rows = pack_svc.list_offline_packs(include_expired=include_expired)
        items = [pack_svc.pack_to_api_dict(r, user) for r in rows]
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"items": items, "total": len(items)}), 200


@mobile_bp.route("/offline-pack/bulk-delete", methods=["POST", "OPTIONS"])
def offline_pack_bulk_delete():
    if request.method == "OPTIONS":
        return "", 200
    return _offline_pack_bulk_delete_post()


@requires_city_context
@role_required("admin", "tecadm", "diretor", "coordenador", "aplicador")
def _offline_pack_bulk_delete_post():
    auth, err = _web_pack_auth()
    if err:
        return err
    user, _ = auth

    body = request.get_json(silent=True) or {}
    raw_ids = body.get("offline_pack_ids")
    if not isinstance(raw_ids, list):
        return jsonify({"error": "offline_pack_ids deve ser uma lista de UUIDs"}), 400

    try:
        result = pack_svc.delete_offline_packs_bulk(
            [str(x) for x in raw_ids], user
        )
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(result), 200


@mobile_bp.route("/offline-pack/<pack_id>/qrcode", methods=["GET", "OPTIONS"])
def offline_pack_qrcode(pack_id):
    if request.method == "OPTIONS":
        return "", 200
    return _offline_pack_qrcode_get(pack_id)


@requires_city_context
@role_required("admin", "tecadm", "diretor", "coordenador", "aplicador")
def _offline_pack_qrcode_get(pack_id):
    auth, err = _web_pack_auth()
    if err:
        return err

    pack = pack_svc.get_offline_pack_by_id(pack_id)
    if not pack:
        return jsonify({"error": "pacote não encontrado"}), 404

    try:
        payload = pack_svc.offline_pack_qrcode_api_dict(pack)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(payload), 200


@mobile_bp.route("/offline-pack/<pack_id>", methods=["GET", "PATCH", "DELETE", "OPTIONS"])
def offline_pack_detail(pack_id):
    if request.method == "OPTIONS":
        return "", 200
    if request.method == "GET":
        return _offline_pack_get_one(pack_id)
    if request.method == "DELETE":
        return _offline_pack_delete(pack_id)
    return _offline_pack_patch(pack_id)


@requires_city_context
@role_required("admin", "tecadm", "diretor", "coordenador", "aplicador")
def _offline_pack_get_one(pack_id):
    auth, err = _web_pack_auth()
    if err:
        return err
    user, _ = auth

    pack = pack_svc.get_offline_pack_by_id(pack_id)
    if not pack:
        return jsonify({"error": "pacote não encontrado"}), 404

    return jsonify(pack_svc.pack_to_api_dict(pack, user)), 200


@requires_city_context
@role_required("admin", "tecadm", "diretor", "coordenador", "aplicador")
def _offline_pack_patch(pack_id):
    auth, err = _web_pack_auth()
    if err:
        return err
    user, ctx = auth

    pack = pack_svc.get_offline_pack_by_id(pack_id)
    if not pack:
        return jsonify({"error": "pacote não encontrado"}), 404

    try:
        pack_svc.assert_can_manage_offline_pack(pack, user)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

    body = request.get_json(silent=True) or {}
    scope = None
    if "scope" in body:
        try:
            scope = _sanitize_scope(body.get("scope") or {})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    ttl_hours = None
    if "ttl_hours" in body:
        try:
            ttl_hours = int(body["ttl_hours"])
        except (TypeError, ValueError):
            return jsonify({"error": "ttl_hours inválido"}), 400

    max_redemptions = None
    if "max_redemptions" in body:
        try:
            max_redemptions = int(body["max_redemptions"])
        except (TypeError, ValueError):
            return jsonify({"error": "max_redemptions inválido"}), 400

    if scope is None and ttl_hours is None and max_redemptions is None:
        return jsonify({"error": "informe scope, ttl_hours e/ou max_redemptions"}), 400

    try:
        pack_svc.update_offline_pack(
            pack=pack,
            city_id=str(ctx.city_id),
            scope=scope,
            ttl_hours=ttl_hours,
            max_redemptions=max_redemptions,
        )
        payload = pack_svc.pack_to_api_dict(pack, user)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(payload), 200


@requires_city_context
@role_required("admin", "tecadm", "diretor", "coordenador", "aplicador")
def _offline_pack_delete(pack_id):
    auth, err = _web_pack_auth()
    if err:
        return err
    user, _ = auth

    pack = pack_svc.get_offline_pack_by_id(pack_id)
    if not pack:
        return jsonify({"error": "pacote não encontrado"}), 404

    try:
        pack_svc.assert_can_manage_offline_pack(pack, user)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

    deleted_id = str(pack.id)
    try:
        pack_svc.delete_offline_pack(pack)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"deleted": True, "offline_pack_id": deleted_id}), 200


@mobile_bp.route("/offline-pack/redeem", methods=["POST", "OPTIONS"])
def offline_pack_redeem():
    if request.method == "OPTIONS":
        return "", 200

    device_id = request.headers.get("X-Device-Id")
    if not device_id or not is_valid_uuid_v4(device_id):
        return jsonify({"error": "X-Device-Id obrigatório (UUID v4)"}), 400

    body = request.get_json(silent=True) or {}
    raw_code = body.get("code", "")
    try:
        normalized = pack_svc.normalize_mobile_input_code(raw_code)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    reg = pack_svc.find_registry_by_normalized(normalized)

    if reg:
        hdr_city = request.headers.get("X-City-ID")
        if hdr_city and str(hdr_city) != str(reg.city_id):
            return jsonify({"error": "X-City-ID não corresponde ao código"}), 400
        try:
            pack_svc.bind_tenant_context_for_redeem(str(reg.city_id))
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        pack = MobileOfflinePackCode.query.get(reg.pack_id)
        if not pack:
            return jsonify({"error": "código não encontrado"}), 404
    else:
        return (
            jsonify(
                {
                    "error": (
                        "código não encontrado: este pacote não está registado para resgate. "
                        "Confira o código ou peça um novo ao aplicador."
                    )
                }
            ),
            404,
        )

    try:
        page = int(body.get("page", 1))
        page_size = int(body.get("page_size", 50))
    except (TypeError, ValueError):
        return jsonify({"error": "page e page_size inválidos"}), 400

    pack_uuid = body.get("offline_pack_id")

    if pack_uuid and str(pack.id) != str(pack_uuid):
        return jsonify({"error": "offline_pack_id não corresponde ao código"}), 400

    ctx = getattr(g, "tenant_context", None)
    redeem_city_id = str(ctx.city_id) if ctx and ctx.city_id else None
    if not redeem_city_id:
        return jsonify({"error": "contexto de município ausente"}), 500

    try:
        payload = pack_svc.redeem_offline_pack_page(
            pack=pack,
            device_id=device_id,
            page=page,
            page_size=page_size,
            city_id=redeem_city_id,
        )
        db.session.commit()
    except PermissionError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(payload), 200
