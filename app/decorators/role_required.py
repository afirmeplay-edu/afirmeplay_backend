from functools import wraps
from flask import request, jsonify
import jwt
from app.models.usuario import Usuario
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

def get_current_user_from_cookie():
    token = request.cookies.get('access_token')
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        print(payload)
        return Usuario.query.get(payload['id'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user_from_cookie()
            if not user or user.role.value not in roles:
                return jsonify({"erro": "Acesso negado."}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator