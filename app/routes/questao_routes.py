from flask import Blueprint, request, jsonify
from app.models.questao import Questao
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required

bp = Blueprint('questoes', __name__, url_prefix='/questoes')

@bp.route('/', methods=['POST'])
@jwt_required()
@role_required("admin","professor","coordenador","diretor")
def criar_questao():
    data = request.get_json()
    questao = Questao(
        enunciado=data['enunciado'],
        alternativas=data['alternativas'],
        resposta_correta=data['resposta_correta'],
        avaliacao_id=data.get('avaliacao_id'),
        tenant_id=get_current_tenant_id()
    )
    db.session.add(questao)
    db.session.commit()
    return jsonify({"mensagem": "Questão criada com sucesso!","id": questao.id})

@bp.route('/', methods=['GET'])
@jwt_required()
def listar_questoes():
    tenant_id = get_current_tenant_id()
    avaliacao_id = request.args.get('avaliacao_id')

    query = Questao.query.filter_by(tenant_id=tenant_id)
    if avaliacao_id:
        query = query.filter_by(avaliacao_id=avaliacao_id)

    questoes = query.all()
    return jsonify([{
        "id": q.id,
        "enunciado": q.enunciado,
        "alternativas": q.alternativas,
        "resposta_correta": q.resposta_correta,
        "avaliacao_id": q.avaliacao_id
    } for q in questoes])
