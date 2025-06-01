from flask_jwt_extended import get_jwt_identity, create_access_token
from werkzeug.security import check_password_hash
from app.models.user import User
# from flask import jsonify
from flask import request
import jwt
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

def authenticate_usuario(usuario, senha):
    return check_password_hash(usuario.password_hash, senha)
        


def get_current_tenant_id():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ')[1]
    try:
        decode = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return decode['tenant_id']
    except:
        return None