"""
Decorator para Exigir Contexto de Cidade (Tenant)
==================================================

Autor: Sistema Multi-Tenant
Data de criação: 2026-02-10

Descrição:
    Este decorator garante que rotas tenant-specific só possam ser
    acessadas quando há um contexto de cidade válido definido.

Uso:
    @bp.route('/school', methods=['GET'])
    @jwt_required()
    @role_required("admin", "diretor")
    @requires_city_context  # ← Bloqueia se não houver city_id
    def listar_escolas():
        context = get_current_tenant_context()
        # Pode usar context.city_id com segurança
        return jsonify(...)

Comportamento:
    - Se há contexto de cidade (has_tenant_context=True) → Permite acesso
    - Se NÃO há contexto de cidade → Retorna 403 com mensagem explicativa
    
    Casos:
    1. Usuário comum → Sempre tem contexto (city_id obrigatório)
    2. Admin com X-City-ID/Slug → Tem contexto (cidade escolhida)
    3. Admin sem header/subdomain → NÃO tem contexto (bloqueado)

Segurança:
    - Impede admin de acessar rotas tenant sem especificar cidade
    - Protege contra queries sem filtro de tenant
    - Garante que search_path está correto antes da query
"""

from functools import wraps
from flask import jsonify, g
import logging

logger = logging.getLogger(__name__)


def requires_city_context(f):
    """
    Decorator que exige contexto de cidade válido para acessar a rota.
    
    Args:
        f: Função decorada (rota Flask)
        
    Returns:
        Função wrapper que valida contexto antes de executar
        
    Raises:
        403: Se não houver contexto de cidade válido
        
    Example:
        >>> @bp.route('/escolas')
        >>> @jwt_required()
        >>> @role_required("admin", "diretor")
        >>> @requires_city_context
        >>> def listar_escolas():
        >>>     context = get_current_tenant_context()
        >>>     return jsonify({"city_id": context.city_id})
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Obter contexto do tenant armazenado pelo middleware
        context = getattr(g, 'tenant_context', None)
        
        # Validar se contexto existe
        if context is None:
            logger.error(
                f"Tentativa de acessar rota tenant sem contexto: {f.__name__}"
            )
            return jsonify({
                "erro": "Contexto de tenant não encontrado",
                "mensagem": "O middleware de resolução de tenant não foi executado corretamente",
                "detalhes": "Contate o administrador do sistema"
            }), 500
        
        # Validar se há contexto de cidade
        if not context.has_tenant_context:
            # Verificar se é admin (pode fornecer contexto via headers)
            if context.is_admin:
                logger.warning(
                    f"Admin tentou acessar rota tenant sem contexto: {f.__name__} | "
                    f"user_id: {context.user_id}"
                )
                return jsonify({
                    "erro": "Contexto de cidade obrigatório para esta operação",
                    "mensagem": (
                        "Esta rota exige que você especifique um município. "
                        "Forneça um dos seguintes headers:"
                    ),
                    "opcoes": [
                        "X-City-ID: <uuid-da-cidade>",
                        "X-City-Slug: <slug-da-cidade>"
                    ],
                    "alternativa": "Ou acesse via subdomínio: <slug>.afirmeplay.com.br"
                }), 403
            else:
                # Usuário comum sem city_id (não deveria acontecer)
                logger.error(
                    f"Usuário comum sem city_id tentou acessar rota tenant: {f.__name__} | "
                    f"user_id: {context.user_id}, role: {context.user_role}"
                )
                return jsonify({
                    "erro": "Usuário não vinculado a um município",
                    "mensagem": "Seu usuário não possui um município associado. Contate o administrador.",
                    "detalhes": "Usuários comuns devem ter city_id definido"
                }), 403
        
        # Contexto válido - permitir acesso
        logger.debug(
            f"Acesso autorizado à rota tenant: {f.__name__} | "
            f"city_id: {context.city_id}, schema: {context.schema}, "
            f"user_role: {context.user_role}"
        )
        
        return f(*args, **kwargs)
    
    return wrapper


def get_current_tenant_context():
    """
    Função auxiliar para obter o contexto do tenant atual.
    
    Esta função é um helper para acessar o contexto armazenado
    pelo middleware em flask.g.
    
    Returns:
        TenantContext ou None se não disponível
        
    Usage:
        >>> context = get_current_tenant_context()
        >>> if context and context.has_tenant_context:
        >>>     print(f"City: {context.city_id}")
        >>>     print(f"Schema: {context.schema}")
        >>>     print(f"Slug: {context.city_slug}")
        
    Note:
        Esta função SEMPRE deve ser chamada APÓS o middleware
        tenant_middleware ter sido executado (via @app.before_request).
    """
    return getattr(g, 'tenant_context', None)


def validate_tenant_access(city_id):
    """
    Valida se o usuário atual tem permissão para acessar o município especificado.
    
    Esta função é útil para validações extras em rotas que recebem
    city_id como parâmetro ou query string.
    
    Args:
        city_id: UUID do município a ser acessado
        
    Returns:
        (bool, str): (permitido, mensagem_erro)
        
    Example:
        >>> @bp.route('/school/<city_id>')
        >>> @jwt_required()
        >>> @requires_city_context
        >>> def get_school(city_id):
        >>>     permitido, erro = validate_tenant_access(city_id)
        >>>     if not permitido:
        >>>         return jsonify({"erro": erro}), 403
        >>>     # Continuar...
    """
    context = get_current_tenant_context()
    
    if context is None:
        return False, "Contexto de tenant não encontrado"
    
    # Admin pode acessar qualquer cidade desde que tenha definido contexto
    if context.is_admin:
        # Verificar se o contexto atual corresponde ao city_id solicitado
        if context.city_id != city_id:
            return False, (
                f"Contexto atual é para cidade {context.city_id}, "
                f"mas tentando acessar {city_id}. "
                f"Atualize o header X-City-ID."
            )
        return True, None
    
    # Usuário comum só pode acessar sua própria cidade
    if context.city_id != city_id:
        logger.warning(
            f"Usuário {context.user_role} tentou acessar cidade diferente: "
            f"permitido={context.city_id}, tentado={city_id}"
        )
        return False, "Você não tem permissão para acessar este município"
    
    return True, None
