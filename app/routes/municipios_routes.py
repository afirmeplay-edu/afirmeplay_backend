from flask import Blueprint, request, jsonify
from app import db
from app.models.municipio import Municipio
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from app.utils.auth import get_current_tenant_id
import uuid

bp = Blueprint('municipios', __name__, url_prefix='/municipios')

# POST - Criar município
@bp.route("/", methods=["POST"])
# @jwt_required()
# @role_required("admin", "diretor", "coordenador")
def criar_municipio():
    data = request.get_json()

    novo_municipio = Municipio(
        id=str(uuid.uuid4()),
        nome=data["nome"],
        estado=data["estado"]
    )

    db.session.add(novo_municipio)
    db.session.commit()

    return jsonify({"mensagem": "Município criado com sucesso", "id": novo_municipio.id}), 201

# GET - Listar todos os municípios
@bp.route("/", methods=["GET"])
@jwt_required()
@role_required("admin", "diretor", "coordenador")
def listar_municipios():
    municipios = Municipio.query.all()

    return jsonify([
        {
            "id": m.id,
            "nome": m.nome,
            "estado": m.estado,
            "criado_em": m.criado_em.isoformat()
        }
        for m in municipios
    ])

# PUT - Atualizar município
@bp.route("/<string:municipio_id>", methods=["PUT"])
@jwt_required()
@role_required("admin", "diretor", "coordenador")
def atualizar_municipio(municipio_id):
    municipio = Municipio.query.get(municipio_id)

    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    data = request.get_json()
    municipio.nome = data.get("nome", municipio.nome)
    municipio.estado = data.get("estado", municipio.estado)

    db.session.commit()
    return jsonify({"mensagem": "Município atualizado com sucesso"})

# DELETE - Excluir município
@bp.route("/<string:municipio_id>", methods=["DELETE"])
@jwt_required()
@role_required("admin", "diretor", "coordenador")
def deletar_municipio(municipio_id):
    municipio = Municipio.query.get(municipio_id)

    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    db.session.delete(municipio)
    db.session.commit()
    return jsonify({"mensagem": "Município deletado com sucesso"})
