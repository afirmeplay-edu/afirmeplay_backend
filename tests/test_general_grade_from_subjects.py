"""Regra B: nota geral = calculate_grade(média das proficiências das disciplinas)."""

from types import SimpleNamespace

from app.services.evaluation_calculator import EvaluationCalculator as EC
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.school_equal_weight_means import (
    general_grade_from_subject_proficiencies,
    hierarchical_mean_from_subject_rows,
)


def _nota(results, level, has_matematica=None):
    return general_grade_from_subject_proficiencies(
        results,
        level,
        course_name="Anos Iniciais",
        has_matematica=has_matematica,
    )


def _aluno(student_id, turma, escola="pedro", serie="5ano", subjects=None, proficiency=0.0):
    return SimpleNamespace(
        student_id=student_id,
        proficiency=proficiency,
        school_id_snapshot=escola,
        class_id_snapshot=turma,
        grade_id_snapshot=serie,
        subject_results=subjects or {},
    )


def _disc(name, proficiency):
    return {"subject_name": name, "proficiency": proficiency, "grade": 0.0}


def test_relatorio_geral_usa_calculate_grade_da_media_de_profs():
    from app.utils.school_equal_weight_means import hierarchical_mean_grade_and_proficiency

    alunos = [
        _aluno(
            "a1",
            "B",
            subjects={
                "pt": _disc("Português", 226.88),
                "mat": _disc("Matemática", 270.50),
            },
        )
    ]
    nota, prof = hierarchical_mean_grade_and_proficiency(
        alunos,
        "turma",
        course_name="Anos Iniciais",
        subject_name="GERAL",
        has_matematica=True,
    )
    media = round_to_two_decimals((226.88 + 270.50) / 2)
    assert round(prof, 2) == media
    assert nota == EC.calculate_grade(
        media, "Anos Iniciais", "GERAL", has_matematica=True
    )


def test_portugues_e_matematica_na_turma_b():
    alunos = [
        _aluno(
            "a1",
            "B",
            subjects={
                "pt": _disc("Português", 226.88),
                "mat": _disc("Matemática", 270.50),
            },
            proficiency=(226.88 + 270.50) / 2,
        )
    ]
    nota, _prof = _nota(alunos, "turma", has_matematica=True)
    media = round_to_two_decimals((226.88 + 270.50) / 2)
    assert nota == EC.calculate_grade(
        media, "Anos Iniciais", "GERAL", has_matematica=True
    )
    nota_pt = EC.calculate_grade(226.88, "Anos Iniciais", "Português")
    nota_mat = EC.calculate_grade(270.50, "Anos Iniciais", "Matemática")
    assert nota != round((nota_pt + nota_mat) / 2, 2)


def test_somente_matematica():
    alunos = [_aluno("a1", "B", subjects={"mat": _disc("Matemática", 270.50)})]
    nota, _prof = _nota(alunos, "turma", has_matematica=True)
    assert nota == EC.calculate_grade(270.50, "Anos Iniciais", "GERAL", has_matematica=True)


def test_somente_portugues():
    alunos = [_aluno("a1", "B", subjects={"pt": _disc("Português", 226.88)})]
    nota, _prof = _nota(alunos, "turma", has_matematica=False)
    assert nota == EC.calculate_grade(
        226.88, "Anos Iniciais", "GERAL", has_matematica=False
    )


def test_transferido_nao_vira_turma_inteira_na_disciplina():
    """João saiu da B, mas o snapshot continua B: vale 1 aluno, não 50% da média."""
    rows = [
        {
            "student_id": f"b-{i}",
            "proficiency": 226.88,
            "grade": 6.5,
            "score_percentage": 60,
            "school_id_snapshot": "pedro",
            "class_id_snapshot": "B",
            "grade_id_snapshot": "5ano",
        }
        for i in range(22)
    ]
    rows.append(
        {
            "student_id": "joao",
            "proficiency": 302.3,
            "grade": 9.2,
            "score_percentage": 86,
            "school_id_snapshot": "pedro",
            "class_id_snapshot": "B",
            "grade_id_snapshot": "5ano",
        }
    )
    _nota_v, prof, _pct = hierarchical_mean_from_subject_rows(
        rows,
        "turma",
        course_name="Anos Iniciais",
        subject_name="Português",
    )
    media_alunos = (22 * 226.88 + 302.3) / 23
    assert round(prof, 2) == round(media_alunos, 2)
    assert round(prof, 1) != 262.9
