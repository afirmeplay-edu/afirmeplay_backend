from flask import Blueprint, request, jsonify
from app.models.escola import Escola
from app import db
from app.decorators.role_required import role_required

bp = Blueprint('escolas', __name__, url_prefix='/escolas')

@bp.route('/', methods=['POST'])
# @role_required("admin")
def criar_escola():
    data = request.get_json()
    escola = Escola(nome=data['nome'], dominio=data['dominio'], cidade=data['cidade'],estado=data['estado'])
    db.session.add(escola)
    db.session.commit()
    return jsonify({"mensagem": "Escola criada com sucesso!","id": escola.id})

@bp.route('/', methods=['GET'])
def listar_escolas():
    escolas = Escola.query.all()
    return jsonify([{ "id": e.id, "nome": e.nome, "dominio": e.dominio } for e in escolas])
