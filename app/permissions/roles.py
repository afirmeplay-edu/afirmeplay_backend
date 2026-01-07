"""
Constantes e Utilitários de Papéis (Roles)
===========================================

Autor: Sistema de Refatoração de Permissões
Data de criação: 2025-01-XX

Descrição:
    Este módulo centraliza todas as constantes e definições de papéis (roles)
    utilizados no sistema. Contém a enum RoleEnum e utilitários para trabalhar
    com roles.

⚠️ MOVER PARA AQUI:
    - RoleEnum de app/models/user.py (mantida no modelo para compatibilidade do banco)
    - Verificações de roles espalhadas pelo código
"""

from enum import Enum
from typing import List


class Roles:
    """
    Classe centralizada com todas as constantes de roles.
    Use Roles.PROFESSOR.value para obter o valor string.
    """
    
    ALUNO = "aluno"
    PROFESSOR = "professor"
    COORDENADOR = "coordenador"
    DIRETOR = "diretor"
    ADMIN = "admin"
    TECADM = "tecadm"
    
    # Lista de todos os roles
    ALL_ROLES = [ALUNO, PROFESSOR, COORDENADOR, DIRETOR, ADMIN, TECADM]
    
    # Roles administrativos (acesso total ou amplo)
    ADMIN_ROLES = [ADMIN, TECADM]
    
    # Roles com acesso a resultados e relatórios
    REPORT_ROLES = [ADMIN, TECADM, DIRETOR, COORDENADOR, PROFESSOR]
    
    # Roles que podem criar e editar avaliações
    EDIT_TEST_ROLES = [ADMIN, TECADM, PROFESSOR, COORDENADOR]
    
    # Roles que podem gerenciar usuários
    MANAGE_USER_ROLES = [ADMIN, TECADM]
    
    @classmethod
    def is_admin_role(cls, role: str) -> bool:
        """Verifica se um role é administrativo"""
        return role in cls.ADMIN_ROLES
    
    @classmethod
    def has_report_access(cls, role: str) -> bool:
        """Verifica se um role tem acesso a relatórios"""
        return role in cls.REPORT_ROLES
    
    @classmethod
    def can_edit_tests(cls, role: str) -> bool:
        """Verifica se um role pode editar avaliações"""
        return role in cls.EDIT_TEST_ROLES
    
    @classmethod
    def can_manage_users(cls, role: str) -> bool:
        """Verifica se um role pode gerenciar usuários"""
        return role in cls.MANAGE_USER_ROLES
    
    @classmethod
    def normalize(cls, role) -> str:
        """
        Normaliza um role para string.
        
        Args:
            role: Role que pode ser RoleEnum, string ou dict
            
        Returns:
            str: Role normalizado em lowercase
        """
        if isinstance(role, Enum):
            return role.value.lower()
        elif isinstance(role, str):
            # Remove prefixos como RoleEnum. se existir
            role = role.lower()
            if '.' in role:
                role = role.split('.')[-1]
            return role
        elif isinstance(role, dict) and 'role' in role:
            return cls.normalize(role['role'])
        else:
            raise ValueError(f"Tipo de role inválido: {type(role)}")
    
    @classmethod
    def is_valid_role(cls, role: str) -> bool:
        """Verifica se um role é válido"""
        return role.lower() in cls.ALL_ROLES


# Importar RoleEnum do modelo para compatibilidade
# ⚠️ RoleEnum continua existindo em app/models/user.py para compatibilidade com banco de dados
# Esta classe Roles é uma camada adicional de abstração
from app.models.user import RoleEnum

__all__ = ['Roles', 'RoleEnum']
