import os
from flask import Blueprint, request, jsonify
from app import db
from app.models.city import City
from app.models.user import User
from app.models.manager import Manager
from app.models.school import School
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.decorators.role_required import get_current_tenant_id

bp = Blueprint('city', __name__, url_prefix='/city')

# Domínio base para montar a URL do subdomínio de cada município
DOMAIN_BASE = os.getenv("APP_DOMAIN", "afirmeplay.com.br")

# POST - Criar município
@bp.route("", methods=["POST"])
@jwt_required()
@role_required("admin","tecadm")
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
            "created_at": c.created_at.isoformat()
        }
        for c in cities
    ])


# GET - Listar todos os domínios (subdomínios) dos municípios
@bp.route("/domains", methods=["GET"])
@jwt_required()
@role_required("admin")
def listar_dominios_municipios():
    """
    Retorna a lista de todos os municípios com seu domínio (subdomínio).
    Cada município é acessível via https://<slug>.<APP_DOMAIN> (ex: https://jiparana.afirmeplay.com.br).
    Apenas admin pode acessar.
    """
    cities = City.query.order_by(City.state, City.name).all()
    return jsonify([
        {
            "id": c.id,
            "name": c.name,
            "state": c.state,
            "slug": c.slug,
            "dominio": f"{c.slug}.{DOMAIN_BASE}",
            "url": f"https://{c.slug}.{DOMAIN_BASE}",
        }
        for c in cities
    ])


# GET - Listar todos os usuários do município (rota mais específica antes de <municipio_id>)
@bp.route("<string:municipio_id>/users", methods=["GET"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def listar_usuarios_municipio(municipio_id):
    """
    Retorna todos os usuários vinculados ao município (city_id = municipio_id).
    Admin pode consultar qualquer município; demais perfis apenas o próprio município.
    """
    try:
        user = get_current_user_from_token()

        # Permissão: admin pode ver qualquer município; outros só o próprio
        if user.get("role") != "admin":
            if user.get("role") in ["diretor", "coordenador"]:
                manager = Manager.query.filter_by(user_id=user.get("id")).first()
                if not manager or not manager.school_id:
                    return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
                school = School.query.get(manager.school_id)
                if not school or school.city_id != municipio_id:
                    return jsonify({"erro": "Você não tem permissão para acessar usuários deste município"}), 403
            else:
                # tecadm, professor
                city_id = user.get("tenant_id") or user.get("city_id")
                if not city_id or city_id != municipio_id:
                    return jsonify({"erro": "Você não tem permissão para acessar usuários deste município"}), 403

        municipio = City.query.get(municipio_id)
        if not municipio:
            return jsonify({"erro": "Município não encontrado"}), 404

        users = User.query.filter_by(city_id=municipio_id).order_by(User.name).all()

        def _serialize_user(u):
            role_val = getattr(u.role, "value", str(u.role)) if u.role else None
            return {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "registration": u.registration,
                "role": role_val,
                "city_id": u.city_id,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }

        return jsonify({
            "municipio": {
                "id": municipio.id,
                "name": municipio.name,
                "state": municipio.state,
            },
            "total": len(users),
            "users": [_serialize_user(u) for u in users],
        })
    except Exception as e:
        return jsonify({"erro": "Erro ao listar usuários do município", "detalhes": str(e)}), 500


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

    data = request.get_json()
    municipio.name = data.get("name", municipio.name)
    municipio.state = data.get("state", municipio.state)

    db.session.commit()
    return jsonify({"mensagem": "Município atualizado com sucesso"})

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
            "created_at": c.created_at.isoformat()
        }
        for c in cities
    ])
