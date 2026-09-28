# -*- coding: utf-8 -*-
"""Detecção de Educação Especial sem banco: o resultado de hoje permanece."""
from types import SimpleNamespace

from app.services.cartao_resposta.course_name_resolver import (
    infer_course_name_from_grade,
    looks_like_grade_label,
)
from app.services.consolidated_report_service import (
    _course_name_for_serie,
    _series_identity_for_class,
    _series_sort_key,
)
from app.services.evaluation_calculator import CourseLevel, EvaluationCalculator
from app.services.special_education import (
    ADAP_EDUCATION_STAGE_ID,
    grade_label_is_exact_adap,
    is_special_education,
    serie_course_is_special_education,
    special_education_label_from_course_text,
    status_from_grade_and_subturma,
    support_level_from_exact_grade_name,
)


def test_stage_id_and_exact_names():
    assert ADAP_EDUCATION_STAGE_ID == "247c4af5-2688-41b0-95fa-443f503a9d87"
    assert support_level_from_exact_grade_name("Suporte 1") == 1
    assert support_level_from_exact_grade_name("ADAP 3") == 3
    assert support_level_from_exact_grade_name("Suporte 1 9º Ano") is None
    assert grade_label_is_exact_adap("ADAP 2") is True
    assert grade_label_is_exact_adap("Suporte 2") is False


def test_curso_do_ano_no_nome_nao_muda():
    assert infer_course_name_from_grade("Suporte 1 9º Ano") == "Anos Finais"
    assert infer_course_name_from_grade("5º Ano") == "Anos Iniciais"
    assert infer_course_name_from_grade("Educação Especial") == "Educação Especial"
    assert infer_course_name_from_grade("ADAP 1") == "Educação Especial"
    assert _course_name_for_serie("Suporte 1 9º Ano") == "Anos Finais"
    assert looks_like_grade_label("9º Ano") is True
    assert looks_like_grade_label("1º AVALIA MUNICIPAL") is False
    assert looks_like_grade_label("Suporte 1") is False
    assert looks_like_grade_label("ADAP 1") is True


def test_calculadora_mantem_educacao_especial_e_anos():
    assert (
        EvaluationCalculator._determine_course_level("Educação Especial")
        == CourseLevel.EDUCACAO_ESPECIAL
    )
    assert (
        EvaluationCalculator._determine_course_level("Anos Iniciais")
        == CourseLevel.ANOS_INICIAIS
    )
    assert (
        EvaluationCalculator._determine_course_level("Anos Finais")
        == CourseLevel.ANOS_FINAIS
    )
    assert (
        EvaluationCalculator._determine_course_level("Suporte 1 9º Ano")
        == CourseLevel.ANOS_INICIAIS
    )


def test_consolidado_separa_ano_sem_renomear_suporte():
    grade = SimpleNamespace(id="gid", name="Suporte 1")
    turma = SimpleNamespace(grade=grade, name="Suporte 1 - 1º ANO")
    assert _series_identity_for_class(turma) == ("gid::1", "Suporte 1 1º Ano")
    assert _series_sort_key("Suporte 1 1º Ano")[0:3] == (0, 1, 1)
    assert _series_sort_key("5º Ano")[0] == 1


def test_ranking_categoria_atual():
    assert serie_course_is_special_education("Suporte 2", "") is True
    assert serie_course_is_special_education("5º Ano", "Anos Iniciais") is False
    assert serie_course_is_special_education("5º Ano", "Educação Especial") is True
    assert serie_course_is_special_education("ADAP 1", "Anos Finais") is True


def test_rotulo_da_analise_ia():
    assert special_education_label_from_course_text("suporte 2") == (
        "Educação Especial (Suporte 2)"
    )
    assert special_education_label_from_course_text("aee") == "Educação Especial"
    assert special_education_label_from_course_text("educacao especial") == (
        "Educação Especial"
    )
    assert special_education_label_from_course_text("adap 1") == (
        "Educação Especial (ADAP 1)"
    )


def test_aluno_sem_subturma_usa_a_serie_atual():
    suporte = SimpleNamespace(
        id="a1",
        class_id="turma-1",
        grade_id="g1",
        subturma_id=None,
        grade=SimpleNamespace(
            name="Suporte 2",
            education_stage_id=ADAP_EDUCATION_STAGE_ID,
        ),
        class_=None,
    )
    regular = SimpleNamespace(
        id="a2",
        class_id="turma-2",
        grade_id="g2",
        subturma_id=None,
        grade=SimpleNamespace(name="5º Ano", education_stage_id="outra-etapa"),
        class_=None,
    )
    assert bool(is_special_education(suporte)) is True
    assert is_special_education(suporte).level == 2
    assert is_special_education(suporte).source == "serie"
    assert bool(is_special_education(regular)) is False

    sub = SimpleNamespace(class_id="turma-regular", support_level=1)
    com_sub = status_from_grade_and_subturma(
        student_class_id="turma-regular",
        grade=SimpleNamespace(name="5º Ano", education_stage_id="outra-etapa"),
        subturma=sub,
    )
    assert com_sub.is_special is True
    assert com_sub.level == 1
    assert com_sub.source == "subturma"

    outra_turma = status_from_grade_and_subturma(
        student_class_id="turma-regular",
        grade=SimpleNamespace(name="5º Ano", education_stage_id="outra-etapa"),
        subturma=SimpleNamespace(class_id="outra", support_level=3),
    )
    assert outra_turma.is_special is False
