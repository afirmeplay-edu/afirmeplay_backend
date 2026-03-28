# -*- coding: utf-8 -*-
"""
Branding municipal: upload de logo (PNG/JPEG), timbrado PDF (1ª página → PNG),
armazenamento MinIO e injeção em test_data para geração de PDFs.
"""
from __future__ import annotations

import base64
import io
import logging
import os
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from PIL import Image
from pypdf import PdfReader

from app import db
from app.models.city import City
from app.services.storage.minio_service import MinIOService

logger = logging.getLogger(__name__)

MAX_LOGO_BYTES = 5 * 1024 * 1024
MAX_LETTERHEAD_PDF_BYTES = 30 * 1024 * 1024
LETTERHEAD_RENDER_DPI = 300

_LOGO_MAGIC: Tuple[Tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
)


def detect_logo_format(file_head: bytes) -> Optional[str]:
    if not file_head or len(file_head) < 4:
        return None
    for magic, fmt in _LOGO_MAGIC:
        if file_head.startswith(magic):
            return fmt
    return None


def validate_logo_bytes(data: bytes) -> str:
    if not data:
        raise ValueError("Arquivo de logo vazio")
    if len(data) > MAX_LOGO_BYTES:
        raise ValueError(f"Logo excede o limite de {MAX_LOGO_BYTES // (1024 * 1024)} MB")
    fmt = detect_logo_format(data)
    if not fmt:
        raise ValueError("Logo deve ser PNG ou JPEG")
    try:
        im = Image.open(io.BytesIO(data))
        im.verify()
    except Exception as e:
        raise ValueError(f"Imagem inválida ou corrompida: {e}") from e
    return fmt


def validate_letterhead_pdf_bytes(data: bytes) -> None:
    if not data:
        raise ValueError("PDF vazio")
    if len(data) > MAX_LETTERHEAD_PDF_BYTES:
        raise ValueError(f"PDF excede o limite de {MAX_LETTERHEAD_PDF_BYTES // (1024 * 1024)} MB")
    if not data.startswith(b"%PDF"):
        raise ValueError("Arquivo não é um PDF válido")
    try:
        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) < 1:
            raise ValueError("PDF não possui páginas")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Não foi possível ler o PDF: {e}") from e


def _pdf2image_poppler_path() -> Optional[str]:
    """
    Production (Linux): Poppler no PATH do sistema — não passar poppler_path.

    Development (Windows): definir POPPLER_PATH para a pasta ``bin`` do Poppler
    (ex.: C:\\poppler\\Library\\bin). Se APP_ENV=development e POPPLER_PATH não
    existir, tenta o PATH padrão (útil para dev em Linux/Mac).
    """
    app_env = (os.getenv("APP_ENV") or "").strip().lower()
    if app_env == "production":
        return None
    if app_env != "development":
        return None
    raw = (os.getenv("POPPLER_PATH") or "").strip()
    if not raw:
        return None
    expanded = os.path.normpath(os.path.expandvars(os.path.expanduser(raw)))
    if not os.path.isdir(expanded):
        raise RuntimeError(
            f"POPPLER_PATH não é um diretório válido: {expanded!r}. "
            "No Windows, use a pasta bin do Poppler (ex.: C:\\poppler\\Library\\bin)."
        )
    return expanded


def _poppler_missing_message() -> str:
    app_env = (os.getenv("APP_ENV") or "").strip().lower()
    if app_env == "development":
        return (
            "Poppler não encontrado para pdf2image. "
            "No Windows: instale o Poppler, defina APP_ENV=development e POPPLER_PATH com o caminho da pasta bin "
            "(ex.: C:\\\\poppler\\\\Library\\\\bin). "
            "No Linux/Mac (dev): instale poppler e garanta pdftoppm no PATH, ou defina POPPLER_PATH."
        )
    return (
        "Poppler não encontrado no servidor (necessário para pdf2image). "
        "Em produção Linux, instale poppler-utils (pdftoppm no PATH)."
    )


