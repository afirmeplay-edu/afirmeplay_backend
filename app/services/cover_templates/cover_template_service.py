# -*- coding: utf-8 -*-
"""CRUD, upload MinIO e preview de templates de capa por avaliação (Test)."""
from __future__ import annotations

import io
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.coverTemplate import CoverTemplate
from app.exams.models.test import Test
from app.services.cover_templates.constants import (
    ALLOWED_ALIGN,
    ALLOWED_FONTS,
    ALLOWED_OVERFLOW,
    ALLOWED_STATUSES,
    ALLOWED_VALIGN,
    MAX_FONT_SIZE_PT,
    MIN_FONT_SIZE_PT,
)
from app.services.cover_templates.coordinates import canonicalize_field_box
from app.services.cover_templates.cover_composer import CoverComposer
from app.services.cover_templates.exceptions import (
    CoverTemplateNotFound,
    CoverTemplateValidationError,
)
from app.services.cover_templates.field_catalog import FIELD_KEYS, catalog_payload
from app.services.cover_templates.file_normalizer import normalize_upload
from app.services.storage.minio_service import MinIOService

logger = logging.getLogger(__name__)

COVER_TEMPLATES_BUCKET = MinIOService.BUCKETS["COVER_TEMPLATES"]


class CoverTemplateService:
    def __init__(self, minio: Optional[MinIOService] = None):
        self.minio = minio or MinIOService()

    def _require_test(self, test_id: str) -> Test:
        test = Test.query.get(test_id)
        if not test:
            raise CoverTemplateNotFound("Avaliação não encontrada")
        return test

    def _require_template(self, test_id: str, template_id: str) -> CoverTemplate:
        self._require_test(test_id)
        template = CoverTemplate.query.filter_by(id=template_id, test_id=test_id).first()
        if not template:
            raise CoverTemplateNotFound("Template de capa não encontrado nesta avaliação")
        return template

    def list_for_test(self, test_id: str) -> List[CoverTemplate]:
        self._require_test(test_id)
        return (
            CoverTemplate.query.filter_by(test_id=test_id)
            .order_by(CoverTemplate.created_at.desc())
            .all()
        )

    def get(self, test_id: str, template_id: str) -> CoverTemplate:
        return self._require_template(test_id, template_id)

    @staticmethod
    def get_active_for_test(test_id: Optional[str]) -> Optional[CoverTemplate]:
        if not test_id:
            return None
        return CoverTemplate.query.filter_by(test_id=test_id, status="active").first()

    def load_original_bytes(self, template: CoverTemplate) -> Tuple[bytes, str]:
        data = self.minio.download_file(template.minio_bucket, template.minio_object_name)
        return data, template.mime_type

    def load_normalized_pdf_bytes(self, template: CoverTemplate) -> bytes:
        object_name = template.normalized_object_name or template.minio_object_name
        return self.minio.download_file(template.minio_bucket, object_name)

    def load_print_pdf_bytes(self, template: CoverTemplate) -> bytes:
        """
        PDF da capa para impressão.

        PDF enviado: bytes originais (vetor). Imagem: re-normaliza do original
        com PNG ou JPEG ≥90 na resolução nativa — corrige capas já gravadas
        com JPEG qualidade 75 do Pillow.
        """
        source_kind = (getattr(template, "source_kind", None) or "").lower()
        filename = getattr(template, "original_filename", None) or f"capa.{source_kind or 'bin'}"

        if source_kind == "pdf":
            try:
                original, _ = self.load_original_bytes(template)
                if original and original.startswith(b"%PDF"):
                    return original
            except Exception as exc:
                logger.warning("Original PDF da capa indisponível: %s", exc)
            return self.load_normalized_pdf_bytes(template)

        if source_kind in ("jpeg", "jpg", "png"):
            try:
                original, _ = self.load_original_bytes(template)
                if original:
                    return normalize_upload(filename, original)["normalized_pdf"]
            except Exception as exc:
                logger.warning(
                    "Re-normalização da capa falhou; usando PDF armazenado: %s",
                    exc,
                )
        return self.load_normalized_pdf_bytes(template)

    def create_from_upload(
        self,
        test_id: str,
        file_storage,
        name: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> CoverTemplate:
        test = self._require_test(test_id)
        if not file_storage or not getattr(file_storage, "filename", None):
            raise CoverTemplateValidationError("Arquivo da capa é obrigatório")

        data = file_storage.read()
        filename = os.path.basename(file_storage.filename or "capa")
        normalized = normalize_upload(filename, data)

        template_id = str(uuid.uuid4())
        ext = {
            "pdf": "pdf",
            "jpeg": "jpg",
            "png": "png",
        }[normalized["source_kind"]]
        original_object = f"{test.id}/{template_id}/original.{ext}"
        normalized_object = f"{test.id}/{template_id}/normalized.pdf"

        uploaded_original = self.minio.upload_file(
            bucket_name=COVER_TEMPLATES_BUCKET,
            object_name=original_object,
            data=data,
            content_type=normalized["mime_type"],
        )
        if not uploaded_original:
            raise CoverTemplateValidationError(
                "Falha ao armazenar o arquivo original da capa",
                code="STORAGE_ERROR",
            )

        uploaded_normalized = self.minio.upload_file(
            bucket_name=COVER_TEMPLATES_BUCKET,
            object_name=normalized_object,
            data=normalized["normalized_pdf"],
            content_type="application/pdf",
        )
        if not uploaded_normalized:
            self.minio.delete_file(COVER_TEMPLATES_BUCKET, original_object)
            raise CoverTemplateValidationError(
                "Falha ao armazenar o PDF normalizado da capa",
                code="STORAGE_ERROR",
            )

        template = CoverTemplate(
            id=template_id,
            test_id=test.id,
            name=(name or "").strip() or filename,
            status="draft",
            original_filename=filename,
            mime_type=normalized["mime_type"],
            source_kind=normalized["source_kind"],
            minio_bucket=COVER_TEMPLATES_BUCKET,
            minio_object_name=original_object,
            normalized_object_name=normalized_object,
            page_count=normalized["page_count"],
            page_width_pt=normalized["page_width_pt"],
            page_height_pt=normalized["page_height_pt"],
            rotation=normalized["rotation"],
            fields={"fields": []},
            version=1,
            created_by=created_by,
        )
        db.session.add(template)
        db.session.commit()
        return template

    def _canonicalize_fields(self, template: CoverTemplate, payload: Any) -> Dict[str, Any]:
        if payload is None:
            return template.fields or {"fields": []}
        if isinstance(payload, dict) and "fields" in payload:
            raw_fields = payload.get("fields")
        elif isinstance(payload, list):
            raw_fields = payload
        else:
            raise CoverTemplateValidationError(
                "fields deve ser uma lista ou um objeto {\"fields\": [...]}"
            )
        if not isinstance(raw_fields, list):
            raise CoverTemplateValidationError("fields deve ser uma lista")

        canonical: List[Dict[str, Any]] = []
        seen_ids = set()
        for index, raw in enumerate(raw_fields):
            if not isinstance(raw, dict):
                raise CoverTemplateValidationError(f"Campo {index} inválido")
            key = (raw.get("key") or "").strip()
            if key not in FIELD_KEYS:
                raise CoverTemplateValidationError(
                    f"Campo '{key}' não está no catálogo disponível"
                )
            field_id = (raw.get("id") or key or f"field_{index}").strip()
            if field_id in seen_ids:
                raise CoverTemplateValidationError(f"id de campo duplicado: {field_id}")
            seen_ids.add(field_id)

            box = canonicalize_field_box(
                raw, template.page_width_pt, template.page_height_pt
            )
            font_name = raw.get("font_name") or "Helvetica"
            if font_name not in ALLOWED_FONTS:
                raise CoverTemplateValidationError(
                    f"Fonte não suportada: {font_name}. "
                    "Use as fontes padrão PDF (Helvetica, Times-Roman, Courier)."
                )
            try:
                font_size = float(raw.get("font_size_pt") or 12)
            except (TypeError, ValueError) as exc:
                raise CoverTemplateValidationError("font_size_pt inválido") from exc
            if font_size < MIN_FONT_SIZE_PT or font_size > MAX_FONT_SIZE_PT:
                raise CoverTemplateValidationError(
                    f"font_size_pt deve estar entre {MIN_FONT_SIZE_PT} e {MAX_FONT_SIZE_PT}"
                )
            align = raw.get("align") or "left"
            valign = raw.get("valign") or "middle"
            overflow = raw.get("overflow") or "ellipsis"
            if align not in ALLOWED_ALIGN:
                raise CoverTemplateValidationError("align deve ser left, center ou right")
            if valign not in ALLOWED_VALIGN:
                raise CoverTemplateValidationError("valign deve ser top, middle ou bottom")
            if overflow not in ALLOWED_OVERFLOW:
                raise CoverTemplateValidationError(
                    "overflow deve ser ellipsis, wrap ou clip"
                )
            page = int(raw.get("page") or 1)
            if page != 1:
                raise CoverTemplateValidationError("A v1 da capa aceita apenas a página 1")

            max_chars = raw.get("max_chars")
            if max_chars is not None:
                try:
                    max_chars = int(max_chars)
                except (TypeError, ValueError) as exc:
                    raise CoverTemplateValidationError("max_chars inválido") from exc
                if max_chars < 1:
                    raise CoverTemplateValidationError("max_chars deve ser positivo")

            canonical.append(
                {
                    "id": field_id,
                    "key": key,
                    "page": 1,
                    **box,
                    "font_name": font_name,
                    "font_size_pt": font_size,
                    "align": align,
                    "valign": valign,
                    "color": raw.get("color") or "#1a1a1a",
                    "uppercase": bool(raw.get("uppercase", False)),
                    "max_chars": max_chars,
                    "overflow": overflow,
                }
            )
        return {"fields": canonical}

    def update(
        self,
        test_id: str,
        template_id: str,
        payload: Dict[str, Any],
    ) -> CoverTemplate:
        template = self._require_template(test_id, template_id)
        if "name" in payload and payload["name"] is not None:
            name = str(payload["name"]).strip()
            if not name:
                raise CoverTemplateValidationError("name não pode ser vazio")
            template.name = name[:200]
        if "fields" in payload:
            template.fields = self._canonicalize_fields(template, payload["fields"])
            template.version = int(template.version or 1) + 1
        if "status" in payload and payload["status"] is not None:
            status = str(payload["status"]).strip()
            if status not in ALLOWED_STATUSES:
                raise CoverTemplateValidationError(
                    "status deve ser draft, active ou inactive"
                )
            if status == "active":
                db.session.flush()
                return self.activate(test_id, template_id)
            template.status = status
        db.session.commit()
        return template

    def activate(self, test_id: str, template_id: str) -> CoverTemplate:
        template = self._require_template(test_id, template_id)
        CoverTemplate.query.filter(
            CoverTemplate.test_id == test_id,
            CoverTemplate.id != template.id,
            CoverTemplate.status == "active",
        ).update({"status": "inactive"}, synchronize_session=False)
        template.status = "active"
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise CoverTemplateValidationError(
                "Já existe um template ativo para esta avaliação",
                code="ACTIVE_CONFLICT",
            ) from exc
        return template

    def delete(self, test_id: str, template_id: str) -> None:
        template = self._require_template(test_id, template_id)
        bucket = template.minio_bucket
        objects = [template.minio_object_name, template.normalized_object_name]
        db.session.delete(template)
        db.session.commit()
        for object_name in objects:
            if object_name:
                try:
                    self.minio.delete_file(bucket, object_name)
                except Exception:
                    logger.warning(
                        "Falha ao remover objeto MinIO %s/%s", bucket, object_name
                    )

    def preview(
        self,
        test_id: str,
        template_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, str]:
        template = self._require_template(test_id, template_id)
        payload = payload or {}
        sample = bool(payload.get("sample", True))
        output_format = str(payload.get("format") or "pdf").lower()
        fields_override = None
        if "fields" in payload:
            fields_override = self._canonicalize_fields(template, payload["fields"])

        cover_base = self.load_print_pdf_bytes(template)
        student = payload.get("student") if isinstance(payload.get("student"), dict) else {}
        test_data = payload.get("test_data") if isinstance(payload.get("test_data"), dict) else {}
        if not test_data:
            test = self._require_test(test_id)
            test_data = {
                "id": test.id,
                "title": test.title,
                "description": test.description,
                "type": test.type,
                "model": test.model,
                "subjects_info": test.subjects_info,
            }
            if test.grade:
                test_data["grade_name"] = test.grade.name

        pdf_bytes = CoverComposer.compose(
            cover_base,
            template,
            student=student,
            test_data=test_data,
            sample=sample,
            fields_override=fields_override,
        )
        if output_format == "png":
            return self._pdf_first_page_png(pdf_bytes), "image/png"
        return pdf_bytes, "application/pdf"

    @staticmethod
    def _pdf_first_page_png(pdf_bytes: bytes) -> bytes:
        try:
            from pdf2image import convert_from_bytes
        except ImportError as exc:
            raise CoverTemplateValidationError(
                "pdf2image não está disponível para gerar PNG de preview",
                code="PREVIEW_PNG_UNAVAILABLE",
            ) from exc
        try:
            images = convert_from_bytes(
                pdf_bytes, dpi=150, first_page=1, last_page=1
            )
        except Exception as exc:
            raise CoverTemplateValidationError(
                f"Não foi possível gerar o PNG de preview: {exc}",
                code="PREVIEW_PNG_FAILED",
            ) from exc
        if not images:
            raise CoverTemplateValidationError("Preview PNG vazio")
        buffer = io.BytesIO()
        images[0].save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def field_catalog() -> Dict[str, Any]:
        return catalog_payload()
