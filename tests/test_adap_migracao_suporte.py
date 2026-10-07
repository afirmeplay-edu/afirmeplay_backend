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
    return grades, classes, schools, students, {}, er, {}, set(), set(), {}, {}, {}, {}


def _cenario_suporte3(alunos, er=None, extras=None, sessoes_abertas=None, estado_form=None):
    """Escola com 9º A, 9º B, turma Suporte 3 do 9º e turma Suporte 3 do 6º (sem regular do 6º)."""
    grades = {
        "g-sup3": SimpleNamespace(id="g-sup3", name="Suporte 3", education_stage_id=None),
        "g-9ano": SimpleNamespace(id="g-9ano", name="9º Ano", education_stage_id=None),
    }
    classes = {
        "c-sup3-9": SimpleNamespace(id="c-sup3-9", name="- 9º ANO", grade_id="g-sup3", school_id="esc-1"),
        "c-sup3-6": SimpleNamespace(id="c-sup3-6", name="- 6º ANO", grade_id="g-sup3", school_id="esc-1"),
        "c-9a": SimpleNamespace(id="c-9a", name="A", grade_id="g-9ano", school_id="esc-1"),
        "c-9b": SimpleNamespace(id="c-9b", name="B", grade_id="g-9ano", school_id="esc-1"),
    }
    students = [SimpleNamespace(subturma_id=None, **a) for a in alunos]
    return lambda: (grades, classes, {"esc-1": "Escola Ficticia"}, students, {}, er or {}, {}, set(),
                    sessoes_abertas or set(), {}, {}, estado_form or {}, extras or {})


def _aluno(id, nome, turma, escola="esc-1"):
    return {"id": id, "name": nome, "class_id": turma, "school_id": escola, "user_id": f"u-{id}"}


def test_suporte3_vai_para_adap3_da_turma_a(monkeypatch):
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3([_aluno("s-3", "Aluna Tres", "c-sup3-9")], er={"s-3": 1}))

    selecao = mod.selecionar_rodada1()

    assert [(c.student_id, c.nivel, c.destino_id) for c in selecao.elegiveis] == [("s-3", 3, "c-9a")]
    assert selecao.excluidos == []


def test_suporte3_sem_turma_regular_do_ano_informa_escola_e_ano(monkeypatch):
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3([_aluno("s-6", "Aluno Seis", "c-sup3-6")]))

    [cand] = mod.selecionar_rodada1().excluidos

    assert cand.motivo == "sem_destino"
    assert cand.detalhe == "Escola Ficticia — 6º ano: SEM TURMA REGULAR DO ANO"


def test_suporte3_com_nota_nos_dois_cadastros_fica_de_fora(monkeypatch):
    alunos = [_aluno("s-3", "Aluna Tres", "c-sup3-9"), _aluno("r-3", "Aluna Tres", "c-9b")]
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3(alunos, er={"s-3": 1, "r-3": 2}))

    [cand] = mod.selecionar_rodada1().excluidos

    assert (cand.student_id, cand.regular_id, cand.motivo) == ("s-3", "r-3", "nota_nos_dois")


def test_matricula_aberta_em_outra_turma_fica_de_fora(monkeypatch):
    extras = {"matriculas_abertas": {"s-3": [{"school_id": "esc-1", "class_id": "c-9b", "valid_from": None}]}}
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3([_aluno("s-3", "Aluna Tres", "c-sup3-9")],
                                                             er={"s-3": 1}, extras=extras))

    [cand] = mod.selecionar_rodada1().excluidos

    assert cand.motivo == "matricula_ou_edicao_manual"
    assert cand.detalhe == "matrícula aberta em outra turma ou escola"


