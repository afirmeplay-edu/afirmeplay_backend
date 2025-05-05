from flask import Blueprint, request, jsonify, make_response
from app.utils.auth import authenticate_usuario
import datetime
import jwt
from app.models.usuario import Usuario

import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

bp = Blueprint('login', __name__, url_prefix='/login')

@bp.route('/', methods=['POST'])
def login():
    data = request.get_json()
    identificador = data.get('matricula')
    senha = data.get('senha')

    if not identificador or not senha:
        return jsonify({"erro": "Identificador (e-mail ou matrícula) e senha são obrigatórios."}), 400

    # tenta encontrar por matrícula (Aluno)
    usuario = Usuario.query.filter_by(matricula=identificador).first()
    
    if not usuario:
        usuario = Usuario.query.filter_by(email=identificador).first()

    if not usuario or not authenticate_usuario(usuario ,senha):
        return jsonify({"erro": "Credenciais inválidas."}), 401

    token_payload = {
        "id": usuario.id,
        "role": usuario.role.value,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }

    token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')
    
    usuario_data = {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "matricula": usuario.matricula,
        "role": usuario.role.value
    }

    response = make_response(jsonify({"mensagem": "Login bem-sucedido.", "usuario": usuario_data}))
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=False,
        samesite='Lax',
        max_age=3600
    )
    return response
  
