# -*- coding: utf-8 -*-
"""
Cache leve (Redis) para resultados de análise de IA.

- Não persiste em banco.
- Usado para evitar timeout em rotas que chamam IA.
- Armazena status: processing|ready|error e o resultado final (JSON) quando pronto.
"""

from __future__ import annotations

import json
import logging
import os
import time
import hashlib
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_redis_client = None


def get_redis_client():
    """Cliente Redis singleton. Retorna None se indisponível."""
    global _redis_client
    try:
        import redis  # type: ignore
    except ImportError:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        redis_url = os.getenv("REDIS_URL") or os.getenv(
            "CELERY_BROKER_URL", "redis://localhost:6379/0"
        )
        redis_password = os.getenv("REDIS_PASSWORD")
        if redis_password and "@" not in redis_url and redis_url.startswith("redis://"):
            parts = redis_url.replace("redis://", "").split("/")
            host_port = parts[0]
            db = parts[1] if len(parts) > 1 else "0"
            redis_url = f"redis://:{redis_password}@{host_port}/{db}"

        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
    except Exception as e:
        logger.warning("Redis indisponível para cache de IA: %s", e)
        _redis_client = None
    return _redis_client


def _now_iso() -> str:
    # Evitar depender de datetime (serialização simples)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def make_cache_key(prefix: str, *, user_id: str, key_parts: Dict[str, Any], prompt_version: str) -> str:
    """
    Gera uma chave determinística curta (hash) para o cache.
    Inclui user_id para evitar vazamento entre usuários com permissões diferentes.
    """
    stable = {
        "prefix": prefix,
        "user_id": str(user_id or ""),
        "prompt_version": str(prompt_version or "v1"),
        "key_parts": key_parts or {},
    }
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
    return f"ai_cache:{prefix}:{digest}"


def get_status(key: str) -> Optional[Dict[str, Any]]:
    r = get_redis_client()
    if not r:
        return None
    try:
        raw = r.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.debug("Falha ao ler cache IA no Redis: %s", e)
        return None


def set_processing(key: str, *, ttl_sec: int) -> bool:
    """
    Define status=processing com NX (lock). Retorna True se setou agora.
    """
    r = get_redis_client()
    if not r:
        return False
    payload = {"status": "processing", "started_at": _now_iso(), "updated_at": _now_iso()}
    try:
        return bool(r.set(key, json.dumps(payload, ensure_ascii=False), ex=int(ttl_sec), nx=True))
    except Exception as e:
        logger.debug("Falha ao setar processing no Redis: %s", e)
        return False


def set_ready(key: str, *, result: Dict[str, Any], ttl_sec: int) -> None:
    r = get_redis_client()
    if not r:
        return
    payload = {
        "status": "ready",
        "updated_at": _now_iso(),
        "result": result or {},
    }
    try:
        r.set(key, json.dumps(payload, ensure_ascii=False, default=str), ex=int(ttl_sec))
    except Exception as e:
        logger.debug("Falha ao setar ready no Redis: %s", e)


def set_error(key: str, *, error: str, details: str = "", ttl_sec: int = 900) -> None:
    r = get_redis_client()
    if not r:
        return
    payload = {
        "status": "error",
        "updated_at": _now_iso(),
        "error": error,
        "details": details,
    }
    try:
        r.set(key, json.dumps(payload, ensure_ascii=False, default=str), ex=int(ttl_sec))
    except Exception as e:
        logger.debug("Falha ao setar error no Redis: %s", e)

