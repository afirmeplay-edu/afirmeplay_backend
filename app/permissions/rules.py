"""
Regras de Permissão de Alto Nível
===================================

Autor: Sistema de Refatoração de Permissões
Data de criação: 2025-01-XX

Descrição:
    Este módulo contém funções de alto nível para verificar permissões de acesso
    a recursos específicos (avaliações, escolas, turmas, etc.).

⚠️ SUBSTITUI:
    - professor_pode_ver_avaliacao() de evaluation_results_routes.py
    - professor_pode_ver_avaliacao_turmas() de evaluation_results_routes.py
    - verificar_permissao_filtros() de evaluation_results_routes.py
    - Verificações inline de permissões espalhadas em rotas
"""

from typing import Dict, Any, Optional
from app.models.test import Test
from app.models.school import School
from app.models.studentClass import Class
# ⚠️ ClassSubject não é usado no sistema (desconsiderado)
from app.models.teacherClass import TeacherClass
from app.models.classTest import ClassTest
from app.models.teacher import Teacher
from .roles import Roles
from .utils import (
    get_teacher_schools,
    get_manager_school,
    get_teacher_classes,
    get_teacher
)


def can_view_test(user: Dict[str, Any], test_id: str) -> bool:
    """
    Verifica se um usuário pode ver uma avaliação específica.
    
    ⚠️ SUBSTITUI: professor_pode_ver_avaliacao() de evaluation_results_routes.py
    
    Regras (lógica OR para professor):
    - ADMIN e TECADM: sempre True (acesso total)
    - PROFESSOR: True se:
      * Criou a avaliação OU
      * Avaliação foi aplicada em TURMAS onde está vinculado (ClassSubject + TeacherClass)
    - DIRETOR/COORDENADOR: True se a avaliação foi aplicada em sua escola
    - Outros: False
    
    Args:
        user: Dicionário com informações do usuário (id, role, etc)
        test_id: ID da avaliação
        
    Returns:
        bool: True se o usuário pode ver a avaliação
    """
    try:
        from .roles import Roles
        role = Roles.normalize(user.get('role', ''))
        
        # Admin e TECADM sempre podem ver
        if Roles.is_admin_role(role):
            return True
        
        # Buscar a avaliação
        test = Test.query.get(test_id)
        if not test:
            return False
        
        # Professor: pode ver se criou OU se foi aplicada nas turmas onde está vinculado
        if role == Roles.PROFESSOR:
            # Critério 1: Professor criou a avaliação
            if test.created_by == user['id']:
                return True
            
            # Critério 2: Avaliação foi aplicada em TURMAS específicas onde professor está vinculado
            # Buscar o registro Teacher
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return False
            
            # Buscar turmas onde a avaliação foi aplicada
            class_tests = ClassTest.query.filter_by(test_id=test_id).all()
            class_ids_avaliacao = [ct.class_id for ct in class_tests]
            
            if not class_ids_avaliacao:
                return False
            
            # Buscar turmas onde o professor está vinculado via ClassSubject
            class_subjects = ClassSubject.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids_subjects = [cs.class_id for cs in class_subjects]
            
            # Buscar turmas onde o professor está vinculado via TeacherClass
            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids_direct = [tc.class_id for tc in teacher_classes]
            
            # Combinar todas as turmas onde o professor está vinculado
            all_teacher_class_ids = list(set(teacher_class_ids_subjects + teacher_class_ids_direct))
            
            if not all_teacher_class_ids:
                return False
            
            # Verificar INTERSECÇÃO entre turmas da avaliação E turmas do professor
            avaliacao_turmas = set(class_ids_avaliacao)
            professor_turmas = set(all_teacher_class_ids)
            
            # Se há pelo menos uma turma em comum, o professor pode ver
            return len(avaliacao_turmas.intersection(professor_turmas)) > 0
        
        # Diretor e Coordenador: podem ver se a avaliação foi aplicada em sua escola
        elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
            school_id = get_manager_school(user['id'])
            if not school_id:
                return False
            
            # Buscar turmas onde a avaliação foi aplicada
            class_tests = ClassTest.query.filter_by(test_id=test_id).all()
            class_ids = [ct.class_id for ct in class_tests]
            
            if not class_ids:
                return False
            
            # Verificar se alguma turma é da escola do diretor/coordenador
            classes_school = Class.query.filter(
                Class.id.in_(class_ids),
                Class.school_id == school_id
            ).all()
            
            return len(classes_school) > 0
        
        return False
        
    except Exception:
        return False


