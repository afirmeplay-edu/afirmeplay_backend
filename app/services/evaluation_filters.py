"""
Serviço de filtros avançados para resultados de avaliações
Implementa filtros eficientes com suporte a paginação e otimização de consultas
"""

from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import and_, or_, func, text
from sqlalchemy.orm import Query, joinedload
from flask import request

from app.models.test import Test
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.subject import Subject
from app.models.grades import Grade
from app.models.school import School
from app.models.studentClass import Class
from app.models.educationStage import EducationStage
from app.models.user import User
from app import db


class EvaluationFilters:
    """
    Serviço especializado em filtros avançados para avaliações e resultados.
    Otimizado para performance com grandes volumes de dados.
    """

    @classmethod
    def parse_pagination_params(cls) -> Tuple[int, int]:
        """
        Extrai parâmetros de paginação da requisição
        
        Returns:
            Tupla (página, limite) com valores padrão
        """
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        # Limitar o máximo para evitar sobrecarga
        limit = min(limit, 1000)
        page = max(page, 1)
        
        return page, limit

    @classmethod
    def parse_evaluation_filters(cls) -> Dict[str, Any]:
        """
        Extrai filtros específicos para avaliações da requisição
        
        Returns:
            Dicionário com filtros aplicáveis
        """
        filters = {}
        
        # Filtros básicos
        if request.args.get('course'):
            filters['course'] = request.args.get('course')
        
        if request.args.get('subject'):
            filters['subject'] = request.args.get('subject')
            
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
            
        if request.args.get('school'):
            filters['school'] = request.args.get('school')
            
        # Filtros de data
        if request.args.get('date_from'):
            filters['date_from'] = request.args.get('date_from')
            
        if request.args.get('date_to'):
            filters['date_to'] = request.args.get('date_to')
            
        # Filtros específicos do criador
        if request.args.get('created_by'):
            filters['created_by'] = request.args.get('created_by')
            
        return filters

    @classmethod
    def parse_student_filters(cls) -> Dict[str, Any]:
        """
        Extrai filtros específicos para alunos da requisição
        
        Returns:
            Dicionário com filtros aplicáveis
        """
        filters = {}
        
        # Filtros básicos
        if request.args.get('course'):
            filters['course'] = request.args.get('course')
            
        if request.args.get('subject'):
            filters['subject'] = request.args.get('subject')
            
        if request.args.get('class_id'):
            filters['class_id'] = request.args.get('class_id')
            
        if request.args.get('school'):
            filters['school'] = request.args.get('school')
            
        if request.args.get('evaluation_id'):
            filters['evaluation_id'] = request.args.get('evaluation_id')
            
        # Filtros de faixa de proficiência
        if request.args.get('proficiency_min'):
            filters['proficiency_min'] = float(request.args.get('proficiency_min'))
            
        if request.args.get('proficiency_max'):
            filters['proficiency_max'] = float(request.args.get('proficiency_max'))
            
        # Filtros de faixa de nota
        if request.args.get('grade_min'):
            filters['grade_min'] = float(request.args.get('grade_min'))
            
        if request.args.get('grade_max'):
            filters['grade_max'] = float(request.args.get('grade_max'))
            
        # Filtro de classificação
        if request.args.get('classification'):
            filters['classification'] = request.args.get('classification')
            
        # Filtro de status da avaliação
        if request.args.get('evaluation_status'):
            filters['evaluation_status'] = request.args.get('evaluation_status')
            
        return filters

    @classmethod
    def apply_evaluation_filters(cls, query: Query, filters: Dict[str, Any]) -> Query:
        """
        Aplica filtros à consulta de avaliações
        
        Args:
            query: Query SQLAlchemy base
            filters: Dicionário de filtros
            
        Returns:
            Query filtrada
        """
        
        # Filtro por curso
        if 'course' in filters:
            query = query.filter(Test.course.ilike(f"%{filters['course']}%"))
            
        # Filtro por disciplina
        if 'subject' in filters:
            query = query.join(Subject, Test.subject == Subject.id)\
                        .filter(Subject.name.ilike(f"%{filters['subject']}%"))
                        
        # Filtro por status
        if 'status' in filters:
            query = query.filter(Test.status == filters['status'])
            
        # Filtro por escola (nas escolas aplicadas)
        if 'school' in filters:
            query = query.filter(Test.schools.contains([filters['school']]))
            
        # Filtros de data
        if 'date_from' in filters:
            query = query.filter(Test.created_at >= filters['date_from'])
            
        if 'date_to' in filters:
            query = query.filter(Test.created_at <= filters['date_to'])
            
        # Filtro por criador
        if 'created_by' in filters:
            query = query.filter(Test.created_by == filters['created_by'])
            
        return query

    @classmethod
    def apply_student_result_filters(cls, base_query: Query, filters: Dict[str, Any]) -> Query:
        """
        Aplica filtros à consulta de resultados de alunos
        
        Args:
            base_query: Query SQLAlchemy base
            filters: Dicionário de filtros
            
        Returns:
            Query filtrada
        """
        
        # Filtro por turma
        if 'class_id' in filters:
            base_query = base_query.filter(Student.class_id == filters['class_id'])
            
        # Filtro por escola
        if 'school' in filters:
            base_query = base_query.filter(Student.school_id == filters['school'])
            
        # Filtro por avaliação específica
        if 'evaluation_id' in filters:
            base_query = base_query.join(StudentAnswer, Student.id == StudentAnswer.student_id)\
                                  .filter(StudentAnswer.test_id == filters['evaluation_id'])
                                  
        # Filtros por disciplina/curso serão aplicados na lógica de cálculo
        # pois dependem dos dados calculados
        
        return base_query

    @classmethod
    def build_optimized_evaluation_query(cls) -> Query:
        """
        Constrói consulta otimizada para avaliações com joins necessários
        
        Returns:
            Query otimizada com eager loading
        """
        return Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade),
            joinedload(Test.class_tests)
        )

    @classmethod
    def build_optimized_student_query(cls) -> Query:
        """
        Constrói consulta otimizada para alunos com joins necessários
        
        Returns:
            Query otimizada com eager loading
        """
        return Student.query.options(
            joinedload(Student.school),
            joinedload(Student.user),
            joinedload(Student.class_relation).joinedload(Class.grade),
            joinedload(Student.class_relation).joinedload(Class.school)
        )

    @classmethod
    def get_filter_options(cls) -> Dict[str, List[Dict]]:
        """
        Retorna opções disponíveis para filtros (para alimentar dropdowns no frontend)
        
        Returns:
            Dicionário com opções de filtros
        """
        
        # Cursos disponíveis
        courses = db.session.query(EducationStage.id, EducationStage.name)\
                          .distinct()\
                          .all()
        
        # Disciplinas disponíveis
        subjects = db.session.query(Subject.id, Subject.name)\
                           .distinct()\
                           .all()
                           
        # Escolas disponíveis
        schools = db.session.query(School.id, School.name)\
                          .distinct()\
                          .all()
                          
        # Status disponíveis
        statuses = [
            {'id': 'pendente', 'name': 'Pendente'},
            {'id': 'agendada', 'name': 'Agendada'},
            {'id': 'em_andamento', 'name': 'Em Andamento'},
            {'id': 'concluida', 'name': 'Concluída'},
            {'id': 'cancelada', 'name': 'Cancelada'}
        ]
        
        # Classificações disponíveis
        classifications = [
            {'id': 'Abaixo do Básico', 'name': 'Abaixo do Básico'},
            {'id': 'Básico', 'name': 'Básico'},
            {'id': 'Adequado', 'name': 'Adequado'},
            {'id': 'Avançado', 'name': 'Avançado'}
        ]
        
        return {
            'courses': [{'id': c.id, 'name': c.name} for c in courses],
            'subjects': [{'id': s.id, 'name': s.name} for s in subjects],
            'schools': [{'id': sc.id, 'name': sc.name} for sc in schools],
            'statuses': statuses,
            'classifications': classifications
        }

    @classmethod
    def apply_search_term(cls, query: Query, search_term: str, search_fields: List[str]) -> Query:
        """
        Aplica termo de busca em múltiplos campos
        
        Args:
            query: Query SQLAlchemy
            search_term: Termo a ser buscado
            search_fields: Lista de campos para buscar
            
        Returns:
            Query com filtro de busca aplicado
        """
        if not search_term:
            return query
            
        # Construir condições OR para busca em múltiplos campos
        search_conditions = []
        
        for field in search_fields:
            if hasattr(Test, field):
                search_conditions.append(
                    getattr(Test, field).ilike(f"%{search_term}%")
                )
                
        if search_conditions:
            query = query.filter(or_(*search_conditions))
            
        return query

    @classmethod
    def get_pagination_metadata(cls, query: Query, page: int, limit: int) -> Dict[str, Any]:
        """
        Calcula metadados de paginação
        
        Args:
            query: Query base para contagem
            page: Página atual
            limit: Limite de itens por página
            
        Returns:
            Metadados de paginação
        """
        total_items = query.count()
        total_pages = (total_items + limit - 1) // limit
        
        has_next = page < total_pages
        has_prev = page > 1
        
        return {
            'current_page': page,
            'per_page': limit,
            'total_items': total_items,
            'total_pages': total_pages,
            'has_next': has_next,
            'has_prev': has_prev,
            'next_page': page + 1 if has_next else None,
            'prev_page': page - 1 if has_prev else None
        } 