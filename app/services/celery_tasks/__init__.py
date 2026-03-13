# -*- coding: utf-8 -*-
"""
Pacote de tasks Celery para processamento assíncrono
Todas as tasks demoradas devem ser criadas aqui
"""

from app.physical_tests.tasks import (
    generate_physical_forms_async
)
from app.services.celery_tasks.answer_sheet_tasks import (
    generate_answer_sheets_batch_async,
    upload_answer_sheets_zip_async
)
from app.services.celery_tasks.competition_tasks import process_finished_competitions

# ✅ Alias para compatibilidade com código antigo
generate_answer_sheets_async = generate_answer_sheets_batch_async

__all__ = [
    'generate_physical_forms_async',
    'generate_answer_sheets_batch_async',
    'generate_answer_sheets_async',  # Alias para compatibilidade
    'upload_answer_sheets_zip_async',
    'process_finished_competitions',
]
