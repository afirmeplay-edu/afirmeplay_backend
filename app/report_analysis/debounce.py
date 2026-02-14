# -*- coding: utf-8 -*-
"""
Serviço de debounce para evitar múltiplas tasks simultâneas
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
    def should_trigger_rebuild(cls, test_id: str, ttl: Optional[int] = None) -> bool:
        """
        Verifica se deve disparar rebuild (debounce).
        
        Args:
            test_id: ID da avaliação
            ttl: Tempo de vida da chave em segundos (padrão: 60s)
        
        Returns:
            True se deve disparar rebuild, False se está em debounce
        """
        redis_client = cls._get_redis_client()
        if not redis_client:
            # Se Redis não está disponível, sempre permite (sem debounce)
            return True
        
        ttl = ttl or cls._debounce_ttl
        key = f"report_rebuild:{test_id}"
        
        try:
            # Tentar criar chave com TTL (set if not exists)
            # Se conseguir criar, retorna True (deve disparar)
            # Se já existe, retorna False (debounce ativo)
            result = redis_client.set(key, "1", ex=ttl, nx=True)
            return result is True
        except Exception as e:
            logger.error(f"Erro ao verificar debounce: {str(e)}")
            # Em caso de erro, permite disparar (fail-safe)
            return True
    
    @classmethod
    def clear_debounce(cls, test_id: str) -> None:
        """
        Remove debounce manualmente (útil para testes ou rebuild forçado)
        
        Args:
            test_id: ID da avaliação
        """
        redis_client = cls._get_redis_client()
        if not redis_client:
            return
        
        key = f"report_rebuild:{test_id}"
        try:
            redis_client.delete(key)
            logger.info(f"Debounce removido para test_id: {test_id}")
        except Exception as e:
            logger.error(f"Erro ao remover debounce: {str(e)}")
    
    @classmethod
    def get_remaining_ttl(cls, test_id: str) -> Optional[int]:
        """
        Retorna TTL restante do debounce (útil para debug)
        
        Args:
            test_id: ID da avaliação
        
        Returns:
            TTL restante em segundos ou None se não existe
        """
        redis_client = cls._get_redis_client()
        if not redis_client:
            return None
        
        key = f"report_rebuild:{test_id}"
        try:
            ttl = redis_client.ttl(key)
            return ttl if ttl > 0 else None
        except Exception as e:
            logger.error(f"Erro ao obter TTL: {str(e)}")
            return None

