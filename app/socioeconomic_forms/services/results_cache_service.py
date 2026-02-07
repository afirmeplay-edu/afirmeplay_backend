# -*- coding: utf-8 -*-
"""
Serviço de gerenciamento de cache de resultados de formulários socioeconômicos.
Inspirado no ReportAggregateService, mas específico para formulários socioeconômicos.
"""

from app import db
from app.socioeconomic_forms.models import FormResultCache
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ResultsCacheService:
    """
    Serviço responsável por gerenciar o cache persistente dos resultados de formulários socioeconômicos.
    """
    
    @classmethod
    def get(cls, form_id, report_type, filters):
        """
        Busca cache específico por form_id, report_type e filtros.
        
        Args:
            form_id: ID do formulário
            report_type: Tipo do relatório ('indices', 'profiles')
            filters: Dicionário com filtros
            
        Returns:
            FormResultCache ou None
        """
        try:
            filters_hash = FormResultCache.generate_filters_hash(filters)
            return FormResultCache.query.filter_by(
                form_id=form_id,
                report_type=report_type,
                filters_hash=filters_hash
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar cache: {str(e)}")
            return None
    
    @classmethod
    def get_result(cls, form_id, report_type, filters):
        """
        Busca resultado do cache (retorna None se dirty ou não existir).
        
        Args:
            form_id: ID do formulário
            report_type: Tipo do relatório
            filters: Dicionário com filtros
            
        Returns:
            dict: Resultado do cache ou None
        """
        cache = cls.get(form_id, report_type, filters)
        if not cache or cache.is_dirty:
            return None
        return cache.result
    
    @classmethod
    def save(cls, form_id, report_type, filters, result, student_count, commit=True):
        """
        Salva resultado no cache.
        
        Args:
            form_id: ID do formulário
            report_type: Tipo do relatório
            filters: Dicionário com filtros
            result: Resultado calculado
            student_count: Total de alunos no escopo
            commit: Se deve fazer commit
            
        Returns:
            FormResultCache: Objeto do cache salvo
        """
        try:
            filters_hash = FormResultCache.generate_filters_hash(filters)
            
            cache = cls.get(form_id, report_type, filters)
            if cache:
                # Atualizar cache existente
                cache.result = result
                cache.student_count = student_count
                cache.is_dirty = False
                cache.updated_at = datetime.utcnow()
                logger.info(f"Cache atualizado: form_id={form_id}, type={report_type}, filters={filters}")
            else:
                # Criar novo cache
                cache = FormResultCache(
                    form_id=form_id,
                    report_type=report_type,
                    filters_hash=filters_hash,
                    filters=filters,
                    result=result,
                    student_count=student_count,
                    is_dirty=False
                )
                db.session.add(cache)
                logger.info(f"Cache criado: form_id={form_id}, type={report_type}, filters={filters}")
            
            if commit:
                db.session.commit()
            
            return cache
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao salvar cache: {str(e)}")
            if commit:
                db.session.rollback()
            raise
    
    @classmethod
    def mark_dirty_for_response(cls, form_response, commit=True):
        """
        Marca caches como dirty quando uma resposta é salva/atualizada.
        Marca APENAS os caches que incluem este aluno nos filtros.
        
        Similar à lógica do evaluation_result_service.py, mas para FormResultCache.
        
        Args:
            form_response: Objeto FormResponse que foi salvo/atualizado
            commit: Se deve fazer commit
        """
        try:
            form_id = form_response.form_id
            user = form_response.user
            student = user.student if user else None
            
            if not student:
                # Se não é estudante, marcar todos os caches do formulário
                logger.warning(f"Resposta sem student vinculado: form_id={form_id}, user_id={form_response.user_id}")
                cls._mark_dirty_all_for_form(form_id, commit=False)
                if commit:
                    db.session.commit()
                return
            
            # Obter dados hierárquicos do estudante
            from app.models import School, City
            
            school = student.school if student.school_id else None
            city = school.city if school and school.city_id else None
            state = city.state if city else None
            grade_id = str(student.grade_id) if student.grade_id else None
            class_id = str(student.class_id) if student.class_id else None
            school_id = student.school_id
            city_id = school.city_id if school else None
            
            # Buscar TODOS os caches deste formulário
            all_caches = FormResultCache.query.filter_by(form_id=form_id).all()
            
            marked_count = 0
            for cache in all_caches:
                cache_filters = cache.filters or {}
                should_mark_dirty = False
                
                # Cache sem filtros (relatório geral) sempre deve ser marcado
                if not cache_filters or all(v is None for v in cache_filters.values()):
                    should_mark_dirty = True
                else:
                    # Verificar se os filtros do cache incluem este estudante
                    # Se qualquer filtro não bater, este cache NÃO inclui este estudante
                    
                    if cache_filters.get('state'):
                        if cache_filters['state'] != state:
                            continue  # Este cache não inclui este estado
                    
                    if cache_filters.get('municipio'):
                        if cache_filters['municipio'] != city_id:
                            continue  # Este cache não inclui este município
                    
                    if cache_filters.get('escola'):
                        if cache_filters['escola'] != school_id:
                            continue  # Este cache não inclui esta escola
                    
                    if cache_filters.get('serie'):
                        if cache_filters['serie'] != grade_id:
                            continue  # Este cache não inclui esta série
                    
                    if cache_filters.get('turma'):
                        if cache_filters['turma'] != class_id:
                            continue  # Este cache não inclui esta turma
                    
                    # Se passou por todos os filtros, este cache inclui este estudante
                    should_mark_dirty = True
                
                if should_mark_dirty and not cache.is_dirty:
                    cache.mark_dirty()
                    marked_count += 1
                    logger.info(
                        f"Cache marcado como dirty: form_id={form_id}, "
                        f"report_type={cache.report_type}, filters={cache.filters}"
                    )
            
            logger.info(f"Total de caches marcados como dirty: {marked_count} de {len(all_caches)}")
            
            if commit:
                db.session.commit()
                
        except SQLAlchemyError as e:
            logger.error(f"Erro ao marcar caches como dirty: {str(e)}")
            if commit:
                db.session.rollback()
            raise
    
    @classmethod
    def _mark_dirty_all_for_form(cls, form_id, commit=True):
        """
        Marca TODOS os caches de um formulário como dirty.
        
        Args:
            form_id: ID do formulário
            commit: Se deve fazer commit
        """
        try:
            caches = FormResultCache.query.filter_by(form_id=form_id).all()
            for cache in caches:
                if not cache.is_dirty:
                    cache.mark_dirty()
            
            logger.info(f"Todos os caches do formulário {form_id} foram marcados como dirty ({len(caches)} caches)")
            
            if commit:
                db.session.commit()
                
        except SQLAlchemyError as e:
            logger.error(f"Erro ao marcar todos os caches como dirty: {str(e)}")
            if commit:
                db.session.rollback()
            raise
    
    @classmethod
    def get_status(cls, form_id, report_type, filters):
        """
        Retorna status do cache.
        
        Args:
            form_id: ID do formulário
            report_type: Tipo do relatório
            filters: Dicionário com filtros
            
        Returns:
            dict: Status do cache
        """
        cache = cls.get(form_id, report_type, filters)
        
        if not cache:
            return {
                'status': 'not_found',
                'has_result': False,
                'is_dirty': True,
                'student_count': 0,
                'last_update': None
            }
        
        if cache.is_dirty:
            status = 'dirty'
        elif cache.result:
            status = 'ready'
        else:
            status = 'empty'
        
        return {
            'status': status,
            'has_result': bool(cache.result),
            'is_dirty': cache.is_dirty,
            'student_count': cache.student_count,
            'last_update': (cache.updated_at or cache.created_at).isoformat() if (cache.updated_at or cache.created_at) else None
        }
    
    @classmethod
    def _safe_commit(cls):
        """Commit seguro com tratamento de erro"""
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Erro no commit: {str(e)}")
            db.session.rollback()
            raise
