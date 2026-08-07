from flask import Blueprint, request, jsonify, g
from app.utils.auth import authenticate_usuario
from app.services.aplicador_user_service import resolve_user_by_login_ident
import datetime
import jwt
from app.models.user import User, RoleEnum
from app.models.school import School  # certifique-se que essa importação está correta
from app.models.student import Student # Import Student model
import logging
import os


SECRET_KEY = os.getenv("JWT_SECRET_KEY")

bp = Blueprint('login', __name__, url_prefix='/login')


def _apply_login_city_from_body(data: dict) -> None:
    """
    Fallback Afirme Ler / app hosts: se o middleware ainda não resolveu município
    (sem X-City-* e sem subdomínio municipal), aceita cityId/citySlug no body.
    """
    from app.utils.tenant_middleware import (
        TenantContext,
        city_id_to_schema_name,
        resolve_city_from_id,
        resolve_city_from_slug,
    )

    tenant_context = getattr(g, "tenant_context", None)
    if tenant_context and getattr(tenant_context, "city_id", None):
        return

    city_id = data.get("cityId") or data.get("city_id")
    city_slug = data.get("citySlug") or data.get("city_slug")
    city = None
    if city_id:
        city = resolve_city_from_id(str(city_id).strip())
        if not city:
            raise ValueError(f"Município não encontrado para o id: {city_id}")
    elif city_slug:
        city = resolve_city_from_slug(str(city_slug).strip().lower())
        if not city:
            raise ValueError(f"Município não encontrado para o slug: {city_slug}")
    else:
        return

    if tenant_context is None:
        tenant_context = TenantContext()
        g.tenant_context = tenant_context
    tenant_context.city_id = city.id
    tenant_context.city_slug = city.slug
    tenant_context.schema = city_id_to_schema_name(city.id)
    tenant_context.has_tenant_context = True


