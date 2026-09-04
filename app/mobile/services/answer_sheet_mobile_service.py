# -*- coding: utf-8 -*-
"""
Serviço para integração de cartões resposta com mobile/offline.
Serializa gabaritos e processa entrada manual de respostas do app.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app import db
from app.answer_sheets.models.answerSheetGabarito import AnswerSheetGabarito
from app.answer_sheets.models.answerSheetResult import AnswerSheetResult
from app.models.student import Student
from app.models.studentClass import Class
from app.reports.report_analysis.answer_sheet_report_builder import (
    get_answer_sheet_target_classes_for_report,
)

logger = logging.getLogger(__name__)

_BROAD_GABARITO_SCOPE_TYPES = ("city", "school")


def _load_gabaritos_for_school(
    school_id: str,
    gabarito_ids: Optional[Set[str]] = None,
) -> List[AnswerSheetGabarito]:
    """
    Gabaritos com school_id na linha + escopo municipal/escola (school_id nulo).
    Com gabarito_ids, inclui IDs explícitos do pacote mesmo sem school_id.
    """
    by_id: Dict[str, AnswerSheetGabarito] = {}

    school_query = AnswerSheetGabarito.query.filter(
        AnswerSheetGabarito.school_id == school_id,
    )
    if gabarito_ids:
        school_query = school_query.filter(
            AnswerSheetGabarito.id.in_(list(gabarito_ids))
        )
    for gab in school_query.order_by(AnswerSheetGabarito.created_at.desc()).limit(50).all():
        by_id[str(gab.id)] = gab

    if gabarito_ids:
        missing = gabarito_ids - set(by_id.keys())
        if missing:
            for gab in AnswerSheetGabarito.query.filter(
                AnswerSheetGabarito.id.in_(list(missing))
            ).all():
                by_id[str(gab.id)] = gab
    else:
        broad_query = AnswerSheetGabarito.query.filter(
            AnswerSheetGabarito.school_id.is_(None),
            AnswerSheetGabarito.scope_type.in_(_BROAD_GABARITO_SCOPE_TYPES),
        )
        for gab in broad_query.order_by(
            AnswerSheetGabarito.created_at.desc()
        ).limit(50).all():
            by_id.setdefault(str(gab.id), gab)

    ordered = sorted(by_id.values(), key=lambda g: g.created_at or "", reverse=True)
    return ordered[:50]


def serialize_gabarito_for_mobile(gabarito: AnswerSheetGabarito) -> Dict[str, Any]:
    """
    Serializa gabarito para envio ao app mobile.
    Inclui apenas estrutura de questões/alternativas, SEM conteúdo das questões.
    
    Args:
        gabarito: Instância de AnswerSheetGabarito
        
    Returns:
        Dict com dados do gabarito formatado para mobile
    """
    blocks_config = gabarito.blocks_config or {}
    if isinstance(blocks_config, str):
        try:
            blocks_config = json.loads(blocks_config)
        except json.JSONDecodeError:
            blocks_config = {}
    
    topology = blocks_config.get("topology") or {}
    blocks_raw = topology.get("blocks") or []
    
    # Serializar blocos (apenas estrutura)
    blocks_out: List[Dict[str, Any]] = []
    for block in blocks_raw:
        questions_out = []
        for question in block.get("questions") or []:
            q = question.get("q")
            if q is None:
                continue
            questions_out.append({
                "q": int(q),
                "alternatives": question.get("alternatives") or ["A", "B", "C", "D"],
            })
        
        blocks_out.append({
            "block_id": block.get("block_id"),
            "subject_id": block.get("subject_id"),
            "subject_name": block.get("subject_name"),
            "questions": questions_out,
        })
    
    # Se não tiver blocos configurados, gerar estrutura padrão
    if not blocks_out and gabarito.num_questions:
        questions_out = []
        for q_num in range(1, gabarito.num_questions + 1):
            questions_out.append({
                "q": q_num,
                "alternatives": ["A", "B", "C", "D"],
            })
        blocks_out.append({
            "block_id": 1,
            "subject_id": None,
            "subject_name": None,
            "questions": questions_out,
        })
    
    return {
        "gabarito_id": str(gabarito.id),
        "title": gabarito.title or "Cartão Resposta",
        "num_questions": gabarito.num_questions,
        "use_blocks": bool(gabarito.use_blocks),
        "blocks": blocks_out,
        "scope_type": gabarito.scope_type,
        "test_id": str(gabarito.test_id) if gabarito.test_id else None,
        "created_at": gabarito.created_at.isoformat() + "Z" if gabarito.created_at else None,
    }


def collect_gabaritos_for_school(
    school_id: str,
    gabarito_ids: Optional[Set[str]] = None,
    class_ids: Optional[Set[str]] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[Tuple[str, str]]]:
    """
    Coleta gabaritos ativos de uma escola e seus vínculos com alunos.
    
    Args:
        school_id: ID da escola
        gabarito_ids: IDs específicos de gabaritos a incluir (opcional, filtra)
        class_ids: IDs de turmas para filtrar alunos (opcional)
        
    Returns:
        Tupla (gabaritos_dict, student_gabarito_links)
        - gabaritos_dict: {gabarito_id: dados_serializados}
        - student_gabarito_links: [(student_id, gabarito_id), ...]
    """
    gabaritos = _load_gabaritos_for_school(school_id, gabarito_ids)
    if not gabaritos:
        return {}, []

    gabaritos_dict: Dict[str, Dict[str, Any]] = {}
    student_links: List[Tuple[str, str]] = []

    for gabarito in gabaritos:
        gabarito_id = str(gabarito.id)
        gabaritos_dict[gabarito_id] = serialize_gabarito_for_mobile(gabarito)

        try:
            turmas_alvo = get_answer_sheet_target_classes_for_report(
                gabarito, "school", school_id
            )
        except Exception as e:
            logger.warning(
                "Erro ao buscar turmas-alvo para gabarito %s: %s",
                gabarito_id,
                e,
            )
            turmas_alvo = []

        if not turmas_alvo:
            logger.warning(
                "Gabarito %s sem turmas-alvo para escola %s",
                gabarito_id,
                school_id,
            )
            continue

        if class_ids:
            turmas_alvo = [t for t in turmas_alvo if str(t.id) in class_ids]

        if not turmas_alvo:
            logger.warning(
                "Gabarito %s sem turmas após filtro de class_ids",
                gabarito_id,
            )
            continue

        turma_ids = [c.id for c in turmas_alvo]
        if turma_ids:
            alunos = Student.query.filter(Student.class_id.in_(turma_ids)).all()
            logger.info(
                "Gabarito %s: %s alunos em %s turmas",
                gabarito_id,
                len(alunos),
                len(turma_ids),
            )
            for aluno in alunos:
                student_links.append((str(aluno.id), gabarito_id))

    return gabaritos_dict, student_links


def get_gabarito_student_results(gabarito_id: str, student_ids: List[str]) -> Dict[str, Optional[str]]:
    """
    Retorna status de correção para cada aluno em um gabarito.
    
    Args:
        gabarito_id: ID do gabarito
        student_ids: Lista de IDs de alunos
        
    Returns:
        Dict {student_id: result_id} ou {student_id: None} se não tiver resultado
    """
    if not student_ids:
        return {}
    
    results = AnswerSheetResult.query.filter(
        AnswerSheetResult.gabarito_id == gabarito_id,
        AnswerSheetResult.student_id.in_(student_ids)
    ).all()
    
    results_map: Dict[str, Optional[str]] = {str(sid): None for sid in student_ids}
    
    # Pegar apenas o resultado mais recente por aluno
    for result in sorted(results, key=lambda r: r.corrected_at or "", reverse=True):
        sid = str(result.student_id)
        if sid in results_map and results_map[sid] is None:
            results_map[sid] = str(result.id)
    
    return results_map
