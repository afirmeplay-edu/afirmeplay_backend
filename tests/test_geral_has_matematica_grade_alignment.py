"""GERAL com Matemática deve usar a mesma escala de nota da disciplina."""

from types import SimpleNamespace

from app.routes.evaluation_results_routes import (
    _has_matematica_para_geral,
    _nome_indica_matematica,
    _test_has_matematica,
)
from app.services.evaluation_calculator import EvaluationCalculator as EC
from app.utils.school_equal_weight_means import hierarchical_mean_grade_and_proficiency


def test_nome_indica_matematica():
    assert _nome_indica_matematica("Matemática") is True
    assert _nome_indica_matematica("matematica") is True
    assert _nome_indica_matematica("Português") is False


def test_test_has_matematica_from_subject_rel():
    test_mat = SimpleNamespace(
        subject_rel=SimpleNamespace(name="Matemática"),
        subjects_info=None,
    )
    test_pt = SimpleNamespace(
        subject_rel=SimpleNamespace(name="Português"),
        subjects_info=None,
    )
    assert _test_has_matematica(test_mat) is True
    assert _test_has_matematica(test_pt) is False


def test_has_matematica_from_grupo_disciplinas():
    scope = {"grupo": {"disciplinas": ["Português", "Matemática"]}}
    assert _has_matematica_para_geral(scope_info=scope) is True
    scope_pt = {"grupo": {"disciplinas": ["Português"]}}
    assert _has_matematica_para_geral(scope_info=scope_pt) is False


def test_calculate_grade_geral_with_matematica_matches_disciplina():
    """Caso real: prof 235.63 → Mat 6.7; GERAL legado dava 6.79."""
    p = 235.63
    nota_mat = EC.calculate_grade(p, "Anos Iniciais", "Matemática")
    nota_geral_legado = EC.calculate_grade(p, "Anos Iniciais", "GERAL")
    nota_geral_fix = EC.calculate_grade(
        p, "Anos Iniciais", "GERAL", has_matematica=True
    )
    assert nota_mat == 6.7
    assert nota_geral_legado == 6.79
    assert nota_geral_fix == nota_mat


def test_hierarchical_geral_math_only_matches_subject_grade():
    results = [
        SimpleNamespace(
            grade=6.7,
            proficiency=235.63,
            school_id_snapshot="s1",
            class_id_snapshot="c1",
            grade_id_snapshot="g1",
        )
    ]
    media_nota_geral, media_prof = hierarchical_mean_grade_and_proficiency(
        results,
        "turma",
        course_name="Anos Iniciais",
        subject_name="GERAL",
        has_matematica=True,
    )
    media_nota_mat, _ = hierarchical_mean_grade_and_proficiency(
        results,
        "turma",
        course_name="Anos Iniciais",
        subject_name="Matemática",
    )
    assert media_prof == 235.63
    assert media_nota_geral == media_nota_mat == 6.7


def test_media_geral_media_das_disciplinas():
    from app.routes.evaluation_results_routes import (
        _aplicar_media_geral_das_disciplinas_grupo,
        _media_geral_from_subject_statistics,
        _media_geral_media_das_disciplinas,
    )

    rows = [
        {"disciplina": "Português", "media_nota": 4.5, "media_proficiencia": 172.75},
        {"disciplina": "Matemática", "media_nota": 6.7, "media_proficiencia": 235.63},
    ]
    nota, prof = _media_geral_media_das_disciplinas(rows)
    assert nota == 5.6
    assert prof == round((172.75 + 235.63) / 2, 2)

    stats = {
        "subjects": {
            "Português": {"average_grade": 4.5, "average_proficiency": 172.75},
            "Matemática": {"average_grade": 6.7, "average_proficiency": 235.63},
        }
    }
    assert _media_geral_from_subject_statistics(stats) == (
        5.6,
        round((172.75 + 235.63) / 2, 2),
    )

    payload = {
        "media_nota_geral": 6.4,
        "media_proficiencia_geral": 226.0,
        "por_disciplina": rows,
    }
    _aplicar_media_geral_das_disciplinas_grupo(payload, {"grupo": {"agrupado": True}})
    assert payload["media_nota_geral"] == 5.6
    assert payload["media_proficiencia_geral"] == round((172.75 + 235.63) / 2, 2)
