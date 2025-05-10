from flask import Blueprint, request, jsonify
from app.models.aluno import Aluno
from app.models.usuario import Usuario
from app.models.usuario import RoleEnum

from app.utils.auth import get_current_tenant_id

from datetime import datetime

from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required

from werkzeug.security import generate_password_hash

bp = Blueprint('alunos', __name__, url_prefix="/alunos")

@bp.route("/", methods=["POST"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def criar_aluno():
    data = request.get_json()
    
    try:
        # Criação do usuário com dados básicos
        novo_usuario = Usuario(
            nome=data["nome"],
            email=data["email"],
            senha_hash=generate_password_hash(data["senha"]),
            matricula=data.get("matricula"),
            role=RoleEnum("aluno"),
            escola_id=data["escola_id"],
            # tenant_id=get_current_tenant_id()
        )
        db.session.add(novo_usuario)
        db.session.flush()  # Garante que novo_usuario.id esteja disponível

        # Converte a data de nascimento se enviada (formato esperado: "YYYY-MM-DD")
        birth_date = None
        if "birth_date" in data:
            birth_date = datetime.strptime(data["birth_date"], "%Y-%m-%d").date()

        # Criação do aluno vinculado ao usuário
        novo_aluno = Aluno(
            nome=data["nome"],
            email=data["email"],
            senha_hash=generate_password_hash(data["senha"]),
            usuario_id=novo_usuario.id,
            matricula=data.get("matricula"),
            birth_date=birth_date,
            education_stage_id=data.get("education_stage_id"),
            escola_id=data["escola_id"],
            grade_id=data.get("grade_id"),
            # tenant_id=get_current_tenant_id()
        )
        db.session.add(novo_aluno)
        db.session.commit()

        return jsonify({"mensagem": "Aluno criado com sucesso!", "id": novo_aluno.id}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": "Erro ao criar aluno", "detalhes": str(e)}), 400
    
    

@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin","professor","coordenador","diretor")
def listar_alunos():
    escola_id = get_current_tenant_id()
    alunos = Aluno.query.filter_by(escola_id=escola_id).all()
    return jsonify([{ "id": a.id, "nome": a.nome, "matricula": a.matricula, "birth_date:": a.birth_date, "education_stage_id":a.education_stage_id, "grade_id":a.grade_id, "criado_em":a.criado_em } for a in alunos])



@bp.route('/<string:aluno_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def atualizar_aluno(aluno_id):
    escola_id = get_current_tenant_id()
    aluno = Aluno.query.filter_by(id=aluno_id, escola_id=escola_id).first()

    if not aluno:
        return jsonify({"erro": "Aluno não encontrado"}), 404

    dados = request.get_json()
    
    # Atualiza dados do usuário vinculado
    usuario = aluno.usuario
    usuario.nome = dados.get("nome", usuario.nome)
    usuario.email = dados.get("email", usuario.email)
    usuario.matricula = dados.get("matricula", usuario.matricula)

    # Atualiza dados do aluno (separados)
    aluno.education_stage_id = dados.get("education_stage_id", aluno.education_stage_id)
    aluno.grade_id = dados.get("grade_id", aluno.grade_id)

    # Atualiza data de nascimento se enviada
    if "birth_date" in dados:
        try:
            aluno.birth_date = datetime.strptime(dados["birth_date"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD."}), 400

    db.session.commit()
    return jsonify({"mensagem": "Aluno atualizado com sucesso"})


@bp.route('/<string:aluno_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def deletar_aluno(aluno_id):
    tenant_id = get_current_tenant_id()
    aluno = Aluno.query.filter_by(id=aluno_id, tenant_id=tenant_id).first()

    if not aluno:
        return jsonify({"erro": "Aluno não encontrado"}), 404

    db.session.delete(aluno)
    db.session.commit()
    return jsonify({"mensagem": "Aluno deletado com sucesso"})
