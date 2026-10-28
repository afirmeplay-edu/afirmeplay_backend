# -*- coding: utf-8 -*-
"""Divisão equilibrada dos blocos na importação do cartão-resposta."""
from app.answer_sheet_import.services.answer_sheet_import_service import _build_blocks

PT = {"id": "pt", "name": "Português"}
MAT = {"id": "mat", "name": "Matemática"}
CIE = {"id": "cie", "name": "Ciências"}
HIS = {"id": "his", "name": "História"}
GEO = {"id": "geo", "name": "Geografia"}


def _rows(*spans):
    rows = []
    question = 1
    for subject, count in spans:
        for _ in range(count):
            rows.append({"subject": subject, "question": question})
            question += 1
    return rows


def _counts(blocks):
    return [block["questions_count"] for block in blocks]


def test_26_vira_13_e_13():
    blocks, errors, warnings = _build_blocks(_rows((PT, 26)))
    assert errors == []
    assert _counts(blocks) == [13, 13]
    assert blocks[0]["start_question"] == 1 and blocks[0]["end_question"] == 13
    assert blocks[1]["start_question"] == 14 and blocks[1]["end_question"] == 26
    assert blocks[0]["subject_id"] == blocks[1]["subject_id"] == "pt"
    assert blocks[0]["subject_name"] == blocks[1]["subject_name"] == "Português"
    assert warnings == ["Português dividido em 2 blocos (Q1–13 e Q14–26)."]


def test_22_permanece_um_bloco():
    blocks, errors, warnings = _build_blocks(_rows((PT, 22)))
    assert errors == []
    assert warnings == []
    assert _counts(blocks) == [22]
    assert blocks[0]["end_question"] == 22


def test_44_vira_22_e_22():
    blocks, errors, warnings = _build_blocks(_rows((PT, 44)))
    assert errors == []
    assert _counts(blocks) == [22, 22]
    assert warnings == ["Português dividido em 2 blocos (Q1–22 e Q23–44)."]


def test_23_vira_12_e_11():
    blocks, errors, warnings = _build_blocks(_rows((PT, 23)))
    assert errors == []
    assert _counts(blocks) == [12, 11]
    assert (blocks[0]["start_question"], blocks[0]["end_question"]) == (1, 12)
    assert (blocks[1]["start_question"], blocks[1]["end_question"]) == (13, 23)
    assert warnings == ["Português dividido em 2 blocos (Q1–12 e Q13–23)."]


def test_26_e_26_viram_quatro_blocos_de_13():
    blocks, errors, warnings = _build_blocks(_rows((PT, 26), (MAT, 26)))
    assert errors == []
    assert _counts(blocks) == [13, 13, 13, 13]
    assert [block["subject_name"] for block in blocks] == ["Português", "Português", "Matemática", "Matemática"]
    assert [(block["start_question"], block["end_question"]) for block in blocks] == [
        (1, 13), (14, 26), (27, 39), (40, 52),
    ]
    assert warnings == [
        "Português dividido em 2 blocos (Q1–13 e Q14–26).",
        "Matemática dividido em 2 blocos (Q27–39 e Q40–52).",
    ]


def test_total_acima_de_88_gera_erro():
    blocks, errors, warnings = _build_blocks(_rows((PT, 89)))
    assert warnings == []
    assert len(blocks) == 5
    assert errors and "88" in errors[0]
    assert "Não cabe neste cartão" in errors[0]


def test_mais_de_4_blocos_gera_erro():
    blocks, errors, warnings = _build_blocks(_rows((PT, 10), (MAT, 10), (CIE, 10), (HIS, 10), (GEO, 10)))
    assert warnings == []
    assert len(blocks) == 5
    assert len(errors) == 1
    assert "seriam 5 blocos" in errors[0]
    assert "máximo é 4" in errors[0]


def test_disciplina_fora_de_ordem_gera_erro_e_nao_divide():
    blocks, errors, warnings = _build_blocks(_rows((PT, 5), (MAT, 5), (PT, 5)))
    assert warnings == []
    assert _counts(blocks) == [5, 5, 5]
    assert len(errors) == 1
    assert "em sequência" in errors[0]
    assert "Português" in errors[0]
