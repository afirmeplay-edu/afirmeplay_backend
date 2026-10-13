# -*- coding: utf-8 -*-
"""
Geração do ZIP impresso do questionário socioeconômico.

Não usa a task da prova física nem Test/ClassTest/gabarito.
O schema do tenant chega como argumento, no mesmo esquema das tasks de resultado.
O ZIP só fica completed depois que upload_from_path devolve o objeto.
"""
import logging
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional

from celery.exceptions import SoftTimeLimitExceeded

from app import db
from app.report_analysis.celery_app import celery_app
from app.utils.tenant_middleware import set_search_path

logger = logging.getLogger(__name__)


def _set_tenant_schema(schema: Optional[str]) -> None:
    try:
        if not schema or schema == "public":
            set_search_path("public")
        else:
            set_search_path(schema)
    except Exception as exc:
        logger.warning("[PRINT] Erro ao definir bind do tenant: %s", exc)
        db.session.rollback()


def _load_form(form_id: str, schema: Optional[str], run_id: str):
    from app.socioeconomic_forms.models import Form

    _set_tenant_schema(schema)
    form = Form.query.get(form_id)
    if form is None or str(form.print_run_id or "") != str(run_id):
        return None
    return form


def _mark_failed(form_id: str, schema: Optional[str], run_id: str, message: str) -> None:
    from app.socioeconomic_forms.models import Form

    db.session.rollback()
    form = _load_form(form_id, schema, run_id)
    if form is None:
        return
    form.print_status = "failed"
    form.print_error = (message or "Falha ao gerar o pacote.")[:4000]
    form.print_finished_at = datetime.utcnow()
    db.session.commit()


@celery_app.task(bind=True, max_retries=0, time_limit=1800, soft_time_limit=1740)
def generate_print_package(self, form_id: str, schema: Optional[str], run_id: str) -> Dict[str, Any]:
    """Monta o ZIP no disco e envia um único objeto. Não publica URL se o upload falhar."""
    from app.services.storage.minio_service import MinIOService
    from app.socioeconomic_forms.services.print_package import (
        PrintRunSuperseded,
        cover_place,
        decide_print_outcome,
        list_print_students,
        write_print_zip,
    )
    from app.socioeconomic_forms.services.questionnaire_pdf_service import (
        SocioeconomicQuestionnairePdfService,
    )

    temp_dir = None
    try:
        form = _load_form(form_id, schema, run_id)
        if form is None:
            logger.info("[PRINT] Execução %s ignorada: formulário ausente ou substituído", run_id)
            return {"success": False, "superseded": True}

        students = list_print_students(form)
        cover_year = form.print_cover_year
        filters = form.filters or {}
        db.session.commit()
        _set_tenant_schema(schema)

        if not students:
            _mark_failed(form_id, schema, run_id, "Nenhum aluno encontrado no escopo deste questionário.")
            return {"success": False, "generated": 0, "failed": 0}

        place = cover_place(students, filters)
        form = _load_form(form_id, schema, run_id)
        if form is None:
            return {"success": False, "superseded": True}
        base_pdf = SocioeconomicQuestionnairePdfService().generate_base_pdf(
            form, place, cover_year=cover_year
        )
        db.session.commit()
        _set_tenant_schema(schema)

        temp_dir = tempfile.mkdtemp(prefix="socio_print_")
        zip_path = os.path.join(temp_dir, f"{run_id}.zip")

        def on_progress(generated: int, failed: int, total: int) -> None:
            done = generated + failed
            if done != total and done % 25 != 0:
                return
            current = _load_form(form_id, schema, run_id)
            if current is None:
                raise PrintRunSuperseded()
            current.print_generated_count = generated
            current.print_failed_count = failed
            current.print_student_count = total
            db.session.commit()
            _set_tenant_schema(schema)

        stats = write_print_zip(
            zip_path,
            base_pdf,
            form_id,
            students,
            on_progress=on_progress,
        )
        del base_pdf

        upload_result = None
        if stats["generated"] > 0:
            bucket = MinIOService.BUCKETS["SOCIOECONOMIC_FORMS"]
            object_name = f"{form_id}/runs/{run_id}.zip"
            upload_result = MinIOService().upload_from_path(bucket, object_name, zip_path)

        outcome = decide_print_outcome(stats, upload_result)
        form = _load_form(form_id, schema, run_id)
        if form is None:
            return {"success": False, "superseded": True}
        form.print_status = outcome["status"]
        form.print_generated_count = stats["generated"]
        form.print_failed_count = stats["failed"]
        form.print_student_count = stats["total"]
        form.print_error = outcome["error"]
        form.print_finished_at = datetime.utcnow()
        if outcome["replace_zip"]:
            form.print_zip_bucket = outcome["bucket"]
            form.print_zip_object_name = outcome["object_name"]
            form.print_zip_url = outcome["url"]
        db.session.commit()
        logger.info(
            "[PRINT] form=%s run=%s status=%s gerados=%s falhas=%s",
            form_id,
            run_id,
            outcome["status"],
            stats["generated"],
            stats["failed"],
        )
        return {
            "success": outcome["status"] == "completed",
            "generated": stats["generated"],
            "failed": stats["failed"],
        }
    except PrintRunSuperseded:
        logger.info("[PRINT] Execução %s interrompida: outra geração assumiu o formulário", run_id)
        db.session.rollback()
        return {"success": False, "superseded": True}
    except SoftTimeLimitExceeded:
        logger.error("[PRINT] Tempo esgotado form=%s run=%s", form_id, run_id)
        _mark_failed(form_id, schema, run_id, "Tempo esgotado ao gerar o pacote.")
        return {"success": False, "error": "timeout"}
    except Exception as exc:
        logger.error("[PRINT] Falha form=%s run=%s: %s", form_id, run_id, exc, exc_info=True)
        _mark_failed(form_id, schema, run_id, str(exc))
        return {"success": False, "error": str(exc)}
    finally:
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
