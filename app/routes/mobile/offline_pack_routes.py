from flask import jsonify, request, g

from app import db
from app.decorators.tenant_required import get_current_tenant_context, requires_city_context
from app.models.mobile_models import MobileOfflinePackCode
from app.models.mobile_offline_pack_registry import MobileOfflinePackRegistry
from app.permissions import get_current_user_from_token, role_required
from app.routes.mobile.blueprint import mobile_bp
from app.services.mobile.device_service import is_valid_uuid_v4
from app.services.mobile import offline_pack_service as pack_svc


def _sanitize_scope(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("scope deve ser um objeto")
    return {k: v for k, v in raw.items() if not str(k).startswith("_")}


@mobile_bp.route("/offline-pack/register", methods=["POST", "OPTIONS"])
def offline_pack_register():
    # OPTIONS (CORS preflight) costuma ir sem JWT / sem X-City-ID quando Host é localhost;
    # não passar por requires_city_context nem role_required.
    if request.method == "OPTIONS":
        return "", 200
    return _offline_pack_register_post()


@requires_city_context
@role_required("admin", "tecadm", "diretor", "coordenador")
def _offline_pack_register_post():
    user = get_current_user_from_token()
    if not user:
        return jsonify({"error": "não autenticado"}), 401

    ctx = get_current_tenant_context()
    if not ctx or not getattr(ctx, "city_id", None):
        return jsonify({"error": "contexto de município obrigatório"}), 403

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
        # Antes do commit: materializar atributos (expire_on_commit + pool pode
        # recarregar o ORM com search_path sem o tenant → UndefinedTable).
        response_pack_id = str(row.id)
        response_expires_at = row.expires_at.isoformat() + "Z"
        response_max_redemptions = int(row.max_redemptions)
        response_scope = pack_svc.user_scope_persisted(row)
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
            }
        ),
        200,
    )


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

    h = pack_svc.hash_code(normalized)
    reg = MobileOfflinePackRegistry.query.filter_by(code_hash=h).first()

    if reg:
        hdr_city = request.headers.get("X-City-ID")
        if hdr_city and str(hdr_city) != str(reg.city_id):
            return jsonify({"error": "X-City-ID não corresponde ao código"}), 400
        try:
            pack_svc.bind_tenant_context_for_redeem(str(reg.city_id))
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        pack = MobileOfflinePackCode.query.get(reg.pack_id)
        if not pack or pack.code_hash != h:
            return jsonify({"error": "código não encontrado"}), 404
    else:
        # Códigos gerados antes do índice public: exige o mesmo critério de cidade do login mobile.
        try:
            from app.utils.tenant_middleware import (
                _resolve_mobile_login_tenant_context,
                set_search_path,
            )

            legacy_ctx = _resolve_mobile_login_tenant_context()
            g.tenant_context = legacy_ctx
            set_search_path(legacy_ctx.schema)
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        if not legacy_ctx.has_tenant_context or not legacy_ctx.city_id:
            return jsonify(
                {
                    "error": (
                        "código não encontrado no índice global; para códigos antigos informe "
                        "X-City-ID, X-City-Slug ou use o subdomínio do município"
                    )
                }
            ), 404
        hdr_city = request.headers.get("X-City-ID")
        if hdr_city and str(hdr_city) != str(legacy_ctx.city_id):
            return jsonify({"error": "X-City-ID não corresponde ao contexto"}), 400
        try:
            pack = pack_svc.find_pack_by_code_normalized(normalized)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

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
