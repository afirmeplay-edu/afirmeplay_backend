# -*- coding: utf-8 -*-
"""Níveis ADAP no universo de RESULTADOS/PARTICIPAÇÃO de provas regulares.

ADAP 1 e 2 entram. ADAP 3 fica fora de nota, proficiência, participação,
esperados/faltas, rankings e **Lista de Frequência** de prova objetiva/impressa
**regular** (online ou cartão). Prova/cartão direcionado a ADAP 3 mantém o 3.

ADAP 3 não participa de avaliações objetivas nem de cartões-resposta
(regra oficial). Avaliações subjetivas permanecem permitidas.
Cadastro, subturma, Avaliação Subjetiva e Relatório de Usuários mantêm o 3.
"""
from __future__ import annotations

from typing import Any, Optional

# Única fonte: não repetir (1, 2) espalhado no código de prova objetiva.
ADAP_OBJETIVO_NIVEIS = (1, 2)
ADAP_OBJETIVO_EXCLUIDO = 3


def nivel_adap_objetivo(level: Any) -> Optional[int]:
    """Devolve 1 ou 2 se o nível faz prova objetiva; senão None."""
    try:
        nivel = int(level)
    except (TypeError, ValueError):
        return None
    return nivel if nivel in ADAP_OBJETIVO_NIVEIS else None


def e_adap_objetivo(level: Any) -> bool:
    return nivel_adap_objetivo(level) is not None


def e_adap_excluido_prova_objetiva(level: Any) -> bool:
    """True só para o nível 3 (fora de objetiva/impressa regular)."""
    try:
        return int(level) == ADAP_OBJETIVO_EXCLUIDO
    except (TypeError, ValueError):
        return False


def sql_excluir_adap3_de_student():
    """Critério SQLAlchemy: exclui alunos com subturma ADAP 3."""
    from sqlalchemy import or_, select

    from app.models.student import Student
    from app.models.subturma import Subturma

    return or_(
        Student.subturma_id.is_(None),
        ~Student.subturma_id.in_(
            select(Subturma.id).where(Subturma.support_level == ADAP_OBJETIVO_EXCLUIDO)
        ),
    )


def prova_direcionada_adap3(*, gabarito_level: Any = None, grade_name: Any = None) -> bool:
    """
    True quando a prova/cartão é do curso Educação Especial → ADAP 3.
    ``gabarito_level`` = retorno de ``gabarito_adap_level``; ``grade_name`` = série do Test.
    """
    if gabarito_level is not None:
        return e_adap_excluido_prova_objetiva(gabarito_level)
    if grade_name is not None:
        from app.services.special_education import support_level_from_exact_grade_name

        return e_adap_excluido_prova_objetiva(
            support_level_from_exact_grade_name(grade_name)
        )
    return False
