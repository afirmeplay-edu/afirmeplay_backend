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
            # Para aluno, buscar school_id na tabela student e pegar city_id da escola
            student = Student.query.filter_by(user_id=usuario.id).first()
            if not student or not student.school_id:
                 logging.error(f"Usuário aluno {usuario.id} sem registro de estudante ou school_id associado.")
                 return jsonify({"erro": "Aluno não vinculado a uma escola."}), 400
            
            # Buscar a escola para obter o city_id
            school = School.query.get(student.school_id)
            if not school:
                logging.error(f"Escola {student.school_id} não encontrada para o aluno {usuario.id}")
                return jsonify({"erro": "Escola do aluno não encontrada."}), 400
            
            tenant_id = school.city_id  # ✅ Usar city_id da escola ao invés de school_id
        elif usuario.role == RoleEnum('admin'):
            tenant_id = None # Admin pode ver tudo, sem restrição de tenant
        else:
            # Para outras roles, usar city_id do usuário
            if not usuario.city_id:
                 logging.error(f"Usuário {usuario.id} ({usuario.role}) sem city_id vinculado.")
                 return jsonify({"erro": f"{usuario.role} não vinculado a um município."}), 400
            tenant_id = usuario.city_id


        token_payload = {
            "sub": usuario.id,
            "tenant_id": tenant_id,
            "role": usuario.role.value,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }

        token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')

        usuario_data = {
            "id": usuario.id,
            "name": usuario.name,
            "email": usuario.email,
            "registration": usuario.registration,
            "tenant_id": tenant_id,
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
