"""
Funções Auxiliares de Permissões
==================================

Autor: Sistema de Refatoração de Permissões
Data de criação: 2025-01-XX

Descrição:
    Este módulo contém funções auxiliares para buscar vínculos e informações
    de usuários necessárias para verificação de permissões.

Funções:
    - get_teacher_schools: Busca escolas onde um professor está vinculado
    - get_manager_school: Busca escola de um diretor/coordenador
    - get_user_scope: Determina escopo de acesso de um usuário
    - get_teacher_classes: Busca turmas onde um professor está vinculado
"""

from typing import List, Optional, Dict, Any
from app.models.teacher import Teacher
from app.models.schoolTeacher import SchoolTeacher
from app.models.manager import Manager
# ⚠️ ClassSubject não é usado no sistema (desconsiderado)
from app.models.teacherClass import TeacherClass
from app.models.studentClass import Class as ClassModel


def get_teacher_schools(user_id: str) -> List[str]:
    """
    Busca todas as escolas onde um professor está vinculado.
    
    ⚠️ Substitui lógica espalhada em várias rotas que faziam:
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        school_teachers = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
        school_ids = [st.school_id for st in school_teachers]
    
    Args:
        user_id: ID do usuário professor
        
    Returns:
        List[str]: Lista de IDs de escolas (sempre strings) onde o professor está vinculado
    """
    from app.utils.uuid_helpers import uuid_list_to_str
    
    try:
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        if not teacher:
            return []
        
        school_teachers = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
        school_ids = [st.school_id for st in school_teachers]
        # ✅ CORRIGIDO: Sempre retornar strings (School.id é VARCHAR)
        return uuid_list_to_str(school_ids)
    except Exception:
        return []


def get_manager_school(user_id: str) -> Optional[str]:
    """
    Busca a escola onde um diretor ou coordenador trabalha.
    
    ⚠️ Substitui lógica espalhada em várias rotas que faziam:
        manager = Manager.query.filter_by(user_id=user_id).first()
        if manager and manager.school_id:
            school_id = manager.school_id
    
    Args:
        user_id: ID do usuário diretor/coordenador
        
    Returns:
        Optional[str]: ID da escola (sempre string) ou None se não encontrar
    """
    from app.utils.uuid_helpers import uuid_to_str
    
    try:
        manager = Manager.query.filter_by(user_id=user_id).first()
        if manager and manager.school_id:
            # ✅ CORRIGIDO: Sempre retornar string (School.id é VARCHAR)
            return uuid_to_str(manager.school_id)
        return None
    except Exception:
        return None


def get_manager_city(user_id: str) -> Optional[str]:
    """
    Busca a cidade onde um tecadm está vinculado.
    
    Args:
        user_id: ID do usuário tecadm
        
    Returns:
        Optional[str]: ID da cidade ou None se não encontrar
    """
    try:
        manager = Manager.query.filter_by(user_id=user_id).first()
        if manager and manager.city_id:
            return manager.city_id
        return None
    except Exception:
        return None


def get_teacher_classes(user_id: str) -> List[str]:
    """
    Busca todas as turmas onde um professor está vinculado.
    
    ⚠️ Substitui lógica espalhada em várias rotas que faziam:
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        # Via TeacherClass (ClassSubject não é usado no sistema)
        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
    
    Args:
        user_id: ID do usuário professor
        
    Returns:
        List[str]: Lista de IDs de turmas onde o professor está vinculado
    """
    try:
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        if not teacher:
            return []
        
        # ✅ CORRIGIDO: Buscar turmas apenas via TeacherClass (ClassSubject não é usado)
        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        class_ids = [tc.class_id for tc in teacher_classes]
        
        return class_ids
    except Exception:
        return []


def get_teacher(user_id: str) -> Optional[Teacher]:
    """
    Busca o registro Teacher associado a um user_id.
    
    Args:
        user_id: ID do usuário
        
    Returns:
        Optional[Teacher]: Objeto Teacher ou None
    """
    try:
        return Teacher.query.filter_by(user_id=user_id).first()
    except Exception:
        return None


def get_manager(user_id: str) -> Optional[Manager]:
    """
    Busca o registro Manager associado a um user_id.
    
    Args:
        user_id: ID do usuário
        
    Returns:
        Optional[Manager]: Objeto Manager ou None
    """
    try:
        return Manager.query.filter_by(user_id=user_id).first()
    except Exception:
        return None


def get_user_scope(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determina o escopo de acesso de um usuário com base em seu role.
    
    ⚠️ Baseado na lógica de verificar_permissao_filtros() de evaluation_results_routes.py
    
    Args:
        user: Dicionário com informações do usuário (id, role, city_id, etc)
        
    Returns:
        Dict com informações de scope:
        {
            'scope': 'all' | 'municipio' | 'escola',
            'city_id': str | None,
            'school_id': str | None,
            'school_ids': List[str] | None  # Para professores
        }
    """
    from .roles import Roles
    
    role = Roles.normalize(user.get('role', ''))
    
    if role == Roles.ADMIN:
        return {
            'scope': 'all',
            'city_id': None,
            'school_id': None,
            'school_ids': None
        }
    
    elif role == Roles.TECADM:
        city_id = user.get('city_id') or user.get('tenant_id')
        return {
            'scope': 'municipio',
            'city_id': city_id,
            'school_id': None,
            'school_ids': None
        }
    
    elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
        school_id = get_manager_school(user['id'])
        city_id = user.get('city_id') or user.get('tenant_id')
        result = {
            'scope': 'escola',
            'city_id': city_id,
            'school_id': school_id,
            'school_ids': [school_id] if school_id else []
        }
        return result
    
    elif role == Roles.PROFESSOR:
        school_ids = get_teacher_schools(user['id'])
        city_id = user.get('city_id') or user.get('tenant_id')
        return {
            'scope': 'escola',
            'city_id': city_id,
            'school_id': None,
            'school_ids': school_ids
        }
    
    else:
        # ALUNO ou outros roles sem acesso especial
        return {
            'scope': 'none',
            'city_id': None,
            'school_id': None,
            'school_ids': []
        }


__all__ = [
    'get_teacher_schools',
    'get_manager_school',
    'get_manager_city',
    'get_teacher_classes',
    'get_teacher',
    'get_manager',
    'get_user_scope'
]
