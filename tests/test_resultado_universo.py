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
from app.services.resultado_universo import (
    _ids_unicos_ordenados,
    carregar_universo_da_prova,
    carregar_universo_das_provas,
    linhas_com_nota_valida,
    resultados_para_notas,
)


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


def test_ids_unicos_ordenados_remove_vazios_e_duplicatas():
    assert _ids_unicos_ordenados(["a", " b ", "a", "", None, "c"]) == ["a", "b", "c"]


def test_carregar_universo_das_provas_vazio_retorna_sem_censo():
    students, notas, censo = carregar_universo_das_provas([])
    assert students == []
    assert notas == []
    assert censo is None


def test_carregar_universo_das_provas_usa_in_e_test_ids_multi(monkeypatch):
    captured = {}
    import app.services.resultado_universo as mod

    class_tests = [SimpleNamespace(class_id="t1", test_id="lp")]
    students = [SimpleNamespace(id="s1", class_id="t1", school_id="esc")]
    results = [SimpleNamespace(student_id="s1", test_id="lp", grade=8)]

    class _CTQuery:
        def filter(self, *args):
            captured["class_test_filter"] = args
            return self

        def all(self):
            return class_tests

    class _StudentQuery:
        def filter(self, *args):
            return self

        def all(self):
            return students

    class _ERQuery:
        def filter(self, *args):
            captured["er_filter"] = args
            return self

        def all(self):
            return results

    monkeypatch.setattr(
        "app.models.classTest.ClassTest",
        SimpleNamespace(query=_CTQuery(), test_id=SimpleNamespace(in_=lambda ids: True)),
    )
    monkeypatch.setattr(
        "app.models.student.Student",
        SimpleNamespace(
            query=_StudentQuery(),
            class_id=SimpleNamespace(in_=lambda ids: True),
        ),
    )
    monkeypatch.setattr(
        "app.models.evaluationResult.EvaluationResult",
        SimpleNamespace(
            query=_ERQuery(),
            test_id=SimpleNamespace(in_=lambda ids: True),
            student_id=SimpleNamespace(in_=lambda ids: True),
        ),
    )

    def _notas(test_ids, alunos, rows, filtro, parear=False):
        captured["notas_test_ids"] = list(test_ids)
        return rows

    def _censo(**kwargs):
        captured["censo_test_ids"] = list(kwargs.get("test_ids") or [])
        return SimpleNamespace(ok=True)

    monkeypatch.setattr(mod, "resultados_para_notas", _notas)
    monkeypatch.setattr(
        "app.services.participation_census_shadow.montar_censo_carregado",
        _censo,
    )

    out_students, out_notas, out_censo = carregar_universo_das_provas(
        ["lp", "mat", "lp"],
        municipio_id="city",
        alunos_filtro="regular",
        parear=True,
    )
    assert [s.id for s in out_students] == ["s1"]
    assert out_notas == results
    assert out_censo.ok is True
    assert captured["notas_test_ids"] == ["lp", "mat"]
    assert captured["censo_test_ids"] == ["lp", "mat"]

    # Wrapper singular continua delegando.
    captured.clear()
    class_tests[:] = [SimpleNamespace(class_id="t1", test_id="lp")]
    carregar_universo_da_prova("lp", municipio_id="city")
    assert captured["notas_test_ids"] == ["lp"]
    assert captured["censo_test_ids"] == ["lp"]


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
