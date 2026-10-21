# -*- coding: utf-8 -*-
"""Sombra do censo: log quando a flag liga, resposta intocada quando desliga."""
import json
from types import SimpleNamespace

import pytest

from app.services import participation_census_shadow as sombra
from app.services.participation_census_shadow import log_participation_census_shadow


def _aluno():
    return SimpleNamespace(
        id="r1",
        name="Maria Lavínia",
        class_id="t1",
        grade_id="g1",
        subturma_id=None,
        subturma=None,
        grade=SimpleNamespace(name="5º Ano", education_stage_id=None),
        class_=SimpleNamespace(id="t1", school_id="e1", grade_id="g1"),
    )


def _prova():
    return SimpleNamespace(
        id="reg-lp",
        title="LP",
        subject="lp",
        subject_rel=SimpleNamespace(name="Língua Portuguesa"),
        subjects_info=None,
        paired_regular_test_id=None,
    )


def _chamada():
    resultado = SimpleNamespace(
        student_id="r1",
        test_id="reg-lp",
        calculated_at=1,
        class_id_snapshot=None,
    )
    historico = SimpleNamespace(
        student_id="snap",
        test_id="reg-lp",
        calculated_at=1,
        class_id_snapshot="t1",
    )
    return resultado, [resultado, historico]


def test_sombra_desligada_nao_calcula(monkeypatch):
    monkeypatch.delenv("PARTICIPATION_CENSUS_SHADOW", raising=False)
    chamadas = []
    monkeypatch.setattr(sombra, "_registrar", lambda **kwargs: chamadas.append(kwargs))
    resultado, linhas = _chamada()
    log_participation_census_shadow(
        superficie="resultados",
        municipio_id="cidade",
        universo="regular",
        test_ids=["reg-lp"],
        alunos=[_aluno()],
        class_tests=[SimpleNamespace(class_id="t1", test_id="reg-lp")],
        resultados=linhas,
        antigo_matriculados=2,
        antigo_participantes=1,
        testes=[_prova()],
    )
    assert chamadas == []
    assert resultado.test_id == "reg-lp"


@pytest.mark.parametrize("valor", ["0", "", "off"])
def test_valores_que_mantem_a_sombra_desligada(monkeypatch, valor):
    monkeypatch.setenv("PARTICIPATION_CENSUS_SHADOW", valor)
    assert sombra.census_shadow_enabled() is False


def test_sombra_ligada_grava_o_censo_sem_nome_de_aluno(monkeypatch, caplog):
    monkeypatch.setenv("PARTICIPATION_CENSUS_SHADOW", "1")
    monkeypatch.setattr(
        "app.services.adap_resultado_pareado.find_paired_adap_tests",
        lambda test_id: [],
    )
    resultado, linhas = _chamada()
    with caplog.at_level("INFO", logger="app.services.participation_census_shadow"):
        log_participation_census_shadow(
            superficie="resultados",
            municipio_id="cidade",
            universo="todos",
            test_ids=["reg-lp"],
            alunos=[_aluno()],
            class_tests=[SimpleNamespace(class_id="t1", test_id="reg-lp")],
            resultados=linhas,
            antigo_matriculados=321,
            antigo_participantes=289,
            testes=[_prova()],
        )
    assert resultado.test_id == "reg-lp"
    linhas_log = [rec.message for rec in caplog.records if "PARTICIPATION_CENSUS_SHADOW" in rec.message]
    assert len(linhas_log) == 1
    assert "Maria" not in linhas_log[0]
    assert "Lavínia" not in linhas_log[0]
    payload = json.loads(linhas_log[0].split(" ", 1)[1])
    assert payload["superficie"] == "resultados"
    assert payload["municipio_id"] == "cidade"
    assert payload["test_ids"] == ["reg-lp"]
    assert payload["universo"] == "todos"
    assert payload["matriculados"] == 1
    assert payload["completos"] == 1
    assert payload["pelo_menos_uma"] == 1
    assert payload["historico"] == 1
    assert payload["antigo_matriculados"] == 321
    assert payload["antigo_participantes"] == 289
    assert payload["por_disciplina"][0]["presentes"] == 1
    assert payload["por_disciplina"][0]["origem_regular"] == 1


def test_falha_na_sombra_nao_sobe(monkeypatch, caplog):
    monkeypatch.setenv("PARTICIPATION_CENSUS_SHADOW", "true")

    def quebra(**kwargs):
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr(sombra, "_registrar", quebra)
    with caplog.at_level("WARNING", logger="app.services.participation_census_shadow"):
        log_participation_census_shadow(
            superficie="participacao",
            municipio_id="cidade",
            universo="todos",
            test_ids=["reg-lp"],
            alunos=[],
            class_tests=[],
            resultados=[],
            antigo_matriculados=0,
            antigo_participantes=0,
        )
    assert any("banco indisponível" in rec.message for rec in caplog.records)
