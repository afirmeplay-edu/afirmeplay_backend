# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


@dataclass
class SttResult:
    text: str
    provider: str
    model: str
    duration_seconds: Optional[float] = None
    raw: Optional[Dict[str, Any]] = None


class SttProvider(Protocol):
    def transcribe(self, audio_bytes: bytes, mime_type: str) -> SttResult:
        ...


def get_stt_provider() -> SttProvider:
    provider = (os.getenv("AFIRME_READING_STT_PROVIDER") or "whisper_api").strip().lower()
    if provider in ("whisper_api", "openai", "whisper"):
        from app.afirme_ler.services.stt.whisper_api import WhisperApiProvider

        return WhisperApiProvider()
    raise RuntimeError(f"STT provider não suportado: {provider}")
