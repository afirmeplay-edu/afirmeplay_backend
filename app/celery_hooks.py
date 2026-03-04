# -*- coding: utf-8 -*-
"""
Hooks globais do Celery para multitenant.

Garante estado limpo de conexão/schema no início e no fim de cada task,
evitando que search_path ou sessão sujos vazem para a próxima task ou para
o pool (ex.: worker morto por SIGKILL não chama teardown; conexão volta ao pool).

- task_prerun: SET search_path TO public no início (estado conhecido).
- task_postrun: reset search_path, commit/rollback e db.session.remove() no fim.

Equivalente a before_request + teardown_request para o ciclo de vida das tasks.
"""

import logging
from celery import signals
from sqlalchemy import text

from app import db

logger = logging.getLogger(__name__)


@signals.task_prerun.connect
def celery_set_default_schema(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Estado conhecido no início de toda task: search_path = public."""
    try:
        db.session.execute(text("SET search_path TO public"))
    except Exception as e:
        logger.warning("[CELERY-HOOK] Erro ao setar search_path no prerun: %s", e)
        try:
            db.session.rollback()
        except Exception:
            pass


@signals.task_postrun.connect
def celery_cleanup(
    sender=None, task_id=None, task=None, args=None, kwargs=None,
    retval=None, state=None, **extra
):
    """Limpa sessão e search_path ao final de toda task."""
    try:
        db.session.execute(text("SET search_path TO public"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.remove()
