"""
Middleware de Resolução de Schema Multi-Tenant
===============================================

Autor: Sistema de Implementação Multi-Tenant
Data de criação: 2026-02-10

Descrição:
    Este módulo implementa a resolução automática de schema PostgreSQL por request,
    garantindo isolamento completo entre municípios (tenants) e segurança de acesso.

Regras de Resolução:
    1. Usuário comum (city_id obrigatório):
       - Usa SEMPRE: city_<city_id>, public
       - NÃO pode trocar de município
       - TecAdm segue essa mesma regra

    2. Admin sem contexto:
       - Usa APENAS: public
       - Pode acessar rotas globais
       - NÃO pode acessar rotas tenant

    3. Admin com contexto:
       - Contexto via X-City-ID ou X-City-Slug
       - Usa: city_<city_id>, public
       - Pode acessar rotas tenant

    4. Subdomínio:
       - Extrai slug do Host header
       - Resolve city_id via public.city.slug
       - Define schema tenant
       - Produção: *.afirmeplay.com.br | Homologação: *.afirmeplay.com

Prioridade de Resolução:
    1. Token JWT city_id (usuário comum)
    2. Header X-City-ID ou X-City-Slug (admin)
    3. Subdomínio do Host
    4. Fallback para public (apenas admin)

Segurança:
    - Validação obrigatória de permissões
    - Isolamento por request
    - Sem vazamento entre tenants
    - Compatible com SQLAlchemy pool de conexões
"""

from functools import wraps
from flask import request, jsonify, g
import jwt
import os
import re
from app import db
from app.models.city import City
from app.models.user import User, RoleEnum
from app.multitenant.db_session_factory import DatabaseSessionFactory
from app.multitenant.tenant_resolver import TenantResolver

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
# Ambiente: development (local), homolog (*.afirmeplay.com), production (*.afirmeplay.com.br)
APP_ENV = os.getenv("APP_ENV", "development").lower()


def _allow_subdomain_from_origin_when_host_has_no_slug():
    """Só em desenvolvimento local: Host sem slug (ex.: API em localhost) e slug no Origin."""
    return APP_ENV == "development"


# Domínios que devem ser ignorados na resolução de subdomínio
IGNORED_HOSTS = [
    'afirmeplay.com.br',
    'www.afirmeplay.com.br',
    'api.afirmeplay.com.br',
    'files.afirmeplay.com.br',
    'afirmeplay.com',
    'www.afirmeplay.com',
    'api.afirmeplay.com',
    'files.afirmeplay.com',
    'localhost',
    '127.0.0.1'
]


class TenantContext:
    """
    Classe para armazenar o contexto do tenant no request atual.
    """
    def __init__(self):
        self.city_id = None
        self.city_slug = None
        self.schema = 'public'
        self.user_id = None
        self.user_role = None
        self.is_admin = False
        self.has_tenant_context = False


def city_id_to_schema_name(city_id):
    """
    Converte city_id (UUID com hífens) no nome do schema PostgreSQL.
    No banco os schemas são criados com underscores (ex: city_9a2f95ed_9f70_4863_a5f1_1b6c6c262b0d).
    """
    if not city_id:
        return 'public'
    return f"city_{str(city_id).replace('-', '_')}"


