from flask import Blueprint, request, jsonify
from app import db
from app.models.city import City
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.utils.auth import get_current_tenant_id

bp = Blueprint('city', __name__, url_prefix='/city')

# POST - Criar município
@bp.route("", methods=["POST"])
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

# GET - Listar municípios
@bp.route("", methods=["GET"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def listar_municipios():
    user = get_current_user_from_token()
    
    if user.get("role") == "admin":
        # Admin pode ver todas as cidades
        cities = City.query.all()
    else:
        # Outros usuários só podem ver sua própria cidade
        city_id = user.get("city_id")
        if not city_id:
            return jsonify({"erro": "Cidade não encontrada para este usuário"}), 404
        cities = City.query.filter_by(id=city_id).all()

    return jsonify([
        {
            "id": c.id,
            "name": c.name,
            "state": c.state,
            "created_at": c.created_at.isoformat()
        }
        for c in cities
    ])

# GET - Buscar município específico
@bp.route("<string:municipio_id>", methods=["GET"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def buscar_municipio(municipio_id):
    user = get_current_user_from_token()
    
    # Verifica se o usuário tem permissão para acessar esta cidade
    if user.get("role") != "admin" and user.get("city_id") != municipio_id:
        return jsonify({"erro": "Você não tem permissão para acessar esta cidade"}), 403

    municipio = City.query.get(municipio_id)
    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    return jsonify({
        "id": municipio.id,
        "name": municipio.name,
        "state": municipio.state,
        "created_at": municipio.created_at.isoformat()
    })

# PUT - Atualizar município
@bp.route("<string:municipio_id>/", methods=["PUT"])
@jwt_required()
@role_required("admin", "diretor", "coordenador")
def atualizar_municipio(municipio_id):
    user = get_current_user_from_token()
    
    # Verifica se o usuário tem permissão para modificar esta cidade
    if user.get("role") != "admin" and user.get("city_id") != municipio_id:
        return jsonify({"erro": "Você não tem permissão para modificar esta cidade"}), 403

    municipio = City.query.get(municipio_id)
    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    data = request.get_json()
    municipio.name = data.get("name", municipio.name)
    municipio.state = data.get("state", municipio.state)

    db.session.commit()
    return jsonify({"mensagem": "Município atualizado com sucesso"})

# DELETE - Excluir município
@bp.route("<string:municipio_id>/", methods=["DELETE"])
@jwt_required()
@role_required("admin")
def deletar_municipio(municipio_id):
    municipio = City.query.get(municipio_id)

    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    db.session.delete(municipio)
    db.session.commit()
    return jsonify({"mensagem": "Município deletado com sucesso"})

# GET - Listar estados únicos
@bp.route("/states", methods=["GET"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def listar_estados():
    user = get_current_user_from_token()
    
    if user.get("role") == "admin":
        # Admin pode ver todos os estados
        cities = City.query.all()
    else:
        # Outros usuários só podem ver o estado de sua própria cidade
        city_id = user.get("city_id")
        if not city_id:
            return jsonify({"erro": "Cidade não encontrada para este usuário"}), 404
        user_city = City.query.get(city_id)
        if not user_city:
            return jsonify({"erro": "Cidade do usuário não encontrada"}), 404
        cities = [user_city]

    # Extrair estados únicos
    unique_states = list(set(city.state for city in cities))
    
    return jsonify([
        {
            "id": state,
            "name": state,
            "uf": state
        }
        for state in unique_states
    ])

# GET - Listar municípios por estado
@bp.route("/municipalities/state/<string:state_name>", methods=["GET"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor")
def listar_municipios_por_estado(state_name):
    user = get_current_user_from_token()
    
    if user.get("role") == "admin":
        # Admin pode ver todos os municípios do estado
        cities = City.query.filter_by(state=state_name).all()
    else:
        # Outros usuários só podem ver sua própria cidade se pertencer ao estado
        city_id = user.get("city_id")
        if not city_id:
            return jsonify({"erro": "Cidade não encontrada para este usuário"}), 404
        user_city = City.query.get(city_id)
        if not user_city or user_city.state != state_name:
            return jsonify({"erro": "Você não tem permissão para acessar municípios deste estado"}), 403
        cities = [user_city]

    return jsonify([
        {
            "id": c.id,
            "name": c.name,
            "state": c.state,
            "created_at": c.created_at.isoformat()
        }
        for c in cities
    ])
