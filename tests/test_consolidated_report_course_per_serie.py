# -*- coding: utf-8 -*-
"""Curso por série e ordem estável no Relatório Geral (consolidado)."""

from types import SimpleNamespace

from app.services.consolidated_report_service import (
    _annotate_proficiency_level_labels,
    _course_name_for_serie,
    _order_rows_by_requested_ids,
    _turma_para_nota_do_consolidado,
    _unique_course_names_from_series_colunas,
)
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.participation_census import (
    AlunoEntradaCenso,
    ClassTestEntrada,
    DisciplinaCenso,
    ParticipationCensusRequest,
    ProvaCenso,
    ResultadoEntradaCenso,
    build_participation_census,
    contagens_celula,
)


def test_frequencia_com_provas_de_series_diferentes_fica_por_coluna():
    lp = DisciplinaCenso("lp", "Língua Portuguesa")
    censo = build_participation_census(
        ParticipationCensusRequest(
            municipio_id="cidade",
            provas=(ProvaCenso("lp-5", (lp,)), ProvaCenso("lp-9", (lp,))),
            universo="todos",
            alunos=(
                AlunoEntradaCenso("a5", "esc", "5ano", "t5"),
                AlunoEntradaCenso("b5", "esc", "5ano", "t5"),
                AlunoEntradaCenso("a9", "esc", "9ano", "t9"),
            ),
            class_tests=(ClassTestEntrada("t5", "lp-5"), ClassTestEntrada("t9", "lp-9")),
            resultados=(
                ResultadoEntradaCenso("a5", "lp-5"),
                ResultadoEntradaCenso("a9", "lp-9"),
            ),
        )
    )
    assert contagens_celula(censo, "esc", "5ano") == (2, 1)
    assert contagens_celula(censo, "esc", "9ano") == (1, 1)
    assert censo.geral.matriculados == 3
    assert censo.geral.presentes_completos == 2


def test_course_name_for_serie_iniciais_vs_finais():
    assert _course_name_for_serie("5º Ano") == "Anos Iniciais"
    assert _course_name_for_serie("9º Ano") == "Anos Finais"
    assert _course_name_for_serie("Suporte 1 9º Ano") == "Anos Finais"


def test_order_rows_by_requested_ids_is_stable():
    rows = [type("T", (), {"id": "b"})(), type("T", (), {"id": "a"})()]
    ordered = _order_rows_by_requested_ids(rows, ["a", "b"], lambda x: x.id)
    assert [r.id for r in ordered] == ["a", "b"]


def test_unique_courses_detects_mixed_scales():
    cols = [
        {"serie_id": "1", "serie_nome": "5º Ano"},
        {"serie_id": "2", "serie_nome": "9º Ano"},
    ]
    assert _unique_course_names_from_series_colunas(cols) == [
        "Anos Iniciais",
        "Anos Finais",
    ]


def test_annotate_niveis_por_serie_uses_per_serie_scale():
    cols = [
        {"serie_id": "1", "serie_nome": "5º Ano"},
        {"serie_id": "2", "serie_nome": "9º Ano"},
    ]
    # 200: Adequado em Iniciais Outras; Básico em Finais Outras
    m = {
        "linhas": [
            {
                "escola_id": "e",
                "escola_nome": "E",
                "valores_por_serie": [200.0, 200.0],
                "taxa_geral_escola": 200.0,
            }
        ],
        "medias_da_rede": {"por_serie": [200.0, 200.0], "taxa_geral": 200.0},
    }
    _annotate_proficiency_level_labels(
        m, cols, subject_name="GERAL", has_matematica=False
    )
    niveis = m["linhas"][0]["niveis_por_serie"]
    assert niveis[0] == EvaluationCalculator.determine_classification(
        200.0, "Anos Iniciais", "GERAL", has_matematica=False
    )
    assert niveis[1] == EvaluationCalculator.determine_classification(
        200.0, "Anos Finais", "GERAL", has_matematica=False
    )
    assert niveis[0] != niveis[1]
    # Média geral misturando cursos → sem nível único
    assert m["medias_da_rede"]["nivel_media_geral"] is None
    assert m["linhas"][0]["nivel_media_escola"] is None


def test_grade_formula_differs_by_serie_course():
    """Mesma proficiência → notas diferentes em Iniciais vs Finais (bug do 5º em finais)."""
    prof = 264.7
    nota_iniciais = EvaluationCalculator.calculate_grade(
        prof, "Anos Iniciais", "GERAL", has_matematica=False
    )
    nota_finais = EvaluationCalculator.calculate_grade(
        prof, "Anos Finais", "GERAL", has_matematica=False
    )
    assert nota_iniciais != nota_finais
    assert _course_name_for_serie("9º Ano") == "Anos Finais"


