from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from app.models.user import User
from app.models.user import RoleEnum
from app import db
from app.decorators.role_required import role_required

from app.decorators.role_required import get_current_tenant_id



bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/criar-usuario', methods=['POST'])
@role_required('admin')
def criar_usuario():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    registration = data.get('registration')
    city_id = data.get("city_id")

    roles_validas = ['aluno', 'professor', 'coordenador', 'diretor', "admin", "tecadm"]
    if role not in roles_validas:
        return jsonify({"erro": "Papel (role) inválido."}), 400

    if not all([name, email, password, role]):
        return jsonify({"erro": "Campos obrigatórios faltando."}), 400

    # Matrícula é opcional para todos os usuários
    pass

    if User.query.filter_by(email=email).first():
        return jsonify({"erro": "Email já cadastrado."}), 400

    # Verificar se matrícula já existe (apenas se for fornecida)
    if registration and User.query.filter_by(registration=registration).first():
        return jsonify({"erro": "Matrícula já cadastrada."}), 400

    novo_usuario = User(
        name=name,
        email=email,
        city_id=city_id,
        password_hash=generate_password_hash(password),
        role=RoleEnum(role),
        registration=registration,  # Matrícula é opcional
    )

    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify({"mensagem": f"{role.capitalize()} criado com sucesso."}), 201