def extract_subdomain(host):
    """
    Extrai o slug do subdomínio do Host header.
    
    Args:
        host: String com o host completo (ex: jiparana.afirmeplay.com.br)
        
    Returns:
        String com o slug ou None se não for um subdomínio válido
        
    Examples:
        >>> extract_subdomain('jiparana.afirmeplay.com.br')
        'jiparana'
        >>> extract_subdomain('jiparana.afirmeplay.com')  # com APP_ENV=homolog
        'jiparana'
        >>> extract_subdomain('afirmeplay.com.br')
        None
        >>> extract_subdomain('api.afirmeplay.com.br')
        None
    """
    if not host:
        return None
    
    # Remover esquema se vier de Origin (ex: http://jaru.localhost:8080)
    if '://' in host:
        host = host.split('://', 1)[1]
    
    # Remover porta se existir (ex: jiparana.afirmeplay.com.br:443 -> jiparana.afirmeplay.com.br)
    host = host.split(':')[0]
    
    # Verificar se é um host ignorado (sem subdomínio)
    if host in IGNORED_HOSTS:
        return None
    
    # ================================
    # Ambiente de PRODUÇÃO
    # ================================
    # Em produção, aceitamos apenas subdomínios de afirmeplay.com.br
    if APP_ENV == "production":
        if 'afirmeplay.com.br' not in host:
            return None
        
        parts = host.split('.')
        # Exemplo válido: jiparana.afirmeplay.com.br
        if len(parts) > 3:
            slug = parts[0]
            if re.match(r'^[a-z0-9-]+$', slug):
                return slug
        
        return None
    
    # ================================
    # Ambiente de HOMOLOGAÇÃO (*.afirmeplay.com)
    # ================================
    # Mesmo comportamento que produção quanto a Host/Origin; domínio base .com (sem .br).
    if APP_ENV == "homolog":
        if host.endswith(".afirmeplay.com.br"):
            return None
        if not host.endswith(".afirmeplay.com"):
            return None
        parts = host.split(".")
        # slug.afirmeplay.com → ex.: jaru.afirmeplay.com
        if len(parts) == 3 and parts[1] == "afirmeplay" and parts[2] == "com":
            slug = parts[0]
            if re.match(r"^[a-z0-9-]+$", slug):
                return slug
        return None
    
    # ================================
    # Ambiente de DESENVOLVIMENTO
    # ================================
    # Em desenvolvimento, aceitamos afirmeplay.com.br, afirmeplay.com e *.localhost
    
    # 1) Regra original para afirmeplay.com.br (para testes locais apontando para esse domínio)
    if 'afirmeplay.com.br' in host:
        parts = host.split('.')
        if len(parts) > 3:
            slug = parts[0]
            if re.match(r'^[a-z0-9-]+$', slug):
                return slug
    
    # 1b) *.afirmeplay.com (paridade com homolog em testes locais / hosts)
    if host.endswith('.afirmeplay.com') and not host.endswith('.afirmeplay.com.br'):
        parts = host.split('.')
        if len(parts) == 3 and parts[1] == 'afirmeplay' and parts[2] == 'com':
            slug = parts[0]
            if re.match(r'^[a-z0-9-]+$', slug):
                return slug
    
    # 2) Suporte a subdomínios em localhost: ex: jiparana.localhost, jaru.localhost
    if host.endswith('.localhost'):
        parts = host.split('.')
        # Ex: ["jiparana", "localhost"]
        if len(parts) >= 2:
            slug = parts[0]
            if re.match(r'^[a-z0-9-]+$', slug):
                return slug
    
    return None


def resolve_city_from_slug(slug):
    """
    Resolve o city_id a partir do slug.
    
    Args:
        slug: String com o slug do município
        
    Returns:
        Objeto City ou None se não encontrado
        
    Note:
        Esta função faz query no schema 'public' para buscar a cidade.
    """
    if not slug:
        return None
    
    try:
        # Garantir que estamos buscando no schema public
        city = City.query.filter_by(slug=slug).first()
        return city
    except Exception as e:
        print(f"Erro ao buscar cidade pelo slug {slug}: {e}")
        return None


def resolve_city_from_id(city_id):
    """
    Resolve o city a partir do city_id.
    
    Args:
        city_id: UUID da cidade
        
    Returns:
        Objeto City ou None se não encontrado
    """
    if not city_id:
        return None
    
    try:
        city = City.query.get(city_id)
        return city
    except Exception as e:
        print(f"Erro ao buscar cidade pelo ID {city_id}: {e}")
        return None