def test_geral_misto_com_e_sem_subject_results_usa_proficiencia_persistida():
    """Não inventar disciplina Outras/fallback ao misturar provas com/sem breakdown."""
    from app.utils.school_equal_weight_means import hierarchical_mean_grade_and_proficiency

    school = "esc-1"
    grade = "serie-8"
    turma = "turma-1"
    with_sr = [
        SimpleNamespace(
            student_id=f"a{i}",
            proficiency=300.0,
            grade=7.0,
            subject_results={
                "m": {"subject_name": "Matemática", "proficiency": 200.0},
                "p": {"subject_name": "Português", "proficiency": 400.0},
            },
            school_id_snapshot=school,
            grade_id_snapshot=grade,
            class_id_snapshot=turma,
        )
        for i in range(3)
    ]
    without_sr = [
        SimpleNamespace(
            student_id=f"b{i}",
            proficiency=100.0,
            grade=2.0,
            subject_results=None,
            school_id_snapshot=school,
            grade_id_snapshot=grade,
            class_id_snapshot=turma,
        )
        for i in range(2)
    ]
    mixed = with_sr + without_sr
    # Média simples dos GERAIS persistidos: (300*3 + 100*2)/5 = 220
    _mg, mp = hierarchical_mean_grade_and_proficiency(
        mixed, "turma", course_name="Anos Finais", has_matematica=True
    )
    assert abs(mp - 220.0) < 0.01
    # Só com breakdown: média das disciplinas (200+400)/2 = 300
    _mg2, mp2 = hierarchical_mean_grade_and_proficiency(
        with_sr, "turma", course_name="Anos Finais", has_matematica=True
    )
    assert abs(mp2 - 300.0) < 0.01


def test_override_geral_taxa_municipal_usa_hierarchical_mean():
    """KPI municipal GERAL do consolidado = hierarchical_mean (paridade /avaliacoes)."""
    from app.services.consolidated_report_service import (
        _override_geral_taxa_municipal_from_results,
    )
    from app.utils.school_equal_weight_means import hierarchical_mean_grade_and_proficiency

    cols = [{"serie_id": "9", "serie_nome": "9º Ano"}]
    results = [
        SimpleNamespace(
            student_id="a1",
            proficiency=170.0,
            grade=2.33,
            subject_results=None,
            school_id_snapshot="e1",
            grade_id_snapshot="9",
            class_id_snapshot="t1",
        ),
        SimpleNamespace(
            student_id="a2",
            proficiency=85.0,
            grade=0.0,
            subject_results=None,
            school_id_snapshot="e1",
            grade_id_snapshot="9",
            class_id_snapshot="t1",
        ),
    ]
    mg, mp = hierarchical_mean_grade_and_proficiency(
        results, "municipio", course_name="Anos Finais", has_matematica=True
    )
    notas = {"GERAL": {"medias_da_rede": {"taxa_geral": 9.99}}, "por_disciplina": {}}
    profs = {"GERAL": {"medias_da_rede": {"taxa_geral": 9.99}}, "por_disciplina": {}}
    _override_geral_taxa_municipal_from_results(notas, profs, results, cols, True)
    assert notas["GERAL"]["medias_da_rede"]["taxa_geral"] == float(
        __import__("app.utils.decimal_helpers", fromlist=["round_to_two_decimals"]).round_to_two_decimals(mg)
    )
    assert profs["GERAL"]["medias_da_rede"]["taxa_geral"] == float(
        __import__("app.utils.decimal_helpers", fromlist=["round_to_two_decimals"]).round_to_two_decimals(mp)
    )


def test_taxa_geral_municipal_e_media_das_escolas_nao_das_series():
    """§7: taxa_geral = média das escolas; por_serie continua média por coluna."""
    from app.services.consolidated_report_service import ScopeIndex, _build_numeric_matriz

    # Escola A: série 5 (240) e 9 (200) → média escola 220
    # Escola B: só série 5 (260) → média escola 260
    # Média escolas = 240; média colunas (série) = ((240+260)/2 + 200)/2 = 225
    cols = [
        {"serie_id": "5", "serie_nome": "5º Ano"},
        {"serie_id": "9", "serie_nome": "9º Ano"},
    ]
    scope = ScopeIndex(
        series_colunas=cols,
        escolas=[
            {"escola_id": "a", "escola_nome": "A"},
            {"escola_id": "b", "escola_nome": "B"},
        ],
        classes_by_cell={
            ("a", "5"): {"t1"},
            ("a", "9"): {"t2"},
            ("b", "5"): {"t3"},
        },
        class_to_cell={},
        students_by_class={},
    )
    cell_vals = {
        ("a", "5"): 240.0,
        ("a", "9"): 200.0,
        ("b", "5"): 260.0,
    }
    matriz = _build_numeric_matriz(scope, lambda e, s: cell_vals.get((e, s)))
    assert matriz["linhas"][0]["taxa_geral_escola"] == 220.0
    assert matriz["linhas"][1]["taxa_geral_escola"] == 260.0
    assert matriz["medias_da_rede"]["por_serie"] == [250.0, 200.0]
    assert matriz["medias_da_rede"]["taxa_geral"] == 240.0


def test_quem_saiu_entra_na_turma_do_snapshot():
    escopo = {"turma-a", "turma-b"}
    saiu = SimpleNamespace(id="maria", class_id=None)
    assert _turma_para_nota_do_consolidado(saiu, escopo, ["turma-a"]) == "turma-a"


def test_quem_ainda_esta_na_turma_nao_muda_de_lugar():
    escopo = {"turma-a", "turma-b"}
    atual = SimpleNamespace(id="ana", class_id="turma-b")
    assert _turma_para_nota_do_consolidado(atual, escopo, ["turma-a"]) == "turma-b"


def test_snapshot_fora_da_prova_nao_entra():
    escopo = {"turma-a"}
    saiu = SimpleNamespace(id="joao", class_id=None)
    assert _turma_para_nota_do_consolidado(saiu, escopo, ["outra-escola"]) is None
