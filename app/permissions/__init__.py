"""
Módulo de Permissões Centralizado
=================================

Autor: Sistema de Refatoração de Permissões
Data de criação: 2025-01-XX

Descrição:
    Este módulo centraliza toda a lógica de permissões da aplicação Flask,
    organizando roles, decoradores, regras de acesso e filtros de queries.

Módulos:
    - roles: Constantes e utilitários de papéis
    - utils: Funções auxiliares para busca de vínculos
    - decorators: Decoradores de rota (como @role_required)
    - rules: Funções de permissão de alto nível (pode ver, pode editar, etc.)
    - query_filters: Filtros SQLAlchemy aplicáveis a queries
"""

from .decorators import role_required, get_current_user_from_token, get_current_tenant_id
from .rules import (
    can_view_test,
    can_edit_test,
    can_view_school,
    can_view_class,
    can_view_results,
    get_user_permission_scope
)
from .query_filters import (
    filter_schools_by_user,
    filter_classes_by_user,
    filter_tests_by_user,
    filter_students_by_user
)
from .utils import (
    get_teacher_schools,
    get_manager_school,
    get_user_scope,
    get_teacher_classes
)

__all__ = [
    # Decorators
    'role_required',
    'get_current_user_from_token',
    'get_current_tenant_id',
    # Rules
    'can_view_test',
    'can_edit_test',
    'can_view_school',
    'can_view_class',
    'can_view_results',
    'get_user_permission_scope',
    # Query Filters
    'filter_schools_by_user',
    'filter_classes_by_user',
    'filter_tests_by_user',
    'filter_students_by_user',
    # Utils
    'get_teacher_schools',
    'get_manager_school',
    'get_user_scope',
    'get_teacher_classes',
]
