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
        
# A função get_current_tenant_id foi movida para app/decorators/role_required.py
# para evitar duplicação de código e manter consistência