def test_matricula_do_regular_com_inicio_no_futuro_fica_de_fora(monkeypatch):
    from datetime import datetime, timedelta

    futuro = datetime.utcnow() + timedelta(hours=1)
    extras = {"matriculas_abertas": {"r-3": [{"school_id": "esc-1", "class_id": "c-9b", "valid_from": futuro}]}}
    alunos = [_aluno("s-3", "Aluna Tres", "c-sup3-9"), _aluno("r-3", "Aluna Tres", "c-9b")]
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3(alunos, er={"s-3": 1}, extras=extras))

    [cand] = mod.selecionar_rodada1().excluidos

    assert cand.motivo == "matricula_ou_edicao_manual"
    assert cand.detalhe.startswith("cadastro regular: matrícula aberta com início no futuro")


def test_matricula_so_com_escola_nao_impede(monkeypatch):
    extras = {"matriculas_abertas": {"s-3": [{"school_id": "esc-1", "class_id": None, "valid_from": None}]}}
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3([_aluno("s-3", "Aluna Tres", "c-sup3-9")],
                                                             er={"s-3": 1}, extras=extras))

    assert [c.student_id for c in mod.selecionar_rodada1().elegiveis] == ["s-3"]


def test_nota_em_cadastro_sem_escola_com_mesmo_nome_fica_de_fora(monkeypatch):
    alunos = [_aluno("s-3", "Aluna Tres", "c-sup3-9"), _aluno("x-3", "ALUNA TRÊS", None, escola=None)]
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3(alunos, er={"s-3": 1, "x-3": 1}))

    [cand] = mod.selecionar_rodada1().excluidos

    assert cand.motivo == "nota_em_cadastro_sem_vinculo"
    assert "x-3" in cand.detalhe


def test_cadastro_sem_escola_e_sem_nota_nao_impede(monkeypatch):
    alunos = [_aluno("s-3", "Aluna Tres", "c-sup3-9"), _aluno("x-3", "Aluna Tres", None, escola=None)]
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3(alunos, er={"s-3": 1}))

    [cand] = mod.selecionar_rodada1().elegiveis

    assert [x["id"] for x in cand.sem_vinculo_mesmo_nome] == ["x-3"]


def test_turmas_de_suporte_e_tabela_por_escola(monkeypatch):
    alunos = [_aluno("s-3", "Aluna Tres", "c-sup3-9"), _aluno("s-6", "Aluno Seis", "c-sup3-6")]
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3(alunos, er={"s-3": 1}))

    selecao = mod.selecionar_rodada1()

    turmas = {t["turma_id"]: (t["alunos"], t["migrariam"], t["ficariam"]) for t in selecao.turmas_suporte}
    assert turmas == {"c-sup3-9": (1, 1, 0), "c-sup3-6": (1, 0, 1)}
    assert mod._tabela_por_escola(selecao) == {"Escola Ficticia": {
        "suporte_1": 0, "suporte_2": 0, "suporte_3": 2, "nivel_indefinido": 0, "migrariam": 1, "ficam_de_fora": 1}}


def _par_regular_9b(er=None, **kw):
    alunos = [_aluno("s-3", "Aluna Tres", "c-sup3-9"), _aluno("r-3", "Aluna Tres", "c-9b")]
    return _cenario_suporte3(alunos, er=er, **kw)


def test_nota_so_no_regular_fica_o_regular_na_propria_turma(monkeypatch):
    monkeypatch.setattr(mod, "_load_rows", _par_regular_9b(er={"r-3": 2}))

    [cand] = mod.selecionar_rodada1().elegiveis

    assert (cand.student_id, cand.regular_id, cand.tipo) == ("s-3", "r-3", "regular_mantido")
    assert (cand.destino_id, cand.nivel) == ("c-9b", 3)


def test_sem_nota_em_nenhum_fica_o_regular(monkeypatch):
    monkeypatch.setattr(mod, "_load_rows", _par_regular_9b())

    [cand] = mod.selecionar_rodada1().elegiveis

    assert cand.tipo == "regular_mantido"
    assert cand.destino_id == "c-9b"


def test_regular_mantido_recusa_suporte_com_respostas(monkeypatch):
    extras = {"outros_dados": {"s-3": {"respostas": 26}}}
    monkeypatch.setattr(mod, "_load_rows", _par_regular_9b(er={"r-3": 1}, extras=extras))

    [cand] = mod.selecionar_rodada1().excluidos

    assert (cand.motivo, cand.detalhe) == ("suporte_com_dados", "respostas=26")


