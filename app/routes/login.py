from flask import Blueprint, request, jsonify
from app.utils.auth import authenticate_usuario
import datetime
import jwt
from app.models.user import User, RoleEnum
from app.models.school import School  # certifique-se que essa importação está correta
from app.models.student import Student # Import Student model
import logging
import os


SECRET_KEY = os.getenv("JWT_SECRET_KEY")

bp = Blueprint('login', __name__, url_prefix='/login')

@bp.route('/', methods=['POST', 'OPTIONS'])
def login():
    # Tratar requisições OPTIONS (preflight)
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
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

        tenant_id = None

        # Define o tenant_id com base na role
        if usuario.role == RoleEnum('aluno'):
            # Para aluno, usar city_id direto do usuário
            if not usuario.city_id:
                logging.error(f"Usuário aluno {usuario.id} sem city_id vinculado.")
                return jsonify({"erro": "Aluno não vinculado a um município."}), 400
            
            tenant_id = usuario.city_id
        elif usuario.role == RoleEnum('admin'):
            tenant_id = None # Admin pode ver tudo, sem restrição de tenant
        elif usuario.role == RoleEnum('tecadm'):
            # Tecadm deve ter city_id definido
            if not usuario.city_id:
                logging.error(f"Usuário tecadm {usuario.id} sem city_id vinculado.")
                return jsonify({"erro": "Tecadm não vinculado a um município."}), 400
            tenant_id = usuario.city_id
        elif usuario.role == RoleEnum('professor'):
            # Professor deve ter city_id definido
            if not usuario.city_id:
                logging.error(f"Usuário professor {usuario.id} sem city_id vinculado.")
                return jsonify({"erro": "Professor não vinculado a um município."}), 400
            tenant_id = usuario.city_id
        else:
            # Para outras roles (diretor, coordenador), usar city_id do usuário
            if not usuario.city_id:
                 logging.error(f"Usuário {usuario.id} ({usuario.role}) sem city_id vinculado.")
                 return jsonify({"erro": f"{usuario.role} não vinculado a um município."}), 400
            tenant_id = usuario.city_id


        # Buscar informações da cidade (se houver tenant_id)
        from app.models.city import City
        city = None
        city_slug = None
        if tenant_id:
            city = City.query.get(tenant_id)
            if city:
                city_slug = city.slug
        
        token_payload = {
            "sub": usuario.id,
            "tenant_id": tenant_id,
            "role": usuario.role.value,
            "city_slug": city_slug,  # Incluir slug no token para facilitar resolução
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }

        token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')

        usuario_data = {
            "id": usuario.id,
            "name": usuario.name,
            "email": usuario.email,
            "registration": usuario.registration,
            "tenant_id": tenant_id,
            "city_slug": city_slug,  # Incluir slug na resposta
            "created_at": usuario.created_at,
            "role": usuario.role.value
        }

        logging.info(f"Login bem-sucedido para usuário: {usuario.email} com papel: {usuario.role} e tenant_id: {tenant_id}")
        response = jsonify({
            "mensagem": "Login bem-sucedido.",
            "user": usuario_data,
            "token": token
        })
        
        # Não adicionar headers CORS explicitamente aqui - deixar o Flask-CORS gerenciar
        
        return response
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"ERRO NO LOGIN - Identificador: {identificador}")
        print(f"ERRO: {str(e)}")
        print(f"TRACEBACK COMPLETO:\n{error_traceback}")
        logging.error(f"Erro inesperado durante o login para identificador {identificador}: {e}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro interno no servidor."}), 500

@bp.route('/test', methods=['GET', 'OPTIONS'])
def test_cors():
    """Endpoint de teste para verificar se o CORS está funcionando"""
    if request.method == 'OPTIONS':
        return jsonify({"message": "CORS preflight OK"}), 200
    
    return jsonify({
        "message": "CORS está funcionando!",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }), 200
