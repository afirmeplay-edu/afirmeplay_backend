"""
⚠️ ESTE ARQUIVO FOI SUBSTITUÍDO ⚠️

Este arquivo foi mantido para compatibilidade com imports existentes,
mas foi SUBSTITUÍDO por app/permissions/decorators.py

Por favor, atualize seus imports:
    ANTES: from app.decorators.role_required import role_required
    DEPOIS: from app.permissions import role_required
    
OU:
    from app.permissions.decorators import role_required, get_current_user_from_token

Data de migração: 2025-01-XX
"""

from functools import wraps
from flask import request, jsonify
import jwt
from app.models.user import User
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

_APLICADOR_AUTO_BLOCKLIST = frozenset({"create_user", "delete_user"})
_MUNICIPAL_STAFF_FOR_APLICADOR = frozenset(
    {"professor", "coordenador", "diretor", "tecadm"}
)


def _expand_roles_for_aplicador(base_roles, view_func):
    roles = list(base_roles)
    norm = {str(r).lower().strip() for r in base_roles}
    if "aplicador" in norm:
        return roles
    if not (norm & _MUNICIPAL_STAFF_FOR_APLICADOR):
        return roles
    if view_func and view_func.__name__ in _APLICADOR_AUTO_BLOCKLIST:
        return roles
    roles.append("aplicador")
    return roles

# ⚠️ Esta função foi movida para app/permissions/decorators.py
def get_current_user_from_token():
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
            "tenant_id": payload.get('tenant_id')  # Usar tenant_id do token JWT
        }
        
        return user_data
    
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# ⚠️ Esta função foi movida para app/permissions/decorators.py
def get_current_tenant_id():
    """Função auxiliar para obter o tenant_id do token atual"""
    user = get_current_user_from_token()
    return user.get('tenant_id') if user else None

# ⚠️ Este decorador foi movido e melhorado em app/permissions/decorators.py
# Use: from app.permissions import role_required
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user_from_token()
            if not user:
                return jsonify({
                    "erro": "Acesso negado.",
                    "mensagem": "Token inválido, expirado ou não informado. Envie o header Authorization: Bearer <token>."
                }), 403
            effective_roles = _expand_roles_for_aplicador(roles, f)
            if user["role"] not in effective_roles:
                return jsonify({
                    "erro": "Acesso negado.",
                    "mensagem": f"Sua função ({user['role']}) não tem permissão para esta rota. Permitidas: {', '.join(effective_roles)}."
                }), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator