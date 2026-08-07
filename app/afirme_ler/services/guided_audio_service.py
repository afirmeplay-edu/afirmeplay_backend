# -*- coding: utf-8 -*-
"""Upload e playback de áudio da Leitura Guiada (MinIO)."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional, Set, Tuple

from app import db
from app.afirme_ler.models import ReadingGuidedSession
from app.services.storage.minio_service import MinIOService
from app.utils.tenant_middleware import get_current_tenant_context

logger = logging.getLogger(__name__)

_MAX_AUDIO_BYTES = int(os.getenv("AFIRME_READING_MAX_AUDIO_MB", "40")) * 1024 * 1024

_ALLOWED_MIME_TYPES: Set[str] = {
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "video/webm",  # Chrome MediaRecorder às vezes envia video/webm
}

_EXT_BY_MIME = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


class GuidedAudioService:
    @staticmethod
    def _normalize_mime(content_type: Optional[str]) -> str:
        raw = (content_type or "").split(";")[0].strip().lower()
        return raw or "application/octet-stream"

    @staticmethod
    def validate_upload(data: bytes, content_type: Optional[str]) -> str:
        if not data:
            raise ValueError("Arquivo de áudio vazio.")
        if len(data) > _MAX_AUDIO_BYTES:
            raise ValueError(
                f"Áudio excede o tamanho máximo permitido ({_MAX_AUDIO_BYTES // (1024 * 1024)} MB)."
            )
        mime = GuidedAudioService._normalize_mime(content_type)
        if mime not in _ALLOWED_MIME_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_MIME_TYPES))
            raise ValueError(f"Tipo de áudio não suportado ({mime}). Aceitos: {allowed}.")
        return mime

    @staticmethod
    def api_playback_path(session_id: str) -> str:
        """Path autenticado GET para o frontend (fetch + blob / Authorization)."""
        path = f"/afirme-reading/guided-sessions/{session_id}/audio"
        base = (os.getenv("PUBLIC_API_BASE_URL") or "").rstrip("/")
        return f"{base}{path}" if base else path

    @staticmethod
    def download_audio(session: ReadingGuidedSession) -> Tuple[bytes, str]:
        if not session.audio_key or not session.audio_bucket:
            raise LookupError("Sessão sem áudio.")
        minio = MinIOService()
        data = minio.download_file(session.audio_bucket, session.audio_key)
        mime = session.audio_mime_type or "application/octet-stream"
        return data, mime

    @staticmethod
    def delete_audio_best_effort(bucket: Optional[str], object_name: Optional[str]) -> None:
        if not bucket or not object_name:
            return
        try:
            MinIOService().delete_file(bucket, object_name)
        except Exception:
            logger.warning(
                "Falha ao remover áudio MinIO (best-effort): %s/%s",
                bucket,
                object_name,
                exc_info=True,
            )

    @staticmethod
    def attach_audio(
        session: ReadingGuidedSession,
        data: bytes,
        content_type: Optional[str],
        *,
        city_id: Optional[str] = None,
    ) -> ReadingGuidedSession:
        mime = GuidedAudioService.validate_upload(data, content_type)

        ctx = get_current_tenant_context()
        resolved_city = city_id
        if not resolved_city and ctx and getattr(ctx, "city_id", None):
            resolved_city = str(ctx.city_id)
        if not resolved_city:
            resolved_city = "unknown"

        bucket = MinIOService.BUCKETS["AFIRME_READING_AUDIO"]
        ext = _EXT_BY_MIME.get(mime, "webm")
        object_name = (
            f"guided/{resolved_city}/{session.id}/{uuid.uuid4().hex}.{ext}"
        )

        if session.audio_key and session.audio_bucket:
            GuidedAudioService.delete_audio_best_effort(
                session.audio_bucket, session.audio_key
            )

        minio = MinIOService()
        result = minio.upload_file(
            bucket_name=bucket,
            object_name=object_name,
            data=data,
            content_type=mime,
        )
        if not result:
            raise RuntimeError("Falha ao enviar áudio para o armazenamento.")

        session.audio_bucket = result.get("bucket") or bucket
        session.audio_key = result.get("object_name") or object_name
        session.audio_mime_type = mime
        session.audio_size_bytes = len(data)
        db.session.commit()
        return session
