# -*- coding: utf-8 -*-
"""
Serviço de gerenciamento de cache de relatórios agregados
Refatorado para não executar cálculos (apenas consulta cache)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.exc import SQLAlchemyError
import logging

from app import db
from app.models.reportAggregate import ReportAggregate

logger = logging.getLogger(__name__)


class ReportAggregateService:
    """
    Serviço responsável por gerenciar o cache persistente dos relatórios agregados.
    
    REFATORADO: Métodos ensure_* não executam mais cálculos.
    Cálculos devem ser executados via tasks Celery.
    """

    @staticmethod
    def _normalize_scope(scope_type: str, scope_id: Optional[str]) -> tuple[str, Optional[str]]:
        scope_type = (scope_type or "overall").lower()
        if scope_type not in {"overall", "city", "school", "teacher"}:
            logger.warning("Scope type inválido recebido: %s. Usando 'overall'.", scope_type)
            scope_type = "overall"
        return scope_type, scope_id if scope_type != "overall" else None

    @classmethod
    def get(cls, test_id: str, scope_type: str = "overall", scope_id: Optional[str] = None) -> Optional[ReportAggregate]:
        """Busca ReportAggregate do banco"""
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        return ReportAggregate.query.filter_by(
            test_id=test_id,
            scope_type=scope_type,
            scope_id=scope_id,
        ).first()

    @classmethod
    def get_payload(
        cls, test_id: str, scope_type: str = "overall", scope_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Busca payload do cache.
        
        Returns:
            Payload se existir e não estiver dirty, None caso contrário.
        """
        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate or aggregate.is_dirty:
            return None
        return aggregate.payload or {}
    
    @classmethod
    def get_ai_analysis(
        cls, test_id: str, scope_type: str = "overall", scope_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Busca análise de IA do cache.
        
        Returns:
            Análise de IA se existir e não estiver dirty, None caso contrário.
        """
        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate or aggregate.ai_analysis_is_dirty or not aggregate.ai_analysis:
            return None
        return aggregate.ai_analysis or {}
    
    @classmethod
    def get_status(
        cls, test_id: str, scope_type: str = "overall", scope_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retorna status do relatório (útil para verificar se está pronto).
        
        Returns:
            Dict com:
            - status: 'ready', 'processing' ou 'not_found'
            - has_payload: bool
            - has_ai_analysis: bool
            - is_dirty: bool
            - ai_analysis_is_dirty: bool
            - last_update: datetime ou None
        """
        aggregate = cls.get(test_id, scope_type, scope_id)
        
        if not aggregate:
            return {
                'status': 'not_found',
                'has_payload': False,
                'has_ai_analysis': False,
                'is_dirty': True,
                'ai_analysis_is_dirty': True,
                'last_update': None
            }
        
        is_ready = (
            not aggregate.is_dirty and 
            aggregate.payload and 
            not aggregate.ai_analysis_is_dirty and 
            aggregate.ai_analysis
        )
        
        return {
            'status': 'ready' if is_ready else 'processing',
            'has_payload': bool(aggregate.payload) and not aggregate.is_dirty,
            'has_ai_analysis': bool(aggregate.ai_analysis) and not aggregate.ai_analysis_is_dirty,
            'is_dirty': aggregate.is_dirty,
            'ai_analysis_is_dirty': aggregate.ai_analysis_is_dirty,
            'last_update': aggregate.updated_at
        }

    @classmethod
    def save_payload(
        cls,
        test_id: str,
        scope_type: str,
        scope_id: Optional[str],
        payload: Dict[str, Any],
        student_count: int = 0,
        commit: bool = True,
    ) -> ReportAggregate:
        """Salva payload no cache"""
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)

        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate:
            aggregate = ReportAggregate(
                test_id=test_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            db.session.add(aggregate)

        aggregate.update_payload(payload or {}, student_count or 0)
        if commit:
            cls._safe_commit()
        return aggregate
    
    @classmethod
    def save_ai_analysis(
        cls,
        test_id: str,
        scope_type: str,
        scope_id: Optional[str],
        ai_analysis: Dict[str, Any],
        commit: bool = True,
    ) -> ReportAggregate:
        """Salva análise de IA no cache"""
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        
        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate:
            aggregate = ReportAggregate(
                test_id=test_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            db.session.add(aggregate)
        
        aggregate.update_ai_analysis(ai_analysis or {})
        if commit:
            cls._safe_commit()
        return aggregate

    @classmethod
    def mark_dirty(
        cls,
        test_id: str,
        scope_type: str,
        scope_id: Optional[str],
        commit: bool = True,
    ) -> None:
        """Marca payload como dirty (desatualizado)"""
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate:
            return
        aggregate.mark_dirty()
        if commit:
            cls._safe_commit()

    @classmethod
    def mark_ai_dirty(
        cls,
        test_id: str,
        scope_type: str,
        scope_id: Optional[str],
        commit: bool = True,
    ) -> None:
        """Marca análise de IA como dirty (desatualizada)"""
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate:
            return
        aggregate.mark_ai_dirty()
        if commit:
            cls._safe_commit()
    
    @classmethod
    def mark_all_dirty_for_test(cls, test_id: str, commit: bool = True) -> None:
        """Marca todos os escopos de uma avaliação como dirty"""
        aggregates = ReportAggregate.query.filter_by(test_id=test_id).all()
        if not aggregates:
            return
        for aggregate in aggregates:
            aggregate.mark_dirty()
            aggregate.mark_ai_dirty()
        if commit:
            cls._safe_commit()
    
    @classmethod
    def ensure_payload(
        cls,
        test_id: str,
        scope_type: str,
        scope_id: Optional[str],
        build_callback=None,  # DEPRECATED: não usado mais
        commit: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        REFATORADO: Apenas retorna payload do cache, não executa cálculos.
        
        Para executar cálculos, use tasks Celery.
        
        Args:
            test_id: ID da avaliação
            scope_type: Tipo de escopo
            scope_id: ID do escopo
            build_callback: DEPRECATED - não usado mais
            commit: DEPRECATED - não usado mais
        
        Returns:
            Payload se existir e não estiver dirty, None caso contrário.
        """
        if build_callback is not None:
            logger.warning(
                "ensure_payload() chamado com build_callback. "
                "Cálculos devem ser executados via tasks Celery."
            )
        
        return cls.get_payload(test_id, scope_type, scope_id)
    
    @classmethod
    def ensure_ai_analysis(
        cls,
        test_id: str,
        scope_type: str,
        scope_id: Optional[str],
        build_ai_callback=None,  # DEPRECATED: não usado mais
        commit: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        REFATORADO: Apenas retorna análise de IA do cache, não chama IA.
        
        Para gerar análise de IA, use tasks Celery.
        
        Args:
            test_id: ID da avaliação
            scope_type: Tipo de escopo
            scope_id: ID do escopo
            build_ai_callback: DEPRECATED - não usado mais
            commit: DEPRECATED - não usado mais
        
        Returns:
            Análise de IA se existir e não estiver dirty, None caso contrário.
        """
        if build_ai_callback is not None:
            logger.warning(
                "ensure_ai_analysis() chamado com build_ai_callback. "
                "Análise de IA deve ser gerada via tasks Celery."
            )
        
        return cls.get_ai_analysis(test_id, scope_type, scope_id)

    @staticmethod
    def _safe_commit():
        """Commit seguro com tratamento de erros"""
        try:
            db.session.commit()
        except SQLAlchemyError:
            logger.exception("Falha ao salvar agregados de relatório")
            db.session.rollback()
            raise

