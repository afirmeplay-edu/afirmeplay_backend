"""
Sistema de alertas via Telegram para erros críticos da aplicação.
Envia notificações para um grupo do Telegram quando erros ocorrem.
"""

import os
import html
import logging
import threading
import traceback
from datetime import datetime
from functools import wraps
from time import time
from typing import Optional, Dict, List
import requests
from flask import request, g, has_request_context

# Cache simples para rate limiting (última vez que foi enviado alerta por chave)
_last_alert_time: Dict[str, float] = {}
_rate_lock = threading.Lock()
_ALERT_COOLDOWN = 60  # Segundos entre alertas da mesma chave
_TELEGRAM_MAX_CHARS = 3900  # Limite da API é 4096 após parsing


def _esc(value) -> str:
    return html.escape(str(value), quote=False)


def _pre_section(title: str, raw: str, max_raw: int) -> str:
    text = raw if len(raw) <= max_raw else raw[:max_raw] + "\n... (truncado)"
    section = f"<b>{title}</b>\n<pre>{_esc(text)}</pre>"
    while len(section) > _TELEGRAM_MAX_CHARS and max_raw > 200:
        max_raw = int(max_raw * 0.7)
        text = raw[:max_raw] + "\n... (truncado)"
        section = f"<b>{title}</b>\n<pre>{_esc(text)}</pre>"
    return section


def _pack_chunks(sections: List[str]) -> List[str]:
    chunks: List[str] = []
    current = ""
    for section in sections:
        if len(section) > _TELEGRAM_MAX_CHARS:
            section = section[:_TELEGRAM_MAX_CHARS]
        candidate = f"{current}\n\n{section}" if current else section
        if len(candidate) > _TELEGRAM_MAX_CHARS:
            chunks.append(current)
            current = section
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _reserve_rate_slot(key: str, cooldown: int) -> bool:
    now = time()
    with _rate_lock:
        last = _last_alert_time.get(key)
        if last is not None and now - last < cooldown:
            return False
        _last_alert_time[key] = now
        if len(_last_alert_time) > 5000:
            cutoff = now - 3600
            for k in [k for k, t in _last_alert_time.items() if t < cutoff]:
                _last_alert_time.pop(k, None)
        return True


def _release_rate_slot(key: str) -> None:
    with _rate_lock:
        _last_alert_time.pop(key, None)


