# -*- coding: utf-8 -*-
"""Upload/download de áudio da sessão ad-hoc de Fluência Leitora (MinIO)."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional, Tuple

from app import db
from app.afirme_ler.models import ReadingFluencySession
from app.afirme_ler.services.guided_audio_service import GuidedAudioService
from app.services.storage.minio_service import MinIOService
from app.utils.tenant_middleware import get_current_tenant_context

logger = logging.getLogger(__name__)

AUDIO_PARTS = frozenset({"q1", "q2", "q3", "mic_test"})

_EXT_BY_MIME = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


class FluencyAudioService:
    @staticmethod
    def api_playback_path(session_id: str, part: Optional[str] = None) -> str:
        path = f"/afirme-reading/fluency-sessions/{session_id}/audio"
        if part:
            path = f"{path}?part={part}"
        base = (os.getenv("PUBLIC_API_BASE_URL") or "").rstrip("/")
        return f"{base}{path}" if base else path

    @staticmethod
    def validate_part(part: Optional[str]) -> str:
        if not part:
            raise ValueError(
                "Campo 'part' é obrigatório (q1 | q2 | q3 | mic_test)."
            )
        normalized = str(part).strip().lower()
        if normalized not in AUDIO_PARTS:
            raise ValueError(
                f"part inválido. Use: {', '.join(sorted(AUDIO_PARTS))}."
            )
        return normalized

    @staticmethod
    def attach_part_audio(
        session: ReadingFluencySession,
        data: bytes,
        content_type: Optional[str],
        *,
        part: str,
        city_id: Optional[str] = None,
    ) -> dict:
        part = FluencyAudioService.validate_part(part)
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
            f"fluency/{resolved_city}/{session.id}/{part}/{uuid.uuid4().hex}.{ext}"
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
        # Garante detecção de mudança em JSON pelo SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(session, "part_audios")
        db.session.commit()

        audio_url = FluencyAudioService.api_playback_path(session.id, part=part)
        return {
            "part": part,
            "audioUrl": audio_url,
            "audioMimeType": mime,
            "audioSizeBytes": len(data),
            "hasAudio": True,
        }

    @staticmethod
    def download_part_audio(
        session: ReadingFluencySession, part: Optional[str] = None
    ) -> Tuple[bytes, str]:
        part_audios = session.part_audios or {}
        meta = None
        if part:
            part = FluencyAudioService.validate_part(part)
            meta = part_audios.get(part)
        elif part_audios:
            meta = next(iter(part_audios.values()))

        if not meta or not meta.get("bucket") or not meta.get("key"):
            raise LookupError("Sessão sem áudio para a parte solicitada.")

        data = MinIOService().download_file(meta["bucket"], meta["key"])
        mime = meta.get("mimeType") or "application/octet-stream"
        return data, mime

    @staticmethod
    def part_audio_summary(session: ReadingFluencySession) -> Dict[str, Any]:
        part_audios = session.part_audios if isinstance(session.part_audios, dict) else {}
        summary: Dict[str, Any] = {}
        for part in ("q1", "q2", "q3", "mic_test"):
            meta = part_audios.get(part)
            has = bool(meta and meta.get("key"))
            entry: Dict[str, Any] = {"hasAudio": has}
            if has:
                entry["audioUrl"] = FluencyAudioService.api_playback_path(
                    session.id, part=part
                )
                entry["audioMimeType"] = meta.get("mimeType")
                entry["audioSizeBytes"] = meta.get("sizeBytes")
            summary[part] = entry
        return summary

    @staticmethod
    def delete_all_best_effort(session: ReadingFluencySession) -> None:
        part_audios = session.part_audios or {}
        for meta in part_audios.values():
            GuidedAudioService.delete_audio_best_effort(
                meta.get("bucket"), meta.get("key")
            )
