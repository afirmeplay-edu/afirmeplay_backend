import re
import unicodedata
import logging
from io import BytesIO
from urllib.parse import unquote
from flask import Blueprint, request, jsonify, send_file, url_for
from app import db
from app.models.city import City
from app.models.user import User
from app.models.manager import Manager
from app.models.school import School
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.decorators.role_required import get_current_tenant_id
from app.services.city_schema_service import provision_city_schema
from app.services.city_branding_service import CityBrandingService, StorageUnavailableError
from app.entitlements.plans import DEFAULT_PLAN_CODE, normalize_plan_code
from app.entitlements.resolver import entitlements_for_city

bp = Blueprint('city', __name__, url_prefix='/city')


def _serialize_city(city: City) -> dict:
    created = city.created_at.isoformat() if city.created_at else None
    plan_code = city.plan_code or DEFAULT_PLAN_CODE
    return {
        "id": city.id,
        "name": city.name,
        "state": city.state,
        "slug": city.slug,
        "plan_code": plan_code,
        "entitlements": entitlements_for_city(city),
        "created_at": created,
    }


def _apply_plan_code_from_payload(municipio: City, data: dict, user: dict):
    """
    Atualiza plan_code se enviado no body. Apenas admin pode alterar.
    Retorna (jsonify, status) em erro ou None se ok / campo ausente.
    """
    if "plan_code" not in data:
        return None
    if (user.get("role") or "").strip().lower() != "admin":
        return jsonify({"erro": "Apenas administradores podem alterar o plano do município"}), 403
    try:
        municipio.plan_code = normalize_plan_code(data.get("plan_code"))
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    return None


def _ensure_municipio_access(user: dict, municipio_id: str):
    """
    Admin: qualquer município. tecadm/professor/aplicador: city_id do token.
    diretor/coordenador: escola do manager no município.
    Retorna (jsonify, status) se negado; None se permitido.
    """
    role = (user.get("role") or "").strip().lower()
    if role == "admin":
        return None
    if role == "tecadm":
        uid = user.get("tenant_id") or user.get("city_id")
        if uid != municipio_id:
            return jsonify({"erro": "Sem permissão para este município"}), 403
        return None
    if role in ("diretor", "coordenador"):
        manager = Manager.query.filter_by(user_id=user.get("id")).first()
        if not manager or not manager.school_id:
            return jsonify({"erro": "Usuário não está vinculado a nenhuma escola"}), 400
        school = School.query.get(manager.school_id)
        if not school or school.city_id != municipio_id:
            return jsonify({"erro": "Sem permissão para este município"}), 403
        return None
    if role in ("professor", "aplicador"):
        uid = user.get("tenant_id") or user.get("city_id")
        if uid != municipio_id:
            return jsonify({"erro": "Sem permissão para este município"}), 403
        return None
    return jsonify({"erro": "Acesso negado"}), 403

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

    user = get_current_user_from_token()
    plan_code = DEFAULT_PLAN_CODE
    if "plan_code" in data:
        if (user.get("role") or "").strip().lower() != "admin":
            return jsonify({"erro": "Apenas administradores podem definir o plano na criação"}), 403
        try:
            plan_code = normalize_plan_code(data.get("plan_code"))
        except ValueError as e:
            return jsonify({"erro": str(e)}), 400

    novo_municipio = City(
        name=name,
        state=state,
        slug=slug,
        plan_code=plan_code,
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
        **_serialize_city(novo_municipio),
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

    return jsonify([_serialize_city(c) for c in cities])


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
            **_serialize_city(c),
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
                # tecadm, professor, aplicador
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
            "municipio": _serialize_city(municipio),
            "total": len(users),
            "users": [_serialize_user(u) for u in users],
        })
    except Exception as e:
        return jsonify({"erro": "Erro ao listar usuários do município", "detalhes": str(e)}), 500


# --- Branding municipal (logo + timbrado) ---------------------------------

def _branding_proxy_url(endpoint: str, municipio_id: str) -> str:
    """URL relativa do proxy de branding (servida pelo backend)."""
    try:
        return url_for(endpoint, municipio_id=municipio_id)
    except Exception:
        # Fallback se o app context não permitir url_for (não deve ocorrer em request).
        suffix = {
            "city.get_branding_logo": "branding/logo",
            "city.get_branding_letterhead_image": "branding/letterhead/image",
            "city.get_branding_letterhead_pdf": "branding/letterhead/pdf",
        }.get(endpoint, "")
        return f"/city/{municipio_id}/{suffix}"


