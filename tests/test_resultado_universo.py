# -*- coding: utf-8 -*-
"""Recorte de nota e troca da participação pelo censo, sem banco."""
from types import SimpleNamespace

from app.participation_report.services import aplicar_censo_no_resumo
from app.services.participation_census import (
    AlunoEntradaCenso,
    ClassTestEntrada,
    DisciplinaCenso,
    ParticipationCensusRequest,
    ProvaCenso,
    build_participation_census,
)
from app.services.resultado_universo import linhas_com_nota_valida, resultados_para_notas


def test_sem_pareamento_corta_quem_esta_fora_do_recorte(monkeypatch):
    regular = SimpleNamespace(id="reg")
    adap = SimpleNamespace(id="adap")
    monkeypatch.setattr(
        "app.services.resultado_universo.filtrar_alunos_resultado",
        lambda students, filtro: [regular],
    )
    notas = resultados_para_notas(
        ["prova"],
        [regular, adap],
        [
            SimpleNamespace(student_id="reg", test_id="prova", grade=8),
            SimpleNamespace(student_id="adap", test_id="prova", grade=4),
            SimpleNamespace(student_id="reg", test_id="outra", grade=1),
        ],
        "regular",
        parear=False,
    )
    assert [item.student_id for item in notas] == ["reg"]
    assert notas[0].grade == 8


def test_com_pareamento_fica_so_a_nota_valida_da_prova(monkeypatch):
    regular = SimpleNamespace(id="reg")
    adap = SimpleNamespace(id="adap")
    projetada = SimpleNamespace(student_id="adap", test_id="prova", grade=7)
    monkeypatch.setattr(
        "app.services.resultado_universo.filtrar_alunos_resultado",
        lambda students, filtro: [regular, adap],
    )

    def _parear(test_id, students, results):
        return students, list(results) + [projetada], {}

    monkeypatch.setattr(
        "app.services.adap_resultado_pareado.apply_pareamento_to_universe",
        _parear,
    )
    notas = resultados_para_notas(
        ["prova"],
        [regular, adap],
        [SimpleNamespace(student_id="reg", test_id="prova", grade=8)],
        "regular_adap",
        parear=True,
    )
    assert sorted(item.student_id for item in notas) == ["adap", "reg"]
    assert {item.grade for item in notas} == {7, 8}


def test_linhas_de_nivel_usam_a_nota_valida():
    aluno = SimpleNamespace(id="adap", name="Ana")
    nota = SimpleNamespace(
        student_id="adap",
        grade=6.5,
        proficiency=180,
        classification="Básico",
        correct_answers=8,
        total_questions=10,
    )
    linhas = linhas_com_nota_valida(
        [{"id": "adap", "nome": "Ana", "nota_geral": 0, "nivel_proficiencia_geral": None}],
        [nota],
        [aluno],
        "todos",
    )
    assert linhas[0]["nota_geral"] == 6.5
    assert linhas[0]["proficiencia_geral"] == 180
    assert linhas[0]["nivel_proficiencia_geral"] == "Básico"
    assert linhas[0]["status_geral"] == "concluida"


def test_resumo_de_participacao_passa_a_usar_o_censo():
    censo = build_participation_census(
        ParticipationCensusRequest(
            municipio_id="cidade",
            provas=(ProvaCenso("reg", (DisciplinaCenso("lp", "Língua Portuguesa"),)),),
            universo="todos",
            alunos=(
                AlunoEntradaCenso("a", "esc", "5", "t1"),
                AlunoEntradaCenso("b", "esc", "5", "t1"),
            ),
            class_tests=(ClassTestEntrada("t1", "reg"),),
            resultados=(
                __import__("app.services.participation_census", fromlist=["ResultadoEntradaCenso"]).ResultadoEntradaCenso(
                    "a", "reg"
                ),
            ),
        )
    )
    payload = {
        "metricas": {
            "matriculados": 9,
            "avaliados": 9,
            "total_turmas": 1,
            "percentual_participacao": 100.0,
        },
        "por_escola": [
            {
                "escola_id": "esc",
                "escola_nome": "Escola",
                "matriculados": 9,
                "avaliados": 9,
                "total_turmas": 1,
                "percentual_participacao": 100.0,
            }
        ],
        "por_turma": [
            {
                "turma_id": "t1",
                "turma_nome": "A",
                "matriculados": 9,
                "avaliados": 9,
                "percentual_participacao": 100.0,
            }
        ],
    }
    aplicar_censo_no_resumo(payload, censo)
    assert payload["metricas"]["matriculados"] == 2
    assert payload["metricas"]["avaliados"] == 1
    assert payload["metricas"]["percentual_participacao"] == 50.0
    assert payload["por_escola"][0]["avaliados"] == 1
    assert payload["por_escola"][0]["escola_nome"] == "Escola"
    assert payload["por_turma"][0]["matriculados"] == 2
    assert payload["metricas"]["total_turmas"] == 1
