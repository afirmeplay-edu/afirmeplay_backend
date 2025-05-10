from flask import Blueprint, request, jsonify
from app.models.escola import Escola
from app import db
from app.decorators.role_required import role_required
from flask_jwt_extended import jwt_required

import uuid

bp = Blueprint('escolas', __name__, url_prefix='/escolas')

# POST - Criar escola
@bp.route('/', methods=['POST'])
@jwt_required()
@role_required("admin", "diretor")
def criar_escola():
    data = request.get_json()

    nova_escola = Escola(
        id=str(uuid.uuid4()),
        nome=data['nome'],
        dominio=data.get('dominio'),
        endereco=data.get('endereco'),
        municipio_id=data['municipio_id']
    )

    db.session.add(nova_escola)
    db.session.commit()

    return jsonify({"mensagem": "Escola criada com sucesso!", "id": nova_escola.id}), 201

# GET - Listar escolas
@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador")
def listar_escolas():
    escolas = Escola.query.all()
    return jsonify([
        {
            "id": e.id,
            "nome": e.nome,
            "dominio": e.dominio,
            "endereco": e.endereco,
            "municipio_id": e.municipio_id,
            "criado_em": e.criado_em.isoformat()
        } for e in escolas
    ])

# PUT - Atualizar escola
@bp.route('/<string:escola_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "diretor")
def atualizar_escola(escola_id):
    escola = Escola.query.get(escola_id)

    if not escola:
        return jsonify({"erro": "Escola não encontrada"}), 404

    data = request.get_json()
    escola.nome = data.get('nome', escola.nome)
    escola.dominio = data.get('dominio', escola.dominio)
    escola.endereco = data.get('endereco', escola.endereco)
    escola.municipio_id = data.get('municipio_id', escola.municipio_id)

    db.session.commit()
    return jsonify({"mensagem": "Escola atualizada com sucesso"})

# DELETE - Excluir escola
@bp.route('/<string:escola_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin")
def deletar_escola(escola_id):
    escola = Escola.query.get(escola_id)

    if not escola:
        return jsonify({"erro": "Escola não encontrada"}), 404

    db.session.delete(escola)
    db.session.commit()
    return jsonify({"mensagem": "Escola deletada com sucesso"})
