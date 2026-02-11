"""
Pacote de Decorators
====================

Exporta decorators para controle de acesso e contexto de tenant.
"""

from .tenant_required import (
    requires_city_context,
    get_current_tenant_context,
    validate_tenant_access
)

__all__ = [
    'requires_city_context',
    'get_current_tenant_context',
    'validate_tenant_access'
]
