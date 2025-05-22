from flask import Blueprint, request, jsonify, make_response
from app.utils.auth import authenticate_usuario
import datetime
import jwt
from app.models.user import User, RoleEnum
from app.models.school import School  # certifique-se que essa importação está correta
import logging
import os


SECRET_KEY = os.getenv("JWT_SECRET_KEY")

bp = Blueprint('login', __name__, url_prefix='/login')

@bp.route('/', methods=['POST'])
def login():
    data = request.get_json()
    identificador = data.get('registration')
    password = data.get('password')
    print(identificador, password)
    if not identificador or not password:
        return jsonify({"erro": "Identificador (e-mail ou matrícula) e senha são obrigatórios."}), 400

    try:
    # tenta encontrar o usuário
        usuario = User.query.filter_by(registration=identificador).first()
        if not usuario:
            usuario = User.query.filter_by(email=identificador).first()

        if not usuario or not authenticate_usuario(usuario, password):
            logging.warning(f"Falha de login para o usuário: {identificador}")
            return jsonify({"erro": "Credenciais inválidas."}), 401

        # Define o tenant_id com base na escola vinculada ao usuário
        token_payload = {
            "sub": usuario.id,
            "city_id": None,
            "role": usuario.role.value,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        if usuario.role == RoleEnum('aluno'):
            if not usuario.escola_id:
                logging.error(f"Usuário {usuario.id} ({usuario.role}) sem escola_id vinculado.")
                return jsonify({"erro": "Aluno não vinculado a uma escola ou município."}), 400
            token_payload["city_id"] = usuario.escola_id
        elif usuario.role == RoleEnum('admin'):
            token_payload["city_id"] = None
        else:
            if not usuario.city_id and usuario.role != RoleEnum('admin'):
                logging.error(f"Usuário {usuario.id} ({usuario.role}) sem city_id vinculado.")
                return jsonify({"erro": f"{usuario.role} não vinculado a um município."}), 400
            token_payload["city_id"] = usuario.city_id

        token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')

        usuario_data = {
            "id": usuario.id,
            "name": usuario.name,
            "email": usuario.email,
            "registration": usuario.registration,
            "tenant_id": token_payload["city_id"],
            "role": usuario.role.value
        }

        response = make_response(jsonify({"mensagem": "Login bem-sucedido.", "usuario": usuario_data}))
        response.set_cookie(
            "access_token",
            token,
            httponly=True,
            secure=False,
            samesite='None',
            max_age=3600
        )
        logging.info(f"Login bem-sucedido para usuário: {usuario.email} com papel: {usuario.role}")
        return response
    except Exception as e:
        logging.error(f"Erro inesperado durante o login para identificador {identificador}: {e}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro interno no servidor."}), 500
