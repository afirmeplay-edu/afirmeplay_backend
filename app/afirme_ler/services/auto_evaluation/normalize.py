# -*- coding: utf-8 -*-
"""Normalização e tokenização de texto para alinhamento de leitura."""
from __future__ import annotations

import re
import unicodedata
from typing import List


_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    text = str(value).lower().strip()
    text = strip_accents(text)
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def tokenize(value: str) -> List[str]:
    normalized = normalize_text(value)
    if not normalized:
        return []
    return [token for token in normalized.split(" ") if token]
