# -*- coding: utf-8 -*-
"""
Autenticação JWT para eventos WebSocket.
"""
from flask import request
import jwt
import os
import logging

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def get_user_from_token(token: str) -> dict:
    """
    Valida token JWT e retorna dados do usuário.
    Retorna dict com user_id, role, etc. ou None se inválido.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        # Retornar payload completo (contém sub, role, tenant_id, etc.)
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token JWT expirado")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token JWT inválido: {e}")
        return None
    except Exception as e:
        logger.warning(f"Erro ao decodificar token JWT: {e}")
        return None


def get_token_from_request() -> str:
    """
    Extrai token JWT do request (query string ou headers).
    """
    # Tentar query string primeiro (comum em WebSocket)
    token = request.args.get('token')
    if token:
        return token
    
    # Tentar header Authorization
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]
    
    return None
