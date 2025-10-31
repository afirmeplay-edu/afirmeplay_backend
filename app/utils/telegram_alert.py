"""
Sistema de alertas via Telegram para erros críticos da aplicação.
Envia notificações para um grupo do Telegram quando erros ocorrem.
"""

import os
import logging
import traceback
from datetime import datetime
from functools import wraps
from time import time
from typing import Optional, Dict
import requests
from flask import request, current_app

# Cache simples para rate limiting (última vez que foi enviado alerta por rota)
_last_alert_time: Dict[str, float] = {}
_ALERT_COOLDOWN = 60  # Segundos entre alertas da mesma rota


def send_telegram_alert(
    error_message: str,
    route: Optional[str] = None,
    method: Optional[str] = None,
    user_id: Optional[str] = None,
    stack_trace: Optional[str] = None,
    additional_info: Optional[Dict] = None
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
    
    Returns:
        True se o alerta foi enviado com sucesso, False caso contrário
    """
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
    
    # Rate limiting: verificar se já foi enviado alerta para esta rota recentemente
    route_key = f"{method}_{route}" if route else "unknown"
    current_time = time()
    
    if route_key in _last_alert_time:
        time_since_last = current_time - _last_alert_time[route_key]
        if time_since_last < _ALERT_COOLDOWN:
            logging.debug(f"Alerta Telegram suprimido por rate limit: {route_key}")
            return False
    
    # Construir mensagem formatada
    # Usar emoji diferente baseado no tipo de erro
    error_lower = error_message.lower()
    if ("não encontrado" in error_lower or "not found" in error_lower or "404" in error_message):
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
    else:
        emoji = "🚨"  # Emoji padrão para erro crítico (500)
        error_type = "ERRO CRÍTICO"
    
    # Montar mensagem principal
    message_parts = [
        f"{emoji} *ALERTA - Backend* ({error_type})",
        f"",
        f"*⏰ Timestamp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
    ]
    
    # Adicionar informações da rota
    if method and route:
        message_parts.append(f"*📍 Rota:* `{method} {route}`")
    elif route:
        message_parts.append(f"*📍 Rota:* `{route}`")
    
    # Adicionar informações do usuário
    if user_id:
        message_parts.append(f"*👤 Usuário:* `{user_id}`")
    
    # Adicionar mensagem de erro
    message_parts.append(f"")
    message_parts.append(f"*❌ Erro:*")
    message_parts.append(f"```")
    message_parts.append(error_message[:1000])  # Limitar tamanho
    message_parts.append(f"```")
    
    # Adicionar stack trace (truncado)
    if stack_trace:
        # Limitar stack trace a 2000 caracteres
        truncated_trace = stack_trace[:2000]
        if len(stack_trace) > 2000:
            truncated_trace += "\n... (truncado)"
        message_parts.append(f"")
        message_parts.append(f"*📋 Stack Trace:*")
        message_parts.append(f"```")
        message_parts.append(truncated_trace)
        message_parts.append(f"```")
    
    # Adicionar informações adicionais
    if additional_info:
        message_parts.append(f"")
        message_parts.append(f"*ℹ️ Informações Adicionais:*")
        for key, value in additional_info.items():
            # Limitar valor para evitar mensagens muito longas
            value_str = str(value)
            if len(value_str) > 500:
                value_str = value_str[:500] + "... (truncado)"
            message_parts.append(f"• *{key}:* `{value_str}`")
    
    # Juntar todas as partes
    full_message = "\n".join(message_parts)
    
    # URL da API do Telegram
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Payload da requisição
    payload = {
        "chat_id": group_id,
        "text": full_message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        logging.debug(f"Enviando alerta Telegram para rota: {route_key}, URL: {url[:50]}...")
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        
        # Atualizar cache de rate limiting
        _last_alert_time[route_key] = current_time
        
        logging.info(f"✅ Alerta Telegram enviado com sucesso para rota: {route_key}")
        return True
        
    except requests.exceptions.RequestException as e:
        # Não usar logging.error aqui para evitar loop infinito
        # Se o Telegram falhar, apenas registrar warning
        logging.warning(f"❌ Falha ao enviar alerta Telegram: {str(e)} | Status: {response.status_code if 'response' in locals() else 'N/A'} | Resposta: {response.text[:200] if 'response' in locals() else 'N/A'}")
        return False
    except Exception as e:
        logging.warning(f"❌ Erro inesperado ao enviar alerta Telegram: {str(e)}", exc_info=True)
        return False


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
