from flask_jwt_extended import get_jwt_identity, create_access_token
from werkzeug.security import check_password_hash, generate_password_hash
from app import db
from app.models.user import User
# from flask import jsonify
from flask import request
import jwt
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

PASSWORD_HASH_METHOD = "pbkdf2:sha256:100000"


def needs_rehash(hash_value: str) -> bool:
    return isinstance(hash_value, str) and hash_value.startswith("scrypt")


def hash_password(plain: str) -> str:
    return generate_password_hash(plain, method=PASSWORD_HASH_METHOD)


def authenticate_usuario(usuario, senha):
    if not usuario or not usuario.password_hash:
        return False
    try:
        ok = check_password_hash(usuario.password_hash, senha)
    except Exception:
        return False
    if not ok:
        return False
    try:
        ph = usuario.password_hash
        if needs_rehash(ph):
            usuario.password_hash = hash_password(senha)
            db.session.add(usuario)
            db.session.commit()
            print(f"[MIGRATION] Usuário {usuario.id} migrado de scrypt para pbkdf2")
    except Exception:
        db.session.rollback()
    return True

# A função get_current_tenant_id foi movida para app/decorators/role_required.py
# para evitar duplicação de código e manter consistência
