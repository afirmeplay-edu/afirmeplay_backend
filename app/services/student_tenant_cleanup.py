# -*- coding: utf-8 -*-
"""
Exclusão lógica de alunos no tenant.

Regra oficial: inativar o aluno sem apagar resultados, respostas, sessões
nem histórico. Exclusão física destrutiva fica reservada a fluxos LGPD
separados (não usados pelo DELETE comum).
"""
from __future__ import annotations

import logging
from typing import Iterable, List, Union

logger = logging.getLogger(__name__)


def soft_deactivate_students(student_ids: Union[str, Iterable[str]]) -> List[str]:
    """
    Marca aluno(s) como inativos (``is_active=False``).

    Preserva EvaluationResult, AnswerSheetResult, TestSession e StudentAnswer.
    Retorna a lista de ids processados.
    """
    if isinstance(student_ids, str):
        ids: List[str] = [student_ids]
    else:
        ids = [str(x) for x in student_ids if x]
    if not ids:
        return []

    from app.models.student import Student

    Student.query.filter(Student.id.in_(ids)).update(
        {Student.is_active: False},
        synchronize_session=False,
    )
    return ids


def delete_student_tenant_dependencies(student_ids: Union[str, Iterable[str]]) -> None:
    """
    Compat: o DELETE comum agora só inativa.

    Não remove resultados/sessões/respostas. Mantém o nome da função para
    callers existentes (student_routes, user_deletion).
    """
    soft_deactivate_students(student_ids)
    logger.info(
        "Soft-deactivate students (histórico preservado): %s",
        student_ids if isinstance(student_ids, str) else list(student_ids),
    )
