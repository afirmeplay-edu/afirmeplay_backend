# -*- coding: utf-8 -*-
"""Lint leve: consumidores migrados não devem reinventar AVG/cortes locais.

Os caminhos canônicos (evaluation_calculator, school_equal_weight_means,
resultado_escopo) ficam fora da checagem.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"

# Arquivos que JÁ devem estar limpos após a migração piloto/núcleo.
MUST_BE_CLEAN = [
    "services/resultado_escopo.py",
    "services/contexto_avaliacao.py",
    "utils/school_equal_weight_means.py",
]

AVG_GRADE_OR_PROF = re.compile(
    r"func\.avg\(\s*(?:EvaluationResult|AnswerSheetResult)\.(?:grade|proficiency)\s*\)",
    re.IGNORECASE,
)
LOCAL_CUTS_DASHBOARD = re.compile(
    r"proficiency\s*<\s*500|proficiency\s*<\s*750",
    re.IGNORECASE,
)


def test_canonicos_nao_usam_avg_sql_de_grade():
    for rel in MUST_BE_CLEAN:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert not AVG_GRADE_OR_PROF.search(text), f"AVG proibido em {rel}"


def test_school_equal_weight_means_nao_faz_media_de_notas_no_geral():
    path = ROOT / "utils/school_equal_weight_means.py"
    text = path.read_text(encoding="utf-8")
    # A docstring/implementação antiga falava em média das notas das disciplinas.
    assert "Nota geral = média das notas das disciplinas" not in text
    assert "calculate_grade" in text
