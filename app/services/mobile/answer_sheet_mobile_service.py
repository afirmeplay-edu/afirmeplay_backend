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
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.student import Student
from app.models.studentClass import Class
from app.report_analysis.answer_sheet_report_builder import (
    get_answer_sheet_target_classes_for_report,
)

logger = logging.getLogger(__name__)


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
    # Buscar gabaritos da escola
    query = AnswerSheetGabarito.query.filter(
        AnswerSheetGabarito.school_id == school_id,
    )
    
    # Filtrar por gabarito_ids específicos se fornecido
    if gabarito_ids:
        query = query.filter(AnswerSheetGabarito.id.in_(list(gabarito_ids)))
    
    gabaritos = query.order_by(AnswerSheetGabarito.created_at.desc()).limit(50).all()
    
    if not gabaritos:
        return {}, []
    
    gabaritos_dict: Dict[str, Dict[str, Any]] = {}
    student_links: List[Tuple[str, str]] = []
    
    for gabarito in gabaritos:
        gabarito_id = str(gabarito.id)
        gabaritos_dict[gabarito_id] = serialize_gabarito_for_mobile(gabarito)
        
        # Buscar turmas-alvo do gabarito (via report scope)
        try:
            turmas_alvo = get_answer_sheet_target_classes_for_report(
                gabarito, "school", school_id
            )
        except Exception as e:
            logger.warning(f"Erro ao buscar turmas-alvo para gabarito {gabarito_id}: {e}")
            turmas_alvo = []
        
        if not turmas_alvo:
            logger.warning(f"Gabarito {gabarito_id} sem turmas-alvo para escola {school_id}")
            continue
        
        # Filtrar turmas se class_ids foi especificado
        if class_ids:
            turmas_alvo = [t for t in turmas_alvo if str(t.id) in class_ids]
        
        if not turmas_alvo:
            logger.warning(f"Gabarito {gabarito_id} sem turmas após filtro de class_ids")
            continue
        
        # Buscar alunos das turmas-alvo
        turma_ids = [c.id for c in turmas_alvo]
        if turma_ids:
            alunos = Student.query.filter(Student.class_id.in_(turma_ids)).all()
            logger.info(f"Gabarito {gabarito_id}: {len(alunos)} alunos em {len(turma_ids)} turmas")
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
