# -*- coding: utf-8 -*-
"""Upload/download de áudio da Leitura Guiada Automática (MinIO)."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional, Tuple

from app import db
from app.afirme_ler.models import ReadingGuidedAutoSession
from app.afirme_ler.services.guided_audio_service import GuidedAudioService
from app.services.storage.minio_service import MinIOService
from app.utils.tenant_middleware import get_current_tenant_context

logger = logging.getLogger(__name__)

_EXT_BY_MIME = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


class GuidedAutoAudioService:
    @staticmethod
    def api_playback_path(session_id: str, part: Optional[str] = None) -> str:
        path = f"/afirme-reading/guided-auto-sessions/{session_id}/audio"
        if part:
            path = f"{path}?part={part}"
        base = (os.getenv("PUBLIC_API_BASE_URL") or "").rstrip("/")
        return f"{base}{path}" if base else path

    @staticmethod
    def attach_part_audio(
        session: ReadingGuidedAutoSession,
        data: bytes,
        content_type: Optional[str],
        *,
        part: str,
        city_id: Optional[str] = None,
    ) -> ReadingGuidedAutoSession:
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
            f"guided-auto/{resolved_city}/{session.id}/{part}/{uuid.uuid4().hex}.{ext}"
        )

        part_audios: Dict[str, Any] = dict(session.part_audios or {})
        previous = part_audios.get(part) or {}
        if previous.get("bucket") and previous.get("key"):
            GuidedAudioService.delete_audio_best_effort(
                previous.get("bucket"), previous.get("key")
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

        meta = {
            "bucket": result.get("bucket") or bucket,
            "key": result.get("object_name") or object_name,
            "mimeType": mime,
            "sizeBytes": len(data),
        }
        part_audios[part] = meta
        session.part_audios = part_audios

        # Campos “principais” apontam para o último áudio enviado (playback simples)
        session.audio_bucket = meta["bucket"]
        session.audio_key = meta["key"]
        session.audio_mime_type = mime
        session.audio_size_bytes = len(data)
        db.session.commit()
        return session

    @staticmethod
    def download_part_audio(
        session: ReadingGuidedAutoSession, part: Optional[str] = None
    ) -> Tuple[bytes, str]:
        part_audios = session.part_audios or {}
        meta = None
        if part and part in part_audios:
            meta = part_audios[part]
        elif session.audio_key and session.audio_bucket:
            meta = {
                "bucket": session.audio_bucket,
                "key": session.audio_key,
                "mimeType": session.audio_mime_type,
            }
        elif part_audios:
            meta = next(iter(part_audios.values()))

        if not meta or not meta.get("bucket") or not meta.get("key"):
            raise LookupError("Sessão sem áudio.")

        data = MinIOService().download_file(meta["bucket"], meta["key"])
        mime = meta.get("mimeType") or session.audio_mime_type or "application/octet-stream"
        return data, mime

    @staticmethod
    def delete_all_best_effort(session: ReadingGuidedAutoSession) -> None:
        part_audios = session.part_audios or {}
        for meta in part_audios.values():
            GuidedAudioService.delete_audio_best_effort(
                meta.get("bucket"), meta.get("key")
            )
        if session.audio_bucket and session.audio_key:
            GuidedAudioService.delete_audio_best_effort(
                session.audio_bucket, session.audio_key
            )
