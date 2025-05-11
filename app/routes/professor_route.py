from flask import Blueprint, request, jsonify
from app.models.aluno import Aluno
from app.models.usuario import Usuario
from app.models.usuario import RoleEnum
from app.models.professor import Professor
from app.models.escola import Escola

from app.utils.auth import get_current_tenant_id
from werkzeug.security import generate_password_hash

from datetime import datetime

from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required

bp = Blueprint('professores', __name__, url_prefix="/professores")

@bp.route('/', methods=['POST'])
@jwt_required()
@role_required("admin", "diretor")
def criar_professor():
    dados = request.get_json()
    
    nome = dados.get("nome")
    email = dados.get("email")
    senha = dados.get("senha")
    matricula = dados.get("matricula")
    birth_date = dados.get("birth_date")
    escolas_ids = dados.get("escolas_ids", [])  # Lista de escolas a vincular

    # Validação básica
    if not all([nome, email, senha, matricula]):
        return jsonify({"erro": "Nome, email, senha e matrícula são obrigatórios"}), 400

    if Usuario.query.filter_by(email=email).first():
        return jsonify({"erro": "Email já cadastrado"}), 400

    if Professor.query.filter_by(matricula=matricula).first():
        return jsonify({"erro": "Matrícula já cadastrada"}), 400

    # Criar usuário associado
    senha_hash = generate_password_hash(senha)
    usuario = Usuario(nome=nome, email=email, senha_hash=senha_hash, role=RoleEnum("professor"), matricula=matricula)
    db.session.add(usuario)
    db.session.flush()  # Para obter o ID gerado

    # Converter data de nascimento
    try:
        data_nascimento = datetime.strptime(birth_date, "%Y-%m-%d").date() if birth_date else None
    except ValueError:
        return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD."}), 400

    # Obter tenant_id (ex: município) do contexto do token
    tenant_id = get_current_tenant_id()

    # Criar professor
    professor = Professor(
        nome=nome,
        email=email,
        senha_hash=senha_hash,
        usuario_id=usuario.id,
        birth_date=data_nascimento,
        matricula=matricula,
        tenant_id=tenant_id
    )

    # Associar escolas
    if escolas_ids:
        escolas = Escola.query.filter(Escola.id.in_(escolas_ids), Escola.municipio_id == tenant_id).all()
        if len(escolas) != len(escolas_ids):
            return jsonify({"erro": "Uma ou mais escolas não encontradas ou não pertencem ao município"}), 400
        professor.escolas.extend(escolas)

    db.session.add(professor)
    db.session.commit()

    return jsonify({"mensagem": "Professor criado com sucesso", "id": professor.id}), 201
