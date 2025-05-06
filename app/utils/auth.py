from flask_jwt_extended import get_jwt_identity, create_access_token
from werkzeug.security import check_password_hash
from app.models.usuario import Usuario
from app.decorators.role_required import get_current_user_from_cookie
# from flask import jsonify
from flask import request
import jwt
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

def authenticate_usuario(usuario, senha):
    #usuario = Usuario.query.filter_by(matricula=matricula).first()
    # if usuario and check_password_hash(usuario.senha, senha):
    #     token = create_access_token(identity={"id": usuario.id, "tenant_id": usuario.tenant_id})
    #     return {"token": token, "aluno":usuario}
    return check_password_hash(usuario.senha_hash, senha)
        


def get_current_tenant_id():
    token = request.cookies.get('access_token')
    decode = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    return decode['tenant_id']
    # identity = get_jwt_identity()
    # return identity.get("tenant_id")