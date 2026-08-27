# -*- coding: utf-8 -*-
"""Playback da prova de fluência leitora por aluno (listas + texto + compreensão)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload

from app.models.student import Student
from app.permissions.roles import Roles
from app.afirme_ler.models import (
    ReadingFluencySession,
    ReadingText,
    ReadingWordList,
)
from app.afirme_ler.services.fluency_audio_service import FluencyAudioService
from app.afirme_ler.services.fluency_results_service import FluencyResultsService
from app.afirme_ler.services.parsing import EVALUATION_KIND_LABELS
from app.afirme_ler.services.reading_evaluation_service import ReadingEvaluationService


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _part(fluency_data: Optional[dict], key: str) -> Dict[str, Any]:
    if not isinstance(fluency_data, dict):
        return {}
    raw = fluency_data.get(key)
    return raw if isinstance(raw, dict) else {}


def _markings(part: dict) -> List[dict]:
    raw = part.get("markings")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _canonical_items(word_list: Optional[ReadingWordList]) -> List[str]:
    if word_list is None:
        return []
    items = word_list.items if isinstance(word_list.items, list) else []
    out: List[str] = []
    for item in items:
        text = str(item).strip() if item is not None else ""
        if text:
            out.append(text)
    return out


def _split_words(text: str) -> List[str]:
    return [token for token in str(text or "").split() if token]


def merge_list_words(
    canonical_items: List[str],
    markings: List[dict],
    last_word_position: Optional[int],
) -> List[dict]:
    """Une a lista canônica com as marcações. status null após o cursor vira nao_leu."""
    by_index: Dict[int, dict] = {}
    for item in markings:
        idx = _as_int(item.get("index"))
        if idx is None:
            continue
        by_index[idx] = item

    max_marking = max(by_index.keys(), default=-1)
    total = max(len(canonical_items), max_marking + 1)
    words: List[dict] = []
    for index in range(total):
        marking = by_index.get(index)
        canonical = canonical_items[index] if index < len(canonical_items) else ""
        word = ""
        if marking:
            raw_word = marking.get("word")
            word = str(raw_word).strip() if raw_word not in (None, "") else canonical
        else:
            word = canonical
        status = None
        source = None
        if marking:
            raw_status = marking.get("status")
            if raw_status not in (None, ""):
                status = str(raw_status).strip().lower()
            source = marking.get("source")
        if status is None and last_word_position is not None:
            if index >= last_word_position:
                status = "nao_leu"
        elif status is None and last_word_position is None:
            status = "nao_leu"
        entry: Dict[str, Any] = {
            "index": index,
            "word": word,
            "status": status,
        }
        if source:
            entry["source"] = source
        words.append(entry)
    return words


def _last_line_index(
    lines: List[dict],
    last_word_position: Optional[int],
) -> Optional[int]:
    if last_word_position is None:
        return None
    if last_word_position <= 0:
        return None
    counted = 0
    last_seen: Optional[int] = None
    for line in lines:
        tokens = _split_words(line.get("text") or "")
        counted += len(tokens)
        last_seen = _as_int(line.get("lineIndex"), default=last_seen)
        if counted >= last_word_position:
            return last_seen
    return last_seen


def build_texto_payload(
    *,
    reading_text: Optional[ReadingText],
    part: dict,
    audio: dict,
) -> dict:
    lines_raw = part.get("lines") if isinstance(part.get("lines"), list) else []
    lines = [item for item in lines_raw if isinstance(item, dict)]
    line_texts = [str(item.get("text") or "") for item in lines]
    content_from_lines = "\n".join(line_texts).strip()
    content = ""
    title = None
    if reading_text is not None:
        title = reading_text.title
        content = (reading_text.content or "").strip()
    if not content:
        content = content_from_lines

    markings = _markings(part)
    has_word_markings = bool(markings)
    last_word_position = _as_int(part.get("lastWordPosition"))
    if last_word_position is None:
        last_word_position = _as_int(part.get("wordsRead"), default=0)

    canonical_tokens: List[str] = []
    if line_texts:
        for text in line_texts:
            canonical_tokens.extend(_split_words(text))
    elif content:
        canonical_tokens = _split_words(content)

    words = None
    if has_word_markings:
        words = merge_list_words(canonical_tokens, markings, last_word_position)

    normalized_lines = []
    for item in lines:
        normalized_lines.append(
            {
                "lineIndex": _as_int(item.get("lineIndex"), default=0),
                "text": str(item.get("text") or ""),
                "wrongWordsCount": _as_int(item.get("wrongWordsCount"), default=0) or 0,
            }
        )

    payload: Dict[str, Any] = {
        "readingTextId": reading_text.id if reading_text else None,
        "title": title,
        "content": content,
        "lines": normalized_lines,
        "markings": markings if has_word_markings else None,
        "hasWordMarkings": has_word_markings,
        "words": words,
        "lastWordPosition": last_word_position if last_word_position is not None else 0,
        "lastLineIndex": _last_line_index(normalized_lines, last_word_position),
        "wordsRead": _as_int(part.get("wordsRead"), default=0) or 0,
        "totalWords": _as_int(part.get("totalWords")),
        "unreadAfterEnd": _as_int(part.get("unreadAfterEnd")),
        "errorsCount": _as_int(part.get("errorsCount"), default=0) or 0,
        "readingTimeSeconds": part.get("readingTimeSeconds"),
        "skipped": bool(part.get("skipped")),
        "notReadReason": part.get("notReadReason"),
        "accuracy": part.get("accuracy"),
        "plcm": part.get("plcm"),
        "precisionLevel": part.get("precisionLevel"),
        "fluencyLevel": part.get("fluencyLevel"),
        "obeyedSensePauses": part.get("obeyedSensePauses"),
        "hasAudio": bool(audio.get("hasAudio")),
    }
    if audio.get("audioUrl"):
        payload["audioUrl"] = audio.get("audioUrl")
    return payload


def _list_payload(
    *,
    word_list: Optional[ReadingWordList],
    word_list_id: Optional[str],
    part: dict,
    audio: dict,
) -> dict:
    last_word_position = _as_int(part.get("lastWordPosition"))
    if last_word_position is None:
        last_word_position = _as_int(part.get("wordsRead"), default=0) or 0
    words = merge_list_words(
        _canonical_items(word_list),
        _markings(part),
        last_word_position,
    )
    payload: Dict[str, Any] = {
        "wordListId": word_list.id if word_list else word_list_id,
        "kind": word_list.kind if word_list else None,
        "name": word_list.name if word_list else None,
        "words": words,
        "lastWordPosition": last_word_position,
        "wordsRead": _as_int(part.get("wordsRead"), default=0) or 0,
        "errorsCount": _as_int(part.get("errorsCount"), default=0) or 0,
        "readingTimeSeconds": part.get("readingTimeSeconds"),
        "skipped": bool(part.get("skipped")),
        "notReadReason": part.get("notReadReason"),
        "accuracy": part.get("accuracy"),
        "plcm": part.get("plcm"),
        "precisionLevel": part.get("precisionLevel"),
        "fluencyLevel": part.get("fluencyLevel"),
        "hasAudio": bool(audio.get("hasAudio")),
    }
    if audio.get("audioUrl"):
        payload["audioUrl"] = audio.get("audioUrl")
    return payload


class FluencyAplicacaoService:
    @staticmethod
    def _role(user: Dict[str, Any]) -> str:
        return Roles.normalize(user.get("role", ""))

    @staticmethod
    def student_aplicacao(
        user: Dict[str, Any],
        student_id: str,
        filters: dict,
    ) -> dict:
        evaluation, _visible = FluencyResultsService._require_evaluation(user, filters)

        student = Student.query.get(student_id)
        if not student:
            raise LookupError("Estudante não encontrado.")

        allowed = FluencyResultsService._apply_permission_roster(
            user, [student], [evaluation]
        )
        if not allowed and FluencyAplicacaoService._role(user) not in (
            Roles.ADMIN,
            Roles.TECADM,
        ):
            raise LookupError("Estudante não encontrado neste recorte.")

        sessions = (
            ReadingFluencySession.query.options(
                joinedload(ReadingFluencySession.student),
                joinedload(ReadingFluencySession.evaluation),
                joinedload(ReadingFluencySession.answers),
            )
            .filter(
                ReadingFluencySession.reading_evaluation_id == evaluation.id,
                ReadingFluencySession.student_id == str(student.id),
            )
            .all()
        )
        session = ReadingEvaluationService._pick_application(sessions)
        if session is None or session.status == "ausente":
            raise LookupError(
                "Aplicação não encontrada para este aluno nesta avaliação."
            )

        return FluencyAplicacaoService._serialize(session)

    @staticmethod
    def _serialize(session: ReadingFluencySession) -> dict:
        fluency = session.fluency_data if isinstance(session.fluency_data, dict) else {}
        q1 = _part(fluency, "q1")
        q2 = _part(fluency, "q2")
        q3 = _part(fluency, "q3")
        audio = FluencyAudioService.part_audio_summary(session)

        word_list_ids = [
            session.words_word_list_id,
            session.uncommon_word_list_id,
        ]
        word_lists = {}
        present_ids = [item for item in word_list_ids if item]
        if present_ids:
            rows = ReadingWordList.query.filter(ReadingWordList.id.in_(present_ids)).all()
            word_lists = {row.id: row for row in rows}

        reading_text = None
        if session.reading_text_id:
            reading_text = (
                ReadingText.query.options(joinedload(ReadingText.questions))
                .filter_by(id=session.reading_text_id)
                .first()
            )

        questions_by_id = {}
        if reading_text is not None:
            for question in reading_text.questions or []:
                questions_by_id[question.id] = question

        answers_payload = []
        for answer in session.answers or []:
            question = questions_by_id.get(answer.reading_text_question_id)
            item: Dict[str, Any] = {
                "readingTextQuestionId": answer.reading_text_question_id,
                "selectedOption": answer.selected_option,
                "isCorrect": bool(answer.is_correct),
            }
            if question is not None:
                item["statement"] = question.statement
                item["options"] = (
                    question.options if isinstance(question.options, list) else []
                )
                item["correctOption"] = question.correct_option
                item["descriptor"] = question.descriptor
            answers_payload.append(item)

        evaluation = session.evaluation
        metrics = fluency.get("metrics") if isinstance(fluency.get("metrics"), dict) else {}
        ica_breakdown = session.ica_breakdown or metrics.get("icaBreakdown")
        leiturimetro = None
        if isinstance(ica_breakdown, dict):
            leiturimetro = ica_breakdown.get("leiturimetroLevel")
        if leiturimetro is None:
            leiturimetro = metrics.get("leiturimetroLevel")

        return {
            "studentId": session.student_id,
            "studentName": session.student.name if session.student else None,
            "sessionId": session.id,
            "evaluationId": session.reading_evaluation_id,
            "evaluationKind": (
                evaluation.evaluation_kind if evaluation else None
            ),
            "evaluationKindLabel": (
                EVALUATION_KIND_LABELS.get(evaluation.evaluation_kind)
                if evaluation
                else None
            ),
            "status": session.status,
            "caderno": session.caderno or fluency.get("caderno"),
            "lista1": _list_payload(
                word_list=word_lists.get(session.words_word_list_id),
                word_list_id=session.words_word_list_id,
                part=q1,
                audio=audio.get("q1") or {},
            ),
            "lista2": _list_payload(
                word_list=word_lists.get(session.uncommon_word_list_id),
                word_list_id=session.uncommon_word_list_id,
                part=q2,
                audio=audio.get("q2") or {},
            ),
            "texto": build_texto_payload(
                reading_text=reading_text,
                part=q3,
                audio=audio.get("q3") or {},
            ),
            "compreensao": {
                "correctCount": session.comprehension_correct_count,
                "total": session.comprehension_total,
                "score": session.comprehension_score,
                "answers": answers_payload,
            },
            "audioUrls": {
                part: meta.get("audioUrl")
                for part, meta in audio.items()
                if meta.get("hasAudio") and meta.get("audioUrl")
            },
            "calculatedPlcm": session.calculated_plcm,
            "calculatedAccuracy": session.calculated_accuracy,
            "precisionLevel": session.precision_level,
            "fluencyLevel": session.fluency_level,
            "icaScore": session.ica_score,
            "icaBreakdown": ica_breakdown,
            "leiturimetroLevel": leiturimetro,
            "startedAt": session.started_at.isoformat() if session.started_at else None,
            "submittedAt": (
                session.submitted_at.isoformat() if session.submitted_at else None
            ),
        }
