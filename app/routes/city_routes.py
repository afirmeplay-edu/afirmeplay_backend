import re
import unicodedata
import logging
from urllib.parse import unquote
from flask import Blueprint, request, jsonify
from app import db
from app.models.city import City
from app.models.user import User
from app.models.manager import Manager
from app.models.school import School
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
        # Usar tenant_id como fallback para city_id
        city_id = user.get("tenant_id") or user.get("city_id")
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
    # Usar tenant_id como fallback para city_id
    user_city_id = user.get("tenant_id") or user.get("city_id")
    if user.get("role") != "admin" and user_city_id != municipio_id:
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
    # Usar tenant_id como fallback para city_id
    user_city_id = user.get("tenant_id") or user.get("city_id")
    if user.get("role") != "admin" and user_city_id != municipio_id:
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
        # Usar tenant_id como fallback para city_id
        city_id = user.get("tenant_id") or user.get("city_id")
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
    
    # Tentar decodificar URL (caso venha com encoding)
    try:
        state_name_decoded = unquote(state_name)
    except:
        state_name_decoded = state_name
    
    logging.info(f"[listar_municipios_por_estado] Role: {user.get('role')}")
    logging.info(f"[listar_municipios_por_estado] state_name original: '{state_name}'")
    logging.info(f"[listar_municipios_por_estado] state_name decoded: '{state_name_decoded}'")
    
    if user.get("role") == "admin":
        # Admin pode ver todos os municípios do estado
        cities = City.query.filter_by(state=state_name).all()
        if not cities:
            # Tentar com o nome decodificado
            cities = City.query.filter_by(state=state_name_decoded).all()
    else:
        # Outros usuários só podem ver sua própria cidade se pertencer ao estado
        # Usar tenant_id como fallback para city_id
        city_id = user.get("tenant_id") or user.get("city_id")
        
        logging.info(f"[listar_municipios_por_estado] city_id: {city_id}")
        
        if not city_id:
            return jsonify({"erro": "Cidade não encontrada para este usuário"}), 404
        
        user_city = City.query.get(city_id)
        if not user_city:
            logging.error(f"[listar_municipios_por_estado] Cidade não encontrada no banco: {city_id}")
            return jsonify({"erro": "Cidade não encontrada"}), 404
        
        logging.info(f"[listar_municipios_por_estado] Cidade: {user_city.name}, Estado DB: '{user_city.state}'")
        
        # Função para normalizar strings (remover acentos, lowercase, trim)
        def normalize_str(s):
            if not s:
                return ""
            # Normalizar NFD (decompor acentos)
            nfd = unicodedata.normalize('NFD', s)
            # Remover marcas diacríticas
            without_accents = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
            return without_accents.lower().strip()
        
        db_state_norm = normalize_str(user_city.state)
        req_state_norm = normalize_str(state_name_decoded)
        
        logging.info(f"[listar_municipios_por_estado] DB normalizado: '{db_state_norm}', Request normalizado: '{req_state_norm}'")
        
        # Comparar estados (normalizado)
        if db_state_norm != req_state_norm:
            logging.warning(f"[listar_municipios_por_estado] Estados não correspondem! Acesso negado.")
            return jsonify({"erro": "Você não tem permissão para acessar municípios deste estado"}), 403
        
        logging.info(f"[listar_municipios_por_estado] Match! Retornando cidade do usuário.")
        # Retorna apenas o município do usuário (não todos do estado)
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

