# -*- coding: utf-8 -*-
"""Testes do resolver de série e payload multi-série do gabarito."""

from app.answer_sheets.services.cartao_resposta.course_name_resolver import (
    infer_course_name_from_grade,
    looks_like_grade_label,
    resolve_grade_name_for_proficiency,
)
from app.answer_sheets.services.cartao_resposta.gabarito_grades import (
    normalize_grades_list,
    pick_grade_for_scope,
)


def test_infer_not_confused_by_preta_in_title():
    # Título com município CHÃ PRETA não deve virar Educação Infantil
    assert infer_course_name_from_grade("9º ANO - 2º AVALIA CHÃ PRETA") == "Anos Finais"
    assert infer_course_name_from_grade("5º ANO - 2º AVALIA CHÃ PRETA") == "Anos Iniciais"
    assert infer_course_name_from_grade("9º Ano") == "Anos Finais"
    assert infer_course_name_from_grade("pré-escola") == "Educação Infantil"
    assert infer_course_name_from_grade("Educação Infantil") == "Educação Infantil"


def test_resolve_never_uses_title():
    class Gab:
        id = "g1"
        grade_name = ""
        grade_id = None
        grades = None
        title = "9º ANO - 2º AVALIA CHÃ PRETA"

    assert resolve_grade_name_for_proficiency(gabarito_obj=Gab()) == ""


def test_resolve_uses_student_series():
    class Grade:
        name = "9º Ano"

    class ClassObj:
        grade = Grade()
        grade_id = "gid-9"

    class Student:
        class_ = ClassObj()

    class Gab:
        id = "g1"
        grade_name = ""
        grade_id = None
        grades = [{"id": "a", "name": "5º Ano"}, {"id": "b", "name": "9º Ano"}]
        title = "QUALQUER TITULO COM PRETA"

    assert resolve_grade_name_for_proficiency(gabarito_obj=Gab(), student=Student()) == "9º Ano"


def test_resolve_single_grade_from_grades_json():
    class Gab:
        id = "g1"
        grade_name = ""
        grade_id = None
        grades = [{"id": "uuid-9", "name": "9º Ano"}]
        title = "Nao usar"

    assert resolve_grade_name_for_proficiency(gabarito_obj=Gab()) == "9º Ano"


def test_normalize_and_pick_grade():
    grades = normalize_grades_list(
        [{"id": "1", "name": "5º Ano"}, {"id": "2", "name": "8º Ano"}],
        resolve_names=False,
    )
    assert len(grades) == 2

    class Gab:
        grades = grades
        grade_id = None
        grade_name = None

    assert pick_grade_for_scope(Gab(), serie_id="2")["name"] == "8º Ano"
    assert pick_grade_for_scope(Gab(), serie_id=None) is None  # multi sem filtro
    Gab.grades = [grades[0]]
    assert pick_grade_for_scope(Gab(), serie_id=None)["id"] == "1"


def test_looks_like_grade_label():
    assert looks_like_grade_label("9º Ano") is True
    assert looks_like_grade_label("1º AVALIA MUNICIPAL") is False
