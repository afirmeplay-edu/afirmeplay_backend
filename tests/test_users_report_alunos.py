# -*- coding: utf-8 -*-
"""Recorte do relatório de usuários, sem banco."""
from types import SimpleNamespace

from app.services.special_education import status_from_grade_and_subturma, SpecialEducationStatus
from app.services.users_report_alunos import (
    aplicar_recorte_relatorio_usuarios,
    contatos_do_recorte,
)


def _status_regular():
    return SpecialEducationStatus(False, None, None)


def _subturma(level, class_id="turma-1"):
    return SimpleNamespace(id=f"sub-{level}", class_id=class_id, support_level=level)


def _aluno(nome, status, **extra):
    row = {
        "id": nome,
        "name": nome,
        "email": f"{nome}@escola.test",
        "school_id": "escola-1",
        "school_name": "Escola",
        "grade_id": "serie-1",
        "grade_name": "5º Ano",
        "class_id": "turma-1",
        "class_name": "A",
        "status": status,
    }
    row.update(extra)
    return row


def _payload(students=4):
    return {
        "general": {
            "students": students,
            "teachers": 3,
            "directors": 1,
            "coordinators": 1,
        },
        "by_school": [
            {
                "school_id": "escola-1",
                "school_name": "Escola",
                "students": students,
                "directors": 1,
                "coordinators": 1,
            }
        ],
        "by_grade": [],
        "by_class": [
            {
                "class_id": "turma-1",
                "class_name": "A",
                "school_id": "escola-1",
                "grade_id": "serie-1",
                "grade_name": "5º Ano",
                "students": students,
                "teachers": 2,
            }
        ],
    }


def test_subturma_nao_entra_em_regular_e_regular_nao_entra_em_adap():
    adap = status_from_grade_and_subturma(
        student_class_id="turma-1",
        grade=SimpleNamespace(name="5º Ano", education_stage_id="etapa-regular"),
        subturma=_subturma(1),
    )
    regular = status_from_grade_and_subturma(
        student_class_id="turma-1",
        grade=SimpleNamespace(name="5º Ano", education_stage_id="etapa-regular"),
        subturma=None,
    )
    registros = [_aluno("Ada", adap), _aluno("Regina", regular)]
    so_regular = aplicar_recorte_relatorio_usuarios(_payload(2), registros, "regular")
    so_adap = aplicar_recorte_relatorio_usuarios(_payload(2), registros, "adap")
    assert [item["name"] for item in so_regular["alunos"]] == ["Regina"]
    assert so_regular["general"]["students"] == 1
    assert so_regular["general"]["regulares"] == 1
    assert so_regular["general"]["educacao_especial"] == 0
    assert [item["name"] for item in so_adap["alunos"]] == ["Ada"]
    assert so_adap["general"]["adap_1"] == 1
    assert so_adap["general"]["educacao_especial"] == 1
    assert so_adap["by_class"][0]["students"] == 1
    assert all(item["name"] != "Regina" for item in so_adap["alunos"])


def test_serie_antiga_suporte_2_cai_em_adap_2():
    status = status_from_grade_and_subturma(
        student_class_id="turma-suporte",
        grade=SimpleNamespace(name="Suporte 2", education_stage_id="outra"),
        subturma=None,
    )
    registros = [_aluno("Bia", status, grade_name="Suporte 2", class_id="turma-suporte")]
    recorte = aplicar_recorte_relatorio_usuarios(_payload(1), registros, "adap")
    assert recorte["general"]["adap_2"] == 1
    assert recorte["general"]["adap_1"] == 0
    assert recorte["general"]["regulares"] == 0
    assert recorte["alunos"][0]["nivel_adap"] == 2
    regular = aplicar_recorte_relatorio_usuarios(_payload(1), registros, "regular")
    assert regular["alunos"] == []
    assert regular["general"]["students"] == 0


def test_todos_nao_altera_o_payload():
    original = _payload(9)
    registros = [
        _aluno("Ada", SpecialEducationStatus(True, 1, "subturma")),
        _aluno("Regina", _status_regular()),
    ]
    devolve = aplicar_recorte_relatorio_usuarios(original, registros, "todos")
    assert devolve is original
    assert devolve["general"]["students"] == 9
    assert devolve["general"]["teachers"] == 3
    assert "alunos" not in devolve
    assert "alunos_filtro" not in devolve


def test_contatos_de_educacao_especial_trazem_so_adap_em_ordem():
    registros = [
        _aluno("Carla", _status_regular()),
        _aluno("bruno", SpecialEducationStatus(True, 2, "subturma")),
        _aluno("Ana", SpecialEducationStatus(True, 3, "serie")),
        _aluno("Sem", SpecialEducationStatus(True, None, "serie")),
    ]
    nomes = [row["name"] for row in contatos_do_recorte(registros, "adap")]
    assert nomes == ["Ana", "bruno"]
    niveis = [row["status"].level for row in contatos_do_recorte(registros, "adap")]
    assert niveis == [3, 2]
