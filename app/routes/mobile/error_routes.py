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
_MAX_BATCH = 50
_HTTP_KEYS = ("method", "url", "status", "duration_ms", "attempt", "response_body")


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


def _sanitize_http(http) -> dict:
    if not isinstance(http, dict):
        return {}
    return {
        k: _truncate(http[k], 500 if k == "response_body" else 300)
        for k in _HTTP_KEYS
        if http.get(k) is not None
    }


def _optional(data: dict, key: str, max_len: int):
    value = data.get(key)
    return _truncate(value, max_len) if value else None


def _process_report(data, user, device_id, *, background: bool) -> dict:
    if not isinstance(data, dict):
        return {"status": "rejected", "error": "item deve ser um objeto"}

    message = data.get("message")
    if not message or not str(message).strip():
        return {"status": "rejected", "error": "message é obrigatório"}

    severity_raw = str(data.get("severity") or "error").strip().lower()
    if severity_raw not in _ALLOWED_SEVERITIES:
        return {"status": "rejected", "error": "severity deve ser fatal, error ou warning"}

    message = _truncate(message, _MAX_MESSAGE)
    stack_trace = data.get("stack_trace")
    stack_trace = _truncate(stack_trace, _MAX_STACK) if stack_trace else None
    screen = _optional(data, "screen", 120)
    app_version = _optional(data, "app_version", 40) or _optional(
        request.headers, "X-App-Version", 40
    )
    os_info = _optional(data, "os", 80) or _optional(request.headers, "X-Platform", 80)
    category = _optional(data, "category", 40)
    error_name = _optional(data, "error_name", 120)
    occurred_at = _optional(data, "occurred_at", 40)
    client_error_id = _optional(data, "client_error_id", 64)
    http = _sanitize_http(data.get("http"))
    extra = _sanitize_extra(data.get("extra"))

    logger.warning(
        "[mobile/v1/errors] severity=%s category=%s user_id=%s device_id=%s screen=%s "
        "occurred_at=%s http=%s message=%s",
        severity_raw,
        category,
        user.id,
        device_id,
        screen,
        occurred_at,
        http or None,
        message[:200],
    )
    if stack_trace:
        logger.warning("[mobile/v1/errors] stack_trace device_id=%s:\n%s", device_id, stack_trace)

    telegram_sent = False
    if severity_raw in _TELEGRAM_SEVERITIES:
        additional_info = {"severity": severity_raw, "device_id": device_id}
        optional_fields = (
            ("category", category),
            ("error_name", error_name),
            ("occurred_at", occurred_at),
            ("screen", screen),
            ("app_version", app_version),
            ("os", os_info),
            ("client_error_id", client_error_id),
        )
        for key, value in optional_fields:
            if value:
                additional_info[key] = value
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        additional_info["role"] = role
        for k, v in http.items():
            additional_info[f"http.{k}"] = v
        for k, v in extra.items():
            additional_info[f"extra.{k}"] = v

        fingerprint = message[:80].replace("\n", " ")
        rate_key = f"mobile_{device_id}_{severity_raw}_{category}_{fingerprint}"

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
                background=background,
                title=f"{severity_raw.upper()} {category}" if category else None,
            )
        )

    result = {"status": "accepted", "severity": severity_raw, "telegram_sent": telegram_sent}
    if client_error_id:
        result["client_error_id"] = client_error_id
    return result


@mobile_bp.route("/errors", methods=["POST", "OPTIONS"])
@jwt_required(optional=True)
def mobile_report_error():
    """
    Recebe erros do cliente mobile e encaminha para Telegram (fatal/error).

    Body JSON (um erro):
      message (obrigatório), stack_trace, severity (fatal|error|warning),
      category, error_name, occurred_at, client_error_id,
      screen, app_version, os, http (object), extra (object)

    Body JSON (lote, fila offline):
      {"errors": [<erro>, ...]}  (máx. 50)
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

    if "errors" in data:
        items = data.get("errors")
        if not isinstance(items, list) or not items:
            return jsonify({"error": "errors deve ser uma lista não vazia"}), 400
        if len(items) > _MAX_BATCH:
            return jsonify({"error": f"máximo de {_MAX_BATCH} erros por lote"}), 400
        results = [
            _process_report(item, user, device_id, background=True) for item in items
        ]
        return jsonify({"status": "accepted", "results": results}), 202

    result = _process_report(data, user, device_id, background=False)
    if result["status"] == "rejected":
        return jsonify({"error": result["error"]}), 400
    return jsonify(result), 202
