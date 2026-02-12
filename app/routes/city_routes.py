import re
from flask import Blueprint, request, jsonify
from app import db
from app.models.city import City
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.decorators.role_required import get_current_tenant_id
from app.services.city_schema_service import provision_city_schema

bp = Blueprint('city', __name__, url_prefix='/city')

# Slug: apenas letras minúsculas, números e hífen ([a-z0-9-]+), máx 100 caracteres
SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")

# POST - Criar município
@bp.route("", methods=["POST"])
@jwt_required()
@role_required("admin","tecadm")
def criar_municipio():
    data = request.get_json() or {}
    name = data.get("name")
    state = data.get("state")
    slug = data.get("slug")

    if not name or not state:
        return jsonify({"erro": "Campos obrigatórios: name, state"}), 400
    if not slug or not isinstance(slug, str):
        return jsonify({"erro": "Campo obrigatório: slug (string)"}), 400

    slug = slug.strip().lower()
    if len(slug) > 100:
        return jsonify({"erro": "slug deve ter no máximo 100 caracteres"}), 400
    if not SLUG_PATTERN.match(slug):
        return jsonify({
            "erro": "slug inválido: apenas letras minúsculas, números e hífen (a-z, 0-9, -)"
        }), 400

    if City.query.filter_by(slug=slug).first():
        return jsonify({"erro": "Já existe um município com este slug"}), 409

    novo_municipio = City(
        name=name,
        state=state,
        slug=slug
    )
    db.session.add(novo_municipio)
    db.session.commit()

    try:
        provision_city_schema(
            city_id=novo_municipio.id,
            city_name=novo_municipio.name,
            city_state=novo_municipio.state
        )
    except Exception as e:
        db.session.delete(novo_municipio)
        db.session.commit()
        return jsonify({
            "erro": "Município criado mas falha ao criar schema no banco. Cidade foi revertida.",
            "detalhe": str(e)
        }), 500

    return jsonify({
        "mensagem": "Município criado com sucesso",
        "id": novo_municipio.id,
        "slug": novo_municipio.slug
    }), 201

# GET - Listar municípios
@bp.route("", methods=["GET"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
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
            "slug": c.slug,
            "created_at": c.created_at.isoformat()
        }
        for c in cities
    ])

# GET - Buscar município específico
@bp.route("<string:municipio_id>", methods=["GET"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
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
        "slug": municipio.slug,
        "created_at": municipio.created_at.isoformat()
    })

# PUT - Atualizar município
@bp.route("<string:municipio_id>/", methods=["PUT"])
@jwt_required()
@role_required("admin", "diretor", "coordenador","tecadm")
def atualizar_municipio(municipio_id):
    user = get_current_user_from_token()
    
    # Verifica se o usuário tem permissão para modificar esta cidade
    if user.get("role") != "admin" and user.get("city_id") != municipio_id:
        return jsonify({"erro": "Você não tem permissão para modificar esta cidade"}), 403

    municipio = City.query.get(municipio_id)
    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    data = request.get_json() or {}
    if "name" in data:
        municipio.name = data["name"]
    if "state" in data:
        municipio.state = data["state"]
    if "slug" in data:
        slug = data["slug"]
        if not isinstance(slug, str):
            return jsonify({"erro": "slug deve ser uma string"}), 400
        slug = slug.strip().lower()
        if len(slug) > 100:
            return jsonify({"erro": "slug deve ter no máximo 100 caracteres"}), 400
        if not SLUG_PATTERN.match(slug):
            return jsonify({
                "erro": "slug inválido: apenas letras minúsculas, números e hífen (a-z, 0-9, -)"
            }), 400
        existente = City.query.filter_by(slug=slug).first()
        if existente and existente.id != municipio.id:
            return jsonify({"erro": "Já existe outro município com este slug"}), 409
        municipio.slug = slug

    db.session.commit()
    return jsonify({
        "mensagem": "Município atualizado com sucesso",
        "id": municipio.id,
        "slug": municipio.slug
    })

# DELETE - Excluir município
@bp.route("<string:municipio_id>/", methods=["DELETE"])
@jwt_required()
@role_required("admin","tecadm")
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
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
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
@role_required("admin", "diretor", "coordenador", "professor","tecadm")
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
            "slug": c.slug,
            "created_at": c.created_at.isoformat()
        }
        for c in cities
    ])
