# -*- coding: utf-8 -*-
"""Testes do resolver de série e payload multi-série do gabarito."""

from app.services.cartao_resposta.course_name_resolver import (
    infer_course_name_from_grade,
    looks_like_grade_label,
    resolve_grade_name_for_proficiency,
)
from app.services.cartao_resposta.gabarito_grades import (
    course_meta_for_gabarito_serie,
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
    normalized = normalize_grades_list(
        [{"id": "1", "name": "5º Ano"}, {"id": "2", "name": "8º Ano"}],
        resolve_names=False,
    )
    assert len(normalized) == 2

    class Gab:
        grades = normalized
        grade_id = None
        grade_name = None

    assert pick_grade_for_scope(Gab(), serie_id="2")["name"] == "8º Ano"
    assert pick_grade_for_scope(Gab(), serie_id=None) is None  # multi sem filtro
    Gab.grades = [normalized[0]]
    assert pick_grade_for_scope(Gab(), serie_id=None)["id"] == "1"


def test_looks_like_grade_label():
    assert looks_like_grade_label("9º Ano") is True
    assert looks_like_grade_label("1º AVALIA MUNICIPAL") is False
    assert looks_like_grade_label("Suporte 1") is True
    assert looks_like_grade_label("ADAP 3") is True


def test_suporte_n_no_cartao_e_educacao_especial():
    assert infer_course_name_from_grade("Suporte 1") == "Educação Especial"
    assert infer_course_name_from_grade("ADAP 2") == "Educação Especial"
    assert infer_course_name_from_grade("Suporte 1", suporte_como_especial=False) == "Anos Iniciais"


def test_resolve_adap_usa_serie_do_gabarito_e_nao_da_turma_mae():
    class Grade:
        name = "5º Ano"

    class ClassObj:
        grade = Grade()
        grade_id = "gid-5"

    class Student:
        class_ = ClassObj()

    class Gab:
        id = "g-adap"
        grade_name = "Suporte 1"
        grade_id = "suporte-1"
        grades = [{"id": "suporte-1", "name": "Suporte 1"}]
        title = "Cartão ADAP 1"

    assert resolve_grade_name_for_proficiency(gabarito_obj=Gab(), student=Student()) == "Suporte 1"
    course, gname, gid = course_meta_for_gabarito_serie(Gab(), serie_id="gid-5")
    assert course == "Educação Especial"
    assert gname == "Suporte 1"
    assert gid == "suporte-1"