def render_pdf_first_page_to_png_bytes(pdf_bytes: bytes, dpi: int = LETTERHEAD_RENDER_DPI) -> bytes:
    try:
        from pdf2image import convert_from_bytes
        from pdf2image.exceptions import PDFInfoNotInstalledError
    except ImportError as e:
        raise RuntimeError("pdf2image não instalado") from e

    poppler_path = _pdf2image_poppler_path()
    convert_kw: Dict[str, Any] = dict(
        dpi=dpi,
        first_page=1,
        last_page=1,
        fmt="png",
    )
    if poppler_path:
        convert_kw["poppler_path"] = poppler_path

    try:
        images = convert_from_bytes(pdf_bytes, **convert_kw)
    except PDFInfoNotInstalledError as e:
        raise RuntimeError(_poppler_missing_message()) from e
    except Exception as e:
        raise ValueError(f"Falha ao rasterizar a primeira página do PDF: {e}") from e

    if not images:
        raise ValueError("Conversão do PDF não retornou imagens")
    buf = io.BytesIO()
    images[0].save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _object_key_logo(city_id: str, ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if ext not in ("png", "jpg"):
        ext = "png"
    return f"cities/{city_id}/logo.{ext}"


def _object_key_letterhead_png(city_id: str) -> str:
    return f"cities/{city_id}/letterhead.png"


def _object_key_letterhead_pdf(city_id: str) -> str:
    return f"cities/{city_id}/letterhead.pdf"


class CityBrandingService:
    """Persistência e leitura de assets de branding por município."""

    def __init__(self) -> None:
        self.minio = MinIOService()
        self.bucket = self.minio.BUCKETS["MUNICIPALITY_LOGOS"]

    def upload_logo(self, city: City, file_bytes: bytes, replace: bool = False) -> None:
        fmt = validate_logo_bytes(file_bytes)
        ext = "jpg" if fmt == "jpg" else "png"
        key = _object_key_logo(city.id, ext)
        if city.logo_url and not replace:
            raise ValueError(
                "Já existe logo para este município. Envie replace=true para substituir."
            )
        if city.logo_url:
            try:
                self.minio.delete_file(self.bucket, city.logo_url)
            except Exception:
                logger.debug("Remoção de logo anterior ignorada", exc_info=True)

        rel = key.split("/", 2)[-1]
        ct = "image/jpeg" if ext == "jpg" else "image/png"
        up = self.minio.upload_city_branding_file(city.id, rel, file_bytes, content_type=ct)
        if not up or not up.get("object_name"):
            raise RuntimeError("Falha ao enviar logo para o armazenamento")
        city.logo_url = up["object_name"]
        db.session.add(city)

    def upload_letterhead_pdf(
        self,
        city: City,
        pdf_bytes: bytes,
        *,
        replace: bool = False,
        store_pdf: bool = True,
    ) -> None:
        validate_letterhead_pdf_bytes(pdf_bytes)
        png_bytes = render_pdf_first_page_to_png_bytes(pdf_bytes)

        if (city.letterhead_image_url or city.letterhead_pdf_url) and not replace:
            raise ValueError(
                "Já existe timbrado para este município. Envie replace=true para substituir."
            )

        for old_key in (city.letterhead_image_url, city.letterhead_pdf_url):
            if old_key:
                try:
                    self.minio.delete_file(self.bucket, old_key)
                except Exception:
                    logger.debug("Remoção de timbrado anterior ignorada", exc_info=True)

        png_key = _object_key_letterhead_png(city.id)
        pdf_key = _object_key_letterhead_pdf(city.id)

        up_png = self.minio.upload_city_branding_file(
            city.id, png_key.split("/", 2)[-1], png_bytes, content_type="image/png"
        )
        if not up_png or not up_png.get("object_name"):
            raise RuntimeError("Falha ao enviar PNG do timbrado para o armazenamento")
        city.letterhead_image_url = up_png["object_name"]

        if store_pdf:
            up_pdf = self.minio.upload_city_branding_file(
                city.id, pdf_key.split("/", 2)[-1], pdf_bytes, content_type="application/pdf"
            )
            if not up_pdf or not up_pdf.get("object_name"):
                raise RuntimeError("Falha ao enviar PDF do timbrado para o armazenamento")
            city.letterhead_pdf_url = up_pdf["object_name"]
        else:
            city.letterhead_pdf_url = None

        db.session.add(city)

    def delete_assets(
        self,
        city: City,
        *,
        logo: bool = False,
        letterhead: bool = False,
    ) -> None:
        if logo and city.logo_url:
            self.minio.delete_file(self.bucket, city.logo_url)
            city.logo_url = None
        if letterhead:
            if city.letterhead_image_url:
                self.minio.delete_file(self.bucket, city.letterhead_image_url)
                city.letterhead_image_url = None
            if city.letterhead_pdf_url:
                self.minio.delete_file(self.bucket, city.letterhead_pdf_url)
                city.letterhead_pdf_url = None
        db.session.add(city)

    def presigned_urls(self, city: City, *, expires_hours: int = 1) -> Dict[str, Optional[str]]:
        exp = timedelta(hours=expires_hours)
        out: Dict[str, Optional[str]] = {
            "logo_url": None,
            "letterhead_image_url": None,
            "letterhead_pdf_url": None,
        }
        if city.logo_url:
            try:
                out["logo_url"] = self.minio.get_presigned_url(self.bucket, city.logo_url, exp)
            except Exception as e:
                logger.warning("Presigned logo: %s", e)
        if city.letterhead_image_url:
            try:
                out["letterhead_image_url"] = self.minio.get_presigned_url(
                    self.bucket, city.letterhead_image_url, exp
                )
            except Exception as e:
                logger.warning("Presigned letterhead png: %s", e)
        if city.letterhead_pdf_url:
            try:
                out["letterhead_pdf_url"] = self.minio.get_presigned_url(
                    self.bucket, city.letterhead_pdf_url, exp
                )
            except Exception as e:
                logger.warning("Presigned letterhead pdf: %s", e)
        return out

    def build_test_data_branding_patch(self, city: City) -> Dict[str, str]:
        """
        Bytes do MinIO → base64 para templates (municipality_logo, letterhead_image_base64).
        """
        patch: Dict[str, str] = {}
        if city.logo_url:
            try:
                raw = self.minio.download_file(self.bucket, city.logo_url)
                if raw:
                    patch["municipality_logo"] = base64.b64encode(raw).decode("ascii")
            except Exception as e:
                logger.warning("Branding: não foi possível baixar logo city=%s: %s", city.id, e)
        if city.letterhead_image_url:
            try:
                raw = self.minio.download_file(self.bucket, city.letterhead_image_url)
                if raw:
                    patch["letterhead_image_base64"] = base64.b64encode(raw).decode("ascii")
            except Exception as e:
                logger.warning("Branding: não foi possível baixar timbrado city=%s: %s", city.id, e)
        return patch


def apply_city_branding_to_test_data(test_data: Optional[Dict[str, Any]], city: Optional[City]) -> Dict[str, Any]:
    """Mescla logo/timbrado do município em test_data (cópia superficial + branding)."""
    base: Dict[str, Any] = dict(test_data) if test_data else {}
    if not city:
        return base
    svc = CityBrandingService()
    patch = svc.build_test_data_branding_patch(city)
    base.update(patch)
    return base


def resolve_city_for_report_pdf(test: Any) -> Optional[City]:
    """Obtém City a partir da primeira turma da avaliação (relatório análise)."""
    try:
        if not getattr(test, "class_tests", None):
            return None
        first_ct = test.class_tests[0]
        from app.models.studentClass import Class

        cls = Class.query.get(first_ct.class_id)
        if not cls or not cls.school_id:
            return None
        from app.models.school import School

        school = School.query.get(cls.school_id)
        if not school or not school.city_id:
            return None
        return City.query.get(school.city_id)
    except Exception as e:
        logger.debug("resolve_city_for_report_pdf: %s", e)
        return None