def can_edit_test(user: Dict[str, Any], test_id: str) -> bool:
    """
    Verifica se um usuário pode editar uma avaliação específica.
    
    ⚠️ SUBSTITUI verificações inline de:
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode editar avaliações que criou"}), 403
    
    Regras:
    - ADMIN e TECADM: sempre True
    - PROFESSOR: True apenas se criou a avaliação
    - DIRETOR/COORDENADOR: True apenas se a avaliação foi aplicada em sua escola
    - Outros: False
    
    Args:
        user: Dicionário com informações do usuário
        test_id: ID da avaliação
        
    Returns:
        bool: True se o usuário pode editar a avaliação
    """
    try:
        from .roles import Roles
        role = Roles.normalize(user.get('role', ''))
        
        # Admin e TECADM sempre podem editar
        if Roles.is_admin_role(role):
            return True
        
        # Buscar a avaliação
        test = Test.query.get(test_id)
        if not test:
            return False
        
        # Professor: pode editar apenas se criou
        if role == Roles.PROFESSOR:
            return test.created_by == user['id']
        
        # Diretor e Coordenador: podem editar se foi aplicada em sua escola
        elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
            school_id = get_manager_school(user['id'])
            if not school_id:
                return False
            
            # Verificar se a avaliação foi aplicada na escola
            class_tests = ClassTest.query.filter_by(test_id=test_id).all()
            class_ids = [ct.class_id for ct in class_tests]
            
            if not class_ids:
                return False
            
            classes_school = Class.query.filter(
                Class.id.in_(class_ids),
                Class.school_id == school_id
            ).all()
            
            return len(classes_school) > 0
        
        return False
        
    except Exception:
        return False


def can_view_school(user: Dict[str, Any], school_id: str) -> bool:
    """
    Verifica se um usuário pode ver uma escola específica.
    
    Regras:
    - ADMIN e TECADM: sempre True
    - PROFESSOR: True se está vinculado à escola
    - DIRETOR/COORDENADOR: True se é a sua escola
    - Outros: False
    
    Args:
        user: Dicionário com informações do usuário
        school_id: ID da escola
        
    Returns:
        bool: True se o usuário pode ver a escola
    """
    try:
        from .roles import Roles
        role = Roles.normalize(user.get('role', ''))
        
        # Admin e TECADM sempre podem ver
        if Roles.is_admin_role(role):
            return True
        
        # Professor: pode ver se está vinculado à escola
        if role == Roles.PROFESSOR:
            teacher_school_ids = get_teacher_schools(user['id'])
            return school_id in teacher_school_ids
        
        # Diretor e Coordenador: podem ver apenas sua escola
        elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
            school_id_user = get_manager_school(user['id'])
            return school_id_user == school_id
        
        return False
        
    except Exception:
        return False