def get_user_from_token():
    """
    Extrai informações do usuário do token JWT.
    
    Returns:
        Dict com informações do usuário ou None se token inválido
        {
            'user_id': str,
            'tenant_id': str,
            'role': str
        }
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        # Aceitar tanto tenant_id quanto city_id no JWT (login emite city_id)
        tenant_id = payload.get('tenant_id') or payload.get('city_id')
        return {
            'user_id': payload.get('sub'),
            'tenant_id': tenant_id,
            'role': payload.get('role')
        }
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _resolve_mobile_offline_pack_redeem_preflight():
    """
    POST /offline-pack/redeem: começa em public para consultar mobile_offline_pack_registry
    pelo hash; a rota depois fixa o tenant via bind_tenant_context_for_redeem.
    """
    ctx = TenantContext()
    ctx.schema = "public"
    ctx.has_tenant_context = False
    return ctx


def _resolve_mobile_login_tenant_context():
    """
    Login mobile sem JWT: exige X-City-ID, X-City-Slug ou subdomínio do município.
    Isolado de fluxos web; usado apenas para POST/OPTIONS em /mobile/v1/auth/login.
    """
    context = TenantContext()
    city = None
    city_id_header = request.headers.get("X-City-ID")
    city_slug_header = request.headers.get("X-City-Slug")
    if city_id_header:
        city = resolve_city_from_id(city_id_header)
    elif city_slug_header:
        city = resolve_city_from_slug(city_slug_header)
    if not city:
        host = request.headers.get("Host")
        slug = extract_subdomain(host)
        if not slug and _allow_subdomain_from_origin_when_host_has_no_slug():
            slug = extract_subdomain(request.headers.get("Origin"))
        if slug:
            city = resolve_city_from_slug(slug)
    if not city:
        print(
            "[mobile/v1/auth/login] Falha ao resolver município — "
            f"X-City-ID={request.headers.get('X-City-ID')!r} "
            f"X-City-Slug={request.headers.get('X-City-Slug')!r} "
            f"Host={request.headers.get('Host')!r} "
            f"Origin={request.headers.get('Origin')!r}"
        )
        raise Exception(
            "Para login mobile informe X-City-ID ou X-City-Slug ou acesse via subdomínio do município."
        )
    context.city_id = city.id
    context.city_slug = city.slug
    context.schema = city_id_to_schema_name(city.id)
    context.has_tenant_context = True
    return context


def resolve_tenant_context():
    """
    Resolve o contexto do tenant para o request atual.
    
    Esta função implementa a lógica completa de resolução de schema,
    seguindo as regras de prioridade e segurança.
    
    Returns:
        TenantContext com o contexto resolvido
        
    Raises:
        401: Token inválido ou expirado
        403: Usuário tentando acessar município não autorizado
        404: Município não encontrado
    """
    path = request.path.rstrip("/")
    if path.endswith("/mobile/v1/auth/login") and request.method in ("POST", "OPTIONS"):
        return _resolve_mobile_login_tenant_context()
    if path.endswith("/mobile/v1/offline-pack/redeem") and request.method == "POST":
        return _resolve_mobile_offline_pack_redeem_preflight()

    context = TenantContext()
    
    # 1. Extrair informações do token JWT
    user_info = get_user_from_token()
    
    if user_info:
        context.user_id = user_info['user_id']
        context.user_role = user_info['role']
        context.is_admin = (user_info['role'] == 'admin')
        
        # 2. Resolver para usuário comum (inclui TecAdm, aluno, professor, etc.)
        if not context.is_admin:
            city_id = user_info.get('tenant_id') or user_info.get('city_id')
            # Se o token não trouxe tenant_id/city_id, buscar na tabela User (public.users)
            if not city_id:
                user_obj = User.query.get(user_info['user_id'])
                if user_obj and getattr(user_obj, 'city_id', None):
                    city_id = str(user_obj.city_id)
            if city_id:
                context.city_id = city_id
                context.has_tenant_context = True
                city = resolve_city_from_id(context.city_id)
                if not city:
                    raise Exception("Município não encontrado para o tenant_id do usuário. Verifique se a cidade existe em public.city.")
                context.city_slug = city.slug
                context.schema = city_id_to_schema_name(context.city_id)
                return context
        
        # 3. Resolver para Admin
        if context.is_admin:
            # 3.1. Verificar headers X-City-ID ou X-City-Slug
            city_id_header = request.headers.get('X-City-ID')
            city_slug_header = request.headers.get('X-City-Slug')
            
            city = None
            if city_id_header:
                city = resolve_city_from_id(city_id_header)
            elif city_slug_header:
                city = resolve_city_from_slug(city_slug_header)
            
            if city:
                context.city_id = city.id
                context.city_slug = city.slug
                context.schema = city_id_to_schema_name(city.id)
                context.has_tenant_context = True
                return context
            
            # 3.2. Verificar subdomínio (Host em produção, Origin em dev/local)
            host = request.headers.get('Host')
            slug = extract_subdomain(host)
            
            # Em desenvolvimento, se o backend estiver em localhost (sem subdomínio),
            # usar o Origin do frontend para extrair o slug (ex: jaru.localhost)
            if not slug and _allow_subdomain_from_origin_when_host_has_no_slug():
                origin = request.headers.get('Origin')
                slug = extract_subdomain(origin)
            
            if slug:
                city = resolve_city_from_slug(slug)
                if city:
                    context.city_id = city.id
                    context.city_slug = city.slug
                    context.schema = city_id_to_schema_name(city.id)
                    context.has_tenant_context = True
                    return context
                else:
                    # Subdomínio inválido
                    raise Exception(f"Município não encontrado para o slug: {slug}")

            # 3.2b. Rotas /mobile/v1/*: JWT emitido no login mobile traz city_id em tenant_id
            if request.path.startswith('/mobile/v1/'):
                tid = user_info.get('tenant_id')
                if tid:
                    city = resolve_city_from_id(tid)
                    if city:
                        context.city_id = city.id
                        context.city_slug = city.slug
                        context.schema = city_id_to_schema_name(city.id)
                        context.has_tenant_context = True
                        return context
            
            # 3.3. Admin sem contexto - usa apenas public
            context.schema = 'public'
            context.has_tenant_context = False
            return context
    
    # 4. Sem autenticação - verificar subdomínio para acesso público (se aplicável)
    host = request.headers.get('Host')
    slug = extract_subdomain(host)
    
    # Em desenvolvimento, se o backend estiver em localhost (sem subdomínio),
    # usar o Origin do frontend para extrair o slug (ex: jaru.localhost)
    if not slug and _allow_subdomain_from_origin_when_host_has_no_slug():
        origin = request.headers.get('Origin')
        slug = extract_subdomain(origin)
    
    if slug:
        city = resolve_city_from_slug(slug)
        if city:
            context.city_id = city.id
            context.city_slug = city.slug
            context.schema = city_id_to_schema_name(city.id)
            context.has_tenant_context = True
            return context
        else:
            raise Exception(f"Município não encontrado para o slug: {slug}")
    
    # 5. Fallback: usar apenas public
    context.schema = 'public'
    context.has_tenant_context = False
    return context


def ensure_tenant_schema_for_user(user_id):
    """
    Garante o bind ORM para o schema do tenant (city_xxx) quando for necessário
    consultar tabelas por-tenant (ex.: student). Use antes de Student.query quando
    o bind atual pode ser public (ex.: após get_competition_or_404).

    Returns:
        True se o schema foi definido ou já era tenant; False se não foi possível
        (ex.: User sem city_id) - a rota deve retornar 400.
    """
    from flask import g
    ctx = getattr(g, "tenant_context", None)
    if ctx and getattr(ctx, "has_tenant_context", False):
        schema = getattr(ctx, "schema", "public")
        if schema and schema != "public":
            set_search_path(schema)  # garantir path mesmo quando contexto já existe (path pode ter sido trocado)
            return True
    user_obj = User.query.get(user_id)
    if user_obj and getattr(user_obj, "city_id", None):
        schema = city_id_to_schema_name(str(user_obj.city_id))
        set_search_path(schema)
        return True
    return False


def set_search_path(schema):
    """
    Compat: antes executava ``SET search_path`` no PostgreSQL; agora ajusta apenas o
    bind ORM via ``schema_translate_map`` (ver ``TenantAwareSession`` / ``physical_schema_binding``).
    """
    from app.multitenant.physical_schema_binding import set_physical_schema_override

    s = str(schema).strip() if schema is not None else "public"
    if s == "public":
        set_physical_schema_override(None)
    else:
        set_physical_schema_override(s)


def _register_multitenant_sessions(context: TenantContext) -> None:
    """
    Registra `g.request_context` e `g.public_session`.

    A tradução `tenant` → schema físico (`city_*`) é feita em `TenantAwareSession`
    (`db.session` / `Model.query`) via `schema_translate_map` no `get_bind`.
    """
    engine = db.engine

    g.request_context = TenantResolver.request_context_from_tenant_context(context, request)

    g.public_session = DatabaseSessionFactory.get_public_session(engine)
    g.tenant_session = None


def tenant_middleware():
    """
    Middleware Flask para resolução automática de tenant por request.
    
    Este middleware deve ser registrado no create_app() usando:
        @app.before_request
        
    Funcionalidade:
        1. Resolve o contexto do tenant
        2. Registra g.request_context e g.public_session; tradução tenant→city_* via db.session (TenantAwareSession)
        3. Armazena contexto no flask.g
        4. Trata erros de autenticação/autorização
        
    Raises:
        400: Erro na resolução do contexto
        404: Município não encontrado
    """
    try:
        # Rotas públicas que só consultam public.city (ou corpo vazio no preflight):
        # não rodar resolve_tenant_context — JWT/Origin/Host podem disparar 400/404 indevidos.
        path_norm = request.path.rstrip('/')
        if request.path.startswith('/mobile/v1/') and request.method == 'OPTIONS':
            ctx = TenantContext()
            ctx.schema = 'public'
            ctx.has_tenant_context = False
            g.tenant_context = ctx
            _register_multitenant_sessions(ctx)
            return None
        if path_norm.endswith('/subdomain/check') and request.method in ('GET', 'HEAD', 'OPTIONS'):
            ctx = TenantContext()
            ctx.schema = 'public'
            ctx.has_tenant_context = False
            g.tenant_context = ctx
            _register_multitenant_sessions(ctx)
            return None
        # OPTIONS /login/ — preflight CORS; o POST de login ainda resolve tenant normalmente.
        if path_norm.endswith('/login') and request.method == 'OPTIONS':
            ctx = TenantContext()
            ctx.schema = 'public'
            ctx.has_tenant_context = False
            g.tenant_context = ctx
            _register_multitenant_sessions(ctx)
            return None

        # Resolver contexto do tenant
        context = resolve_tenant_context()
        
        # Armazenar contexto no flask.g para acesso global
        g.tenant_context = context

        _register_multitenant_sessions(context)

    except Exception as e:
        error_message = str(e)
        is_mobile = request.path.startswith("/mobile/v1/")

        if "não encontrado" in error_message.lower():
            key = "error" if is_mobile else "erro"
            return jsonify({key: error_message}), 404

        if is_mobile:
            return jsonify({"error": error_message}), 400

        return jsonify(
            {"erro": f"Erro ao resolver contexto do tenant: {error_message}"}
        ), 400


def get_current_tenant_context():
    """
    Obtém o contexto do tenant atual armazenado no flask.g.
    
    Returns:
        TenantContext ou None se não disponível
        
    Usage:
        >>> context = get_current_tenant_context()
        >>> if context.has_tenant_context:
        >>>     print(f"City ID: {context.city_id}")
    """
    return getattr(g, 'tenant_context', None)
