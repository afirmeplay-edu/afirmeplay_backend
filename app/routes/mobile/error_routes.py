# -*- coding: utf-8 -*-
"""Reporte de erros do app mobile → Telegram."""
import logging
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models.user import User, RoleEnum
from app.routes.mobile.blueprint import mobile_bp
from app.services.mobile.device_service import is_valid_uuid_v4
from app.utils.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)

_ALLOWED = frozenset(
    {
        RoleEnum.ADMIN,
        RoleEnum.COORDENADOR,
        RoleEnum.DIRETOR,
        RoleEnum.TECADM,
        RoleEnum.APLICADOR,
        RoleEnum.PROFESSOR,
    }
)

_TELEGRAM_SEVERITIES = frozenset({"fatal", "error"})
_ALLOWED_SEVERITIES = frozenset({"fatal", "error", "warning"})
_MAX_MESSAGE = 2000
_MAX_STACK = 4000
_MAX_EXTRA_KEYS = 20
_MAX_EXTRA_VALUE = 300


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


def _truncate(value, max_len: int) -> str:
    text = str(value) if value is not None else ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "... (truncado)"


def _sanitize_extra(extra) -> dict:
    if not isinstance(extra, dict):
        return {}
    out = {}
    for i, (key, value) in enumerate(extra.items()):
        if i >= _MAX_EXTRA_KEYS:
            break
        out[str(key)[:80]] = _truncate(value, _MAX_EXTRA_VALUE)
    return out


@mobile_bp.route("/errors", methods=["POST", "OPTIONS"])
@jwt_required(optional=True)
def mobile_report_error():
    """
    Recebe erros do cliente mobile e encaminha para Telegram (fatal/error).

    Body JSON:
      message (obrigatório), stack_trace, severity (fatal|error|warning),
      screen, app_version, os, extra (object)
    """
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

    data = request.get_json(silent=True) or {}
    message = data.get("message")
    if not message or not str(message).strip():
        return jsonify({"error": "message é obrigatório"}), 400

    severity_raw = str(data.get("severity") or "error").strip().lower()
    if severity_raw not in _ALLOWED_SEVERITIES:
        return jsonify({"error": "severity deve ser fatal, error ou warning"}), 400

    message = _truncate(message, _MAX_MESSAGE)
    stack_trace = data.get("stack_trace")
    stack_trace = _truncate(stack_trace, _MAX_STACK) if stack_trace else None
    screen = _truncate(data.get("screen"), 120) if data.get("screen") else None
    app_version = _truncate(data.get("app_version"), 40) if data.get("app_version") else None
    os_info = _truncate(data.get("os"), 80) if data.get("os") else None
    extra = _sanitize_extra(data.get("extra"))

    logger.warning(
        "[mobile/v1/errors] severity=%s user_id=%s device_id=%s screen=%s message=%s",
        severity_raw,
        user.id,
        device_id,
        screen,
        message[:200],
    )

    telegram_sent = False
    if severity_raw in _TELEGRAM_SEVERITIES:
        additional_info = {
            "severity": severity_raw,
            "device_id": device_id,
        }
        if screen:
            additional_info["screen"] = screen
        if app_version:
            additional_info["app_version"] = app_version
        if os_info:
            additional_info["os"] = os_info
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        additional_info["role"] = role
        for k, v in extra.items():
            additional_info[f"extra.{k}"] = v

        fingerprint = message[:80].replace("\n", " ")
        rate_key = f"mobile_{device_id}_{severity_raw}_{fingerprint}"

        telegram_sent = bool(
            send_telegram_alert(
                error_message=message,
                route=screen or "mobile/client",
                method="CLIENT",
                user_id=str(user.id),
                stack_trace=stack_trace,
                additional_info=additional_info,
                source="Mobile",
                rate_limit_key=rate_key,
            )
        )

    return (
        jsonify(
            {
                "status": "accepted",
                "severity": severity_raw,
                "telegram_sent": telegram_sent,
            }
        ),
        202,
    )