@bp.route('/', methods=['POST', 'OPTIONS'])
def login():
    # Tratar requisições OPTIONS (preflight)
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    # ==========================
    # DEBUG TENANT / SUBDOMÍNIO
    # ==========================
    try:
        from flask import g
        host = request.headers.get('Host')
        origin = request.headers.get('Origin')
        app_env = os.getenv("APP_ENV")
        tenant_context = getattr(g, 'tenant_context', None)
        
        print("=== DEBUG LOGIN TENANT CONTEXT ===")
        print(f"APP_ENV: {app_env}")
        print(f"Host header: {host}")
        print(f"Origin header: {origin}")
        print(f"X-City-ID: {request.headers.get('X-City-ID')}")
        print(f"X-City-Slug: {request.headers.get('X-City-Slug')}")
        if tenant_context:
            print(f"TenantContext.city_id: {tenant_context.city_id}")
            print(f"TenantContext.city_slug: {tenant_context.city_slug}")
            print(f"TenantContext.schema: {tenant_context.schema}")
            print(f"TenantContext.has_tenant_context: {tenant_context.has_tenant_context}")
        else:
            print("TenantContext: None (g.tenant_context não definido)")
        print("=== FIM DEBUG LOGIN TENANT CONTEXT ===")
    except Exception as debug_exc:
        print(f"Erro ao imprimir debug de tenant no login: {debug_exc}")
    
    data = request.get_json(silent=True) or {}
    identificador = data.get('registration')
    password = data.get('password')
    print(identificador, password)
    if not identificador or not password:
        return jsonify({"erro": "Identificador (e-mail ou matrícula) e senha são obrigatórios."}), 400

    try:
        try:
            _apply_login_city_from_body(data)
        except ValueError as city_err:
            return jsonify({"erro": "Município inválido", "mensagem": str(city_err)}), 404

        tenant_context = getattr(g, "tenant_context", None)
        login_city_id = (
            str(tenant_context.city_id)
            if tenant_context and getattr(tenant_context, "city_id", None)
            else None
        )
        usuario = resolve_user_by_login_ident(identificador, login_city_id)

        if not usuario or not authenticate_usuario(usuario, password):
            logging.warning(f"Falha de login para o usuário: {identificador}")
            return jsonify({"erro": "Credenciais inválidas."}), 401

        # ========================================
        # VALIDAÇÃO DE MUNICÍPIO (SEGURANÇA)
        # ========================================
        # Usuários comuns: município via subdomínio municipal, X-City-* ou body
        # (Afirme Ler / localhost). Admin pode logar sem município.
        
        if usuario.role != RoleEnum('admin'):
            tenant_context = getattr(g, 'tenant_context', None)
            
            if not tenant_context or not tenant_context.city_id:
                logging.warning(
                    f"Tentativa de login sem município: "
                    f"Usuário {usuario.email} (role: {usuario.role.value}, city_id: {usuario.city_id})"
                )
                return jsonify({
                    "erro": "Acesso negado",
                    "mensagem": (
                        "Informe o município no login (header X-City-Slug ou X-City-ID, "
                        "ou body citySlug/cityId), ou acesse pelo subdomínio do município "
                        "(ex.: <seu-municipio>.afirmeplay.com.br)."
                    ),
                }), 403
            
            # Validar se o usuário pertence ao município informado
            if usuario.city_id != tenant_context.city_id:
                logging.warning(
                    f"Tentativa de login em município incorreto: "
                    f"Usuário {usuario.email} (city_id: {usuario.city_id}) "
                    f"tentou acessar município {tenant_context.city_id} (slug: {tenant_context.city_slug})"
                )
                return jsonify({
                    "erro": "Acesso negado",
                    "mensagem": "Você não tem permissão para acessar este município. "
                               "Verifique se selecionou o município correto."
                }), 403
        
        tenant_id = None

        # Define o tenant_id com base na role
        if usuario.role == RoleEnum('aluno'):
            # Para aluno, usar city_id direto do usuário
            if not usuario.city_id:
                logging.error(f"Usuário aluno {usuario.id} sem city_id vinculado.")
                return jsonify({"erro": "Aluno não vinculado a um município."}), 400
            
            tenant_id = usuario.city_id
        elif usuario.role == RoleEnum('admin'):
            tenant_id = None # Admin pode ver tudo, sem restrição de tenant
        elif usuario.role == RoleEnum('tecadm'):
            # Tecadm deve ter city_id definido
            if not usuario.city_id:
                logging.error(f"Usuário tecadm {usuario.id} sem city_id vinculado.")
                return jsonify({"erro": "Tecadm não vinculado a um município."}), 400
            tenant_id = usuario.city_id
        elif usuario.role == RoleEnum('professor'):
            # Professor deve ter city_id definido
            if not usuario.city_id:
                logging.error(f"Usuário professor {usuario.id} sem city_id vinculado.")
                return jsonify({"erro": "Professor não vinculado a um município."}), 400
            tenant_id = usuario.city_id
        else:
            # Para outras roles (diretor, coordenador), usar city_id do usuário
            if not usuario.city_id:
                 logging.error(f"Usuário {usuario.id} ({usuario.role}) sem city_id vinculado.")
                 return jsonify({"erro": f"{usuario.role} não vinculado a um município."}), 400
            tenant_id = usuario.city_id


        # Buscar informações da cidade (se houver tenant_id)
        from app.models.city import City
        from app.entitlements.plans import DEFAULT_PLAN_CODE
        from app.entitlements.resolver import entitlements_for_city
        city = None
        city_slug = None
        plan_code = None
        entitlements = None
        if tenant_id:
            city = City.query.get(tenant_id)
            if city:
                city_slug = city.slug
                plan_code = city.plan_code or DEFAULT_PLAN_CODE
                entitlements = entitlements_for_city(city)
        
        token_payload = {
            "sub": usuario.id,
            "tenant_id": tenant_id,
            "city_id": tenant_id,  # alias para middleware / persist-user
            "role": usuario.role.value,
            "city_slug": city_slug,  # Incluir slug no token para facilitar resolução
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        }
        if plan_code:
            token_payload["plan_code"] = plan_code

        token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')

        usuario_data = {
            "id": usuario.id,
            "name": usuario.name,
            "email": usuario.email,
            "registration": usuario.registration,
            "tenant_id": tenant_id,
            "city_id": tenant_id,
            "city_slug": city_slug,  # Incluir slug na resposta
            "created_at": usuario.created_at,
            "role": usuario.role.value,
        }
        if plan_code:
            usuario_data["plan_code"] = plan_code
        if entitlements:
            usuario_data["entitlements"] = entitlements

        logging.info(f"Login bem-sucedido para usuário: {usuario.email} com papel: {usuario.role} e tenant_id: {tenant_id}")
        response = jsonify({
            "mensagem": "Login bem-sucedido.",
            "user": usuario_data,
            "token": token
        })
        
        # Não adicionar headers CORS explicitamente aqui - deixar o Flask-CORS gerenciar
        
        return response
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"ERRO NO LOGIN - Identificador: {identificador}")
        print(f"ERRO: {str(e)}")
        print(f"TRACEBACK COMPLETO:\n{error_traceback}")
        logging.error(f"Erro inesperado durante o login para identificador {identificador}: {e}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro interno no servidor."}), 500

@bp.route('/test', methods=['GET', 'OPTIONS'])
def test_cors():
    """Endpoint de teste para verificar se o CORS está funcionando"""
    if request.method == 'OPTIONS':
        return jsonify({"message": "CORS preflight OK"}), 200
    
    return jsonify({
        "message": "CORS está funcionando!",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }), 200