def test_regular_mantido_recusa_suporte_com_questionario(monkeypatch):
    monkeypatch.setattr(mod, "_load_rows", _par_regular_9b(estado_form={"u-s-3": {"f1": "respondido"}}))

    [cand] = mod.selecionar_rodada1().excluidos

    assert cand.motivo == "suporte_com_dados"
    assert "questionario_f1" in cand.detalhe


def test_regular_mantido_recusa_prova_em_andamento_no_suporte(monkeypatch):
    monkeypatch.setattr(mod, "_load_rows", _par_regular_9b(sessoes_abertas={"s-3"}))

    [cand] = mod.selecionar_rodada1().excluidos

    assert cand.motivo == "prova_em_andamento"


def test_regular_mantido_recusa_terceiro_cadastro_sem_escola(monkeypatch):
    alunos = [_aluno("s-3", "Aluna Tres", "c-sup3-9"), _aluno("r-3", "Aluna Tres", "c-9b"),
              _aluno("x-3", "Aluna Tres", None, escola=None)]
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3(alunos))

    [cand] = mod.selecionar_rodada1().excluidos

    assert (cand.motivo, cand.detalhe) == ("mais_de_dois_cadastros", "x-3 (sem escola)")


def test_regular_mantido_recusa_terceiro_cadastro_em_outra_escola(monkeypatch):
    alunos = [_aluno("s-3", "Aluna Tres", "c-sup3-9"), _aluno("r-3", "Aluna Tres", "c-9b"),
              _aluno("y-3", "Aluna Tres", "c-outra", escola="esc-2")]
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3(alunos))

    [cand] = mod.selecionar_rodada1().excluidos

    assert (cand.motivo, cand.detalhe) == ("mais_de_dois_cadastros", "y-3 (esc-2)")


def test_regular_mantido_recusa_dois_cadastros_regulares(monkeypatch):
    alunos = [_aluno("s-3", "Aluna Tres", "c-sup3-9"), _aluno("r-3", "Aluna Tres", "c-9b"),
              _aluno("r-4", "Aluna Tres", "c-9a")]
    monkeypatch.setattr(mod, "_load_rows", _cenario_suporte3(alunos))

    [cand] = mod.selecionar_rodada1().excluidos

    assert cand.motivo == "mais_de_um_candidato_forte"


def test_regular_mantido_recusa_regular_ja_em_subturma(monkeypatch):
    rows = _par_regular_9b()()
    rows[3][1].subturma_id = "sub-x"
    monkeypatch.setattr(mod, "_load_rows", lambda: rows)

    [cand] = mod.selecionar_rodada1().excluidos

    assert (cand.motivo, cand.detalhe) == ("matricula_ou_edicao_manual", "cadastro regular: já vinculado a uma subturma")


def test_gravacao_recusa_aluno_movido_depois_da_selecao():
    cand = mod.Candidato(student_id="s-3", nome="Aluna Tres", escola_id="esc-1", escola="Escola Ficticia",
                         turma_suporte_id="c-sup3-9", turma_suporte="- 9º ANO", nivel=3, ano=9,
                         regular_id="r-3", regular_turma_id="c-9b")
    aluno = SimpleNamespace(class_id="c-sup3-9", school_id="esc-1", subturma_id=None)

    mod._conferir_estado_selecionado(cand, aluno, SimpleNamespace(class_id="c-9b", school_id="esc-1"))
    with pytest.raises(mod.MigracaoError):
        mod._conferir_estado_selecionado(cand, SimpleNamespace(class_id="c-9a", school_id="esc-1", subturma_id=None),
                                         SimpleNamespace(class_id="c-9b", school_id="esc-1"))
    with pytest.raises(mod.MigracaoError):
        mod._conferir_estado_selecionado(cand, aluno, SimpleNamespace(class_id="c-sup3-9", school_id="esc-1"))


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
