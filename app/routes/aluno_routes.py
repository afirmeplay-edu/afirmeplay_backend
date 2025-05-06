from flask import Blueprint, request, jsonify
from app.models.aluno import Aluno
from app.models.usuario import Usuario
from app.models.usuario import RoleEnum

from app.utils.auth import get_current_tenant_id

from datetime import date

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
        matricula=data.get("matricula"),
        email=data["email"],  # ou algum identificador único
        senha_hash=generate_password_hash(data["senha"]),
        role=RoleEnum("aluno"),
        tenant_id=get_current_tenant_id()
    )
    db.session.add(novo_usuario)
    db.session.flush()  # Garante que novo_usuario.id esteja disponível
    
    
    # Criar o aluno relacionado
    novo_aluno = Aluno(
        usuario_id=novo_usuario.id,
        nome = data.get("nome"),
        email = data.get("email"),
        birth_date = date(1993,8,12),
        matricula=data.get("matricula"),
        education_stage_id=data.get("education_stage_id"),
        grade_id=data.get("grade_id"),
        tenant_id=get_current_tenant_id()
    )
    db.session.add(novo_aluno)
    db.session.commit()
    
    return jsonify({"mensagem": "Aluno criado com sucesso!","id": novo_aluno.id})

@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin","professor","coordenador","diretor")
def listar_alunos():
    tenant_id = get_current_tenant_id()
    print(tenant_id)
    alunos = Aluno.query.filter_by(tenant_id=tenant_id).all()
    return jsonify([{ "id": a.id, "nome": a.nome, "matricula": a.matricula, "Data de Nascimento: ": a.birth_date } for a in alunos])
