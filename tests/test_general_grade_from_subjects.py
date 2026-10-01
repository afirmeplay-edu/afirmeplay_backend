"""Nota geral = média das notas das disciplinas, cada uma na própria faixa."""

from types import SimpleNamespace

from app.services.evaluation_calculator import EvaluationCalculator as EC
from app.utils.school_equal_weight_means import (
    general_grade_from_subject_proficiencies,
    hierarchical_mean_from_subject_rows,
)


def _nota(results, level):
    return general_grade_from_subject_proficiencies(
        results, level, course_name="Anos Iniciais"
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


def test_relatorio_geral_com_disciplinas_nao_usa_formula_de_matematica():
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
    nota, _prof = hierarchical_mean_grade_and_proficiency(
        alunos,
        "turma",
        course_name="Anos Iniciais",
        subject_name="GERAL",
        has_matematica=True,
    )
    assert nota == 7.25


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
    nota, _prof = _nota(alunos, "turma")
    nota_pt = EC.calculate_grade(226.88, "Anos Iniciais", "Português")
    nota_mat = EC.calculate_grade(270.50, "Anos Iniciais", "Matemática")
    assert nota_pt == 6.47
    assert nota_mat == 8.03
    assert nota == round((nota_pt + nota_mat) / 2, 2)
    assert nota == 7.25
    nota_errada = EC.calculate_grade(
        (226.88 + 270.50) / 2, "Anos Iniciais", "GERAL", has_matematica=True
    )
    assert nota != nota_errada


def test_tres_disciplinas_ciencias_usa_outras():
    alunos = [
        _aluno(
            "a1",
            "B",
            subjects={
                "pt": _disc("Português", 200.0),
                "mat": _disc("Matemática", 200.0),
                "cie": _disc("Ciências", 200.0),
            },
        )
    ]
    nota, _prof = _nota(alunos, "turma")
    esperada = (
        EC.calculate_grade(200.0, "Anos Iniciais", "Português")
        + EC.calculate_grade(200.0, "Anos Iniciais", "Matemática")
        + EC.calculate_grade(200.0, "Anos Iniciais", "Ciências")
    ) / 3
    assert EC.calculate_grade(200.0, "Anos Iniciais", "Ciências") == EC.calculate_grade(
        200.0, "Anos Iniciais", "Português"
    )
    assert nota == round(esperada, 2)
    assert nota != EC.calculate_grade(200.0, "Anos Iniciais", "GERAL", has_matematica=True)


def test_portugues_e_ciencias_nao_usam_matematica():
    alunos = [
        _aluno(
            "a1",
            "B",
            subjects={
                "pt": _disc("Português", 210.0),
                "cie": _disc("Ciências", 230.0),
            },
        )
    ]
    nota, _prof = _nota(alunos, "turma")
    esperada = (
        EC.calculate_grade(210.0, "Anos Iniciais", "Português")
        + EC.calculate_grade(230.0, "Anos Iniciais", "Ciências")
    ) / 2
    assert nota == round(esperada, 2)
    assert nota != EC.calculate_grade(220.0, "Anos Iniciais", "Matemática")


def test_ciencias_e_ingles_dividem_por_dois():
    alunos = [
        _aluno(
            "a1",
            "B",
            subjects={
                "cie": _disc("Ciências", 180.0),
                "ing": _disc("Inglês", 220.0),
            },
        )
    ]
    nota, _prof = _nota(alunos, "turma")
    esperada = (
        EC.calculate_grade(180.0, "Anos Iniciais", "Ciências")
        + EC.calculate_grade(220.0, "Anos Iniciais", "Inglês")
    ) / 2
    assert nota == round(esperada, 2)


def test_somente_matematica():
    alunos = [_aluno("a1", "B", subjects={"mat": _disc("Matemática", 270.50)})]
    nota, _prof = _nota(alunos, "turma")
    assert nota == EC.calculate_grade(270.50, "Anos Iniciais", "Matemática")


def test_somente_portugues():
    alunos = [_aluno("a1", "B", subjects={"pt": _disc("Português", 226.88)})]
    nota, _prof = _nota(alunos, "turma")
    assert nota == EC.calculate_grade(226.88, "Anos Iniciais", "Português")


def _turma(nome, pt, mat, quantidade):
    return [
        _aluno(
            f"{nome}-{i}",
            nome,
            subjects={"pt": _disc("Português", pt), "mat": _disc("Matemática", mat)},
        )
        for i in range(quantidade)
    ]


def test_pedro_ribeiro_turmas_e_escola():
    alunos = (
        _turma("A", 241.53, 305.27, 22)
        + _turma("B", 226.88, 270.50, 23)
        + _turma("C", 205.30, 233.77, 21)
    )
    nota_a, _ = _nota([a for a in alunos if a.class_id_snapshot == "A"], "turma")
    nota_b, _ = _nota([a for a in alunos if a.class_id_snapshot == "B"], "turma")
    nota_c, _ = _nota([a for a in alunos if a.class_id_snapshot == "C"], "serie")
    nota_escola, _ = _nota(alunos, "escola")
    assert nota_a == 8.18
    assert nota_b == 7.25
    assert nota_c == 6.15
    assert nota_escola == 7.20


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
    _nota, prof, _pct = hierarchical_mean_from_subject_rows(
        rows,
        "turma",
        course_name="Anos Iniciais",
        subject_name="Português",
    )
    media_alunos = (22 * 226.88 + 302.3) / 23
    assert round(prof, 2) == round(media_alunos, 2)
    assert round(prof, 1) != 262.9
