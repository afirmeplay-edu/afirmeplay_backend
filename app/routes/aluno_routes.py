from flask import Blueprint, request, jsonify
from app.models.aluno import Aluno
from app.models.usuario import Usuario
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required

from werkzeug.security import generate_password_hash

bp = Blueprint('alunos', __name__, url_prefix="/alunos")

@bp.route("/", methods=["POST"])
@jwt_required()
@role_required("admin","professor","coordenador","diretor")
def criar_aluno():
    data = request.get_json()
     # Criar o usuário base
    novo_usuario = Usuario(
        nome=data["nome"],
        email=data["email"],  # ou algum identificador único
        senha_hash=generate_password_hash(data["senha"]),
        role="aluno",
        tenant_id=get_current_tenant_id()
    )
    db.session.add(novo_usuario)
    db.session.flush()  # Garante que novo_usuario.id esteja disponível
    
    
    # Criar o aluno relacionado
    novo_aluno = Aluno(
        usuario_id=novo_usuario.id,
        matricula=data["matricula"],
        classe_id=data.get("classe_id"),
        tenant_id=novo_usuario.tenant_id
    )
    db.session.add(novo_aluno)
    db.session.commit()
    
    return jsonify({"mensagem": "Aluno criado com sucesso!","id": novo_aluno.id})

@bp.route('/', methods=['GET'])
@jwt_required()
def listar_alunos():
    tenant_id = get_current_tenant_id()
    alunos = Aluno.query.filter_by(tenant_id=tenant_id).all()
    return jsonify([{ "id": a.id, "nome": a.nome, "matricula": a.matricula } for a in alunos])
