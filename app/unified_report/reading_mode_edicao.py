# -*- coding: utf-8 -*-
"""
Modo B do Relatório Unificado — leitura por edição (ano + evaluation_kind).

Isolado do modo A (uma ReadingEvaluation) para remoção fácil se o gestor
ficar só com o padrão "por avaliação".

Não altera app.afirme_ler (scoring/services): apenas importa
FluencyResultsService helpers, _pick_report_session e FluencyScoring.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import joinedload

from app.afirme_ler.models import ReadingEvaluation, ReadingEvaluationSession, ReadingFluencySession
from app.afirme_ler.scoring import FluencyScoring
from app.afirme_ler.services.fluency_results_service import (
    FluencyResultsService,
    _as_str_set,
    _eval_ids,
    _pick_report_session,
    evaluation_year,
)
from app.afirme_ler.services.parsing import EVALUATION_KIND_LABELS, validate_evaluation_kind
from app.models.city import City

# Espelha o rótulo curto do service principal (não importar circularmente).
_LEITURA_EDICAO_ROTULO = {
    "entrada": "Leitura de Entrada",
    "formativa": "Leitura Formativa",
    "saida": "Leitura de Saída",
}


def find_reading_evaluations_for_edition(
    user: dict,
    *,
    ano: int,
    edicao: str,
    scope_class_ids: Sequence[str],
) -> List[ReadingEvaluation]:
    """
    Todas as ReadingEvaluation visíveis do mesmo kind+ano que cobrem
    ao menos uma turma do escopo (class_ids ∩ escopo).
    """
    kind = validate_evaluation_kind(edicao)
    scope = {str(cid) for cid in (scope_class_ids or []) if cid}
    visible = FluencyResultsService._visible_evaluations(user)
    matching: List[ReadingEvaluation] = []
    for evaluation in visible:
        if evaluation.evaluation_kind != kind:
            continue
        if evaluation_year(evaluation) != int(ano):
            continue
        eval_classes = _as_str_set(_eval_ids(evaluation, "class_ids"))
        if scope and eval_classes and not (eval_classes & scope):
            continue
        if scope and not eval_classes:
            # Sem turmas explícitas: inclui se a escola do escopo estiver coberta
            # (ou se não houver school_ids — ciclo amplo).
            school_ids = _as_str_set(_eval_ids(evaluation, "school_ids"))
            if school_ids:
                # Mantém; o filtro de alunos do relatório já delimita o universo.
                pass
        matching.append(evaluation)
    matching.sort(key=lambda e: ((e.title or "").lower(), str(e.id)))
    return matching


def build_reading_by_edition(
    user: dict,
    city: City,
    *,
    ano: int,
    edicao: str,
    scope_class_ids: Sequence[str],
    student_ids: Sequence[str],
) -> Tuple[None, Dict[str, Any], dict]:
    """
    Scores de leitura para o modo B.

    - Junta sessões de todas as avaliações da edição no escopo.
    - Prioridade por aluno: mesma de ``_pick_report_session``
      (finalizada → ausente → em_andamento → pendente; dentro do status, a mais recente).
    - Consultas em lote (IN): contagem de SQL constante com mais alunos.
    - aggregate=None: a comparação WARNING com leitoresFluentesPct fica só no modo A.

    Retorna (aggregate, by_student_id → StudentReadingScore, meta).
    """
    kind = validate_evaluation_kind(edicao)
    year = int(ano)
    evaluations = find_reading_evaluations_for_edition(
        user, ano=year, edicao=kind, scope_class_ids=scope_class_ids
    )
    if not evaluations:
        raise ValueError(
            "Nenhuma avaliação de leitura encontrada para o ano/edição no escopo informado"
        )

    ids = [str(sid) for sid in student_ids if sid]
    eval_ids = [item.id for item in evaluations]
    fluency_by_student: Dict[str, List[Any]] = defaultdict(list)
    legacy_by_student: Dict[str, List[Any]] = defaultdict(list)

    if eval_ids and ids:
        fluency_rows = (
            ReadingFluencySession.query.options(
                joinedload(ReadingFluencySession.evaluation)
            )
            .filter(
                ReadingFluencySession.reading_evaluation_id.in_(eval_ids),
                ReadingFluencySession.student_id.in_(ids),
            )
            .all()
        )
        for session in fluency_rows:
            fluency_by_student[str(session.student_id)].append(session)

        legacy_rows = ReadingEvaluationSession.query.filter(
            ReadingEvaluationSession.reading_evaluation_id.in_(eval_ids),
            ReadingEvaluationSession.student_id.in_(ids),
        ).all()
        for session in legacy_rows:
            legacy_by_student[str(session.student_id)].append(session)

    by_student: Dict[str, Any] = {}
    for sid in ids:
        session = _pick_report_session(fluency_by_student.get(sid) or [])
        if session is None:
            session = _pick_report_session(legacy_by_student.get(sid) or [])
        if session is not None:
            by_student[sid] = FluencyScoring.from_session(session)

    rotulo = _LEITURA_EDICAO_ROTULO.get(
        kind, f"Leitura {EVALUATION_KIND_LABELS.get(kind, kind)}"
    )
    meta = {
        "modo": "edicao",
        "id": None,
        "titulo": f"{rotulo} — todas as avaliações de {year}",
        "ano": year,
        "edicao": kind,
        "edicaoLabel": EVALUATION_KIND_LABELS.get(kind, kind),
        "avaliacoesIncluidas": [
            {"id": str(e.id), "titulo": e.title or ""} for e in evaluations
        ],
    }
    # city reservado para paridade de assinatura / futuros cortes; bundle não usado no B.
    _ = city
    _ = user
    return None, by_student, meta


def describe_picked_session(
    sessions: Iterable[Any],
) -> Optional[Dict[str, Any]]:
    """Útil em scripts de validação: qual sessão _pick_report_session escolheu e por quê."""
    items = list(sessions or [])
    if not items:
        return None
    picked = _pick_report_session(items)
    if picked is None:
        return None
    status = getattr(picked, "status", None)
    same_status = [s for s in items if getattr(s, "status", None) == status]
    return {
        "sessionId": str(getattr(picked, "id", "") or ""),
        "readingEvaluationId": str(
            getattr(picked, "reading_evaluation_id", "") or ""
        ),
        "status": status,
        "motivo": (
            f"Prioridade de status '{status}' "
            f"({len(same_status)} sessão(ões) nesse status; escolhida a mais recente)."
        ),
    }
