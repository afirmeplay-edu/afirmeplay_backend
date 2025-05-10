from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from app.models.usuario import Usuario
from app.models.usuario import RoleEnum
from app import db
from app.decorators.role_required import role_required

from app.utils.auth import get_current_tenant_id



bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/criar-usuario', methods=['POST'])
# @role_required('admin')
def criar_usuario():
    data = request.get_json()
    nome = data.get('nome')
    email = data.get('email')
    senha = data.get('senha')
    role = data.get('role')
    matricula = data.get('matricula')
    escola_id = data.get("escola_id")
    # tenant_id = data.get('tenant_id')

    roles_validas = ['aluno', 'professor', 'coordenador', 'diretor',"admin"]
    if role not in roles_validas:
        return jsonify({"erro": "Papel (role) inválido."}), 400

    if not all([nome, email, senha, role]):
        return jsonify({"erro": "Campos obrigatórios faltando."}), 400

    if role == 'aluno' and not matricula:
        return jsonify({"erro": "Campo 'matricula' é obrigatório para alunos."}), 400

    if Usuario.query.filter_by(email=email).first():
        return jsonify({"erro": "Email já cadastrado."}), 400

    if role == 'aluno' and Usuario.query.filter_by(matricula=matricula).first():
        return jsonify({"erro": "Matrícula já cadastrada."}), 400

    novo_usuario = Usuario(
        nome=nome,
        email=email,
        escola_id=escola_id,
        senha_hash=generate_password_hash(senha),
        role=RoleEnum(role),
        matricula=matricula if role == 'aluno' else None,
        # tenant_id = tenant_id
    )

    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify({"mensagem": f"{role.capitalize()} criado com sucesso."}), 201
