# -*- coding: utf-8 -*-
"""
Cálculo de proficiência por disciplina para cartões resposta.
Usa blocks_config (com subject_id por bloco) para agregar acertos por disciplina
e calcular proficiência e classificação por disciplina e média geral.
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from app.services.cartao_resposta.course_name_resolver import infer_course_name_from_grade

logger = logging.getLogger(__name__)


def _get_course_name_from_grade(grade_name: str) -> str:
    """
    Compatibilidade retroativa: mantém API antiga usada por rotas.
    """
    return infer_course_name_from_grade(grade_name)


def _resolve_subject_name(subject_id: str, subject_name: Optional[str]) -> str:
    """Retorna subject_name; se vazio, tenta buscar do modelo Subject."""
    if subject_name and str(subject_name).strip():
        return str(subject_name).strip()
    try:
        from app.models.subject import Subject
        obj = Subject.query.get(str(subject_id))
        if obj and getattr(obj, 'name', None):
            return obj.name
    except Exception as e:
        logger.debug(f"Erro ao buscar Subject por id {subject_id}: {e}")
    return 'Outras'


def calcular_proficiencia_por_disciplina(
    blocks_config: Optional[Dict],
    validated_answers: Dict[int, Optional[str]],
    gabarito_dict: Dict[int, str],
    grade_name: str = '',
) -> Tuple[Dict[str, Any], float, str]:
    """
    Calcula proficiência e classificação por disciplina e média geral.

    Args:
        blocks_config: Config do gabarito (topology.blocks ou blocks com subject_id).
        validated_answers: Respostas detectadas { num_questao: "A"|None, ... }.
        gabarito_dict: Respostas corretas { num_questao: "A", ... }.
        grade_name: Nome da série para inferir nível do curso.

    Returns:
        (proficiency_by_subject, proficiency_media, classification_geral)
        - proficiency_by_subject: { subject_id: { subject_name, proficiency, classification, correct_answers, total_questions } }
        - proficiency_media: média das proficiências por disciplina
        - classification_geral: classificação para a média (usa "GERAL" no calculator)
    """
    from app.services.evaluation_calculator import EvaluationCalculator

    course_name = infer_course_name_from_grade(grade_name)
    proficiency_by_subject = {}
    blocks = _extract_blocks_with_questions(blocks_config)
    if not blocks:
        # Fallback: um único bloco com todas as questões (sem subject_id)
        all_q = list(gabarito_dict.keys())
        if all_q:
            correct = sum(1 for q in all_q if validated_answers.get(q) == gabarito_dict.get(q))
            total = len(all_q)
            subject_name = 'Outras'
            prof = EvaluationCalculator.calculate_proficiency(
                correct, total, course_name, subject_name
            )
            classification = EvaluationCalculator.determine_classification(
                prof, course_name, subject_name
            )
            grade = EvaluationCalculator.calculate_grade(
                prof, course_name, subject_name,
                use_simple_calculation=False
            )
            proficiency_by_subject['geral'] = {
                'subject_name': subject_name,
                'proficiency': prof,
                'classification': classification,
                'grade': grade,
                'correct_answers': correct,
                'total_questions': total,
            }
            return proficiency_by_subject, prof, classification
        return {}, 0.0, 'Não calculado'

    # Agrupar por subject_id (questões podem estar em vários blocos da mesma disciplina)
    questions_by_subject: Dict[str, List[int]] = {}
    subject_names: Dict[str, str] = {}
    for block in blocks:
        subject_id = block.get('subject_id')
        if not subject_id:
            subject_id = f"block_{block.get('block_id', 0)}"
        subject_id = str(subject_id)
        subject_name = _resolve_subject_name(subject_id, block.get('subject_name'))
        subject_names[subject_id] = subject_name
        q_list = block.get('question_numbers', [])
        if subject_id not in questions_by_subject:
            questions_by_subject[subject_id] = []
        questions_by_subject[subject_id].extend(q_list)

    for subject_id, question_numbers in questions_by_subject.items():
        if not question_numbers:
            continue
        correct = sum(
            1 for q in question_numbers
            if validated_answers.get(q) == gabarito_dict.get(q)
        )
        total = len(question_numbers)
        subject_name = subject_names.get(subject_id, 'Outras')
        proficiency = EvaluationCalculator.calculate_proficiency(
            correct, total, course_name, subject_name
        )
        classification = EvaluationCalculator.determine_classification(
            proficiency, course_name, subject_name
        )
        grade = EvaluationCalculator.calculate_grade(
            proficiency, course_name, subject_name,
            use_simple_calculation=False
        )
        proficiency_by_subject[subject_id] = {
            'subject_name': subject_name,
            'proficiency': round(proficiency, 2),
            'classification': classification,
            'grade': grade,
            'correct_answers': correct,
            'total_questions': total,
        }

    if not proficiency_by_subject:
        return {}, 0.0, 'Não calculado'

    proficiencies = [v['proficiency'] for v in proficiency_by_subject.values()]
    proficiency_media = round(sum(proficiencies) / len(proficiencies), 2)
    classification_geral = EvaluationCalculator.determine_classification(
        proficiency_media, course_name, 'GERAL'
    )
    return proficiency_by_subject, proficiency_media, classification_geral


def _extract_blocks_with_questions(blocks_config: Optional[Dict]) -> List[Dict]:
    """
    Extrai lista de blocos com subject_id/subject_name e lista de números de questão.
    Preferência: topology.blocks (com questions[].q), senão blocks (com start_question/end_question).
    """
    if not blocks_config:
        return []
    blocks = blocks_config.get('topology', {}).get('blocks', [])
    if not blocks:
        blocks = blocks_config.get('blocks', [])
    if not blocks:
        return []

    result = []
    for block in blocks:
        subject_id = block.get('subject_id')
        subject_name = block.get('subject_name')
        block_id = block.get('block_id')
        question_numbers = []
        if 'questions' in block:
            for q_item in block.get('questions', []):
                q_num = q_item.get('q') if isinstance(q_item, dict) else q_item
                if q_num is not None:
                    question_numbers.append(int(q_num))
        else:
            start_q = block.get('start_question')
            end_q = block.get('end_question')
            if start_q is not None and end_q is not None:
                question_numbers = list(range(int(start_q), int(end_q) + 1))
        if question_numbers:
            result.append({
                'block_id': block_id,
                'subject_id': subject_id,
                'subject_name': subject_name,
                'question_numbers': question_numbers,
            })
    return result
