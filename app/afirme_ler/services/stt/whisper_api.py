# -*- coding: utf-8 -*-
"""Speech-to-Text via OpenAI Whisper API."""
from __future__ import annotations

import io
import os
from typing import Optional

from app.afirme_ler.services.stt.base import SttResult

_MIME_TO_FILENAME = {
    "audio/webm": "audio.webm",
    "video/webm": "audio.webm",
    "audio/ogg": "audio.ogg",
    "audio/mp4": "audio.m4a",
    "audio/mpeg": "audio.mp3",
    "audio/wav": "audio.wav",
    "audio/x-wav": "audio.wav",
}


class WhisperApiProvider:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv(
            "AFIRME_READING_OPENAI_API_KEY"
        )
        self.model = model or os.getenv("AFIRME_READING_STT_MODEL") or "whisper-1"
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY (ou AFIRME_READING_OPENAI_API_KEY) não configurada para STT."
            )

    def transcribe(self, audio_bytes: bytes, mime_type: str) -> SttResult:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        filename = _MIME_TO_FILENAME.get((mime_type or "").split(";")[0].strip().lower(), "audio.webm")
        buffer = io.BytesIO(audio_bytes)
        buffer.name = filename

        response = client.audio.transcriptions.create(
            model=self.model,
            file=buffer,
            language="pt",
            response_format="verbose_json",
        )

        text = getattr(response, "text", None) or ""
        duration = getattr(response, "duration", None)
        raw = None
        try:
            raw = response.model_dump() if hasattr(response, "model_dump") else None
        except Exception:
            raw = None

        return SttResult(
            text=text.strip(),
            provider="whisper_api",
            model=self.model,
            duration_seconds=float(duration) if duration is not None else None,
            raw=raw,
        )