def _serve_branding_asset(municipio_id: str, asset_kind: str):
    """Lógica comum aos proxies GET de logo/timbrado."""
    user = get_current_user_from_token()
    denied = _ensure_municipio_access(user, municipio_id)
    if denied:
        return denied
    municipio = City.query.get(municipio_id)
    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404
    svc = CityBrandingService()
    asset_key = svc.get_asset_object_key(municipio, asset_kind)
    try:
        data, ctype = svc.load_asset(municipio, asset_kind)
    except LookupError as e:
        return jsonify({"erro": str(e)}), 404
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except StorageUnavailableError as e:
        logging.error(
            "Storage indisponível city_id=%s asset=%s key=%s erro=%s",
            municipio_id,
            asset_kind,
            asset_key,
            e,
            exc_info=True,
        )
        return jsonify({"erro": "Armazenamento de branding indisponível no momento"}), 503
    except Exception as e:
        logging.error(
            "Erro ao servir branding city_id=%s asset=%s key=%s erro=%s",
            municipio_id,
            asset_kind,
            asset_key,
            e,
            exc_info=True,
        )
        return jsonify({"erro": "Erro ao carregar asset de branding"}), 500
    return send_file(
        BytesIO(data),
        mimetype=ctype,
        as_attachment=False,
        max_age=3600,
    )