def can_view_class(user: Dict[str, Any], class_id: str) -> bool:
    """
    Verifica se um usuário pode ver uma turma específica.
    
    ⚠️ Baseado em: professor_pode_ver_avaliacao_turmas() de evaluation_results_routes.py
    
    Regras:
    - ADMIN e TECADM: sempre True
    - PROFESSOR: True se está vinculado à turma
    - DIRETOR/COORDENADOR: True se a turma pertence à sua escola
    - Outros: False
    
    Args:
        user: Dicionário com informações do usuário
        class_id: ID da turma
        
    Returns:
        bool: True se o usuário pode ver a turma
    """
    try:
        from .roles import Roles
        role = Roles.normalize(user.get('role', ''))
        
        # Admin e TECADM sempre podem ver
        if Roles.is_admin_role(role):
            return True
        
        # Buscar informações da turma
        turma = Class.query.get(class_id)
        if not turma:
            return False
        
        # Professor: pode ver se está vinculado à turma
        if role == Roles.PROFESSOR:
            teacher_class_ids = get_teacher_classes(user['id'])
            return class_id in teacher_class_ids
        
        # Diretor e Coordenador: podem ver se a turma pertence à sua escola
        elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
            school_id_user = get_manager_school(user['id'])
            return turma.school_id == school_id_user
        
        return False
        
    except Exception:
        return False


def can_view_results(user: Dict[str, Any], filters: Dict[str, Any] = None) -> bool:
    """
    Verifica se um usuário pode visualizar resultados com base nos filtros.
    
    Args:
        user: Dicionário com informações do usuário
        filters: Dicionário com filtros aplicados (opcional)
        
    Returns:
        bool: True se o usuário pode ver resultados
    """
    from .roles import Roles
    
    role = Roles.normalize(user.get('role', ''))
    
    # Apenas roles com acesso a relatórios
    return Roles.has_report_access(role)


def validate_professor_school_for_results(user: Dict[str, Any], escola_id: str = None) -> Dict[str, Any]:
    """
    Valida se um professor selecionou uma escola específica para visualizar resultados.
    
    ⚠️ NOVA FUNÇÃO: Específica para validação de resultados (sempre exige escola)
    
    Args:
        user: Dicionário com informações do usuário
        escola_id: ID da escola selecionada (obrigatório para professores)
        
    Returns:
        Dict com resultado da validação:
        {
            'valid': bool,
            'error': str | None,
            'school_id': str | None
        }
    """
    from .roles import Roles
    
    role = Roles.normalize(user.get('role', ''))
    
    # Apenas professores precisam validar seleção de escola para resultados
    if role != Roles.PROFESSOR:
        return {
            'valid': True,
            'error': None,
            'school_id': escola_id
        }
    
    # Professor DEVE selecionar uma escola específica para ver resultados
    if not escola_id or escola_id.lower() == 'all':
        return {
            'valid': False,
            'error': 'Para professores, é obrigatório selecionar uma escola específica para visualizar resultados',
            'school_id': None
        }
    
    # Verificar se a escola selecionada é uma das escolas vinculadas ao professor
    teacher_school_ids = get_teacher_schools(user['id'])
    if escola_id not in teacher_school_ids:
        return {
            'valid': False,
            'error': 'Você não tem acesso a esta escola',
            'school_id': None
        }
    
    return {
        'valid': True,
        'error': None,
        'school_id': escola_id
    }


