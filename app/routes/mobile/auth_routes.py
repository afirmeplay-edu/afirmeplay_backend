from datetime import timedelta

from flask import request, jsonify, g
from flask_jwt_extended import create_access_token

from app import db
from app.models.user import User, RoleEnum
from app.utils.auth import authenticate_usuario
from app.routes.mobile.blueprint import mobile_bp
from app.services.mobile.device_service import register_or_touch_device, is_valid_uuid_v4

_MOBILE_LOGIN_ROLES = frozenset(
    {
        RoleEnum.ADMIN,
        RoleEnum.COORDENADOR,
        RoleEnum.DIRETOR,
        RoleEnum.TECADM,
    }
)


@mobile_bp.route("/auth/login", methods=["POST", "OPTIONS"])
def mobile_auth_login():
    if request.method == "OPTIONS":
        return "", 200

    device_id = request.headers.get("X-Device-Id")
    if not device_id or not is_valid_uuid_v4(device_id):
        print(
            "[mobile/v1/auth/login] 400 — X-Device-Id inválido ou ausente: "
            f"{device_id!r} (uuid v4 válido? {is_valid_uuid_v4(device_id) if device_id else False})"
        )
        return jsonify({"error": "X-Device-Id obrigatório (UUID v4)"}), 400

    data = request.get_json(silent=True) or {}
    ident = data.get("registration") or data.get("email")
    password = data.get("password")
    if not ident or not password:
        print(
            "[mobile/v1/auth/login] 400 — corpo JSON: "
            f"keys={list(data.keys())} tem_ident={bool(ident)} tem_password={bool(password)}"
        )
        return jsonify({"error": "registration/email e password obrigatórios"}), 400

    usuario = User.query.filter_by(registration=ident).first()
    if not usuario:
        usuario = User.query.filter_by(email=ident).first()

    if not usuario or not authenticate_usuario(usuario, password):
        print(f"[mobile/v1/auth/login] 401 — credenciais inválidas para ident={ident!r}")
        return jsonify({"error": "Credenciais inválidas"}), 401

    if usuario.role not in _MOBILE_LOGIN_ROLES:
        print(
            f"[mobile/v1/auth/login] 403 — role não permitido: {usuario.role!r} user_id={usuario.id}"
        )
        return jsonify({"error": "Perfil não autorizado para API mobile"}), 403

    ctx = getattr(g, "tenant_context", None)
    token_city_id = None
    if ctx and getattr(ctx, "city_id", None):
        token_city_id = str(ctx.city_id)
    elif usuario.city_id:
        token_city_id = str(usuario.city_id)

    token = create_access_token(
        identity=str(usuario.id),
        additional_claims={
            "role": usuario.role.value,
            "city_id": token_city_id,
        },
        expires_delta=timedelta(hours=8),
    )

    try:
        register_or_touch_device(str(usuario.id), device_id)
        db.session.commit()
    except PermissionError as e:
        db.session.rollback()
        print(f"[mobile/v1/auth/login] 403 — device: {e}")
        return jsonify({"error": str(e)}), 403
    except Exception:
        db.session.rollback()
        raise

    print(
        f"[mobile/v1/auth/login] 200 — user_id={usuario.id} role={usuario.role.value} "
        f"city_id={token_city_id}"
    )
    return jsonify(
        {
            "token": token,
            "user": {
                "id": usuario.id,
                "name": usuario.name,
                "email": usuario.email,
                "registration": usuario.registration,
                "role": usuario.role.value,
                "city_id": token_city_id,
            },
        }
    ), 200