def _deliver(bot_token: str, group_id: str, chunks: List[str], route_key: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = None
    try:
        total = len(chunks)
        for i, chunk in enumerate(chunks, start=1):
            text = chunk if total == 1 else f"<i>({i}/{total})</i>\n{chunk}"
            response = requests.post(
                url,
                json={
                    "chat_id": group_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=5,
            )
            response.raise_for_status()
        logging.info(f"✅ Alerta Telegram enviado com sucesso para: {route_key}")
        return True
    except requests.exceptions.RequestException as e:
        # Não usar logging.error aqui para evitar loop infinito
        _release_rate_slot(route_key)
        logging.warning(
            f"❌ Falha ao enviar alerta Telegram: {e} | "
            f"Status: {response.status_code if response is not None else 'N/A'} | "
            f"Resposta: {response.text[:200] if response is not None else 'N/A'}"
        )
        return False
    except Exception as e:
        _release_rate_slot(route_key)
        logging.warning(f"❌ Erro inesperado ao enviar alerta Telegram: {e}", exc_info=True)
        return False


def send_telegram_alert(
    error_message: str,
    route: Optional[str] = None,
    method: Optional[str] = None,
    user_id: Optional[str] = None,
    stack_trace: Optional[str] = None,
    additional_info: Optional[Dict] = None,
    source: str = "Backend",
    rate_limit_key: Optional[str] = None,
    cooldown: Optional[int] = None,
    background: bool = False,
    title: Optional[str] = None,
) -> bool:
    """
    Envia um alerta para o grupo do Telegram configurado.
    
    Args:
        error_message: Mensagem principal do erro
        route: Rota onde o erro ocorreu
        method: Método HTTP (GET, POST, DELETE, etc.)
        user_id: ID do usuário que fez a requisição (se disponível)
        stack_trace: Stack trace do erro (truncado se muito longo)
        additional_info: Informações adicionais como dict
        source: Origem do alerta (ex.: Backend, Mobile) — aparece no título
        rate_limit_key: Chave customizada de cooldown; padrão method_route
        cooldown: Segundos de cooldown para a chave; padrão _ALERT_COOLDOWN
        background: Envia em thread separada (retorna True se foi agendado)
        title: Tipo do erro exibido no título; padrão inferido da mensagem
    
    Returns:
        True se o alerta foi enviado (ou agendado) com sucesso, False caso contrário
    """
    if has_request_context():
        g.telegram_alert_sent = True

    # Verificar se alertas estão habilitados
    alert_enabled = os.getenv('TELEGRAM_ALERT_ENABLED', 'false').lower() == 'true'
    logging.debug(f"Telegram alert enabled: {alert_enabled} (valor ENV: {os.getenv('TELEGRAM_ALERT_ENABLED')})")
    
    if not alert_enabled:
        logging.debug("Telegram alert desabilitado via TELEGRAM_ALERT_ENABLED")
        return False
    
    # Obter credenciais do Telegram
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    group_id = os.getenv('TELEGRAM_GROUP_ID')
    
    logging.debug(f"Verificando configuração Telegram - Bot Token presente: {bool(bot_token)}, Group ID presente: {bool(group_id)}")
    
    if not bot_token or not group_id:
        missing = []
        if not bot_token:
            missing.append('TELEGRAM_BOT_TOKEN')
        if not group_id:
            missing.append('TELEGRAM_GROUP_ID')
        logging.warning(f"Telegram alert não configurado: faltam {', '.join(missing)}")
        return False
    
    # Rate limiting: verificar se já foi enviado alerta para esta chave recentemente
    route_key = rate_limit_key or (f"{method}_{route}" if route else "unknown")
    if not _reserve_rate_slot(route_key, cooldown if cooldown is not None else _ALERT_COOLDOWN):
        logging.debug(f"Alerta Telegram suprimido por rate limit: {route_key}")
        return False
    
    # Construir mensagem formatada
    # Usar emoji diferente baseado no tipo de erro
    error_lower = error_message.lower()
    severity = (additional_info or {}).get("severity") if additional_info else None
    severity_norm = str(severity).lower() if severity else ""

    if severity_norm == "fatal":
        emoji = "🚨"
        error_type = "FATAL"
    elif severity_norm == "warning":
        emoji = "⚠️"
        error_type = "WARNING"
    elif severity_norm == "error":
        emoji = "📱" if source.lower() == "mobile" else "🚨"
        error_type = "ERROR"
    elif ("não encontrado" in error_lower or "not found" in error_lower or "404" in error_message):
        emoji = "⚠️"  # Emoji para avisos (404)
        error_type = "AVISO"
    elif ("unauthorized" in error_lower or "401" in error_message):
        emoji = "🔒"  # Emoji para não autorizado (401)
        error_type = "NÃO AUTORIZADO"
    elif ("forbidden" in error_lower or "403" in error_message):
        emoji = "🚫"  # Emoji para proibido (403)
        error_type = "PROIBIDO"
    elif ("bad request" in error_lower or "400" in error_message):
        emoji = "❌"  # Emoji para bad request (400)
        error_type = "BAD REQUEST"
    elif ("gateway timeout" in error_lower or "504" in error_message):
        emoji = "⏱️"  # Emoji para timeout (504)
        error_type = "GATEWAY TIMEOUT"
    else:
        emoji = "🚨"  # Emoji padrão para erro crítico (500)
        error_type = "ERRO CRÍTICO"
    if title:
        error_type = title
    
    source_label = source.strip() or "Backend"
    header_lines = [
        f"{emoji} <b>ALERTA - {_esc(source_label)}</b> ({_esc(error_type)})",
        "",
        f"<b>⏰ Timestamp:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if method and route:
        header_lines.append(f"<b>📍 Rota:</b> <code>{_esc(method)} {_esc(route)}</code>")
    elif route:
        header_lines.append(f"<b>📍 Rota:</b> <code>{_esc(route)}</code>")
    if user_id:
        header_lines.append(f"<b>👤 Usuário:</b> <code>{_esc(user_id)}</code>")

    sections = ["\n".join(header_lines)]
    sections.append(_pre_section("❌ Erro:", str(error_message), 1500))
    if stack_trace:
        sections.append(_pre_section("📋 Stack Trace:", str(stack_trace), 3000))
    if additional_info:
        info_section = "<b>ℹ️ Informações Adicionais:</b>"
        for key, value in additional_info.items():
            value_str = str(value)
            if len(value_str) > 1500:
                value_str = value_str[:1500] + "... (truncado)"
            line = f"• <b>{_esc(key)}:</b> <code>{_esc(value_str)}</code>"
            if len(info_section) + len(line) + 1 > _TELEGRAM_MAX_CHARS:
                sections.append(info_section)
                info_section = line
            else:
                info_section = f"{info_section}\n{line}"
        sections.append(info_section)

    chunks = _pack_chunks(sections)

    if background:
        threading.Thread(
            target=_deliver,
            args=(bot_token, group_id, chunks, route_key),
            daemon=True,
        ).start()
        return True
    return _deliver(bot_token, group_id, chunks, route_key)


def alert_on_error(func):
    """
    Decorator para enviar alerta Telegram automaticamente quando uma função/rota gera erro.
    
    Uso:
        @alert_on_error
        @bp.route('/example', methods=['DELETE'])
        def delete_example():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Obter informações do contexto
            route = request.path if request else None
            method = request.method if request else None
            
            # Tentar obter user_id do token JWT (se disponível)
            user_id = None
            try:
                if request and hasattr(request, 'current_user'):
                    user_id = getattr(request.current_user, 'id', None)
            except:
                pass
            
            # Obter stack trace
            stack_trace = traceback.format_exc()
            
            # Informações adicionais
            additional_info = {}
            if request:
                additional_info['URL Completa'] = request.url
                additional_info['IP'] = request.remote_addr
                if request.is_json:
                    try:
                        json_data = request.get_json()
                        if json_data:
                            # Limitar dados JSON para evitar mensagens muito longas
                            json_str = str(json_data)[:300]
                            additional_info['Body JSON'] = json_str
                    except:
                        pass
            
            # Enviar alerta
            send_telegram_alert(
                error_message=str(e),
                route=route,
                method=method,
                user_id=user_id,
                stack_trace=stack_trace,
                additional_info=additional_info if additional_info else None
            )
            
            # Re-raise a exceção para que o error handler padrão trate
            raise
    
    return wrapper
