# -*- coding: utf-8 -*-
from types import SimpleNamespace
from datetime import datetime

from app.afirme_ler.services.fluency_results_service import (
    evaluation_year,
    evaluations_same_cycle,
    normalize_turno,
    previous_edition,
)
from app.afirme_ler.services.results_copy import (
    alertas_from_indicadores,
    criterios_payload,
    frase_analitica,
)
from app.afirme_ler.scoring import FluencyScoring, StudentReadingInput


def test_normalize_turno():
    assert normalize_turno("morning") == "Matutino"
    assert normalize_turno("manhã") == "Matutino"
    assert normalize_turno("Vespertino") == "Vespertino"
    assert normalize_turno("full-time") == "Integral"
    assert normalize_turno(None) is None


def test_previous_edition():
    assert previous_edition("entrada") is None
    assert previous_edition("formativa") == "entrada"
    assert previous_edition("saida") == "formativa"


def test_evaluation_year():
    ev = SimpleNamespace(
        application_start=datetime(2026, 3, 1),
        created_at=datetime(2025, 1, 1),
    )
    assert evaluation_year(ev) == 2026
    ev2 = SimpleNamespace(application_start=None, created_at=datetime(2025, 8, 1))
    assert evaluation_year(ev2) == 2025


def test_criterios_ifl_mvp():
    criterios = criterios_payload()
    assert "peso 0" in criterios["pesosIfl"]
    assert "peso 10" in criterios["pesosIfl"]
    assert "2,5" in criterios["pesosIfl"]
    assert "0 a 10" in criterios["iflDescricao"]
    assert "mais de 65" in criterios["fluencia"]


def test_alertas_participacao_baixa():
    alertas = alertas_from_indicadores(
        {"previstos": 100, "avaliados": 70, "participacao": 70.0, "ifl": 5.0}
    )
    ids = {item["id"] for item in alertas}
    assert "participacao-baixa" in ids
    assert alertas_from_indicadores(
        {"previstos": 100, "avaliados": 90, "participacao": 90.0, "ifl": 6.0}
    ) == []


def test_frase_e_ifl_do_nivel_na_exportacao():
    frase = frase_analitica(
        nivel_label="Leitor Iniciante", ppm=72.0, precisao=91.0, avaliado=True
    )
    assert "Leitor Iniciante" in frase
    assert FluencyScoring.ifl_do_nivel("LI") == 6.0
    score = FluencyScoring.score_student(
        StudentReadingInput(status="presente", palavras_corretas=11, desconhecidas_corretas=6)
    )
    assert score.nivel == "LI"


def test_evaluations_same_cycle_por_turmas():
    a = SimpleNamespace(class_ids=["t1", "t2"], school_ids=["s1"])
    b = SimpleNamespace(class_ids=["t2", "t3"], school_ids=["s9"])
    c = SimpleNamespace(class_ids=["t9"], school_ids=["s1"])
    d = SimpleNamespace(class_ids=[], school_ids=["s1"])
    e = SimpleNamespace(class_ids=[], school_ids=["s1"])
    assert evaluations_same_cycle(a, b) is True
    assert evaluations_same_cycle(a, c) is False
    assert evaluations_same_cycle(d, e) is True