def validate_professor_school_selection(user: Dict[str, Any], escola_id: str = None, require_school: bool = True) -> Dict[str, Any]:
    """
    Valida se um professor selecionou uma escola específica.
    
    ⚠️ ALTERADO: Agora permite modo flexível para listagem vs resultados
    
    Args:
        user: Dicionário com informações do usuário
        escola_id: ID da escola selecionada (opcional)
        require_school: Se True, exige escola específica. Se False, permite sem escola para listagem
        
    Returns:
        Dict com resultado da validação:
        {
            'valid': bool,
            'error': str | None,
            'school_id': str | None
        }
    """
    from .roles import Roles
    
    role = Roles.normalize(user.get('role', ''))
    
    # Apenas professores precisam validar seleção de escola
    if role != Roles.PROFESSOR:
        return {
            'valid': True,
            'error': None,
            'school_id': escola_id
        }
    
    # Se não exige escola específica (para listagem), permitir sem escola
    if not require_school:
        if not escola_id or escola_id.lower() == 'all':
            return {
                'valid': True,
                'error': None,
                'school_id': None
            }
        else:
            # Verificar se a escola selecionada é uma das escolas vinculadas ao professor
            teacher_school_ids = get_teacher_schools(user['id'])
            if escola_id not in teacher_school_ids:
                return {
                    'valid': False,
                    'error': 'Você não tem acesso a esta escola',
                    'school_id': None
                }
            return {
                'valid': True,
                'error': None,
                'school_id': escola_id
            }
    
    # Modo restritivo: Professor deve selecionar uma escola específica (para resultados)
    if not escola_id or escola_id.lower() == 'all':
        return {
            'valid': False,
            'error': 'Para professores, é obrigatório selecionar uma escola específica',
            'school_id': None
        }
    
    # Verificar se a escola selecionada é uma das escolas vinculadas ao professor
    teacher_school_ids = get_teacher_schools(user['id'])
    if escola_id not in teacher_school_ids:
        return {
            'valid': False,
            'error': 'Você não tem acesso a esta escola',
            'school_id': None
        }
    
    return {
        'valid': True,
        'error': None,
        'school_id': escola_id
    }


def get_user_permission_scope(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determina o escopo de permissões de um usuário para filtros.
    
    ⚠️ SUBSTITUI: verificar_permissao_filtros() de evaluation_results_routes.py
    
    Args:
        user: Dicionário com informações do usuário
        
    Returns:
        Dict com informações de permissão:
        {
            'permitted': bool,
            'scope': str ('all' | 'municipio' | 'escola'),
            'city_id': str | None,
            'filters': Dict com configurações de filtros
        }
    """
    from .roles import Roles
    
    role = Roles.normalize(user.get('role', ''))
    city_id = user.get('city_id') or user.get('tenant_id')
    
    if role == Roles.ADMIN:
        return {
            'permitted': True,
            'scope': 'all',
            'filters': {
                'estados': 'all',
                'municipios': 'all',
                'escolas': 'all',
                'series': 'all',
                'turmas': 'all',
                'avaliacoes': 'all'
            }
        }
    
    elif role == Roles.TECADM:
        if not city_id:
            return {
                'permitted': False,
                'error': 'Tecadm não vinculado a um município'
            }
        
        return {
            'permitted': True,
            'scope': 'municipio',
            'city_id': city_id,
            'filters': {
                'estados': 'specific',
                'municipios': 'specific',
                'escolas': 'municipio',
                'series': 'municipio',
                'turmas': 'municipio',
                'avaliacoes': 'municipio'
            }
        }
    
    elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
        if not city_id:
            return {
                'permitted': False,
                'error': 'Usuário não vinculado a uma escola'
            }
        
        return {
            'permitted': True,
            'scope': 'escola',
            'city_id': city_id,
            'filters': {
                'estados': 'specific',
                'municipios': 'specific',
                'escolas': 'specific',
                'series': 'escola',
                'turmas': 'escola',
                'avaliacoes': 'escola'
            }
        }
    
    elif role == Roles.PROFESSOR:
        return {
            'permitted': True,
            'scope': 'escola',
            'city_id': city_id,
            'filters': {
                'estados': 'specific',
                'municipios': 'specific',
                'escolas': 'obrigatorio',  # ✅ ALTERADO: Professor DEVE selecionar escola específica
                'series': 'vinculadas',
                'turmas': 'vinculadas',
                'avaliacoes': 'vinculadas'
            }
        }
    
    else:
        return {
            'permitted': False,
            'error': 'Papel não autorizado para visualizar resultados'
        }


__all__ = [
    'can_view_test',
    'can_edit_test',
    'can_view_school',
    'can_view_class',
    'can_view_results',
    'get_user_permission_scope',
    'validate_professor_school_selection',
    'validate_professor_school_for_results'  # ✅ NOVA FUNÇÃO
]
