"""
Decoradores de Permissões
==========================

Autor: Sistema de Refatoração de Permissões
Data de criação: 2025-01-XX

Descrição:
    Este módulo contém decoradores para controle de acesso baseado em roles.

⚠️ MOVER DE:
    - app/decorators/role_required.py (código antigo será comentado)
    - Função role_required foi centralizada aqui
"""

from functools import wraps
from flask import request, jsonify
import jwt
from app.models.user import User
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def get_current_user_from_token():
    """
    Extrai e valida o usuário atual do token JWT.
    
    ⚠️ MOVER DE: app/decorators/role_required.py
    
    Returns:
        Dict com informações do usuário ou None se token inválido
        {
            'id': str,
            'email': str,
            'role': str,
            'city_id': str,
            'tenant_id': str
        }
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user = User.query.get(payload['sub'])
        if not user:
            return None
        
        user_data = {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "city_id": user.city_id,
            "tenant_id": payload.get('tenant_id')
        }
        
        return user_data
    
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_tenant_id():
    """
    Função auxiliar para obter o tenant_id do token atual.
    
    ⚠️ MOVER DE: app/decorators/role_required.py
    
    Returns:
        str: tenant_id ou None
    """
    user = get_current_user_from_token()
    return user.get('tenant_id') if user else None


def role_required(*roles):
    """
    Decorador para exigir que o usuário tenha um dos roles especificados.
    
    ⚠️ MOVER DE: app/decorators/role_required.py
    
    Uso:
        @app.route('/admin')
        @role_required('admin', 'tecadm')
        def admin_route():
            return "Acesso permitido"
    
    Args:
        *roles: Roles aceitos para acessar a rota
        
    Returns:
        Decorated function com verificação de role
        
    Raises:
        403: Se usuário não autenticado ou role incorreto
    """
    from .roles import Roles
    
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user_from_token()
            
            if not user:
                return jsonify({"erro": "Acesso negado. Usuário não autenticado."}), 403
            
            # Normalizar role do usuário
            user_role = Roles.normalize(user.get('role', ''))
            
            # Normalizar roles aceitos
            normalized_roles = [Roles.normalize(role) for role in roles]
            
            # Verificar se o role do usuário está entre os aceitos
            if user_role not in normalized_roles:
                return jsonify({
                    "erro": "Acesso negado. Permissões insuficientes.",
                    "role_required": normalized_roles,
                    "user_role": user_role
                }), 403
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


__all__ = [
    'get_current_user_from_token',
    'get_current_tenant_id',
    'role_required'
]
