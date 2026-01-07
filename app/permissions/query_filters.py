"""
Filtros SQLAlchemy Aplicáveis a Queries
========================================

Autor: Sistema de Refatoração de Permissões
Data de criação: 2025-01-XX

Descrição:
    Este módulo contém funções para aplicar filtros SQLAlchemy baseados em
    permissões de usuário em queries de recursos (escolas, turmas, avaliações, etc.).

⚠️ SUBSTITUI:
    - Trechos de código que aplicavam .filter() diretamente baseado em user['role']
    - Lógica repetida em várias rotas para filtrar escolas, turmas, avaliações
    - Lógica em _gerar_opcoes_proximos_filtros() de evaluation_results_routes.py

Funções retornam queries modificadas que já têm os filtros aplicados.
"""

from sqlalchemy.orm import Query
from typing import List
from .roles import Roles
from .utils import get_teacher_schools, get_manager_school, get_user_scope, get_teacher


def filter_schools_by_user(query: Query, user: dict) -> Query:
    """
    Aplica filtros de escolas baseado no role do usuário.
    
    ⚠️ SUBSTITUI verificações inline em várias rotas que faziam:
        if user['role'] in ['diretor', 'coordenador']:
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if manager and manager.school_id:
                query = query.filter(School.id == manager.school_id)
        elif user['role'] == 'professor':
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            school_teachers = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            school_ids = [st.school_id for st in school_teachers]
            if school_ids:
                query = query.filter(School.id.in_(school_ids))
    
    Args:
        query: Query SQLAlchemy de escolas
        user: Dicionário com informações do usuário
        
    Returns:
        Query: Query filtrada de acordo com permissões do usuário
    """
    role = Roles.normalize(user.get('role', ''))
    
    # Admin e TECADM veem todas as escolas
    if Roles.is_admin_role(role):
        return query
    
    # Diretor e Coordenador: apenas sua escola
    elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
        school_id = get_manager_school(user['id'])
        if school_id:
            return query.filter(lambda q: q.school_id == school_id)
        else:
            # Se não tem escola vinculada, forçar resultado vazio
            return query.filter(lambda q: q.school_id == None)
    
    # Professor: apenas escolas onde está vinculado
    elif role == Roles.PROFESSOR:
        school_ids = get_teacher_schools(user['id'])
        if school_ids:
            return query.filter(lambda q: q.school_id.in_(school_ids))
        else:
            # Se não tem escolas vinculadas, forçar resultado vazio
            return query.filter(lambda q: q.school_id == None)
    
    # Outros roles (ALUNO): resultado vazio
    return query.filter(lambda q: q.school_id == None)


def filter_classes_by_user(query: Query, user: dict) -> Query:
    """
    Aplica filtros de turmas baseado no role do usuário.
    
    Args:
        query: Query SQLAlchemy de turmas
        user: Dicionário com informações do usuário
        
    Returns:
        Query: Query filtrada de acordo com permissões do usuário
    """
    # ⚠️ ClassSubject não é usado no sistema (desconsiderado)
    from app.models.teacherClass import TeacherClass
    from app.models.studentClass import Class as ClassModel
    from .utils import get_teacher
    
    role = Roles.normalize(user.get('role', ''))
    
    # Admin e TECADM veem todas as turmas
    if Roles.is_admin_role(role):
        return query
    
    # Diretor e Coordenador: apenas turmas de sua escola
    elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
        school_id = get_manager_school(user['id'])
        if school_id:
            return query.filter(ClassModel.school_id == school_id)
        else:
            return query.filter(ClassModel.school_id == None)
    
        # Professor: apenas turmas onde está vinculado
    elif role == Roles.PROFESSOR:
        teacher = get_teacher(user['id'])
        if teacher:
            # ✅ Buscar turmas via TeacherClass (ClassSubject não é usado)
            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            class_ids = [tc.class_id for tc in teacher_classes]
            
            if class_ids:
                return query.filter(ClassModel.id.in_(class_ids))
        
        return query.filter(ClassModel.id == None)
    
    # Outros roles: resultado vazio
    return query.filter(ClassModel.id == None)


