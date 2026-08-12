# -*- coding: utf-8 -*-
"""Alinhamento em janela entre tokens esperados e reconhecidos."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

from app.afirme_ler.services.auto_evaluation.levenshtein import similarity
from app.afirme_ler.services.auto_evaluation.phonetic import to_phonetic

MatchType = Literal["correct", "error", "omitted", "extra", "repeat"]

SIMILARITY_THRESHOLD = 0.85
WINDOW_WORD_LIST = 4
WINDOW_TEXT = 6


@dataclass
class AlignmentItem:
    position: int
    expected_token: Optional[str]
    recognized_token: Optional[str]
    similarity: Optional[float]
    phonetic_expected: Optional[str]
    phonetic_recognized: Optional[str]
    match_type: MatchType


@dataclass
class AlignmentResult:
    items: List[AlignmentItem]
    words_read: int
    errors_count: int
    omitted_count: int
    extra_count: int
    correct_count: int


def _token_similarity(expected: str, recognized: str) -> float:
    if expected == recognized:
        return 1.0
    direct = similarity(expected, recognized)
    phonetic = similarity(to_phonetic(expected), to_phonetic(recognized))
    return max(direct, phonetic)


def align_tokens(
    expected_tokens: List[str],
    recognized_tokens: List[str],
    *,
    window: int = WINDOW_TEXT,
    threshold: float = SIMILARITY_THRESHOLD,
) -> AlignmentResult:
    """
    Alinha tokens com janela deslizante.
    O cursor do esperado avança em acerto confirmado ou similaridade >= threshold.
    """
    items: List[AlignmentItem] = []
    i = 0  # expected cursor
    j = 0  # recognized cursor
    position = 0
    correct_count = 0
    errors_count = 0
    omitted_count = 0
    extra_count = 0
    words_read = 0

    while i < len(expected_tokens) and j < len(recognized_tokens):
        expected = expected_tokens[i]
        best_k = None
        best_score = -1.0
        best_token = None
        end = min(len(recognized_tokens), j + max(1, window))

        for k in range(j, end):
            candidate = recognized_tokens[k]
            score = _token_similarity(expected, candidate)
            if score > best_score:
                best_score = score
                best_k = k
                best_token = candidate

        if best_k is not None and best_score >= threshold:
            # Tokens reconhecidos pulados na janela = extras / repetições
            for k in range(j, best_k):
                skipped = recognized_tokens[k]
                match_type: MatchType = "repeat" if skipped == expected else "extra"
                items.append(
                    AlignmentItem(
                        position=position,
                        expected_token=None,
                        recognized_token=skipped,
                        similarity=None,
                        phonetic_expected=None,
                        phonetic_recognized=to_phonetic(skipped),
                        match_type=match_type,
                    )
                )
                position += 1
                extra_count += 1
                words_read += 1

            items.append(
                AlignmentItem(
                    position=position,
                    expected_token=expected,
                    recognized_token=best_token,
                    similarity=round(best_score, 4),
                    phonetic_expected=to_phonetic(expected),
                    phonetic_recognized=to_phonetic(best_token or ""),
                    match_type="correct",
                )
            )
            position += 1
            correct_count += 1
            words_read += 1
            i += 1
            j = best_k + 1
        else:
            # Sem match na janela: conta erro no esperado e consome 1 reconhecido se houver
            recognized = recognized_tokens[j] if j < len(recognized_tokens) else None
            score = (
                _token_similarity(expected, recognized)
                if recognized is not None
                else None
            )
            items.append(
                AlignmentItem(
                    position=position,
                    expected_token=expected,
                    recognized_token=recognized,
                    similarity=round(score, 4) if score is not None else None,
                    phonetic_expected=to_phonetic(expected),
                    phonetic_recognized=to_phonetic(recognized) if recognized else None,
                    match_type="error",
                )
            )
            position += 1
            errors_count += 1
            words_read += 1
            i += 1
            if recognized is not None:
                j += 1

    while i < len(expected_tokens):
        expected = expected_tokens[i]
        items.append(
            AlignmentItem(
                position=position,
                expected_token=expected,
                recognized_token=None,
                similarity=None,
                phonetic_expected=to_phonetic(expected),
                phonetic_recognized=None,
                match_type="omitted",
            )
        )
        position += 1
        omitted_count += 1
        errors_count += 1
        i += 1

    while j < len(recognized_tokens):
        recognized = recognized_tokens[j]
        items.append(
            AlignmentItem(
                position=position,
                expected_token=None,
                recognized_token=recognized,
                similarity=None,
                phonetic_expected=None,
                phonetic_recognized=to_phonetic(recognized),
                match_type="extra",
            )
        )
        position += 1
        extra_count += 1
        words_read += 1
        j += 1

    return AlignmentResult(
        items=items,
        words_read=words_read,
        errors_count=errors_count,
        omitted_count=omitted_count,
        extra_count=extra_count,
        correct_count=correct_count,
    )
