# -*- coding: utf-8 -*-
"""Contrato oficial: Regra B (nota = calculate_grade(média de proficiências))."""

from types import SimpleNamespace

from app.services.evaluation_calculator import EvaluationCalculator as EC
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.school_equal_weight_means import (
    general_grade_from_subject_proficiencies,
    hierarchical_mean_grade_and_proficiency,
)


def _disc(name, proficiency):
    return {"subject_name": name, "proficiency": proficiency, "grade": 0.0}


def _aluno(student_id, turma, subjects, escola="pedro", serie="5ano"):
    profs = [float(v["proficiency"]) for v in subjects.values()]
    return SimpleNamespace(
        student_id=student_id,
        proficiency=sum(profs) / len(profs) if profs else 0.0,
        grade=0.0,
        school_id_snapshot=escola,
        class_id_snapshot=turma,
        grade_id_snapshot=serie,
        subject_results=subjects,
    )


def test_geral_individual_e_calculate_grade_da_media_de_profs():
    """Português 226.88 + Matemática 270.50 → média 248.69 → calculate_grade(GERAL)."""
    alunos = [
        _aluno(
            "a1",
            "B",
            {
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
    media_prof = round_to_two_decimals((226.88 + 270.50) / 2)
    assert round(prof, 2) == media_prof
    assert nota == EC.calculate_grade(
        media_prof, "Anos Iniciais", "GERAL", has_matematica=True
    )
    # Não é a média das notas disciplinares (regra antiga / regra A).
    nota_pt = EC.calculate_grade(226.88, "Anos Iniciais", "Português")
    nota_mat = EC.calculate_grade(270.50, "Anos Iniciais", "Matemática")
    assert nota != round((nota_pt + nota_mat) / 2, 2)


def test_general_grade_from_subject_proficiencies_segue_regra_b():
    alunos = [
        _aluno(
            "a1",
            "B",
            {
                "pt": _disc("Português", 226.88),
                "mat": _disc("Matemática", 270.50),
            },
        )
    ]
    nota, prof = general_grade_from_subject_proficiencies(
        alunos,
        "turma",
        course_name="Anos Iniciais",
        has_matematica=True,
    )
    media = round_to_two_decimals((226.88 + 270.50) / 2)
    assert round(prof, 2) == media
    assert nota == EC.calculate_grade(
        media, "Anos Iniciais", "GERAL", has_matematica=True
    )


def test_hierarquia_turma_serie_escola_sem_ponderacao():
    """Turmas com tamanhos diferentes: peso igual por turma."""
    t1 = [
        SimpleNamespace(
            student_id=f"t1-{i}",
            proficiency=200.0,
            grade=5.0,
            school_id_snapshot="e1",
            class_id_snapshot="A",
            grade_id_snapshot="5",
        )
        for i in range(3)
    ]
    t2 = [
        SimpleNamespace(
            student_id="t2-0",
            proficiency=300.0,
            grade=8.0,
            school_id_snapshot="e1",
            class_id_snapshot="B",
            grade_id_snapshot="5",
        )
    ]
    nota, prof = hierarchical_mean_grade_and_proficiency(
        t1 + t2,
        "serie",
        course_name="Anos Iniciais",
        subject_name="GERAL",
        has_matematica=False,
    )
    assert round(prof, 2) == 250.0
    assert nota == EC.calculate_grade(
        250.0, "Anos Iniciais", "GERAL", has_matematica=False
    )


def test_course_level_fundamental_ii_e_anos_finais():
    from app.services.evaluation_calculator import CourseLevel

    assert EC._determine_course_level("Ensino Fundamental II") == CourseLevel.ANOS_FINAIS
    assert EC._determine_course_level("Ensino Fundamental - Anos Finais") == CourseLevel.ANOS_FINAIS
    assert EC._determine_course_level("Anos Iniciais") == CourseLevel.ANOS_INICIAIS
    assert EC._determine_course_level("Ensino Médio") == CourseLevel.ENSINO_MEDIO


def test_classificacao_arredonda_antes_de_classificar():
    """Média crua 199.995 deve classificar como Básico após arredondar para 200.00."""
    media = (199.99 + 200.00) / 2
    assert media == 199.995
    arred = round_to_two_decimals(media)
    assert arred == 200.0
    label = EC.determine_classification(
        arred, "Anos Iniciais", "GERAL", has_matematica=False
    )
    assert label == "Adequado"