def filter_tests_by_user(query: Query, user: dict, escola_id: str = None, require_school: bool = True) -> Query:
    """
    Aplica filtros de avaliações baseado no role do usuário.
    
    ⚠️ ALTERADO: Agora permite modo flexível para listagem vs resultados
    
    Args:
        query: Query SQLAlchemy de avaliações
        user: Dicionário com informações do usuário
        escola_id: ID da escola específica (obrigatório para professores em modo restritivo)
        require_school: Se True, exige escola específica. Se False, permite sem escola para listagem
        
    Returns:
        Query: Query filtrada de acordo com permissões do usuário
    """
    from app.models.test import Test
    from app.models.teacher import Teacher
    from app.models.teacherClass import TeacherClass
    from app.models.classTest import ClassTest
    from app.models.studentClass import Class as ClassModel
    from sqlalchemy import or_
    
    role = Roles.normalize(user.get('role', ''))
    
    # Admin e TECADM veem todas as avaliações
    if Roles.is_admin_role(role):
        return query
    
    # ✅ ALTERADO: Professor: avaliações que criou OU aplicadas em TURMAS específicas
    elif role == Roles.PROFESSOR:
        
        teacher = get_teacher(user['id'])
        if not teacher:
            # Professor não válido, retornar apenas avaliações que criou
            return query.filter(Test.created_by == user['id'])
        
        # Buscar TURMAS onde o professor está vinculado
        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        teacher_class_ids = [tc.class_id for tc in teacher_classes]
        
        # Criar filtro OR: avaliações que criou OU aplicadas em suas TURMAS
        filters = [Test.created_by == user['id']]
        
        if teacher_class_ids:
            # Se exige escola específica, filtrar por escola
            if require_school and escola_id and escola_id.lower() != 'all':
                # Verificar se a escola selecionada é uma das escolas vinculadas ao professor
                teacher_school_ids = get_teacher_schools(user['id'])
                if escola_id not in teacher_school_ids:
                    # Escola não vinculada ao professor, retornar resultado vazio
                    return query.filter(Test.id == None)
                
                # Filtrar turmas que pertencem à escola selecionada
                classes_escola = ClassModel.query.filter(
                    ClassModel.id.in_(teacher_class_ids),
                    ClassModel.school_id == escola_id
                ).all()
                teacher_class_ids_escola = [c.id for c in classes_escola]
                
                if teacher_class_ids_escola:
                    # Buscar avaliações aplicadas nessas turmas específicas da escola
                    class_tests = ClassTest.query.filter(ClassTest.class_id.in_(teacher_class_ids_escola)).all()
                    test_ids_vinculadas = [ct.test_id for ct in class_tests]
                    
                    if test_ids_vinculadas:
                        filters.append(Test.id.in_(test_ids_vinculadas))
            else:
                # Modo flexível: mostrar todas as avaliações das turmas do professor (para listagem)
                class_tests = ClassTest.query.filter(ClassTest.class_id.in_(teacher_class_ids)).all()
                test_ids_vinculadas = [ct.test_id for ct in class_tests]
                
                if test_ids_vinculadas:
                    filters.append(Test.id.in_(test_ids_vinculadas))
        
        # Aplicar filtro OR
        return query.filter(or_(*filters))
    
    # Diretor e Coordenador: apenas avaliações aplicadas em sua escola
    elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
        school_id = get_manager_school(user['id'])
        if not school_id:
            return query.filter(Test.id == None)  # Forçar resultado vazio
        
        # Se exige escola específica, validar se é a escola vinculada
        if require_school and escola_id and escola_id.lower() != 'all':
            if escola_id != school_id:
                # Escola selecionada não é a escola vinculada, retornar resultado vazio
                return query.filter(Test.id == None)
        
        # Filtrar avaliações que foram aplicadas em turmas da escola
        # Buscar turmas da escola
        classes = ClassModel.query.filter_by(school_id=school_id).all()
        class_ids = [c.id for c in classes]
        
        if class_ids:
            # Buscar avaliações aplicadas nessas turmas
            class_tests = ClassTest.query.filter(ClassTest.class_id.in_(class_ids)).all()
            test_ids = [ct.test_id for ct in class_tests]
            
            if test_ids:
                return query.filter(Test.id.in_(test_ids))
        
        return query.filter(Test.id == None)
    
    # Outros roles: resultado vazio
    return query.filter(Test.id == None)


def filter_students_by_user(query: Query, user: dict) -> Query:
    """
    Aplica filtros de estudantes baseado no role do usuário.
    
    Args:
        query: Query SQLAlchemy de estudantes
        user: Dicionário com informações do usuário
        
    Returns:
        Query: Query filtrada de acordo com permissões do usuário
    """
    from app.models.student import Student
    
    role = Roles.normalize(user.get('role', ''))
    
    # Admin e TECADM veem todos os estudantes
    if Roles.is_admin_role(role):
        return query
    
    # Diretor e Coordenador: apenas estudantes de sua escola
    elif role in [Roles.DIRETOR, Roles.COORDENADOR]:
        school_id = get_manager_school(user['id'])
        if school_id:
            return query.filter(lambda q: q.school_id == school_id)
        else:
            return query.filter(lambda q: q.school_id == None)
    
    # Professor: apenas estudantes de suas turmas
    elif role == Roles.PROFESSOR:
        school_ids = get_teacher_schools(user['id'])
        if school_ids:
            return query.filter(lambda q: q.school_id.in_(school_ids))
        else:
            return query.filter(lambda q: q.school_id == None)
    
    # Outros roles: resultado vazio
    return query.filter(lambda q: q.school_id == None)


def filter_by_city(query: Query, user: dict, city_column) -> Query:
    """
    Aplica filtro de cidade baseado no user (para TECADM).
    
    Args:
        query: Query SQLAlchemy
        user: Dicionário com informações do usuário
        city_column: Coluna de cidade da query (ex: School.city_id)
        
    Returns:
        Query: Query filtrada por cidade se aplicável
    """
    role = Roles.normalize(user.get('role', ''))
    
    if role == Roles.TECADM:
        city_id = user.get('city_id') or user.get('tenant_id')
        if city_id:
            return query.filter(city_column == city_id)
    
    return query


__all__ = [
    'filter_schools_by_user',
    'filter_classes_by_user',
    'filter_tests_by_user',
    'filter_students_by_user',
    'filter_by_city'
]
