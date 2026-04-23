# -*- coding: utf-8 -*-
"""
Hooks globais do Celery para multitenant.

Garante estado limpo de override de schema e sessão no início e no fim de cada task.

- task_prerun: limpa override de schema físico (estado conhecido).
- task_postrun: commit/rollback e db.session.remove() no fim.

Equivalente a before_request + teardown_request para o ciclo de vida das tasks.
"""

import logging
from celery import signals

from app import db
from app.multitenant.physical_schema_binding import clear_physical_schema_override

logger = logging.getLogger(__name__)


def _get_flask_app():
    """Obtém a app Flask (usada pelos hooks fora do contexto da task)."""
    from app.report_analysis.celery_app import _get_flask_app as _get
    return _get()


@signals.task_prerun.connect
def celery_set_default_schema(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Estado conhecido no início de toda task: sem override de schema físico."""
    app = _get_flask_app()
    with app.app_context():
        try:
            clear_physical_schema_override()
        except Exception as e:
            logger.warning("[CELERY-HOOK] Erro ao limpar override de schema no prerun: %s", e)
            try:
                db.session.rollback()
            except Exception:
                pass


@signals.task_postrun.connect
def celery_cleanup(
    sender=None, task_id=None, task=None, args=None, kwargs=None,
    retval=None, state=None, **extra
):
    """Limpa sessão e override de schema ao final de toda task (dentro de app context)."""
    app = _get_flask_app()
    with app.app_context():
        try:
            clear_physical_schema_override()
            db.session.commit()
        except Exception:
            db.session.rollback()
        finally:
            db.session.remove()
