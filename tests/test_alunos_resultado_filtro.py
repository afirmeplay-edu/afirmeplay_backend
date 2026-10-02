# -*- coding: utf-8 -*-
"""Filtro de alunos de Resultados, sem banco (vínculo já na memória)."""
from types import SimpleNamespace

from app.services.alunos_resultado_filtro import (
    AlunosFiltroInvalido,
    aplicar_universo_alunos,
    filtrar_alunos_resultado,
    parse_alunos_filtro,
)
from app.services.special_education import ADAP_EDUCATION_STAGE_ID


def _grade(name, stage=None):
    return SimpleNamespace(name=name, education_stage_id=stage)


def _aluno(aluno_id, *, grade, subturma=None, class_id="turma-regular"):
    return SimpleNamespace(
        id=aluno_id,
        class_id=class_id,
        grade_id=None,
        grade=grade,
        subturma_id=None if subturma is None else subturma.id,
        subturma=subturma,
    )


def _sub(level, class_id="turma-regular"):
    return SimpleNamespace(id=f"sub-{level}", class_id=class_id, support_level=level)


def _turma_mista():
    serie = _grade("5º Ano")
    return [
        _aluno("regular", grade=serie),
        _aluno("adap1", grade=serie, subturma=_sub(1)),
        _aluno("adap2", grade=serie, subturma=_sub(2)),
        _aluno("adap3", grade=serie, subturma=_sub(3)),
    ]


def _ids(students):
    return [student.id for student in students]


def test_parametro_ausente_e_todos():
    assert parse_alunos_filtro(None) == "todos"
    assert parse_alunos_filtro("") == "todos"
    assert parse_alunos_filtro("  TODOS ") == "todos"
    assert parse_alunos_filtro("regular_adap") == "regular_adap"


def test_parametro_invalido():
    try:
        parse_alunos_filtro("adap3")
    except AlunosFiltroInvalido as exc:
        assert "regular_adap" in str(exc)
    else:
        raise AssertionError("valor inválido deveria falhar")


def test_opcoes_excluem_adap_3():
    alunos = _turma_mista()
    assert _ids(filtrar_alunos_resultado(alunos, "regular")) == ["regular"]
    assert _ids(filtrar_alunos_resultado(alunos, "regular_adap")) == ["regular", "adap1", "adap2"]
    assert _ids(filtrar_alunos_resultado(alunos, "adap")) == ["adap1", "adap2"]
    mesmo = filtrar_alunos_resultado(alunos, "todos")
    assert mesmo is alunos
    assert _ids(filtrar_alunos_resultado(alunos, None)) == _ids(alunos)


def test_serie_antiga_conta_como_adap_pelo_nivel():
    serie_regular = _grade("5º Ano")
    antigo_1 = _aluno(
        "antigo1",
        grade=_grade("ADAP 1", ADAP_EDUCATION_STAGE_ID),
        class_id="turma-antiga",
    )
    antigo_3 = _aluno(
        "antigo3",
        grade=_grade("Suporte 3"),
        class_id="turma-antiga-3",
    )
    regular = _aluno("regular", grade=serie_regular)
    grupo = [regular, antigo_1, antigo_3]
    assert _ids(filtrar_alunos_resultado(grupo, "adap")) == ["antigo1"]
    assert _ids(filtrar_alunos_resultado(grupo, "regular")) == ["regular"]
    assert _ids(filtrar_alunos_resultado(grupo, "regular_adap")) == ["regular", "antigo1"]


def test_transferido_sem_subturma_conta_como_regular():
    serie = _grade("5º Ano")
    saiu = _aluno("saiu", grade=serie, class_id="outra-turma")
    resultado = SimpleNamespace(student_id="saiu")
    alunos, resultados = aplicar_universo_alunos([saiu], "regular", [resultado])
    assert _ids(alunos) == ["saiu"]
    assert resultados == [resultado]
    _, fora = aplicar_universo_alunos(
        [_aluno("adap3", grade=serie, subturma=_sub(3))],
        "regular",
        [SimpleNamespace(student_id="adap3")],
    )
    assert fora == []


def test_todos_nao_recria_as_listas():
    alunos = _turma_mista()
    resultados = [SimpleNamespace(student_id="adap3")]
    out_alunos, out_resultados = aplicar_universo_alunos(alunos, "todos", resultados)
    assert out_alunos is alunos
    assert out_resultados is resultados
    assert aplicar_universo_alunos(alunos, None, resultados)[1] is resultados
