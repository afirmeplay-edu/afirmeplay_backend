# -*- coding: utf-8 -*-
"""
Cache de agregados de relatório — ponto canônico de import.

A implementação completa (Celery-safe) vive em ``app.report_analysis.services``.
Qualquer consumidor novo deve importar daqui; a chave inclui alunos/roster
via ``compose_scope_id`` / ``invalidate_for_test``.
"""
from app.report_analysis.services import ReportAggregateService

__all__ = ["ReportAggregateService"]
