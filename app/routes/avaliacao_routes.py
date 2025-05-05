from flask import Blueprint, request, jsonify
from app.models.avaliacao import Avaliacao
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required

bp = Blueprint('avaliacoes', __name__, url_prefix='/avaliacoes')

@bp.route('/', methods=['POST'])
@jwt_required()
@role_required("admin","professor", "coordenador","diretor")
def criar_avaliacao():
    data = request.get_json()
    avaliacao = Avaliacao(
        titulo=data['titulo'],
        descricao=data.get('descricao'),
        data_aplicacao=data.get('data_aplicacao'),
        tenant_id=get_current_tenant_id()
    )
    db.session.add(avaliacao)
    db.session.commit()
    return jsonify({"mensagem": "Avaliação criada com sucesso!","id": avaliacao.id})

@bp.route('/', methods=['GET'])
@jwt_required()
def listar_avaliacoes():
    tenant_id = get_current_tenant_id()
    avaliacoes = Avaliacao.query.filter_by(tenant_id=tenant_id).all()
    return jsonify([{ "id": a.id, "titulo": a.titulo, "descricao": a.descricao,"data_aplicacao": str(a.data_aplicacao) } for a in avaliacoes])
