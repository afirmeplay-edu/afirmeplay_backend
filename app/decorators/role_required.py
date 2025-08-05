from functools import wraps
from flask import request, jsonify
import jwt
from app.models.user import User
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

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
            
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "city_id": user.city_id  # Adicionando city_id
        }
    
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user_from_token()
            if not user or user['role'] not in roles:
                return jsonify({"erro": "Acesso negado."}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator