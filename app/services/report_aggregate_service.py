from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.exc import SQLAlchemyError
import logging

from app import db
from app.models.reportAggregate import ReportAggregate


class ReportAggregateService:
    """
    Serviço responsável por gerenciar o cache persistente dos relatórios agregados.
    """

    @staticmethod
    def _normalize_scope(scope_type: str, scope_id: Optional[str]) -> tuple[str, Optional[str]]:
        scope_type = (scope_type or "overall").lower()
        if scope_type not in {"overall", "city", "school", "teacher"}:
            logging.warning("Scope type inválido recebido: %s. Usando 'overall'.", scope_type)
            scope_type = "overall"
        return scope_type, scope_id if scope_type != "overall" else None

    @classmethod
    def get(cls, test_id: str, scope_type: str = "overall", scope_id: Optional[str] = None) -> Optional[ReportAggregate]:
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
        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate or aggregate.is_dirty:
            return None
        return aggregate.payload or {}
    
    @classmethod
    def get_ai_analysis(
        cls, test_id: str, scope_type: str = "overall", scope_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Busca análise de IA cacheada"""
        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate or aggregate.ai_analysis_is_dirty or not aggregate.ai_analysis:
            return None
        return aggregate.ai_analysis or {}

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
        """Salva análise de IA"""
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        
        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate:
            # Se não existe, criar apenas para análise de IA
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
        """Marca análise de IA como dirty"""
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        aggregate = cls.get(test_id, scope_type, scope_id)
        if not aggregate:
            return
        aggregate.mark_ai_dirty()
        if commit:
            cls._safe_commit()
    
    @classmethod
    def mark_all_dirty_for_test(cls, test_id: str, commit: bool = True) -> None:
        aggregates = ReportAggregate.query.filter_by(test_id=test_id).all()
        if not aggregates:
            return
        for aggregate in aggregates:
            aggregate.mark_dirty()
            aggregate.mark_ai_dirty()
        if commit:
            cls._safe_commit()
    
    @classmethod
    def ensure_ai_analysis(
        cls,
        test_id: str,
        scope_type: str,
        scope_id: Optional[str],
        build_ai_callback,
        commit: bool = True,
    ) -> Dict[str, Any]:
        """
        Garante que análise de IA existe.
        Análise de IA é compartilhada entre todos os roles do mesmo escopo.
        """
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        aggregate = cls.get(test_id, scope_type, scope_id)
        
        if aggregate and not aggregate.ai_analysis_is_dirty and aggregate.ai_analysis:
            logging.info(f"Análise IA cache HIT para {scope_type}:{scope_id}")
            return aggregate.ai_analysis
        
        # Não encontrou - gerar análise de IA
        logging.info(f"Análise IA cache MISS - gerando para {scope_type}:{scope_id}")
        ai_analysis = build_ai_callback()
        
        # Salvar análise de IA
        cls.save_ai_analysis(
            test_id, scope_type, scope_id,
            ai_analysis,
            commit=commit
        )
        
        return ai_analysis

    @classmethod
    def ensure_payload(
        cls,
        test_id: str,
        scope_type: str,
        scope_id: Optional[str],
        build_callback,
        commit: bool = True,
    ) -> Dict[str, Any]:
        """
        Retorna o payload existente. Caso não exista ou esteja marcado como dirty,
        chama o callback de construção, salva e retorna o payload atualizado.
        """
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        aggregate = cls.get(test_id, scope_type, scope_id)

        if aggregate and not aggregate.is_dirty and aggregate.payload:
            return aggregate.payload

        payload, student_count = build_callback()
        cls.save_payload(
            test_id=test_id,
            scope_type=scope_type,
            scope_id=scope_id,
            payload=payload,
            student_count=student_count or 0,
            commit=commit,
        )
        return payload

    @staticmethod
    def _safe_commit():
        try:
            db.session.commit()
        except SQLAlchemyError:
            logging.exception("Falha ao salvar agregados de relatório")
            db.session.rollback()
            raise