@bp.route("<string:municipio_id>/branding", methods=["GET"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def obter_branding_municipio(municipio_id):
    user = get_current_user_from_token()
    denied = _ensure_municipio_access(user, municipio_id)
    if denied:
        return denied
    municipio = City.query.get(municipio_id)
    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    svc = CityBrandingService()
    logo_key = svc.get_asset_object_key(municipio, "logo")
    letterhead_image_key = svc.get_asset_object_key(municipio, "letterhead_image")
    letterhead_pdf_key = svc.get_asset_object_key(municipio, "letterhead_pdf")

    logo_url = (
        _branding_proxy_url("city.get_branding_logo", municipio.id)
        if logo_key and svc.asset_exists(logo_key)
        else None
    )
    letterhead_image_url = (
        _branding_proxy_url("city.get_branding_letterhead_image", municipio.id)
        if letterhead_image_key and svc.asset_exists(letterhead_image_key)
        else None
    )
    letterhead_pdf_url = (
        _branding_proxy_url("city.get_branding_letterhead_pdf", municipio.id)
        if letterhead_pdf_key and svc.asset_exists(letterhead_pdf_key)
        else None
    )
    # Campo `presigned` mantido por compatibilidade de contrato com o frontend,
    # mas o conteúdo agora são URLs servidas pelo próprio backend (proxy autenticado
    # que baixa do MinIO interno). Isso evita expor o storage diretamente e remove
    # a dependência do hostname público (files.afirmeplay.com.br) na URL final.
    urls = {
        "logo_url": logo_url,
        "letterhead_image_url": letterhead_image_url,
        "letterhead_pdf_url": letterhead_pdf_url,
    }
    return jsonify({
        "city_id": municipio.id,
        "logo_object_key": logo_key if logo_url else None,
        "letterhead_image_object_key": letterhead_image_key if letterhead_image_url else None,
        "letterhead_pdf_object_key": letterhead_pdf_key if letterhead_pdf_url else None,
        "presigned": urls,
        "urls": urls,
    })


@bp.route("<string:municipio_id>/branding/logo", methods=["GET"])
@jwt_required(locations=["headers", "query_string"])
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def get_branding_logo(municipio_id):
    """Proxy autenticado: devolve os bytes do logo armazenado no MinIO."""
    return _serve_branding_asset(municipio_id, "logo")


@bp.route("<string:municipio_id>/branding/letterhead/image", methods=["GET"])
@jwt_required(locations=["headers", "query_string"])
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def get_branding_letterhead_image(municipio_id):
    """Proxy autenticado: PNG do timbrado (primeira página renderizada)."""
    return _serve_branding_asset(municipio_id, "letterhead_image")


@bp.route("<string:municipio_id>/branding/letterhead/pdf", methods=["GET"])
@jwt_required(locations=["headers", "query_string"])
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def get_branding_letterhead_pdf(municipio_id):
    """Proxy autenticado: PDF original do timbrado."""
    return _serve_branding_asset(municipio_id, "letterhead_pdf")


@bp.route("<string:municipio_id>/branding/logo", methods=["POST"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "tecadm")
def upload_branding_logo_municipio(municipio_id):
    user = get_current_user_from_token()
    denied = _ensure_municipio_access(user, municipio_id)
    if denied:
        return denied
    municipio = City.query.get(municipio_id)
    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    replace = request.args.get("replace", "false").lower() in ("1", "true", "yes")
    if "file" not in request.files:
        return jsonify({"erro": "Campo multipart 'file' obrigatório"}), 400
    f = request.files["file"]
    raw = f.read()
    try:
        svc = CityBrandingService()
        svc.upload_logo(municipio, raw, replace=replace)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 409 if "replace" in str(e).lower() or "Já existe" in str(e) else 400
    except RuntimeError as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500

    logo_url = _branding_proxy_url("city.get_branding_logo", municipio.id)
    return jsonify({
        "mensagem": "Logo atualizado",
        "logo_object_key": municipio.logo_url,
        "presigned": logo_url,
        "url": logo_url,
    })


@bp.route("<string:municipio_id>/branding/letterhead", methods=["POST"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "tecadm")
def upload_branding_letterhead_municipio(municipio_id):
    user = get_current_user_from_token()
    denied = _ensure_municipio_access(user, municipio_id)
    if denied:
        return denied
    municipio = City.query.get(municipio_id)
    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    replace = request.args.get("replace", "false").lower() in ("1", "true", "yes")
    store_pdf = request.args.get("store_pdf", "true").lower() in ("1", "true", "yes")
    if "file" not in request.files:
        return jsonify({"erro": "Campo multipart 'file' obrigatório"}), 400
    f = request.files["file"]
    raw = f.read()
    try:
        svc = CityBrandingService()
        svc.upload_letterhead_pdf(municipio, raw, replace=replace, store_pdf=store_pdf)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        msg = str(e)
        code = 409 if "replace" in msg.lower() or "Já existe" in msg else 400
        return jsonify({"erro": msg}), code
    except RuntimeError as e:
        db.session.rollback()
        msg = str(e).lower()
        code = 503 if "poppler" in msg or "pdf2image" in msg else 500
        return jsonify({"erro": str(e)}), code

    letterhead_image_url = (
        _branding_proxy_url("city.get_branding_letterhead_image", municipio.id)
        if municipio.letterhead_image_url else None
    )
    letterhead_pdf_url = (
        _branding_proxy_url("city.get_branding_letterhead_pdf", municipio.id)
        if municipio.letterhead_pdf_url else None
    )
    urls = {
        "letterhead_image_url": letterhead_image_url,
        "letterhead_pdf_url": letterhead_pdf_url,
    }
    return jsonify({
        "mensagem": "Timbrado atualizado (PNG gerado a partir da primeira página)",
        "letterhead_image_object_key": municipio.letterhead_image_url,
        "letterhead_pdf_object_key": municipio.letterhead_pdf_url,
        "presigned": urls,
        "urls": urls,
    })


@bp.route("<string:municipio_id>/branding", methods=["DELETE"])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "tecadm")
def remover_branding_municipio(municipio_id):
    user = get_current_user_from_token()
    denied = _ensure_municipio_access(user, municipio_id)
    if denied:
        return denied
    municipio = City.query.get(municipio_id)
    if not municipio:
        return jsonify({"erro": "Município não encontrado"}), 404

    logo = request.args.get("logo", "false").lower() in ("1", "true", "yes")
    letterhead = request.args.get("letterhead", "false").lower() in ("1", "true", "yes")
    if not logo and not letterhead:
        return jsonify({"erro": "Informe logo=true e/ou letterhead=true"}), 400
    try:
        CityBrandingService().delete_assets(municipio, logo=logo, letterhead=letterhead)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
    return jsonify({"mensagem": "Branding removido", "city_id": municipio.id})


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

    return jsonify(_serialize_city(municipio))


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

    plan_err = _apply_plan_code_from_payload(municipio, data, user)
    if plan_err:
        return plan_err

    db.session.commit()
    return jsonify({
        "mensagem": "Município atualizado com sucesso",
        **_serialize_city(municipio),
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

    return jsonify([_serialize_city(c) for c in cities])

