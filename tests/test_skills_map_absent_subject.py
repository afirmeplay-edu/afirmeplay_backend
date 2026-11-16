# -*- coding: utf-8 -*-
"""skills_map: disciplina ausente nao entra no denominador daquela disciplina."""

from types import SimpleNamespace

from app.services.skills_map_service import _answer_sheet_subject_absent_for_student
from app.services.cartao_resposta.proficiency_by_subject import make_absent_subject_entry


PORT_ID = "subj-port"
MAT_ID = "subj-mat"
PORT_Q = list(range(1, 21))
MAT_Q = list(range(21, 41))


def test_subject_absent_via_pbs_flag():
    r = SimpleNamespace(
        proficiency_by_subject={
            PORT_ID: make_absent_subject_entry("Português", 20),
            MAT_ID: {
                "subject_name": "Matemática",
                "absent": False,
                "grade": 7.0,
                "proficiency": 240.0,
                "classification": "Adequado",
            },
        },
        detected_answers={i: None for i in PORT_Q} | {i: "A" for i in MAT_Q},
    )
    assert _answer_sheet_subject_absent_for_student(r, PORT_ID, PORT_Q) is True
    assert _answer_sheet_subject_absent_for_student(r, MAT_ID, MAT_Q) is False


def test_subject_absent_via_blank_block_legacy():
    """Cartao antigo: PBS ainda com 0, mas bloco 100% em branco."""
    r = SimpleNamespace(
        proficiency_by_subject={
            PORT_ID: {
                "subject_name": "Português",
                "grade": 0.0,
                "proficiency": 0.0,
                "classification": "Abaixo do Básico",
            },
            MAT_ID: {
                "subject_name": "Matemática",
                "grade": 7.0,
                "proficiency": 240.0,
                "classification": "Adequado",
            },
        },
        detected_answers={i: None for i in PORT_Q} | {i: "A" for i in MAT_Q},
    )
    assert _answer_sheet_subject_absent_for_student(r, PORT_ID, PORT_Q) is True
    assert _answer_sheet_subject_absent_for_student(r, MAT_ID, MAT_Q) is False


def test_real_zero_not_absent():
    """Marcou tudo errado (nota 0) nao e ausente."""
    r = SimpleNamespace(
        proficiency_by_subject={
            PORT_ID: {
                "subject_name": "Português",
                "absent": False,
                "grade": 0.0,
                "proficiency": 0.0,
                "classification": "Abaixo do Básico",
            },
        },
        detected_answers={i: "B" for i in PORT_Q},
    )
    assert _answer_sheet_subject_absent_for_student(r, PORT_ID, PORT_Q) is False


def test_denominator_logic_exclude_absent_student():
    """Simula a regra do mapa: ausente sai do denominador; acertos absolutos iguais."""
    students = [
        SimpleNamespace(id="a", absent_pt=True, answers={}),
        SimpleNamespace(id="b", absent_pt=False, answers={1: "A"}),
        SimpleNamespace(id="c", absent_pt=False, answers={1: "B"}),
    ]
    gab = {1: "A"}
    correct = 0
    total = 0
    for st in students:
        if st.absent_pt:
            continue
        total += 1
        if st.answers.get(1) == gab[1]:
            correct += 1
    assert total == 2
    assert correct == 1
    assert round(100.0 * correct / total, 2) == 50.0
