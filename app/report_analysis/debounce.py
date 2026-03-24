# -*- coding: utf-8 -*-
"""
Serviço de debounce para evitar múltiplas tasks simultâneas

==============================================================
RELATÓRIOS QUE USAM ESTE ARQUIVO:
  - Análise das Avaliações  (frontend: AnaliseAvaliacoes / analise-avaliacoes)
  - Relatório Escolar       (frontend: RelatorioEscolar)

RESPONSABILIDADE:
  Mecanismo Redis para evitar que múltiplas requisições simultâneas
  disparem tasks Celery duplicadas para o mesmo relatório.
  A chave de debounce é por (test_id, scope_type, scope_id).

ARQUIVOS RELACIONADOS AO SISTEMA DE RELATÓRIOS:
  app/report_analysis/routes.py       → rotas Flask
  app/report_analysis/tasks.py        → tasks Celery que consultam este serviço
  app/report_analysis/services.py     → ReportAggregateService (cache no banco)
  app/report_analysis/calculations.py → re-exporta funções de cálculo
  app/report_analysis/debounce.py     ← este arquivo
  app/report_analysis/celery_app.py   → configuração do Celery
  app/routes/report_routes.py         → funções de cálculo + _determinar_escopo_por_role
  app/routes/evaluation_results_routes.py → dados tabulares (/avaliacoes e /opcoes-filtros)
==============================================================
"""

import logging
import redis
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv('app/.env')

logger = logging.getLogger(__name__)


class ReportDebounceService:
    """
    Serviço para implementar debounce de rebuild de relatórios.
    Evita que múltiplas tasks sejam agendadas para o mesmo test_id em um curto período.
    """
    
    _redis_client: Optional[redis.Redis] = None
    _debounce_ttl: int = 60  # 60 segundos por padrão
    
    @classmethod
    def _get_redis_client(cls) -> Optional[redis.Redis]:
        """Obtém cliente Redis (singleton)"""
        if cls._redis_client is None:
            try:
                # Usar apenas Redis local: REDIS_URL ou CELERY_BROKER_URL (mesma instância do Celery), sem fallback para VPS
                redis_url = os.getenv('REDIS_URL') or os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
                
                # Se houver senha do Redis separada, adicionar à URL
                redis_password = os.getenv('REDIS_PASSWORD')
                if redis_password and '@' not in redis_url:
                    # Adicionar senha à URL do Redis
                    # Formato: redis://:password@host:port/db
                    if redis_url.startswith('redis://'):
                        parts = redis_url.replace('redis://', '').split('/')
                        host_port = parts[0]
                        db = parts[1] if len(parts) > 1 else '0'
                        redis_url = f'redis://:{redis_password}@{host_port}/{db}'
                
                cls._redis_client = redis.from_url(redis_url, decode_responses=True)
                # Testar conexão
                cls._redis_client.ping()
                logger.info("Conexão Redis estabelecida para debounce")
            except Exception as e:
                logger.warning(f"Redis não disponível para debounce: {str(e)}. Debounce desabilitado.")
                cls._redis_client = None
        return cls._redis_client
    
    @classmethod
    def _make_key(
        cls,
        entity_id: str,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        *,
        kind: str = "test",
    ) -> str:
        """Gera a chave Redis. kind=test (avaliação) ou kind=answer_sheet (cartão-resposta)."""
        prefix = "report_rebuild:as:" if kind == "answer_sheet" else "report_rebuild:"
        if scope_type:
            return f"{prefix}{entity_id}:{scope_type}:{scope_id or 'all'}"
        return f"{prefix}{entity_id}"

    @classmethod
    def should_trigger_rebuild(
        cls,
        entity_id: str,
        ttl: Optional[int] = None,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        *,
        kind: str = "test",
    ) -> bool:
        """
        Verifica se deve disparar rebuild (debounce).
        
        Args:
            entity_id: ID da avaliação ou gabarito
            ttl: Tempo de vida da chave em segundos (padrão: 60s)
            scope_type: Tipo de escopo (city, school, teacher, overall)
            scope_id: ID do escopo
            kind: test | answer_sheet
        
        Returns:
            True se deve disparar rebuild, False se está em debounce
        """
        redis_client = cls._get_redis_client()
        if not redis_client:
            return True
        
        ttl = ttl or cls._debounce_ttl
        key = cls._make_key(entity_id, scope_type, scope_id, kind=kind)
        
        try:
            result = redis_client.set(key, "1", ex=ttl, nx=True)
            return result is True
        except Exception as e:
            logger.error(f"Erro ao verificar debounce: {str(e)}")
            return True
    
    @classmethod
    def clear_debounce(
        cls,
        entity_id: str,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        *,
        kind: str = "test",
    ) -> None:
        """
        Remove debounce manualmente (útil para testes ou rebuild forçado).
        
        Args:
            entity_id: ID da avaliação ou gabarito
            scope_type: Tipo de escopo (opcional)
            scope_id: ID do escopo (opcional)
            kind: test | answer_sheet
        """
        redis_client = cls._get_redis_client()
        if not redis_client:
            return
        
        key = cls._make_key(entity_id, scope_type, scope_id, kind=kind)
        try:
            redis_client.delete(key)
            logger.info(f"Debounce removido para {key}")
        except Exception as e:
            logger.error(f"Erro ao remover debounce: {str(e)}")
    
    @classmethod
    def get_remaining_ttl(
        cls,
        entity_id: str,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        *,
        kind: str = "test",
    ) -> Optional[int]:
        """
        Retorna TTL restante do debounce.
        
        Args:
            entity_id: ID da avaliação ou gabarito
            scope_type: Tipo de escopo (opcional)
            scope_id: ID do escopo (opcional)
            kind: test | answer_sheet
        
        Returns:
            TTL restante em segundos ou None se não existe
        """
        redis_client = cls._get_redis_client()
        if not redis_client:
            return None
        
        key = cls._make_key(entity_id, scope_type, scope_id, kind=kind)
        try:
            ttl = redis_client.ttl(key)
            return ttl if ttl > 0 else None
        except Exception as e:
            logger.error(f"Erro ao obter TTL: {str(e)}")
            return None

