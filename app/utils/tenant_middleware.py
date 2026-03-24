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
from sqlalchemy import text
from app import db
from app.models.city import City
from app.models.user import User, RoleEnum

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
# Ambiente da aplicação: "production", "development", etc.
APP_ENV = os.getenv("APP_ENV", "development").lower()
SUBDOMAIN_MODE = os.getenv("SUBDOMAIN_MODE", "standard").strip().lower()
DEMO_SUBDOMAIN_SUFFIX = "-demo"

# Domínios que devem ser ignorados na resolução de subdomínio
IGNORED_HOSTS = [
    'afirmeplay.com.br',
    'www.afirmeplay.com.br',
    'api.afirmeplay.com.br',
    'files.afirmeplay.com.br',
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


def normalize_city_slug_from_subdomain(slug):
    """
    Normaliza o slug extraído do host para o slug real salvo em public.city.

    Modos:
        - standard: usa slug como está (ex: city)
        - demo_suffix: exige sufixo '-demo' e remove para buscar cidade (ex: city-demo -> city)
    """
    if not slug or not isinstance(slug, str):
        return None

    slug = slug.strip().lower()
    if not re.match(r'^[a-z0-9-]+$', slug):
        return None

    if SUBDOMAIN_MODE == "demo_suffix":
        if not slug.endswith(DEMO_SUBDOMAIN_SUFFIX):
            return None
        base_slug = slug[:-len(DEMO_SUBDOMAIN_SUFFIX)]
        if not base_slug or not re.match(r'^[a-z0-9-]+$', base_slug):
            return None
        return base_slug

    return slug


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
            slug = normalize_city_slug_from_subdomain(parts[0])
            if slug:
                return slug
        
        return None
    
    # ================================
    # Ambiente de DESENVOLVIMENTO
    # ================================
    # Em desenvolvimento, aceitamos tanto afirmeplay.com.br quanto *.localhost
    
    # 1) Regra original para afirmeplay.com.br (para testes locais apontando para esse domínio)
    if 'afirmeplay.com.br' in host:
        parts = host.split('.')
        if len(parts) > 3:
            slug = normalize_city_slug_from_subdomain(parts[0])
            if slug:
                return slug
    
    # 2) Suporte a subdomínios em localhost: ex: jiparana.localhost, jaru.localhost
    if host.endswith('.localhost'):
        parts = host.split('.')
        # Ex: ["jiparana", "localhost"]
        if len(parts) >= 2:
            slug = normalize_city_slug_from_subdomain(parts[0])
            if slug:
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
            if not slug and APP_ENV != "production":
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
            
            # 3.3. Admin sem contexto - usa apenas public
            context.schema = 'public'
            context.has_tenant_context = False
            return context
    
    # 4. Sem autenticação - verificar subdomínio para acesso público (se aplicável)
    host = request.headers.get('Host')
    slug = extract_subdomain(host)
    
    # Em desenvolvimento, se o backend estiver em localhost (sem subdomínio),
    # usar o Origin do frontend para extrair o slug (ex: jaru.localhost)
    if not slug and APP_ENV != "production":
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
    Garante que o search_path está no schema do tenant (city_xxx) quando for
    necessário consultar tabelas por-tenant (ex.: student). Use antes de
    Student.query quando o path atual pode ser public (ex.: após get_competition_or_404).

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
    Define o search_path do PostgreSQL para o request atual.
    
    Args:
        schema: String com o schema ou lista de schemas
        
    Note:
        - O search_path é definido por sessão/conexão e vale imediatamente.
        - NÃO fazemos commit() aqui para que a mesma conexão (com o path setado)
          seja usada nas próximas queries do mesmo request; commit() devolveria
          a conexão ao pool e a próxima query poderia usar outra (com path em public).
        - Se a transação estiver abortada (erro anterior), faz rollback e tenta novamente.
        
    Examples:
        >>> set_search_path('city_123')
        # Define: SET search_path TO city_123, public
        
        >>> set_search_path('public')
        # Define: SET search_path TO public
    """
    if schema != 'public':
        search_path = f'"{schema}", public'
    else:
        search_path = "public"
    sql = text(f"SET search_path TO {search_path}")

    try:
        db.session.execute(sql)
    except Exception as e:
        err_msg = str(e).lower()
        if "aborted" in err_msg or "infailedsqltransaction" in err_msg or "current transaction" in err_msg:
            try:
                db.session.rollback()
                db.session.execute(sql)
                return
            except Exception as retry_e:
                print(f"Erro ao definir search_path (após rollback): {retry_e}")
                db.session.rollback()
                raise retry_e
        print(f"Erro ao definir search_path: {e}")
        db.session.rollback()
        raise


def tenant_middleware():
    """
    Middleware Flask para resolução automática de tenant por request.
    
    Este middleware deve ser registrado no create_app() usando:
        @app.before_request
        
    Funcionalidade:
        1. Resolve o contexto do tenant
        2. Define o search_path no PostgreSQL
        3. Armazena contexto no flask.g
        4. Trata erros de autenticação/autorização
        
    Raises:
        400: Erro na resolução do contexto
        404: Município não encontrado
    """
    try:
        # Resolver contexto do tenant
        context = resolve_tenant_context()
        
        # Armazenar contexto no flask.g para acesso global
        g.tenant_context = context
        
        # Definir search_path
        set_search_path(context.schema)
        
    except Exception as e:
        error_message = str(e)
        
        if "não encontrado" in error_message.lower():
            return jsonify({"erro": error_message}), 404
        else:
            return jsonify({"erro": f"Erro ao resolver contexto do tenant: {error_message}"}), 400


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
