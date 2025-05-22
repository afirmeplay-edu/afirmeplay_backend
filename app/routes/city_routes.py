from flask import Blueprint, request, jsonify
from app import db
from app.models.city import City
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from app.utils.auth import get_current_tenant_id

bp = Blueprint('city', __name__, url_prefix='/city')

# POST - Criar município
@bp.route("/", methods=["POST"])
@jwt_required()
@role_required("admin")
def criar_municipio():
    data = request.get_json()

    novo_municipio = City(
        name=data["name"],
        state=data["state"]
    )

    db.session.add(novo_municipio)
    db.session.commit()

    return jsonify({"mensagem": "Município criado com sucesso", "id": novo_municipio.id}), 201

# GET - Listar todos os municípios
@bp.route("/", methods=["GET"])
@jwt_required()
@role_required("admin")
def listar_municipios():
    city = City.query.all()

    return jsonify([
        {
            "id": c.id,
            "name": c.name,
            "state": c.state,
            "created_at": c.created_at.isoformat()
        }
        for c in city
    ])

# PUT - Atualizar município
@bp.route("/<string:municipio_id>", methods=["PUT"])
@jwt_required()
@role_required("admin")
def atualizar_municipio(municipio_id):
    municipio = City.query.get(municipio_id)

    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    data = request.get_json()
    municipio.name = data.get("name", municipio.name)
    municipio.state = data.get("state", municipio.state)

    db.session.commit()
    return jsonify({"mensagem": "Município atualizado com sucesso"})

# DELETE - Excluir município
@bp.route("/<string:municipio_id>", methods=["DELETE"])
@jwt_required()
@role_required("admin")
def deletar_municipio(municipio_id):
    municipio = City.query.get(municipio_id)

    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    db.session.delete(municipio)
    db.session.commit()
    return jsonify({"mensagem": "Município deletado com sucesso"})
