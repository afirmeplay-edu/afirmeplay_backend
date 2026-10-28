# -*- coding: utf-8 -*-
"""Recorte Regular / Educação Especial do relatório de participação, sem banco."""
from types import SimpleNamespace

from app.participation_report.grupos import (
    AcumuladorGrupos,
    anexar_grupos_do_censo,
    recortar_roster,
)
from app.services.alunos_resultado_filtro import aluno_entra_no_filtro
from app.services.special_education import status_from_grade_and_subturma, SpecialEducationStatus


def _status_regular():
    return SpecialEducationStatus(False, None, None)


def _status_adap(nivel, fonte="subturma"):
    return SpecialEducationStatus(True, nivel, fonte)


def _roster():
    statuses = {
        "regular": _status_regular(),
        "adap1": _status_adap(1),
        "adap2": _status_adap(2, "serie"),
        "adap3": _status_adap(3),
        "sem_nivel": SpecialEducationStatus(True, None, "serie"),
    }
    matriculados = set(statuses)
    avaliados = {"regular", "adap1", "sem_nivel"}
    return matriculados, avaliados, statuses


def test_filtro_do_cartao_usa_a_mesma_regra_da_online():
    matriculados, avaliados, statuses = _roster()
    for filtro in ("todos", "regular", "regular_adap", "adap"):
        mantidos, presentes = recortar_roster(matriculados, avaliados, statuses, filtro)
        esperado = {
            aluno_id
            for aluno_id, status in statuses.items()
            if aluno_entra_no_filtro(status, filtro)
        }
        assert mantidos == esperado
        assert presentes == esperado & avaliados


def test_todos_nao_muda_matriculados_nem_avaliados():
    matriculados, avaliados, statuses = _roster()
    mantidos, presentes = recortar_roster(matriculados, avaliados, statuses, "todos")
    assert mantidos == matriculados
    assert presentes == avaliados
    mantidos_ausente, presentes_ausente = recortar_roster(
        matriculados, avaliados, statuses, None
    )
    assert mantidos_ausente == matriculados
    assert presentes_ausente == avaliados


def test_gabarito_adap_1_participa_so_sobre_o_publico_adap():
    """Regular da mesma turma não entra no roster do gabarito ADAP 1."""
    statuses = {
        "a": _status_adap(1),
        "b": _status_adap(1),
        "c": _status_adap(1),
    }
    matriculados, avaliados = recortar_roster(
        set(statuses), {"a", "b"}, statuses, "todos"
    )
    assert matriculados == set(statuses)
    acumulado = AcumuladorGrupos()
    for aluno_id in matriculados:
        acumulado.add(statuses[aluno_id], aluno_id in avaliados)
    grupos = acumulado.fechar()
    assert grupos["regular"]["matriculados"] == 0
    assert grupos["adap_2"]["matriculados"] == 0
    assert grupos["adap_3"]["matriculados"] == 0
    assert grupos["adap_1"] == {
        "matriculados": 3,
        "avaliados": 2,
        "percentual_participacao": 66.67,
    }
    assert grupos["educacao_especial"]["matriculados"] == 3
    assert grupos["educacao_especial"]["avaliados"] == 2
    assert grupos["educacao_especial"]["percentual_participacao"] == 66.67


def test_serie_antiga_suporte_entra_no_nivel_e_nao_no_regular():
    grade = SimpleNamespace(name="Suporte 2", education_stage_id="outra-etapa")
    status = status_from_grade_and_subturma(
        student_class_id="turma-1", grade=grade, subturma=None
    )
    acumulado = AcumuladorGrupos()
    acumulado.add(status, True)
    grupos = acumulado.fechar()
    assert grupos["regular"]["matriculados"] == 0
    assert grupos["adap_2"]["matriculados"] == 1
    assert grupos["adap_2"]["avaliados"] == 1
    assert grupos["educacao_especial"]["matriculados"] == 1
    assert grupos["adap_1"]["matriculados"] == 0
    assert grupos["adap_3"]["matriculados"] == 0


def test_censo_acrescenta_grupos_sem_alterar_os_totais():
    payload = {
        "metricas": {"matriculados": 10, "avaliados": 4, "percentual_participacao": 40.0},
        "por_escola": [
            {"escola_id": "escola-1", "matriculados": 10, "avaliados": 4}
        ],
        "por_turma": [
            {"turma_id": "turma-1", "matriculados": 10, "avaliados": 4}
        ],
    }
    censo = SimpleNamespace(
        alunos=[
            SimpleNamespace(
                no_denominador=True,
                perfil="regular",
                nivel_adap=None,
                participacao_completa=False,
                participacao_pelo_menos_uma=True,
                escola_id="escola-1",
                serie_id="serie-1",
                turma_id="turma-1",
            ),
            SimpleNamespace(
                no_denominador=True,
                perfil="adap",
                nivel_adap=1,
                participacao_completa=False,
                participacao_pelo_menos_uma=False,
                escola_id="escola-1",
                serie_id="serie-1",
                turma_id="turma-1",
            ),
            SimpleNamespace(
                no_denominador=False,
                perfil="regular",
                nivel_adap=None,
                participacao_completa=False,
                participacao_pelo_menos_uma=False,
                escola_id="escola-1",
                serie_id="serie-1",
                turma_id="turma-1",
            ),
        ]
    )
    anexar_grupos_do_censo(
        payload, censo, grupo=False, serie_nomes={"serie-1": "5º Ano"}
    )
    assert payload["metricas"]["matriculados"] == 10
    assert payload["metricas"]["avaliados"] == 4
    assert payload["metricas"]["percentual_participacao"] == 40.0
    assert payload["por_escola"][0]["matriculados"] == 10
    assert payload["por_turma"][0]["avaliados"] == 4
    assert payload["metricas"]["grupos"]["regular"]["matriculados"] == 1
    assert payload["metricas"]["grupos"]["regular"]["avaliados"] == 1
    assert payload["metricas"]["grupos"]["adap_1"]["matriculados"] == 1
    assert payload["metricas"]["grupos"]["adap_1"]["avaliados"] == 0
    assert payload["por_serie"][0]["serie_nome"] == "5º Ano"
    assert payload["por_serie"][0]["matriculados"] == 2
