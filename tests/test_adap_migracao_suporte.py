# -*- coding: utf-8 -*-
"""Regras puras da migração de Suporte para ADAP (sem banco)."""
from types import SimpleNamespace

import pytest

from app.services import adap_migracao_suporte as mod
from app.services.adap_migracao_suporte import _estado_formulario, conflito_questionario


def test_estado_formulario():
    assert _estado_formulario("completed") == "respondido"
    assert _estado_formulario("in_progress") == "em_andamento"
    assert _estado_formulario("pending") == "pendente"
    assert _estado_formulario(None) == "pendente"


def test_sem_conflito_quando_mantido_so_tem_pendente_ou_outro_formulario():
    regular = {"f1": "respondido", "f12": "pendente"}
    assert conflito_questionario(regular, {}) == []
    assert conflito_questionario(regular, {"f1": "pendente", "f11": "pendente"}) == []
    assert conflito_questionario(regular, {"f12": "respondido"}) == []


def test_conflito_quando_os_dois_responderam_ou_mantido_comecou():
    regular = {"f1": "respondido", "f3": "respondido"}
    assert conflito_questionario(regular, {"f1": "respondido"}) == ["f1"]
    assert conflito_questionario(regular, {"f3": "em_andamento", "f1": "pendente"}) == ["f3"]


def _rows_dois_suporte():
    grades = {
        "g-sup1": SimpleNamespace(id="g-sup1", name="Suporte 1", education_stage_id=None),
        "g-4ano": SimpleNamespace(id="g-4ano", name="4º Ano", education_stage_id=None),
    }
    classes = {
        "c-sup": SimpleNamespace(id="c-sup", name="- 4º ANO", grade_id="g-sup1", school_id="esc-1"),
        "c-4a": SimpleNamespace(id="c-4a", name="A", grade_id="g-4ano", school_id="esc-1"),
    }
    schools = {"esc-1": "Escola 1"}
    students = [
        SimpleNamespace(id="s-1", name="Aluno Um", class_id="c-sup", school_id="esc-1", user_id="u-1"),
        SimpleNamespace(id="s-2", name="Aluno Dois", class_id="c-sup", school_id="esc-1", user_id="u-2"),
    ]
    er = {"s-1": 1, "s-2": 1}
    return grades, classes, schools, students, {}, er, {}, set(), set(), {}, {}, {}


def test_excluir_aluno_tira_so_o_id_informado(monkeypatch):
    monkeypatch.setattr(mod, "_load_rows", _rows_dois_suporte)

    sem_exclusao = mod.selecionar_rodada1()
    assert {c.student_id for c in sem_exclusao.elegiveis} == {"s-1", "s-2"}

    selecao = mod.selecionar_rodada1(excluir_alunos={"s-2"})
    assert [c.student_id for c in selecao.elegiveis] == ["s-1"]
    assert [(c.student_id, c.motivo) for c in selecao.excluidos] == [("s-2", "excluido_manual")]


def _ambiente(monkeypatch, database):
    import app

    sessao = SimpleNamespace(execute=lambda *a, **k: SimpleNamespace(scalar=lambda: 1))
    monkeypatch.setattr(app, "db", SimpleNamespace(session=sessao), raising=False)
    monkeypatch.setattr(mod, "database_target", lambda: {"host": "db.local", "port": 5432, "database": database})


def test_trava_recusa_write_em_afirmeplay_prod_sem_confirmacao(monkeypatch):
    _ambiente(monkeypatch, "afirmeplay_prod")
    schema = "city_abc"

    with pytest.raises(mod.MigracaoError):
        mod.assert_environment(schema, write=True, confirmar_producao=None)
    with pytest.raises(mod.MigracaoError):
        mod.assert_environment(schema, write=True, confirmar_producao="city_outro")
    assert mod.assert_environment(schema, write=True, confirmar_producao=schema)["producao"] is True
    assert mod.assert_environment(schema, write=False, confirmar_producao=None)["producao"] is True


def test_trava_aceita_write_em_afirmeplay_teste(monkeypatch):
    _ambiente(monkeypatch, "afirmeplay_teste")

    target = mod.assert_environment("city_abc", write=True, confirmar_producao=None)
    assert target["producao"] is False
