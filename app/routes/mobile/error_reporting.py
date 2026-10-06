# -*- coding: utf-8 -*-
"""Log + alerta Telegram para respostas de erro das rotas /mobile/v1."""
import logging
import traceback
from typing import Any, Dict, List, Optional

from flask import g, request
from flask_jwt_extended import get_jwt_identity

from app.routes.mobile.blueprint import mobile_bp
from app.utils.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)

_SKIP_ENDPOINTS = frozenset({"mobile_api.mobile_report_error"})
_NOISY_STATUSES = frozenset({401, 404})
_COOLDOWN_5XX = 60
_COOLDOWN_4XX = 300
_COOLDOWN_NOISY = 900
_COOLDOWN_UPLOAD = 120
_MAX_SUBMISSION_LINES = 30


def remember_exception() -> None:
    """Guarda o traceback da exceção atual para o alerta da resposta de erro."""
    g.mobile_error_trace = traceback.format_exc()


def _current_user_id() -> Optional[str]:
    try:
        uid = get_jwt_identity()
        return str(uid) if uid is not None else None
    except Exception:
        return None


def _request_json() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _summarize_body(data: Dict[str, Any]) -> str:
    parts = []
    for i, (key, value) in enumerate(data.items()):
        if i >= 12:
            parts.append("...")
            break
        if key in ("password", "senha", "token", "code"):
            parts.append(f"{key}=***")
        elif isinstance(value, list):
            parts.append(f"{key}=list[{len(value)}]")
        elif isinstance(value, dict):
            parts.append(f"{key}=obj[{len(value)}]")
        else:
            parts.append(f"{key}={str(value)[:80]}")
    return ", ".join(parts)


def _client_info(data: Dict[str, Any]) -> Dict[str, str]:
    info: Dict[str, str] = {}
    device_id = request.headers.get("X-Device-Id")
    if device_id:
        info["device_id"] = device_id
    app_version = request.headers.get("X-App-Version")
    if app_version:
        info["app_version"] = app_version[:40]
    platform = request.headers.get("X-Platform")
    if platform:
        info["platform"] = platform[:80]
    if not app_version:
        info["user_agent"] = request.headers.get("User-Agent", "N/A")[:200]
    city_id = request.headers.get("X-City-ID")
    if city_id:
        info["city_id"] = city_id
    school_id = request.args.get("school_id") or data.get("school_id")
    if school_id:
        info["school_id"] = str(school_id)
    info["ip"] = request.headers.get("X-Forwarded-For", request.remote_addr or "N/A")
    return info


def _response_error_message(response) -> str:
    if response.direct_passthrough:
        return f"HTTP {response.status_code}"
    body = response.get_json(silent=True)
    if isinstance(body, dict):
        for key in ("error", "erro", "message", "msg"):
            if body.get(key):
                return str(body[key])
    text = response.get_data(as_text=True) or ""
    return text[:500] or f"HTTP {response.status_code}"


@mobile_bp.after_request
def _alert_on_mobile_error_response(response):
    try:
        status = response.status_code
        if (
            status < 400
            or request.method == "OPTIONS"
            or request.endpoint in _SKIP_ENDPOINTS
            or g.get("telegram_alert_sent")
        ):
            return response

        data = _request_json()
        message = _response_error_message(response)
        user_id = _current_user_id()
        info = _client_info(data)
        info["status"] = str(status)
        info["severity"] = "error" if status >= 500 else "warning"
        query = request.query_string.decode("utf-8", "replace")
        if query:
            info["query"] = query[:300]
        if data:
            info["body"] = _summarize_body(data)

        log = logger.error if status >= 500 else logger.warning
        log(
            "[mobile/v1] %s %s -> %s user_id=%s device_id=%s message=%s",
            request.method,
            request.path,
            status,
            user_id,
            info.get("device_id"),
            message[:300],
        )

        if status >= 500:
            cooldown = _COOLDOWN_5XX
        elif status in _NOISY_STATUSES:
            cooldown = _COOLDOWN_NOISY
        else:
            cooldown = _COOLDOWN_4XX
        client_key = info.get("device_id") or info["ip"]

        send_telegram_alert(
            error_message=message,
            route=request.path,
            method=request.method,
            user_id=user_id,
            stack_trace=g.get("mobile_error_trace"),
            additional_info=info,
            source="Mobile API",
            rate_limit_key=f"mobile_http_{status}_{request.endpoint}_{client_key}_{message[:60]}",
            cooldown=cooldown,
            background=True,
            title=f"HTTP {status}",
        )
    except Exception:
        logger.warning("Falha ao reportar erro mobile", exc_info=True)
    return response


SYNC_UPLOAD_FIELDS = ("student_id", "test_id", "sync_bundle_version", "test_content_version")


def report_submission_errors(
    *,
    errors: List[Dict[str, Any]],
    submissions: List[Any],
    applied: int,
    user_id: str,
    device_id: str,
    school_id: Optional[str] = None,
    id_key: str = "submission_id",
    fields: tuple = SYNC_UPLOAD_FIELDS,
) -> None:
    """Alerta único por lote com os itens que falharam (resposta continua 200)."""
    by_id = {str(s.get(id_key)): s for s in submissions if isinstance(s, dict)}
    lines = []
    traces = []
    codes = set()
    for r in errors:
        sub_id = str(r.get(id_key))
        src = by_id.get(sub_id, {})
        code = r.get("code") or "-"
        codes.add(code if code != "-" else str(r.get("message"))[:40])
        context = " ".join(f"{f}={src.get(f)}" for f in fields)
        line = f"[{code}] {id_key}={sub_id} {context} :: {r.get('message')}"
        if r.get("_detail"):
            line += f" ({r['_detail']})"
        lines.append(line)
        if r.get("_trace") and len(traces) < 2:
            traces.append(f"{id_key} {sub_id}:\n{r['_trace']}")

    for line in lines:
        logger.warning("[mobile/v1] %s erro %s", request.path, line)

    shown = lines[:_MAX_SUBMISSION_LINES]
    if len(lines) > len(shown):
        shown.append(f"... mais {len(lines) - len(shown)} erro(s)")

    info = _client_info({"school_id": school_id} if school_id else {})
    info["severity"] = "error"
    info["applied"] = str(applied)
    info["errors"] = str(len(errors))
    info["total"] = str(applied + len(errors))

    send_telegram_alert(
        error_message="\n".join(shown),
        route=request.path,
        method=request.method,
        user_id=user_id,
        stack_trace="\n\n".join(traces) or None,
        additional_info=info,
        source="Mobile API",
        rate_limit_key=(
            f"mobile_batch_{request.endpoint}_{device_id}_{'|'.join(sorted(codes))[:200]}"
        ),
        cooldown=_COOLDOWN_UPLOAD,
        background=True,
        title=f"LOTE COM {len(errors)} ERRO(S)",
    )


def strip_internal_fields(results: List[Dict[str, Any]]) -> None:
    for r in results:
        r.pop("_trace", None)
        r.pop("_detail", None)
